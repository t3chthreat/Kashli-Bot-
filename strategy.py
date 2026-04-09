# kalshi_bot/strategy.py
"""
kalshi_bot/strategy.py — Kalshi Volatility Position Strategy

Takes directional positions on BTC/ETH/SOL Kalshi markets based on
momentum signals vs. current market pricing.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from kalshi_bot.analytics import EnsembleSignalGate
from kalshi_bot.scanner import Opportunity

logger = logging.getLogger(__name__)

MIN_EDGE = 0.05   # 5% minimum edge to enter
KELLY_FRACTION = 0.25   # fractional Kelly (25%)
MAX_CONTRACTS_PER_SIGNAL = 20


@dataclass
class TradeSignal:
    ticker: str
    side: str            # 'yes' | 'no'
    price: float         # limit price (0.0–1.0)
    contracts: int
    edge_pct: float
    confidence: str      # 'HIGH' | 'MEDIUM'
    signal_type: str     # 'momentum' | 'mean_reversion' | 'macro'


@dataclass
class EdgeResult:
    ticker: str
    edge_pct: float
    confidence: str      # 'HIGH' | 'MEDIUM' | 'LOW'
    signal_type: str


class KalshiVolatilityStrategy:
    """
    Takes directional positions on Kalshi crypto/macro markets based on
    momentum signals vs. current market pricing.

    Key design: scanner runs externally in main.py; opportunities are passed
    into run_cycle() rather than fetched internally.
    """

    def __init__(self, client, feed, risk):
        self.client = client
        self.feed = feed
        self.risk = risk
        self._gate = EnsembleSignalGate(
            max_vpin=0.58,
            min_volume_24h=1000,
            required_signals=3,
        )
        self._cycle = 0

    def run_cycle(self, opportunities: list[Opportunity]) -> list[TradeSignal]:
        self._cycle += 1
        signals: list[TradeSignal] = []

        halted, reason = self.risk.is_halted()
        if halted:
            logger.warning("Bot halted: %s — skipping cycle", reason)
            return signals

        for opp in opportunities:
            can, reason_str = self.risk.can_open_market(opp.ticker)
            if not can:
                logger.debug("Risk blocked %s: %s", opp.ticker, reason_str)
                continue

            edge = self._compute_edge(opp)
            if edge.edge_pct < MIN_EDGE or edge.confidence == "LOW":
                continue

            contracts = self._size_position(edge)
            if contracts <= 0:
                continue

            # Determine side: if our estimate > market price, buy YES; else buy NO
            our_prob = self.feed.estimate_up_probability(
                _ticker_to_symbol(opp.ticker), timeframe="15min"
            ) if opp.category == "crypto" else 0.5
            side = "yes" if our_prob >= opp.yes_price else "no"
            price = opp.yes_price if side == "yes" else opp.no_price

            signal = TradeSignal(
                ticker=opp.ticker,
                side=side,
                price=price,
                contracts=contracts,
                edge_pct=edge.edge_pct,
                confidence=edge.confidence,
                signal_type=edge.signal_type,
            )
            signals.append(signal)
            logger.info("Signal: %s %s @ %.2f edge=%.1f%%", opp.ticker, side, price, edge.edge_pct * 100)

        return signals

    def _compute_edge(self, opp: Opportunity) -> EdgeResult:
        """Compute edge for a given opportunity using price feed."""
        symbol = _ticker_to_symbol(opp.ticker)
        edge_pct = self.feed.edge_vs_market(
            symbol=symbol,
            market_yes_price=opp.yes_price,
            timeframe="15min",
        )

        if edge_pct >= 0.10:
            confidence = "HIGH"
        elif edge_pct >= 0.05:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        signal_type = "macro" if opp.category == "macro" else "momentum"

        return EdgeResult(
            ticker=opp.ticker,
            edge_pct=edge_pct,
            confidence=confidence,
            signal_type=signal_type,
        )

    def _size_position(self, edge: EdgeResult) -> int:
        """Fractional Kelly sizing. HIGH=full Kelly fraction, MEDIUM=half."""
        kelly_mult = 1.0 if edge.confidence == "HIGH" else 0.5
        # Simplified Kelly: contracts = kelly_fraction * kelly_mult * max_contracts
        contracts = int(KELLY_FRACTION * kelly_mult * MAX_CONTRACTS_PER_SIGNAL)
        return max(1, contracts)


def _ticker_to_symbol(ticker: str) -> str:
    """Extract crypto symbol from Kalshi ticker (e.g. BTCZ-25DEC95K → BTC)."""
    for sym in ("BTC", "ETH", "SOL"):
        if ticker.upper().startswith(sym):
            return sym
    return ticker.split("-")[0][:3].upper()
