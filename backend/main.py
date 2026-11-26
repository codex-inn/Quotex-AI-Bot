import asyncio
import json
import math
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "Quotex AI Market Data API"
API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
OTCHARTS_API_KEY = os.getenv("OTCHARTS_API_KEY", "").strip()
API_BASE = "https://api.twelvedata.com"
OTCHARTS_CANDLES_URL = "https://otcharts.com/v1/candles"
WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"
ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "ALLOWED_ORIGINS", "https://codex-inn.github.io"
).split(",") if x.strip()]
CACHE_SECONDS = max(30, int(os.getenv("CANDLES_CACHE_SECONDS", "60")))
ALLOWED_SYMBOLS = {
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD"
}
# These are the only OTC values evidenced by the supplied OTCharts request.
OTC_SYMBOLS = {"EURUSD_otc"}
OTC_TIMEFRAMES = {60}
cache: dict[str, tuple[float, dict[str, Any]]] = {}
otc_cache: dict[str, tuple[float, dict[str, Any]]] = {}


async def send_heartbeats(upstream):
    while True:
        await asyncio.sleep(10)
        await upstream.send(json.dumps({"action": "heartbeat"}))


def map_otcharts_candles(payload: Any) -> list[dict[str, Any]]:
    """Convert OTCharts Unix-second OHLC rows to the chart's datetime/OHLC shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("candles"), list):
        raise ValueError("Provider returned an invalid candle response")
    values = []
    for row in payload["candles"]:
        if not isinstance(row, dict):
            continue
        try:
            timestamp = float(row["time"])
            if not math.isfinite(timestamp):
                continue
            # OTCharts example uses Unix seconds. Accommodate millisecond epochs too.
            if timestamp > 1e12:
                timestamp /= 1000
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z")
            candle = {
                "datetime": dt,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            if not all(math.isfinite(candle[k]) for k in ("open", "high", "low", "close")):
                continue
            if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
                continue
            if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
                continue
            values.append(candle)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            continue
    return sorted(values, key=lambda candle: candle["datetime"])


app = FastAPI(title=APP_NAME, version="1.1.0")
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
        "quotex_otc": "available" if OTCHARTS_API_KEY else "needs_api_key",
        "otc_supported_symbols": sorted(OTC_SYMBOLS),
        "otc_supported_timeframes_seconds": sorted(OTC_TIMEFRAMES),
        "streaming": "Twelve Data WebSocket for spot FX; plan and symbol access dependent",
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
        raise HTTPException(502, "Spot-FX candle request failed") from exc
    if payload.get("status") == "error" or not payload.get("values"):
        raise HTTPException(502, "Spot-FX provider returned no candle data")
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


@app.get("/api/otc/candles")
async def otc_candles(symbol: str = "EURUSD_otc", tf: int = 60, limit: int = 160):
    if symbol not in OTC_SYMBOLS:
        raise HTTPException(400, "Unsupported OTC symbol")
    if tf not in OTC_TIMEFRAMES:
        raise HTTPException(400, "Unsupported OTC timeframe")
    if not 1 <= limit <= 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    if not OTCHARTS_API_KEY:
        raise HTTPException(503, "Backend is missing OTCHARTS_API_KEY")
    key = f"{symbol}:{tf}:{limit}"
    now = time.monotonic()
    cached = otc_cache.get(key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return {**cached[1], "cached": True, "cache_seconds": CACHE_SECONDS}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                OTCHARTS_CANDLES_URL,
                params={"venue": "quotex", "symbol": symbol, "tf": tf, "limit": limit},
                headers={"Authorization": f"Bearer {OTCHARTS_API_KEY}"},
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "OTCharts candle request failed") from exc
    try:
        values = map_otcharts_candles(payload)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    if not values:
        raise HTTPException(502, "OTCharts returned no valid candles")
    result = {
        "source": "OTCharts",
        "market": "quotex_otc",
        "venue": "quotex",
        "symbol": symbol,
        "timeframe_seconds": tf,
        "values": values,
        "provider_timestamp": int(time.time()),
        "cached": False,
        "cache_seconds": CACHE_SECONDS,
        "delivery": "REST polling; this endpoint does not provide ticks or a WebSocket stream.",
    }
    otc_cache[key] = (now, result)
    return result


@app.websocket("/ws")
async def price_stream(client_ws: WebSocket, symbol: str = "EUR/USD"):
    origin = client_ws.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        await client_ws.close(code=1008)
        return
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
            heartbeat_task = asyncio.create_task(send_heartbeats(upstream))
            await client_ws.send_json({
                "event": "subscribing",
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
                elif data.get("event") in {"status", "subscribe-status"}:
                    await client_ws.send_json(data)
                elif data.get("event") == "error" or data.get("status") == "error":
                    await client_ws.send_json({
                        "event": "error",
                        "message": data.get("message", "Provider rejected the stream subscription"),
                    })
            heartbeat_task.cancel()
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
