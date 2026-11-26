import unittest
import pandas as pd
from analyzer import add_indicators, candle_patterns, analyze

class AnalyzerTests(unittest.TestCase):
    def test_indicators_are_added(self):
        df=pd.DataFrame({"open":[1+i*.001 for i in range(70)],"high":[1.002+i*.001 for i in range(70)],"low":[.999+i*.001 for i in range(70)],"close":[1.001+i*.001 for i in range(70)]})
        out=add_indicators(df)
        for col in ("ema9","ema21","ema50","rsi","macd","macd_signal"):
            self.assertIn(col,out.columns)
        self.assertFalse(out["ema9"].isna().all())

    def test_engulfing_pattern(self):
        prev=pd.Series({"open":1.10,"high":1.11,"low":1.08,"close":1.09})
        current=pd.Series({"open":1.085,"high":1.12,"low":1.08,"close":1.115})
        self.assertIn("bullish_engulfing",candle_patterns(current,prev))

    def test_short_history_is_no_trade(self):
        df=pd.DataFrame({"open":[1]*10,"high":[1.1]*10,"low":[.9]*10,"close":[1]*10})
        self.assertEqual(analyze(df)["signal"],"NO TRADE")

if __name__=="__main__": unittest.main()
