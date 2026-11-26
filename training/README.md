# Quotex chart image model training

This is a trainable image classifier, not a pretrained Quotex strategy. It starts from ImageNet-pretrained ResNet18 weights and must be fine-tuned on your own labelled chart screenshots before predictions are meaningful.

## Dataset

Create one folder per visual class under `data/chart_images/`:

```
bullish_engulfing/ bearish_engulfing/ hammer/ shooting_star/
doji/ morning_star/ evening_star/ three_white_soldiers/
three_black_crows/ bullish_trend/ bearish_trend/ range/
breakout_up/ breakout_down/
```

Put cropped chart examples in the correct class folder. Aim for 100–500 diverse images per class. Include multiple themes, symbols, zoom levels and time periods. Exclude indicators/overlays unless they are consistently part of the intended input. Keep images from the same trading session together when creating a final chronological holdout set; the script's random validation split is only an initial training check and can overstate generalisation.

## Train locally (no model API key)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r training/requirements.txt
py training/train_chart_model.py --data data/chart_images --out models --epochs 12
```

Training downloads standard pretrained ResNet18 weights on first run, so internet access is needed for that initial download; no paid API key is used. A GPU is helpful but not required.

The output is `models/quotex-chart.onnx`, `models/labels.json` and `models/best_checkpoint.pt`. Keep these files out of Git until model quality and licensing are reviewed. Place the ONNX file and labels JSON in the backend deployment's `models/` directory for server inference, and publish the same ONNX file plus labels JSON at the website's `models/` path for browser inference. The browser feature will remain unavailable until those model assets exist.

## Evaluation

Do not treat the random validation accuracy as trading accuracy. Evaluate on a separate, later, unseen time period and report per-class precision/recall, confusion matrix, false CALL/PUT rate, and calibration. A chart-pattern label alone does not establish the next candle direction. A production signal should require separate, out-of-sample outcome validation.


## Multi-timeframe analysis (M1 + M5 + M15 + M30 + H1)

The backend now exposes `POST /api/analysis/multitimeframe`. Send a chronological list of one-minute OHLC candles; the service aggregates complete UTC-aligned bars into M5, M15, M30 and H1, then reports EMA 9/21 trend context and RSI(14) for each timeframe.

Example request body:

```json
{
  "candles": [
    {
      "datetime": "2026-11-26T10:00:00Z",
      "open": 1.0500,
      "high": 1.0510,
      "low": 1.0495,
      "close": 1.0505
    }
  ]
}
```

The example shows the required shape only; at least 60 unique, timezone-aware, one-minute candles are required. For H1 to become ready, provide at least 30 complete hourly bars (1,800 consecutive one-minute candles). Missing minutes cause incomplete higher-timeframe bars to be excluded. Only completed bars are analysed; optional `as_of` accepts an ISO-8601 timestamp and bars not yet closed at that time are dropped.

The API returns a per-timeframe direction and an overall CALL/PUT/WAIT label. It returns CALL or PUT only when all five timeframes are ready and aligned; otherwise it returns WAIT. This is a transparent technical-analysis rule, not a trained ML model, calibrated probability, or validated trading edge. Spot FX and Quotex OTC data must remain separately identified; do not combine markets as if their prices were interchangeable.
