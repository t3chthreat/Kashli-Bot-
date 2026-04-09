import re
from dataclasses import dataclass
from kalshi_bot.macro_signals import is_high_impact_window

CRYPTO_PATTERNS = [
    r'\b(BTC|bitcoin)\b', r'\b(ETH|ethereum)\b', r'\b(SOL|solana)\b',
    r'\$\d+[,k]', r'above|below|reach|exceed',
]


@dataclass
class Opportunity:
    ticker: str
    category: str       # 'crypto' | 'macro'
    yes_price: float    # midpoint 0.0–1.0
    no_price: float
    volume_24h: float
    liquidity: float
    end_date: str
    question: str


def _is_crypto(title: str) -> bool:
    return any(re.search(p, title, re.IGNORECASE) for p in CRYPTO_PATTERNS)


def _market_to_opportunity(m: dict, category: str) -> Opportunity:
    yes_mid = ((m.get("yes_bid", 0) + m.get("yes_ask", 100)) / 2) / 100
    return Opportunity(
        ticker=m["ticker"],
        category=category,
        yes_price=yes_mid,
        no_price=1.0 - yes_mid,
        volume_24h=m.get("volume", 0),
        liquidity=m.get("liquidity", 0),
        end_date=m.get("close_time", ""),
        question=m.get("title", ""),
    )


def scan_crypto_markets(client, min_volume: float = 1000.0) -> list[Opportunity]:
    markets = client.get_markets(status="open")
    return [
        _market_to_opportunity(m, "crypto")
        for m in markets
        if _is_crypto(m.get("title", "")) and m.get("volume", 0) >= min_volume
    ]


def scan_macro_markets(client, min_volume: float = 500.0) -> list[Opportunity]:
    markets = client.get_markets(status="open")
    macro_keywords = ["fed", "cpi", "inflation", "gdp", "unemployment", "rate", "fomc"]
    high_impact = is_high_impact_window(hours=24)
    effective_min = min_volume * 0.5 if high_impact else min_volume
    return [
        _market_to_opportunity(m, "macro")
        for m in markets
        if any(kw in m.get("title", "").lower() for kw in macro_keywords)
        and m.get("volume", 0) >= effective_min
        and not _is_crypto(m.get("title", ""))
    ]


def rank_by_volume(opps: list[Opportunity]) -> list[Opportunity]:
    return sorted(opps, key=lambda o: o.volume_24h, reverse=True)
