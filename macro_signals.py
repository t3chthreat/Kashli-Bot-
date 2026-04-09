import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import requests

logger = logging.getLogger(__name__)


@dataclass
class MacroEvent:
    name: str
    event_date: datetime
    consensus_estimate: float | None
    prior_value: float | None
    impact: str  # 'high' | 'medium' | 'low'


def _fetch_fred_calendar() -> list[dict]:
    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key:
        return []
    url = "https://api.stlouisfed.org/fred/releases/dates"
    r = requests.get(
        url,
        params={"api_key": api_key, "file_type": "json", "limit": 50},
        timeout=5,
    )
    r.raise_for_status()
    return r.json().get("release_dates", [])


def get_upcoming_events(days_ahead: int = 7) -> list[MacroEvent]:
    raw = _fetch_fred_calendar()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days_ahead)
    events = []
    for item in raw:
        try:
            dt = datetime.strptime(item["date"], "%Y-%m-%d")
            if dt <= cutoff:
                name = item.get("name", item.get("release_name", "Unknown"))
                events.append(MacroEvent(
                    name=name,
                    event_date=dt,
                    consensus_estimate=None,
                    prior_value=None,
                    impact="high" if any(kw in name.lower() for kw in ("cpi", "fed", "fomc", "gdp", "unemployment"))
                           else "medium",
                ))
        except (KeyError, ValueError):
            continue
    return events


def estimate_probability(event: MacroEvent, kalshi_price: float) -> float:
    return kalshi_price


def is_high_impact_window(hours: int = 24) -> bool:
    try:
        events = get_upcoming_events(days_ahead=int(hours / 24) + 1)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)
        return any(e.impact == "high" and e.event_date <= cutoff for e in events)
    except Exception as exc:
        logger.warning("macro_signals: FRED unavailable (%s) — fail-open returning False", exc)
        return False
