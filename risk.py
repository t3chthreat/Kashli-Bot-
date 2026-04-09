import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kalshi_bot.config import Config


@dataclass
class Position:
    ticker: str
    contracts: int
    side: str           # 'yes' | 'no'
    entry_price: float
    order_id: str
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskManager:
    def __init__(self, config: Config):
        self.config = config
        self.positions: dict[str, Position] = {}
        self._daily_pnl: float = 0.0
        self._total_exposure: float = 0.0
        self._halted: bool = False
        self._halt_reason: str = ""
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.session_start: float = time.time()

    def is_halted(self) -> tuple[bool, str]:
        # Check daily loss limit dynamically (not just when record_fill is called)
        if self._daily_pnl <= -abs(self.config.daily_loss_limit_usd):
            self._halt_reason = f"Daily loss limit hit: ${self._daily_pnl:.2f}"
            return True, self._halt_reason
        return self._halted, self._halt_reason

    def can_open_market(self, ticker: str) -> tuple[bool, str]:
        halted, reason = self.is_halted()
        if halted:
            return False, f"Bot halted: {reason}"

        if len(self.positions) >= self.config.max_open_positions:
            if ticker not in self.positions:
                return False, f"Max open positions reached ({self.config.max_open_positions})"

        if self._total_exposure + self.config.max_position_usd > self.config.max_exposure_usd:
            return False, f"Exposure limit: ${self.config.max_exposure_usd:.2f}"

        return True, "ok"

    def record_fill(self, ticker: str, side: str, price: float, contracts: int) -> None:
        self.total_trades += 1
        if side in ("yes", "no"):
            # New position opened
            cost = price * contracts
            self._total_exposure += cost
        elif side == "settlement":
            # Position closed — reduce exposure by cost basis
            pos = self.positions.get(ticker)
            if pos:
                cost_basis = pos.entry_price * pos.contracts
                self._total_exposure = max(0.0, self._total_exposure - cost_basis)
                # pnl tracked by executor — not here to avoid double-counting

    def total_exposure(self) -> float:
        return self._total_exposure

    def reset_daily(self) -> None:
        self._daily_pnl = 0.0
        self._halted = False
        self._halt_reason = ""

    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades * 100

    def _halt(self, reason: str) -> None:
        self._halted = True
        self._halt_reason = reason
