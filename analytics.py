"""
kalshi_bot/analytics.py — Research-Backed Market Analytics

Implements microstructure metrics from academic research.
"""

import math
import statistics
from typing import Optional


def compute_vpin(trades: list[dict], bucket_size: int = 50) -> float:
    if not trades or len(trades) < bucket_size:
        return 0.35

    buckets = []
    current_buy = 0.0
    current_sell = 0.0
    current_vol = 0.0

    for trade in trades:
        size = float(trade.get("size", 0))
        side = trade.get("side", "buy").lower()

        if side == "buy":
            current_buy += size
        else:
            current_sell += size
        current_vol += size

        if current_vol >= bucket_size:
            order_imbalance = abs(current_buy - current_sell) / current_vol
            buckets.append(order_imbalance)
            current_buy = 0.0
            current_sell = 0.0
            current_vol = 0.0

    if not buckets:
        return 0.35

    return min(statistics.mean(buckets), 1.0)


def compute_roll_measure(prices: list[float]) -> float:
    if len(prices) < 10:
        return 0.0

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    if len(changes) < 2:
        return 0.0

    n = len(changes) - 1
    mean1 = statistics.mean(changes[:-1])
    mean2 = statistics.mean(changes[1:])

    cov = sum(
        (changes[i] - mean1) * (changes[i + 1] - mean2)
        for i in range(n)
    ) / n

    if cov < 0:
        return 2.0 * math.sqrt(-cov)
    return 0.0


def market_quality_score(
    spread: float,
    mid_price: float,
    volume_24h: float,
    num_traders: int = 0,
    vpin: float = 0.35,
    roll: float = 0.0,
) -> float:
    spread_score = min(spread / 0.15, 1.0)
    volume_score = min(volume_24h / 5000.0, 1.0)
    proximity_score = 1.0 - abs(mid_price - 0.5) * 2.0
    proximity_score = max(proximity_score, 0.0)
    vpin_score = max(1.0 - (vpin / 0.6), 0.0)
    roll_score = max(1.0 - (roll / 0.05), 0.0)

    score = (
        spread_score    * 0.40 +
        volume_score    * 0.25 +
        proximity_score * 0.20 +
        vpin_score      * 0.10 +
        roll_score      * 0.05
    )

    return round(min(score, 1.0), 4)


class EnsembleSignalGate:
    def __init__(
        self,
        min_spread: float = 0.04,
        max_vpin: float = 0.55,
        min_volume_24h: float = 500.0,
        max_roll: float = 0.05,
        boundary_buffer: float = 0.06,
        required_signals: int = 4,
    ):
        self.min_spread = min_spread
        self.max_vpin = max_vpin
        self.min_volume_24h = min_volume_24h
        self.max_roll = max_roll
        self.boundary_buffer = boundary_buffer
        self.required_signals = required_signals

    def evaluate(
        self,
        spread: float,
        mid_price: float,
        vpin: float,
        volume_24h: float,
        roll: float,
    ) -> tuple[bool, list[dict]]:
        signals = [
            {
                "name": "Spread Width",
                "pass": spread >= self.min_spread,
                "value": f"{spread:.2%}",
                "threshold": f">= {self.min_spread:.2%}",
                "weight": "Profit exists in the spread",
            },
            {
                "name": "VPIN Toxicity",
                "pass": vpin <= self.max_vpin,
                "value": f"{vpin:.3f}",
                "threshold": f"<= {self.max_vpin:.3f}",
                "weight": "Flow is not adversely informed",
            },
            {
                "name": "Volume (24h)",
                "pass": volume_24h >= self.min_volume_24h,
                "value": f"${volume_24h:,.0f}",
                "threshold": f">= ${self.min_volume_24h:,.0f}",
                "weight": "Market is liquid enough",
            },
            {
                "name": "Roll Momentum",
                "pass": roll <= self.max_roll,
                "value": f"{roll:.4f}",
                "threshold": f"<= {self.max_roll:.4f}",
                "weight": "Market not in runaway momentum",
            },
            {
                "name": "Price Boundary",
                "pass": self.boundary_buffer < mid_price < (1.0 - self.boundary_buffer),
                "value": f"{mid_price:.4f}",
                "threshold": f"{self.boundary_buffer:.2f} < p < {1 - self.boundary_buffer:.2f}",
                "weight": "Not near resolution edge (0 or 1)",
            },
        ]

        passed = sum(1 for s in signals if s["pass"])
        go = passed >= self.required_signals

        return go, signals
