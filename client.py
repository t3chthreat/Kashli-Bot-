import base64
import time
import httpx
from dataclasses import dataclass
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

@dataclass
class Fill:
    order_id: str
    ticker: str
    side: str
    price: float
    contracts: int

class KalshiClient:
    def __init__(self, key_id: str, private_key):
        self.key_id = key_id
        self._private_key = private_key
        self._http = httpx.Client(base_url=BASE_URL, timeout=10.0)

    @classmethod
    def from_env(cls) -> "KalshiClient":
        import os
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        key_id = os.environ["KALSHI_KEY_ID"]
        pem = os.environ["KALSHI_PRIVATE_KEY"].encode()
        private_key = load_pem_private_key(pem, password=None)
        return cls(key_id=key_id, private_key=private_key)

    def _sign_request(self, method: str, path: str) -> dict:
        ts = str(int(time.time() * 1000))
        msg = (ts + method.upper() + path).encode()
        sig = self._private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        }

    def _get(self, path: str, params: dict = None) -> dict:
        headers = self._sign_request("GET", path)
        r = self._http.get(path, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        headers = self._sign_request("POST", path)
        r = self._http.post(path, headers=headers, json=body)
        r.raise_for_status()
        return r.json()

    def get_balance(self) -> float:
        data = self._get("/portfolio/balance")
        return data["balance"]["available_balance"] / 100  # cents → dollars

    def get_markets(self, status: str = "open", limit: int = 200) -> list[dict]:
        data = self._get("/markets", params={"status": status, "limit": limit})
        return [m for m in data.get("markets", []) if m.get("status") == status]

    def get_orderbook(self, ticker: str) -> dict:
        return self._get(f"/markets/{ticker}/orderbook")

    def place_order(self, ticker: str, side: str, price: int, count: int,
                    action: str = "buy", client_order_id: str = "") -> dict:
        body = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "type": "limit",
            "yes_price": price if side == "yes" else 100 - price,
            "count": count,
            "client_order_id": client_order_id,
        }
        return self._post("/portfolio/orders", body)

    def cancel_order(self, order_id: str) -> bool:
        try:
            r = self._http.delete(
                f"/portfolio/orders/{order_id}",
                headers=self._sign_request("DELETE", f"/portfolio/orders/{order_id}")
            )
            r.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def get_fills(self) -> list[Fill]:
        raw = self._get("/portfolio/fills").get("fills", [])
        result = []
        for f in raw:
            side = f.get("side", "")
            # Use yes_price for "yes" fills, no_price for "no" fills
            if side == "yes":
                price_cents = f.get("yes_price", 0)
            else:
                price_cents = f.get("no_price", f.get("yes_price", 0))
            result.append(Fill(
                order_id=f.get("order_id", ""),
                ticker=f.get("ticker", ""),
                side=side,
                price=price_cents / 100,
                contracts=f.get("count", 0),
            ))
        return result

    async def ws_connect(self, tickers: list[str], on_message) -> None:
        uri = "wss://trading-api.kalshi.com/trade-api/ws/v2"
        subscribe_msg = {
            "id": 1,
            "cmd": "subscribe",
            "params": {"channels": ["orderbook_delta"], "market_tickers": tickers}
        }
        await self._ws_reconnect_loop(uri, subscribe_msg, on_message)

    async def _ws_reconnect_loop(self, uri, subscribe_msg, on_message, max_attempts=10) -> None:
        import asyncio
        import json
        import websockets as ws
        attempts = 0
        while True:
            try:
                websocket = await ws.connect(uri)
                try:
                    await websocket.send(json.dumps(subscribe_msg))
                    attempts = 0
                    async for raw in websocket:
                        on_message(json.loads(raw))
                finally:
                    await websocket.close()
            except Exception as exc:
                attempts += 1
                if attempts >= max_attempts:
                    raise RuntimeError(f"WebSocket failed after {max_attempts} attempts") from exc
                await asyncio.sleep(5)

    def ws_disconnect(self) -> None:
        pass  # cancellation handled by asyncio task cancellation
