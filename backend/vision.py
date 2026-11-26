"""Shared ONNX inference for uploaded chart screenshots."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

MODEL_DIR = Path(os.getenv("VISION_MODEL_DIR", "models"))
MODEL_PATH = MODEL_DIR / "quotex-chart.onnx"
LABELS_PATH = MODEL_DIR / "labels.json"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DIRECTION = {
    "bullish_engulfing": "bullish", "hammer": "bullish",
    "morning_star": "bullish", "three_white_soldiers": "bullish",
    "bullish_trend": "bullish", "breakout_up": "bullish",
    "bearish_engulfing": "bearish", "shooting_star": "bearish",
    "evening_star": "bearish", "three_black_crows": "bearish",
    "bearish_trend": "bearish", "breakout_down": "bearish",
    "doji": "neutral", "range": "neutral",
}


def predict_image(raw: bytes) -> dict:
    if not MODEL_PATH.is_file() or not LABELS_PATH.is_file():
        raise FileNotFoundError("Trained model is not installed. Train it and place models/quotex-chart.onnx and models/labels.json.")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a readable image.") from exc
    image.thumbnail((1600, 1600))
    with LABELS_PATH.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    size = int(metadata.get("image_size", 224))
    image = image.resize((size, size))
    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    tensor = np.transpose(array, (2, 0, 1))[None, ...].astype(np.float32)
    import onnxruntime as ort
    session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    logits = session.run(["logits"], {"image": tensor})[0][0]
    exp = np.exp(logits - np.max(logits))
    probs = exp / np.sum(exp)
    classes = metadata["classes"]
    idx = int(np.argmax(probs))
    label = classes[idx]
    confidence = float(probs[idx])
    direction = DIRECTION.get(label, "unknown")
    # A classifier score is not a calibrated probability or a trade-win probability.
    signal = "WAIT"
    if confidence >= 0.80 and direction in {"bullish", "bearish"}:
        signal = "CALL" if direction == "bullish" else "PUT"
    return {
        "model": "ResNet18 chart-image classifier",
        "class": label,
        "direction": direction,
        "score": round(confidence, 4),
        "signal": signal,
        "signal_policy": "WAIT unless a directional class reaches 0.80 model score; not a win probability.",
        "model_validation_accuracy": metadata.get("validation_accuracy"),
        "warning": "Experimental image classification. Validate on unseen market sessions; this is not a guaranteed or standalone trading signal.",
    }
