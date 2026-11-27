"""Experimental screenshot trend inference using the separately trained HOG/SVM artifact."""
from __future__ import annotations
import io, os
from pathlib import Path
import joblib
import numpy as np
from PIL import Image, UnidentifiedImageError
from skimage.feature import hog

MODEL_PATH = Path(os.getenv("TREND_MODEL_PATH", "models/quotex-trend.joblib"))

def predict_trend(raw: bytes) -> dict:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError("Trend model missing. Install models/quotex-trend.joblib from the experimental training package.")
    try:
        image = Image.open(io.BytesIO(raw)).convert("L").resize((160, 90))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a readable image.") from exc
    features = hog(np.asarray(image, dtype=np.uint8), orientations=9,
                   pixels_per_cell=(8, 8), cells_per_block=(2, 2),
                   block_norm="L2-Hys").reshape(1, -1)
    model = joblib.load(MODEL_PATH)
    probs = model.predict_proba(features)[0]
    classes = model.named_steps["svm"].classes_
    index = int(np.argmax(probs))
    label, score = str(classes[index]), float(probs[index])
    return {
        "model": "HOG + RBF-SVM experimental screenshot trend classifier",
        "class": label,
        "direction": {"bullish_trend": "bullish", "bearish_trend": "bearish",
                      "sideways_or_mixed": "sideways"}.get(label, "unknown"),
        "score": round(score, 4),
        "signal": "CALL" if label == "bullish_trend" else "PUT" if label == "bearish_trend" else "INSUFFICIENT DATA",
        "warning": "Score measures model classification confidence, not probability of a winning trade. Labels were automatically generated from chart pixels; validate with human labels and unseen future outcomes."
    }
