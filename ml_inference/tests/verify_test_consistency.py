"""Verify direct and raw-input end-to-end consistency for all 948 frozen Test events."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml_inference.feature_builder import FEATURES, FrozenFeatureBuilder  # noqa: E402
from ml_inference.loader import get_pipeline  # noqa: E402

FINAL = ROOT / "ml_experiments/modeling/three_class/final_t2"
MERGED = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
RAW = ROOT / "data/emdat_raw.xlsx"
FROZEN_PRED = FINAL / "predictions/test_predictions.csv"
OUTPUT = ROOT / "ml_inference/reports/test_consistency_results.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pipeline = get_pipeline()
    frozen = pd.read_csv(FROZEN_PRED).set_index("event_id")
    data = pd.read_csv(MERGED, usecols=["event_id", "country_code", "disaster_type", "disaster_subtype",
                                                "year", "total_deaths", "event_date", "date_granularity"])
    data = data[data.year.between(2022, 2023) & data.total_deaths.notna()].copy()
    raw = pd.read_excel(RAW, sheet_name="EM-DAT Data", dtype=object, keep_default_na=False,
                        usecols=["DisNo.", "Magnitude", "Magnitude Scale"])
    raw.columns = ["event_id", "magnitude", "magnitude_scale"]
    raw.event_id = raw.event_id.astype(str)
    data = data.merge(raw, on="event_id", how="left", validate="one_to_one")
    if len(data) != 948 or set(data.event_id) != set(frozen.index):
        raise RuntimeError("Test source/frozen prediction alignment failed")
    builder = FrozenFeatureBuilder()
    rows, payloads = [], []
    for row in data.itertuples(index=False):
        timestamp = pd.Timestamp(row.event_date)
        if row.date_granularity == "day": event_date = timestamp.strftime("%Y-%m-%d")
        elif row.date_granularity == "month": event_date = timestamp.strftime("%Y-%m")
        else: event_date = timestamp.strftime("%Y")
        payload = {"country_code": row.country_code, "disaster_type": row.disaster_type,
                   "disaster_subtype": row.disaster_subtype, "event_date": event_date,
                   "date_granularity": row.date_granularity,
                   "magnitude": None if row.magnitude == "" else row.magnitude,
                   "magnitude_scale": None if row.magnitude_scale == "" else row.magnitude_scale}
        frame, _ = builder.build(payload)
        rows.append(frame); payloads.append(payload)
    X = pd.concat(rows, ignore_index=True)[FEATURES]
    pred = pipeline.predict(X)
    classes = pipeline.named_steps["model"].classes_.tolist()
    proba = pipeline.predict_proba(X)[:, [classes.index(x) for x in ["Low", "Moderate", "Severe"]]]
    expected = frozen.loc[data.event_id]
    expected_proba = expected[["probability_Low", "probability_Moderate", "probability_Severe"]].to_numpy()
    class_matches = pred == expected.predicted_label.to_numpy()
    probability_error = np.abs(proba - expected_proba)

    first = payloads[0]
    reversed_payload = dict(reversed(list(first.items())))
    a, _ = builder.build(first); b, _ = builder.build(reversed_payload)
    order_class_equal = bool(pipeline.predict(a)[0] == pipeline.predict(b)[0])
    order_probability_diff = float(np.max(np.abs(pipeline.predict_proba(a) - pipeline.predict_proba(b))))
    result = {
        "test_events": len(data), "pipeline_direct_reference": "frozen final Test predictions",
        "end_to_end_source": "raw request fields reconstructed from frozen EM-DAT plus frozen lookup assets",
        "prediction_class_match_count": int(class_matches.sum()),
        "prediction_class_match_rate": float(class_matches.mean()),
        "mismatch_event_ids": data.loc[~class_matches, "event_id"].tolist(),
        "predict_proba_max_abs_error": float(probability_error.max()),
        "predict_proba_values_over_1e_12": int((probability_error > 1e-12).sum()),
        "feature_columns_exact": X.columns.tolist() == FEATURES,
        "feature_columns": X.columns.tolist(), "class_order": classes,
        "json_field_order_class_equal": order_class_equal,
        "json_field_order_probability_max_abs_error": order_probability_diff,
        "passed": bool(class_matches.all() and probability_error.max() <= 1e-12 and X.columns.tolist() == FEATURES
                       and classes == ["Low", "Moderate", "Severe"] and order_class_equal and order_probability_diff <= 1e-12),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]: raise SystemExit(1)


if __name__ == "__main__": main()
