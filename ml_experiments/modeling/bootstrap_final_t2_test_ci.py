"""Reproduce frozen T2 test metrics and compute deterministic stratified bootstrap CIs.

This script reads only frozen validation/test prediction artifacts. It does not load
the modeling dataset, maturity rows, or fit/modify any model or preprocessor.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MODELING_ROOT = REPO_ROOT / "ml_experiments/modeling"
LABELS = ["Low", "Moderate", "Severe"]
SEED = 20260827
N_BOOTSTRAP = 2_000
TEST_PREDICTIONS = MODELING_ROOT / "three_class/final_t2/predictions/test_predictions.csv"
MODEL_PATH = MODELING_ROOT / "three_class/final_t2/artifacts/final_t2_pipeline.joblib"
OUTPUT_PATH = MODELING_ROOT / "reports/third_stage_supplement_ci.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metric_values(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0)),
        "low_recall": float(recall[0]),
        "low_f1": float(f1[0]),
        "moderate_recall": float(recall[1]),
        "moderate_f1": float(f1[1]),
        "severe_precision": float(precision[2]),
        "severe_recall": float(recall[2]),
        "severe_f1": float(f1[2]),
        "quadratic_weighted_kappa": float(cohen_kappa_score(y_true, y_pred, labels=LABELS, weights="quadratic")),
    }


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return center - margin, center + margin


def collapsed_validation_metrics(path: Path) -> dict[str, object]:
    frame = pd.read_csv(path)
    collapsed = {"High": "Severe", "Extreme": "Severe"}
    y_true = frame["true_label"].replace(collapsed).to_numpy()
    y_pred = frame["predicted_label"].replace(collapsed).to_numpy()
    values = metric_values(y_true, y_pred)
    return {
        "rows": int(len(frame)),
        "metrics": {key: values[key] for key in [
            "accuracy", "balanced_accuracy", "macro_f1", "weighted_f1",
            "severe_precision", "severe_recall", "severe_f1",
        ]},
    }


def main() -> None:
    frame = pd.read_csv(TEST_PREDICTIONS)
    required = {"event_id", "year", "true_label", "predicted_label"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"Missing required prediction columns: {sorted(required - set(frame.columns))}")
    if len(frame) != 948 or frame["event_id"].isna().any() or frame["event_id"].duplicated().any():
        raise RuntimeError("Frozen Test prediction integrity check failed")
    if set(frame["year"].astype(int)) != {2022, 2023}:
        raise RuntimeError("Test years changed or non-Test years were read")
    counts = frame["true_label"].value_counts().reindex(LABELS).to_dict()
    if counts != {"Low": 305, "Moderate": 524, "Severe": 119}:
        raise RuntimeError(f"Test class counts changed: {counts}")

    y_true = frame["true_label"].to_numpy()
    y_pred = frame["predicted_label"].to_numpy()
    point = metric_values(y_true, y_pred)
    expected = {
        "accuracy": 0.7151898734177216,
        "balanced_accuracy": 0.7137004445126819,
        "macro_f1": 0.6811013972875063,
        "weighted_f1": 0.7178671823414073,
        "quadratic_weighted_kappa": 0.5434242822078885,
        "severe_precision": 0.5373134328358209,
        "severe_recall": 0.6050420168067226,
        "severe_f1": 0.5691699604743083,
    }
    for name, value in expected.items():
        if not math.isclose(point[name], value, rel_tol=0, abs_tol=1e-12):
            raise RuntimeError(f"Point estimate mismatch for {name}: {point[name]} != {value}")

    matrix = confusion_matrix(y_true, y_pred, labels=LABELS).tolist()
    expected_matrix = [[277, 14, 14], [147, 329, 48], [31, 16, 72]]
    if matrix != expected_matrix:
        raise RuntimeError(f"Confusion matrix mismatch: {matrix}")

    rng = np.random.default_rng(SEED)
    class_indices = {label: np.flatnonzero(y_true == label) for label in LABELS}
    samples = {name: np.empty(N_BOOTSTRAP, dtype=float) for name in point}
    for iteration in range(N_BOOTSTRAP):
        sampled_indices = np.concatenate([
            rng.choice(indices, size=len(indices), replace=True)
            for indices in class_indices.values()
        ])
        values = metric_values(y_true[sampled_indices], y_pred[sampled_indices])
        for name, value in values.items():
            samples[name][iteration] = value

    intervals = {
        name: {
            "point_estimate": point[name],
            "ci_lower": float(np.percentile(values, 2.5)),
            "ci_upper": float(np.percentile(values, 97.5)),
        }
        for name, values in samples.items()
    }
    wilson_lower, wilson_upper = wilson_interval(72, 119)

    candidates = pd.read_csv(MODELING_ROOT / "lightgbm/reports/lightgbm_candidate_comparison.csv")
    selected = json.loads((MODELING_ROOT / "lightgbm/artifacts/selected_lightgbm_config.json").read_text(encoding="utf-8"))
    if len(candidates) != 18 or selected["candidate_id"] != "LGBM-V2_P3_low_rate_balanced" or selected["best_iteration"] != 291:
        raise RuntimeError("Historical LightGBM selection audit failed")

    rf_validation_path = MODELING_ROOT / "predictions/validation_predictions.csv"
    lgbm_validation_path = MODELING_ROOT / "lightgbm/predictions/validation_predictions.csv"
    rf_validation = pd.read_csv(rf_validation_path)
    lgbm_validation = pd.read_csv(lgbm_validation_path)
    if len(rf_validation) != 804 or len(lgbm_validation) != 804:
        raise RuntimeError("Historical validation row count changed")
    if set(rf_validation["event_id"]) != set(lgbm_validation["event_id"]):
        raise RuntimeError("RF and LightGBM validation events do not align")
    rf_truth = rf_validation.set_index("event_id")["true_label"].sort_index()
    lgbm_truth = lgbm_validation.set_index("event_id")["true_label"].sort_index()
    if not rf_truth.equals(lgbm_truth):
        raise RuntimeError("RF and LightGBM validation labels differ")

    t2_validation = collapsed_validation_metrics(MODELING_ROOT / "three_class/predictions/validation_predictions_T2.csv")
    result = {
        "method": {
            "name": "stratified_event_bootstrap_percentile",
            "iterations": N_BOOTSTRAP,
            "random_seed": SEED,
            "confidence_level": 0.95,
            "sampling": "sample with replacement within each true class, preserving original class counts",
            "maturity_data_read": False,
        },
        "inputs": {
            "test_predictions": str(TEST_PREDICTIONS.relative_to(REPO_ROOT)),
            "test_predictions_sha256": sha256(TEST_PREDICTIONS),
            "frozen_model": str(MODEL_PATH.relative_to(REPO_ROOT)),
            "frozen_model_sha256": sha256(MODEL_PATH),
        },
        "test_audit": {
            "rows": int(len(frame)),
            "years": sorted(frame["year"].astype(int).unique().tolist()),
            "class_counts": {key: int(value) for key, value in counts.items()},
            "duplicate_event_ids": int(frame["event_id"].duplicated().sum()),
            "confusion_matrix_labels": LABELS,
            "confusion_matrix": matrix,
        },
        "bootstrap_intervals": intervals,
        "severe_recall_wilson": {
            "successes": 72,
            "total": 119,
            "point_estimate": 72 / 119,
            "ci_lower": wilson_lower,
            "ci_upper": wilson_upper,
        },
        "historical_model_audit": {
            "lightgbm_candidate_rows": int(len(candidates)),
            "selected_lightgbm_candidate": selected["candidate_id"],
            "selected_lightgbm_best_iteration": int(selected["best_iteration"]),
            "validation_rows_each": 804,
            "validation_event_ids_identical": True,
            "validation_true_labels_identical": True,
            "historical_task": "four_class_Low_Moderate_High_Extreme",
            "posthoc_three_class_evaluation": {
                "note": "High and Extreme predictions/labels are collapsed to Severe only for supplementary evaluation; models are not retrained.",
                "random_forest_rf_v2_c09": collapsed_validation_metrics(rf_validation_path),
                "lightgbm_v2_p3_balanced": collapsed_validation_metrics(lgbm_validation_path),
                "final_rf_t2_validation": t2_validation,
            },
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "output_sha256": sha256(OUTPUT_PATH),
        "test_rows": len(frame),
        "model_sha256": result["inputs"]["frozen_model_sha256"],
        "maturity_data_read": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
