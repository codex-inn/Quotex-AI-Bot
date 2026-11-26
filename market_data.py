"""External spot-FX candle data adapter (not Quotex/OTC data)."""
import os, requests
import pandas as pd

BASE="https://api.twelvedata.com/time_series"

def fetch_candles(symbol: str, outputsize: int=120) -> pd.DataFrame:
    key=os.getenv("TWELVEDATA_API_KEY","").strip()
    if not key: raise RuntimeError("TWELVEDATA_API_KEY is not configured")
    response=requests.get(BASE,params={"symbol":symbol,"interval":os.getenv("INTERVAL","1min"),
        "outputsize":outputsize,"apikey":key,"format":"JSON"},timeout=20)
    response.raise_for_status()
    payload=response.json()
    if "values" not in payload:
        raise RuntimeError(payload.get("message","Market data provider returned no candle values"))
    df=pd.DataFrame(payload["values"])
    df=df.rename(columns={"datetime":"datetime"})
    for col in ("open","high","low","close"):
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df["datetime"]=pd.to_datetime(df["datetime"],errors="coerce")
    return df.dropna(subset=["datetime","open","high","low","close"]).sort_values("datetime").reset_index(drop=True)
