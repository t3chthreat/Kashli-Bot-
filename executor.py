# kalshi_bot/executor.py
import logging
from dataclasses import dataclass
from typing import Optional

from kalshi_bot.client import KalshiClient
from kalshi_bot.risk import RiskManager, Position
from kalshi_bot.strategy import TradeSignal
from kalshi_bot.db import Trade

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    order_id: Optional[str]
    mode: str
    status: str
    simulated: bool = False


class Executor:
    def __init__(self, client: KalshiClient, risk: RiskManager, db_session):
        self.client = client
        self.risk = risk
        self.db = db_session
        self._open_positions: dict[str, Position] = {}

    def execute_trade(self, signal: TradeSignal, mode: str) -> OrderResult:
        if mode == "dry_run":
            self._log_signal(signal, mode)
            return OrderResult(order_id=None, mode=mode, status="logged", simulated=True)

        if mode == "paper":
            pos = Position(
                ticker=signal.ticker,
                contracts=signal.contracts,
                side=signal.side,
                entry_price=signal.price,
                order_id=f"paper-{signal.ticker}",
            )
            self._open_positions[signal.ticker] = pos
            self.risk.record_fill(signal.ticker, signal.side, signal.price, signal.contracts)
            self._write_trade(signal, order_id=pos.order_id, mode=mode)
            return OrderResult(order_id=pos.order_id, mode=mode, status="filled", simulated=True)

        # live
        price_cents = int(signal.price * 100)
        result = self.client.place_order(signal.ticker, signal.side, price_cents, signal.contracts)
        order_id = result.get("order_id", "")
        pos = Position(
            ticker=signal.ticker,
            contracts=signal.contracts,
            side=signal.side,
            entry_price=signal.price,
            order_id=order_id,
        )
        self._open_positions[signal.ticker] = pos
        self.risk.record_fill(signal.ticker, signal.side, signal.price, signal.contracts)
        self._write_trade(signal, order_id=order_id, mode=mode)
        return OrderResult(order_id=order_id, mode=mode, status=result.get("status", "resting"))

    def handle_settlement(self, ticker: str, resolved_yes: bool) -> None:
        pos = self._open_positions.pop(ticker, None)
        if not pos:
            return
        win = (pos.side == "yes" and resolved_yes) or (pos.side == "no" and not resolved_yes)
        pnl = (1.0 - pos.entry_price) * pos.contracts if win else -pos.entry_price * pos.contracts
        self.risk.record_fill(
            ticker,
            side="settlement",
            price=1.0 if resolved_yes else 0.0,
            contracts=pos.contracts,
        )
        trade = self.db.query(Trade).filter_by(order_id=pos.order_id).first()
        if trade:
            trade.status = "closed"
            trade.pnl_usd = pnl
            self.db.commit()
        logger.info("Settlement %s resolved_yes=%s pnl=%.2f", ticker, resolved_yes, pnl)

    def track_open_orders(self) -> None:
        fills = self.client.get_fills()
        for fill in fills:
            if fill.ticker and fill.ticker not in self._open_positions:
                logger.debug("Untracked fill: %s", fill)

    def close_position(self, position: Position) -> None:
        self.client.cancel_order(position.order_id)
        self._open_positions.pop(position.ticker, None)

    def _log_signal(self, signal: TradeSignal, mode: str) -> None:
        logger.info(
            "[%s] %s %s @ %.2f edge=%.1f%%",
            mode.upper(), signal.ticker, signal.side, signal.price, signal.edge_pct * 100,
        )

    def _write_trade(self, signal: TradeSignal, order_id: str, mode: str) -> None:
        trade = Trade(
            ticker=signal.ticker,
            category="crypto" if signal.signal_type != "macro" else "macro",
            side=signal.side,
            price=signal.price,
            contracts=signal.contracts,
            cost_usd=signal.price * signal.contracts,
            edge_at_entry=signal.edge_pct,
            signal_type=signal.signal_type,
            order_id=order_id,
            status="open",
            mode=mode,
        )
        self.db.add(trade)
        self.db.commit()
