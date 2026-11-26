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
