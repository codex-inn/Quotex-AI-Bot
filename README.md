# Quotex AI — Web Market Analyzer

Web-only market-analysis dashboard with a secure backend adapter for external spot-FX data. No Telegram, Quotex login, or automated trading.

## Website
https://codex-inn.github.io/Quotex-AI-Bot/

Enable GitHub Pages in Settings → Pages → Deploy from a branch → main → /(root).

## Live spot-FX setup (Twelve Data)
1. Create a Twelve Data account and check current Forex pair entitlements, WebSocket availability, credits, rate limits and terms. Streaming and 1-second ticks are plan-dependent.
2. Deploy the backend using backend/Dockerfile or backend/render.yaml.
3. In backend host secret settings, set TWELVEDATA_API_KEY to your private key. Also set ALLOWED_ORIGINS=https://codex-inn.github.io and CANDLES_CACHE_SECONDS=60.
4. Check https://YOUR-BACKEND/health. provider_configured should be true.
5. Edit config.js and set window.QUOTEX_API_BASE = "https://YOUR-BACKEND"; then commit.
6. Reload GitHub Pages and select Live spot Forex.

Never put the provider key in config.js, HTML, JavaScript, GitHub Pages or chat. The backend proxies the provider REST candle history and WebSocket tick stream. The 1-second selector is a target/staleness preference, not a guarantee; the provider controls actual tick delivery.

## OTC
The Quotex OTC selector reports unavailable unless an authorized OTC feed is integrated. This app does not scrape Quotex or relabel external spot-FX quotes as Quotex OTC prices.

## Backend endpoints
- GET /health — provider configuration
- GET /api/candles?symbol=EUR/USD&interval=1min&outputsize=160 — OHLC candles
- WS /ws?symbol=EUR/USD — price stream

## Local backend
cd backend
python -m venv .venv
pip install -r requirements.txt
Set TWELVEDATA_API_KEY and ALLOWED_ORIGINS in your environment, then run: uvicorn main:app --reload --port 8000

Signals are transparent rule scores, not probabilities or financial advice. No trades are placed. Legacy Python offline backtest files remain in the repository.