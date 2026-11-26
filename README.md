# Quotex AI — Web Market Analyzer

A browser-only, demo-first market-analysis dashboard. No Telegram bot, BotFather token, broker login, or trade execution.

## Open the website
After enabling GitHub Pages:
1. Open **Settings → Pages** in this repository.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch `main` and folder `/ (root)`, then Save.
4. Your site will be available at: https://codex-inn.github.io/Quotex-AI-Bot/

## Features
- Responsive browser dashboard
- Major forex pair selector and 1m / 5m / 15m display options
- Demo OHLC candles and chart
- EMA 9/21/50, RSI(14), MACD
- Bullish/bearish engulfing, pin bar and doji pattern detection
- Transparent CALL / PUT / NO TRADE rule scoring
- CSV import for historical OHLC data
- Simplified next-candle backtest and results summary

## Data and safety
The dashboard initially generates **synthetic demo candles**. It does not show live prices. Import a CSV with columns `datetime,open,high,low,close` to analyse historical candles. The timeframe selector changes the display label; uploaded CSV timestamps are not resampled automatically.

A rule score is not a probability or guaranteed win rate. Backtests use a simplified next-candle close direction and do not model Quotex settlement, spreads, latency, slippage, ties, or OTC pricing. External spot-FX data may differ from Quotex OTC prices. This is educational software, not financial advice.

## Optional local Python backtest
The repository also retains a command-line CSV backtester:
```bash
pip install -r requirements.txt
python backtest.py --csv data/sample_EURUSD.csv
python -m unittest discover -s tests -v
``

## Project files
- `index.html` — complete static web app (HTML, CSS, JavaScript)
- `analyzer.py` — Python indicator and rule-analysis module
- `backtest.py` — Python historical CSV backtester
- `data/sample_EURUSD.csv` — synthetic sample dataset
- `tests/` — basic unit tests
