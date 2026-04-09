import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

def _env_float(var: str, default: str) -> float:
    val = os.getenv(var, default)
    try:
        return float(val)
    except ValueError:
        raise EnvironmentError(f"Invalid value for {var}: expected a number, got '{val}'")

def _env_int(var: str, default: str) -> int:
    val = os.getenv(var, default)
    try:
        return int(val)
    except ValueError:
        raise EnvironmentError(f"Invalid value for {var}: expected an integer, got '{val}'")

@dataclass
class Config:
    kalshi_key_id: str = field(default_factory=lambda: os.getenv("KALSHI_KEY_ID", ""))
    kalshi_private_key: str = field(default_factory=lambda: os.getenv("KALSHI_PRIVATE_KEY", ""))
    max_position_usd: float = field(default_factory=lambda: _env_float("MAX_POSITION_USD", "25"))
    max_exposure_usd: float = field(default_factory=lambda: _env_float("MAX_EXPOSURE_USD", "200"))
    daily_loss_limit_usd: float = field(default_factory=lambda: _env_float("DAILY_LOSS_LIMIT_USD", "50"))
    min_edge: float = field(default_factory=lambda: _env_float("MIN_EDGE", "0.05"))
    max_open_positions: int = field(default_factory=lambda: _env_int("MAX_OPEN_POSITIONS", "5"))
    scan_interval_secs: int = field(default_factory=lambda: _env_int("SCAN_INTERVAL_SECS", "30"))
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    s3_backup_bucket: str = field(default_factory=lambda: os.getenv("S3_BACKUP_BUCKET", ""))

    @staticmethod
    def validate_required() -> None:
        missing = [k for k in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY") if not os.getenv(k)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
