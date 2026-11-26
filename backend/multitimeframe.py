"""Multi-timeframe analysis from a chronological one-minute OHLC series.

This is a transparent technical-analysis feature, not a trained or validated
trading predictor. It only uses completed bars and returns WAIT when evidence
is incomplete or timeframes disagree.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TIMEFRAMES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}


def _parse_time(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, str):
        raise ValueError("Each candle needs an ISO timestamp in 'datetime'.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Candle timestamps must include a timezone (prefer UTC/Z).")
    return parsed.astimezone(timezone.utc)


def _normalise(rows: Any) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError("'candles' must be a list of one-minute OHLC rows.")
    result = []
    for row in rows:
        try:
            stamp = _parse_time(row.get("datetime", row.get("timestamp")))
            candle = {key: float(row[key]) for key in ("open", "high", "low", "close")}
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid candle; require timezone-aware datetime and numeric OHLC.") from exc
        if not all(v == v and abs(v) != float("inf") for v in candle.values()):
            raise ValueError("OHLC values must be finite numbers.")
        if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
            raise ValueError("Candle high is inconsistent with OHLC.")
        if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
            raise ValueError("Candle low is inconsistent with OHLC.")
        result.append({"time": stamp, **candle})
    result.sort(key=lambda x: x["time"])
    if len(result) < 60:
        raise ValueError("At least 60 one-minute candles are required.")
    if len({row["time"] for row in result}) != len(result):
        raise ValueError("Duplicate candle timestamps found.")
    return result


def _aggregate(rows: list[dict], minutes: int) -> list[dict]:
    buckets: dict[datetime, list[dict]] = {}
    for row in rows:
        minute = row["time"].replace(second=0, microsecond=0)
        epoch_minute = int(minute.timestamp() // 60)
        start = datetime.fromtimestamp((epoch_minute // minutes) * minutes * 60, tz=timezone.utc)
        buckets.setdefault(start, []).append(row)
    bars = []
    for start, group in sorted(buckets.items()):
        # Require every minute in the interval; partial higher-timeframe bars are excluded.
        if len(group) != minutes:
            continue
        if any((group[i]["time"] - group[i - 1]["time"]).total_seconds() != 60 for i in range(1, len(group))):
            continue
        bars.append({
            "time": start,
            "open": group[0]["open"],
            "high": max(x["high"] for x in group),
            "low": min(x["low"] for x in group),
            "close": group[-1]["close"],
        })
    return bars


def _ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    value = values[0]
    for item in values[1:]:
        value = alpha * item + (1 - alpha) * value
    return value


def _rsi(values: list[float], period: int = 14) -> float:
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    if len(changes) < period:
        return 50.0
    gains = [max(x, 0.0) for x in changes[:period]]
    losses = [max(-x, 0.0) for x in changes[:period]]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    for change in changes[period:]:
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
    if avg_loss == 0:
        return 100.0 if avg_gain else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def _analyse(rows: list[dict], name: str) -> dict:
    if len(rows) < 30:
        return {"timeframe": name, "bars": len(rows), "direction": "unknown",
                "ready": False, "reason": "Need at least 30 complete bars for EMA 21 context."}
    closes = [x["close"] for x in rows]
    e9, e21 = _ema(closes, 9), _ema(closes, 21)
    rsi = _rsi(closes)
    last = rows[-1]
    candle = "bullish" if last["close"] > last["open"] else "bearish" if last["close"] < last["open"] else "neutral"
    direction = "bullish" if e9 > e21 and closes[-1] > e21 else "bearish" if e9 < e21 and closes[-1] < e21 else "sideways"
    return {
        "timeframe": name, "bars": len(rows), "last_completed_candle": last["time"].isoformat(),
        "direction": direction, "candle": candle, "ema9": round(e9, 8),
        "ema21": round(e21, 8), "rsi14": round(rsi, 2), "ready": True,
    }


def analyse_multitimeframe(payload: dict) -> dict:
    rows = _normalise(payload.get("candles"))
    as_of_value = payload.get("as_of")
    as_of = _parse_time(as_of_value) if as_of_value else rows[-1]["time"] + __import__("datetime").timedelta(minutes=1)
    # Drop any one-minute bar that has not fully closed by as_of.
    rows = [row for row in rows if row["time"] + __import__("datetime").timedelta(minutes=1) <= as_of]
    if len(rows) < 60:
        raise ValueError("Fewer than 60 completed one-minute candles remain after the as_of cutoff.")
    results = {}
    for name, minutes in TIMEFRAMES.items():
        bars = rows if minutes == 1 else _aggregate(rows, minutes)
        results[name] = _analyse(bars, name)
    ready = [x for x in results.values() if x["ready"]]
    directions = {x["direction"] for x in ready if x["direction"] in {"bullish", "bearish"}}
    aligned = len(ready) == len(TIMEFRAMES) and len(directions) == 1
    signal = "WAIT"
    if aligned and all(x["direction"] == "bullish" for x in ready):
        signal = "CALL"
    elif aligned and all(x["direction"] == "bearish" for x in ready):
        signal = "PUT"
    return {
        "timeframes": results,
        "alignment": "bullish" if signal == "CALL" else "bearish" if signal == "PUT" else "mixed_or_incomplete",
        "signal": signal,
        "policy": "CALL/PUT only when all five completed timeframes align; otherwise WAIT.",
        "note": "Rule-based technical context only. Not a trained model, win probability, or guarantee. Uses complete one-minute bars resampled to M1/M5/M15/M30/H1.",
    }
