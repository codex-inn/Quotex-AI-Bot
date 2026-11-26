"""Transparent rule-based forex candle analysis. Scores are not probabilities."""
from __future__ import annotations
import pandas as pd
import numpy as np

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    close = x["close"].astype(float)
    for n in (9, 21, 50):
        x[f"ema{n}"] = close.ewm(span=n, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi"] = (100 - 100 / (1 + rs)).fillna(50)
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    x["macd"] = fast - slow
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False).mean()
    return x

def candle_patterns(row: pd.Series, prev: pd.Series | None) -> list[str]:
    o,h,l,c = [float(row[k]) for k in ("open","high","low","close")]
    body = abs(c-o); span = max(h-l, 1e-12)
    upper = h-max(o,c); lower = min(o,c)-l
    found=[]
    if body/span < 0.10: found.append("doji")
    if lower > body*2 and upper < body*1.2 and c >= o: found.append("bullish_pin_bar")
    if upper > body*2 and lower < body*1.2 and c <= o: found.append("bearish_pin_bar")
    if prev is not None:
        po,pc=float(prev["open"]),float(prev["close"])
        if c>o and pc<po and o<=pc and c>=po: found.append("bullish_engulfing")
        if c<o and pc>po and o>=pc and c<=po: found.append("bearish_engulfing")
    return found

def analyze(df: pd.DataFrame, min_score: int=4) -> dict:
    if len(df) < 60: return {"signal":"NO TRADE","score":0,"reasons":["Need at least 60 candles"]}
    x=add_indicators(df).dropna()
    if len(x)<2: return {"signal":"NO TRADE","score":0,"reasons":["Insufficient indicator history"]}
    r=x.iloc[-1]; p=x.iloc[-2]
    patterns=candle_patterns(r,p)
    bull=bear=0; reasons=[]
    if r.ema9>r.ema21: bull+=1; reasons.append("EMA9 above EMA21")
    elif r.ema9<r.ema21: bear+=1; reasons.append("EMA9 below EMA21")
    if r.close>r.ema50: bull+=1; reasons.append("Price above EMA50")
    elif r.close<r.ema50: bear+=1; reasons.append("Price below EMA50")
    if r.rsi>52 and r.rsi<70: bull+=1; reasons.append(f"RSI bullish ({r.rsi:.1f})")
    elif r.rsi<48 and r.rsi>30: bear+=1; reasons.append(f"RSI bearish ({r.rsi:.1f})")
    if r.macd>r.macd_signal: bull+=1; reasons.append("MACD above signal")
    elif r.macd<r.macd_signal: bear+=1; reasons.append("MACD below signal")
    if any(z in patterns for z in ("bullish_engulfing","bullish_pin_bar")): bull+=1; reasons.append("Bullish candle pattern")
    if any(z in patterns for z in ("bearish_engulfing","bearish_pin_bar")): bear+=1; reasons.append("Bearish candle pattern")
    score=max(bull,bear)
    signal="CALL" if bull>=min_score and bull>bear else ("PUT" if bear>=min_score and bear>bull else "NO TRADE")
    return {"signal":signal,"score":score,"bull_score":bull,"bear_score":bear,
            "score_scale":5,"score_label":"rule points, not probability",
            "rsi":round(float(r.rsi),1),"patterns":patterns,"reasons":reasons,
            "candle_time":str(r.get("datetime","unknown")),"close":float(r.close)}
