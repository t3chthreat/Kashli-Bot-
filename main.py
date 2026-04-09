import logging
import sys
import time

import click
from apscheduler.schedulers.background import BackgroundScheduler

from kalshi_bot.config import Config
from kalshi_bot.client import KalshiClient
from kalshi_bot.price_feed import PriceFeed
from kalshi_bot.scanner import scan_crypto_markets, scan_macro_markets, rank_by_volume
from kalshi_bot.risk import RiskManager
from kalshi_bot.strategy import KalshiVolatilityStrategy
from kalshi_bot.executor import Executor
from kalshi_bot.display import Display
from kalshi_bot.db import init_db
from kalshi_bot.backup import restore_from_s3, upload_to_s3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@click.command()
@click.option("--scan", "mode", flag_value="scan", help="Scan and display opportunities, no trading")
@click.option("--dry-run", "mode", flag_value="dry_run", default=True, help="Full cycle, no orders (default)")
@click.option("--paper", "mode", flag_value="paper", help="Simulated fills at live prices")
@click.option("--live", "mode", flag_value="live", help="Real orders — real money")
def cli(mode: str):
    config = Config()
    try:
        Config.validate_required()
    except EnvironmentError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Restore DB from S3 on startup if backup bucket configured
    if config.s3_backup_bucket:
        restore_from_s3(config.s3_backup_bucket)

    client = KalshiClient.from_env()
    db_session = init_db()
    display = Display()

    if mode == "scan":
        _do_scan(client, display)
        return

    _run_bot(mode=mode, config=config, client=client, db_session=db_session, display=display)


def _do_scan(client, display):
    opps = rank_by_volume(scan_crypto_markets(client) + scan_macro_markets(client))
    display.render_opportunities(opps)


def _run_bot(mode: str, config=None, client=None, db_session=None, display=None):
    config = config or Config()
    client = client or KalshiClient.from_env()
    db_session = db_session or init_db()
    display = display or Display()

    feed = PriceFeed()
    risk = RiskManager(config)
    strategy = KalshiVolatilityStrategy(client=client, feed=feed, risk=risk)
    executor = Executor(client=client, risk=risk, db_session=db_session)

    scheduler = BackgroundScheduler()
    scheduler.add_job(risk.reset_daily, "cron", hour=0, minute=0, timezone="UTC")
    if config.s3_backup_bucket:
        scheduler.add_job(
            upload_to_s3, "interval", hours=6,
            args=[config.s3_backup_bucket],
            id="s3_backup",
        )
    scheduler.start()

    logger.info("Kalshi Bot starting in %s mode", mode.upper())
    try:
        while True:
            opps = rank_by_volume(scan_crypto_markets(client) + scan_macro_markets(client))
            signals = strategy.run_cycle(opps)
            for signal in signals:
                executor.execute_trade(signal, mode=mode)
            executor.track_open_orders()
            display.render_status(opps, signals, risk)
            time.sleep(config.scan_interval_secs)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    cli()
