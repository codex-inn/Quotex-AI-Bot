import asyncio
import json
import os
import time
from typing import Any

import httpx
import websockets
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "Quotex AI Market Data API"
API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
API_BASE = "https://api.twelvedata.com"
WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"
ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "ALLOWED_ORIGINS", "https://codex-inn.github.io"
).split(",") if x.strip()]
CACHE_SECONDS = max(30, int(os.getenv("CANDLES_CACHE_SECONDS", "60")))
ALLOWED_SYMBOLS = {
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD"
}
cache: dict[str, tuple[float, dict[str, Any]]] = {}

app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": "Twelve Data",
        "provider_configured": bool(API_KEY),
        "spot_fx": "available" if API_KEY else "needs_api_key",
        "quotex_otc": "unavailable_no_authorized_feed",
        "streaming": "Twelve Data WebSocket; plan and symbol access dependent",
    }


@app.get("/api/candles")
async def candles(symbol: str = "EUR/USD", interval: str = "1min", outputsize: int = 120):
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(400, "Unsupported pair")
    if interval not in {"1min", "5min", "15min"}:
        raise HTTPException(400, "Unsupported interval")
    if not API_KEY:
        raise HTTPException(503, "Backend is missing TWELVEDATA_API_KEY")
    outputsize = min(max(outputsize, 60), 500)
    key = f"{symbol}:{interval}:{outputsize}"
    now = time.monotonic()
    cached = cache.get(key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return {**cached[1], "cached": True, "cache_seconds": CACHE_SECONDS}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{API_BASE}/time_series",
                params={"symbol": symbol, "interval": interval, "outputsize": outputsize},
                headers={"Authorization": f"apikey {API_KEY}"},
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f"Market-data request failed: {exc}") from exc
    if payload.get("status") == "error" or not payload.get("values"):
        message = payload.get("message", "Provider returned no candle data")
        raise HTTPException(502, message)
    values = []
    for row in reversed(payload["values"]):
        try:
            values.append({
                "datetime": row["datetime"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    if len(values) < 60:
        raise HTTPException(502, "Provider returned fewer than 60 valid candles")
    result = {
        "source": "Twelve Data",
        "market": "spot_fx",
        "symbol": symbol,
        "interval": interval,
        "values": values,
        "provider_timestamp": int(time.time()),
        "cached": False,
        "cache_seconds": CACHE_SECONDS,
        "note": "External spot-FX feed; not Quotex OTC pricing.",
    }
    cache[key] = (now, result)
    return result


@app.websocket("/ws")
async def price_stream(client_ws: WebSocket, symbol: str = "EUR/USD"):
    await client_ws.accept()
    if symbol not in ALLOWED_SYMBOLS:
        await client_ws.send_json({"event": "error", "message": "Unsupported pair"})
        await client_ws.close(code=1008)
        return
    if not API_KEY:
        await client_ws.send_json({"event": "error", "message": "Backend API key is not configured"})
        await client_ws.close(code=1011)
        return
    try:
        async with websockets.connect(
            f"{WS_URL}?apikey={API_KEY}",
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as upstream:
            await upstream.send(json.dumps({
                "action": "subscribe",
                "params": {"symbols": symbol},
            }))
            await client_ws.send_json({
                "event": "connected",
                "provider": "Twelve Data",
                "symbol": symbol,
                "market": "spot_fx",
            })
            async for raw in upstream:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if data.get("event") == "price" and data.get("symbol", "").upper() == symbol.upper():
                    await client_ws.send_json({
                        "event": "price",
                        "symbol": symbol,
                        "price": data.get("price"),
                        "timestamp": data.get("timestamp"),
                        "source": "Twelve Data",
                        "market": "spot_fx",
                    })
                elif data.get("event") == "status":
                    await client_ws.send_json(data)
                elif data.get("event") == "error" or data.get("status") == "error":
                    await client_ws.send_json({
                        "event": "error",
                        "message": data.get("message", "Provider rejected the stream subscription"),
                    })
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await client_ws.send_json({"event": "error", "message": str(exc)[:240]})
        except Exception:
            pass
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
