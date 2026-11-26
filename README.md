# Quotex AI — Web Market Analyzer

Web-only market-analysis dashboard with a backend adapter for external market data. No Quotex login or automated trading.

## Website
https://codex-inn.github.io/Quotex-AI-Bot/

Enable GitHub Pages in Settings → Pages → Deploy from a branch → main → /(root).

## Deploy the backend
1. Deploy the backend using `backend/Dockerfile` or `backend/render.yaml`.
2. In your backend host's private environment settings, add the provider secrets you use:
   - `TWELVEDATA_API_KEY` for spot-FX candles and the provider's WebSocket tick stream.
   - `OTCHARTS_API_KEY` for the OTCharts Quotex OTC candle REST endpoint.
3. Set `ALLOWED_ORIGINS=https://codex-inn.github.io` and `CANDLES_CACHE_SECONDS=60`.
4. Check `https://YOUR-BACKEND/health`. The response lists the configured providers and the supported OTC symbol/timeframe.
5. Edit `config.js` and set `window.QUOTEX_API_BASE = "https://YOUR-BACKEND"`; commit that public backend URL, which is not a secret.
6. Reload GitHub Pages. Select **Quotex OTC** to load the supported pair and one-minute timeframe.

Never put either provider key in `config.js`, HTML, JavaScript, GitHub Pages, or chat. Store each key only in the backend host's secret settings. The example value in `backend/.env.example` is a placeholder. The OTCharts token must be entered by the repository owner; it is not included in this repository or commit.

## Quotex OTC data
The backend calls `https://otcharts.com/v1/candles` with `venue=quotex`, the selected symbol, timeframe in seconds, and candle limit. It sends `Authorization: Bearer <OTCHARTS_API_KEY>` from the server and maps returned OHLC values and Unix timestamps into the chart's `datetime/open/high/low/close` format.

Only `EURUSD_otc` and `tf=60` seconds are enabled because those are the only symbol and timeframe demonstrated by the supplied API request. The browser polls the REST candle endpoint once per minute. This is periodic candle retrieval; the supplied endpoint does not document a WebSocket or tick stream, so OTC chart updates are not tick-by-tick. Other OTCharts symbols/timeframes are rejected until their support is confirmed.

## Spot Forex
The existing Twelve Data integration remains separate. Its REST endpoint loads spot-FX candles, and its WebSocket stream may deliver ticks subject to provider plan, symbol access, and delivery. Spot-FX prices are not Quotex OTC prices.

## Backend endpoints
- `GET /health` — provider configuration and OTC capabilities
- `GET /api/candles?symbol=EUR/USD&interval=1min&outputsize=160` — Twelve Data spot-FX OHLC
- `GET /api/otc/candles?symbol=EURUSD_otc&tf=60&limit=160` — OTCharts Quotex OTC OHLC via REST
- `GET /api/export/csv?market=quotex_otc&symbol=EURUSD_otc&tf=60&limit=500` — download separate Quotex OTC candles as CSV
- `GET /api/export/csv?market=forex&symbol=EUR/USD&tf=60&limit=500` — download separate spot-Forex candles as CSV
- `WS /ws?symbol=EUR/USD` — Twelve Data spot-FX price stream only

## Local backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OTCHARTS_API_KEY = "set-your-private-token-here"
$env:ALLOWED_ORIGINS = "https://codex-inn.github.io"
uvicorn main:app --reload --port 8000
```

Set `TWELVEDATA_API_KEY` too if using the existing spot-FX integration. Do not commit a real `.env` file or provider token.

Signals are transparent rule scores, not probabilities or financial advice. No trades are placed. Legacy Python offline backtest files remain in the repository.

## Dashboard features
- Responsive dark trading-analysis workspace for desktop and mobile.
- OHLC candlestick chart with EMA 9, EMA 21 and EMA 50 overlays.
- Candle recognition: doji, hammer, shooting star, bullish/bearish engulfing, inside bar, morning/evening star, and three white soldiers/three black crows when the candle sequence matches.
- RSI 14, MACD, EMA trend context, and recent swing support/resistance levels.
- Transparent CALL / PUT / WAIT rule scoring with individual reasons. The score is a count of confirmations, not an AI probability or a promise of accuracy.
- CSV import with OHLC validation and a historical next-candle direction backtest.
- Screenshot upload with experimental candle-shape extraction and relative pixel-based OHLC estimates. Screenshot-derived values are for visual context only; the app deliberately does not issue CALL/PUT from them.
- No synthetic demo candles are generated. The dashboard waits for a user-uploaded screenshot, imported OHLC CSV, or configured live provider.
- Imported history, screenshot-derived estimates, spot-FX data and Quotex OTC data are separate sources.

The browser-side rule analysis works without a provider when you import a CSV containing real OHLC candles. Screenshot extraction is approximate and never produces a CALL/PUT signal. The app does not generate synthetic market candles. CSV rows are sorted chronologically when valid timestamps are present. To receive Quotex OTC candles, configure the backend and a valid OTCharts token as described above. The website does not collect Quotex login credentials, scrape the trading platform, or execute orders.


## Trained screenshot vision AI (browser + backend)

The repository now includes a ResNet18 training pipeline and shared ONNX inference:
- `training/train_chart_model.py` fine-tunes an image classifier from labelled chart screenshots.
- `backend/vision.py` and `POST /api/vision/predict` run the same ONNX model in the Python backend.
- The website has separate **Run browser-trained AI** and **Run backend-trained AI** controls. Browser inference uses ONNX Runtime Web; backend inference uses ONNX Runtime CPU.
- Both paths require the same trained files: `models/quotex-chart.onnx` and `models/labels.json`. They are intentionally not included as fake/pretrained trading assets. Until trained files are deployed, the vision model controls remain unavailable or report that the model is missing.

Follow [training/README.md](training/README.md) to build the labelled dataset and train the model. No paid AI API key is needed. A first training run downloads the standard ResNet18 initialization weights. To enable backend inference, deploy the backend with its `models/` folder populated; to enable browser inference, publish those same two files under the website's `models/` folder. Do not commit large model weights unless you intentionally want them public.

The classifier identifies chart-image classes; it does not predict a guaranteed next candle. Its displayed score is a model class score, not a win probability. Validate chronologically on unseen market sessions and keep WAIT as the default when confidence/evidence is weak. Live Quotex OTC prices remain a separate feed integration and still require a legitimate data provider; this vision model does not need that feed.
