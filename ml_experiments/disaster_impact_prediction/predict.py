from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from modeling import PredictionInterval, sanitize_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict total deaths for one EM-DAT-like event.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True, help="JSON object with model features.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = joblib.load(args.model)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    frame = sanitize_features(pd.DataFrame([payload]))

    prediction = np.maximum(0.0, bundle["model"].predict(frame))
    interval = PredictionInterval(**bundle["interval"])
    lower, upper = interval.bounds(prediction)

    result = {
        "target": bundle["target"],
        "prediction": float(prediction[0]),
        "interval_90": {
            "lower": float(lower[0]),
            "upper": float(upper[0]),
        },
        "display": (
            f"预测死亡人数: {prediction[0]:.0f} "
            f"(90%置信区间: {lower[0]:.0f}-{upper[0]:.0f})"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
