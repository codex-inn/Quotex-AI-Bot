# Quotex AI Analysis Bot (Demo Only)

Telegram-only, demo-first forex analysis for 1-minute candles. This project generates educational CALL/PUT *analysis alerts* from external market data. It does not connect to Quotex, place trades, or execute real-money orders.

> **Risk notice:** Signals are uncertain and are not financial advice. A scoring value is not a win probability. External spot-FX prices may differ from Quotex prices, especially OTC instruments. Do not assume backtest results predict live outcomes.

## Features
- Major FX pairs: EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD
- EMA 9/21/50, RSI(14), MACD(12,26,9)
- Basic bullish/bearish engulfing, pin-bar and doji detection
- Transparent weighted rule score; CALL, PUT or NO TRADE
- Telegram alerts with candle timestamp and explanation
- CSV historical backtesting with next-candle outcome and configurable payout
- Docker deployment for a persistent worker

## Quick start
1. Create a Telegram bot with [@BotFather](https://t.me/BotFather), then send it a message.
2. Get a market-data API key from [Twelve Data](https://twelvedata.com/).
3. Copy `.env.example` to `.env` and set secrets locally.
4. Install and run:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python backtest.py --csv data/sample_EURUSD.csv
python bot.py
```

## Environment
- `TELEGRAM_BOT_TOKEN`: BotFather token (secret)
- `TELEGRAM_CHAT_ID`: chat ID that receives alerts (send /start to your bot first)
- `TWELVEDATA_API_KEY`: Twelve Data API key (secret)
- `PAIRS`: comma-separated symbols, default list uses Twelve Data format (e.g. EUR/USD)
- `INTERVAL`: default `1min`
- `POLL_SECONDS`: polling interval; default 60
- `MIN_SCORE`: minimum rule score to emit a directional alert; default 4
- `PAYOUT`: hypothetical net payout per 1 unit risk on a win for backtest; default 0.80

Never commit `.env` or paste tokens into chat. Set the same variables in your hosting provider's secret/environment settings.

## Backtesting
CSV must contain columns `datetime,open,high,low,close` (volume optional). Example:

```bash
python backtest.py --csv data/sample_EURUSD.csv --payout 0.80 --min-score 4
```

The demo CSV is synthetic and only validates the pipeline. Use properly licensed, timestamped historical data for meaningful testing. The backtest evaluates the *next candle close* as a simplified outcome; it does not model Quotex settlement, spreads, latency, slippage, ties, or OTC pricing.

## Cloud hosting
Deploy as a **Docker worker/background worker** on a provider that supports persistent processes (for example Render, Railway, or a VPS). This is not a GitHub Pages app. Add environment variables in the host dashboard; do not put secrets in source control. See `Dockerfile` and `render.yaml`.

## Limitations
- No Quotex login, scraping, browser automation, account access, or order execution.
- Twelve Data plan limits and symbol availability apply. The bot skips a pair if the provider rejects it.
- OTC instruments are not supported by this external spot-FX feed.
- Rule-based scoring is not machine-learning prediction and is not a probability.
