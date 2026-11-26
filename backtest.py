"""Simple next-candle close backtest for OHLC CSV files."""
import argparse
import pandas as pd
from analyzer import analyze

def run_backtest(df, payout=0.80, min_score=4):
    df=df.sort_values("datetime").reset_index(drop=True)
    trades=[]
    # Each decision uses candles up to i; outcome is next candle close direction.
    for i in range(60,len(df)-1):
        result=analyze(df.iloc[:i+1],min_score)
        if result["signal"]=="NO TRADE": continue
        entry=float(df.iloc[i]["close"]); exit_price=float(df.iloc[i+1]["close"])
        won=(exit_price>entry) if result["signal"]=="CALL" else (exit_price<entry)
        trades.append({"time":str(df.iloc[i]["datetime"]),"signal":result["signal"],"won":won,
                       "score":result["score"]})
    n=len(trades); wins=sum(t["won"] for t in trades)
    net=sum(payout if t["won"] else -1.0 for t in trades)
    return {"trades":n,"wins":wins,"losses":n-wins,
            "win_rate_pct":round(wins/n*100,2) if n else 0,
            "net_units_per_1_unit_risk":round(net,2),
            "trades_detail":trades}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True); p.add_argument("--payout",type=float,default=0.80)
    p.add_argument("--min-score",type=int,default=4); a=p.parse_args()
    df=pd.read_csv(a.csv)
    required={"datetime","open","high","low","close"}
    if not required.issubset(df.columns): raise SystemExit("CSV requires: "+", ".join(sorted(required)))
    for c in ("open","high","low","close"): df[c]=pd.to_numeric(df[c],errors="coerce")
    df["datetime"]=pd.to_datetime(df["datetime"],errors="coerce")
    df=df.dropna(subset=list(required))
    result=run_backtest(df,a.payout,a.min_score)
    print("DEMO BACKTEST — simplified next-candle close outcome")
    for k,v in result.items():
        if k!="trades_detail": print(f"{k}: {v}")
    print("Not Quotex settlement; excludes spreads, latency, ties and OTC differences.")

if __name__=="__main__": main()
