"""
kalshi_bot/price_feed.py — Live Crypto Price Feed (CoinGecko — Free, No API Key)

Fetches real-time BTC, ETH, SOL spot prices to:
  1. Calculate momentum signals (is price trending up or down?)
  2. Calibrate our YES/NO probability estimate vs the market's current odds
  3. Detect divergence between market price and true probability
     → Divergence = edge → take the position the market is mispricing
"""
import time
import statistics
import requests
from typing import Optional

# Coinbase public API — no key needed, US-accessible, generous rate limits
COINBASE_URL = "https://api.coinbase.com/v2/prices"
COINBASE_PAIRS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}

# CoinGecko as fallback
COINGECKO_URL = "https://api.coingecko.com/api/v3"
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

HISTORY_LIMIT = 30


class PriceFeed:
    def __init__(self):
        self._price_history: dict[str, list[float]] = {a: [] for a in COINBASE_PAIRS}
        self._last_fetch: float = 0
        self._fetch_interval: int = 20
        self._last_prices: dict[str, float] = {}

    def fetch(self) -> dict[str, float]:
        prices = self._fetch_coinbase() or self._fetch_coingecko()
        if prices:
            for symbol, price in prices.items():
                self._price_history[symbol].append(price)
                if len(self._price_history[symbol]) > HISTORY_LIMIT:
                    self._price_history[symbol].pop(0)
            self._last_prices = prices
            self._last_fetch = time.time()
        return self._last_prices

    def _fetch_coinbase(self) -> dict[str, float]:
        try:
            prices = {}
            for symbol, pair in COINBASE_PAIRS.items():
                r = requests.get(f"{COINBASE_URL}/{pair}/spot", timeout=8)
                r.raise_for_status()
                prices[symbol] = float(r.json()["data"]["amount"])
            return prices
        except Exception:
            return {}

    def _fetch_coingecko(self) -> dict[str, float]:
        try:
            ids = ",".join(COINGECKO_IDS.values())
            r = requests.get(
                f"{COINGECKO_URL}/simple/price",
                params={"ids": ids, "vs_currencies": "usd"},
                timeout=8,
            )
            r.raise_for_status()
            data = r.json()
            return {
                symbol: float(data[cg_id]["usd"])
                for symbol, cg_id in COINGECKO_IDS.items()
                if cg_id in data and "usd" in data[cg_id]
            }
        except Exception:
            return {}

    def get_prices(self) -> dict[str, float]:
        if time.time() - self._last_fetch > self._fetch_interval:
            return self.fetch()
        return self._last_prices

    def momentum(self, symbol: str, lookback: int = 5) -> float:
        hist = self._price_history.get(symbol, [])
        if len(hist) < lookback + 1:
            return 0.0
        recent = hist[-lookback:]
        first = recent[0]
        last = recent[-1]
        if first == 0:
            return 0.0
        return (last - first) / first

    def short_momentum(self, symbol: str) -> float:
        return self.momentum(symbol, lookback=3)

    def medium_momentum(self, symbol: str) -> float:
        return self.momentum(symbol, lookback=10)

    def volatility(self, symbol: str) -> float:
        hist = self._price_history.get(symbol, [])
        if len(hist) < 5:
            return 0.0
        changes = [
            abs(hist[i] - hist[i - 1]) / hist[i - 1]
            for i in range(1, len(hist))
            if hist[i - 1] > 0
        ]
        return statistics.mean(changes) if changes else 0.0

    def estimate_up_probability(self, symbol: str, timeframe: str = "15min") -> float:
        short_mom = self.short_momentum(symbol)
        med_mom = self.medium_momentum(symbol)
        vol = self.volatility(symbol)
        if timeframe in ("5min", "15min"):
            mom_signal = (short_mom * 0.7 + med_mom * 0.3)
            mom_weight = 0.20
        elif timeframe == "1hr" or timeframe == "1h":
            mom_signal = (short_mom * 0.3 + med_mom * 0.7)
            mom_weight = 0.15
        else:
            mom_signal = med_mom
            mom_weight = 0.10
        adjustment = max(-mom_weight, min(mom_weight, mom_signal * 2.0))
        prob = 0.50 + adjustment
        if vol > 0.002:
            prob = 0.50 + (prob - 0.50) * 0.7
        return round(max(0.20, min(0.80, prob)), 4)

    def edge_vs_market(self, symbol: str, market_yes_price: float, timeframe: str = "15min") -> float:
        """Returns edge as a float (abs difference between our prob estimate and market price)."""
        our_prob = self.estimate_up_probability(symbol, timeframe)
        edge_pct = abs(our_prob - market_yes_price)
        return round(edge_pct, 4)
