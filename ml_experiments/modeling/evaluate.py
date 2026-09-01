"""Evaluation helpers with a fixed impact-level class order."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)

from feature_config import LABEL_ORDER


def evaluate_predictions(y_true, y_pred) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    aggregate = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(y_true, y_pred, labels=LABEL_ORDER, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=LABEL_ORDER, average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABEL_ORDER, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=LABEL_ORDER, average="weighted", zero_division=0)),
    }
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABEL_ORDER, zero_division=0
    )
    per_class = pd.DataFrame({
        "class": LABEL_ORDER,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support.astype(int),
    })
    matrix = pd.DataFrame(
        confusion_matrix(y_true, y_pred, labels=LABEL_ORDER),
        index=[f"true_{label}" for label in LABEL_ORDER],
        columns=[f"pred_{label}" for label in LABEL_ORDER],
    )
    return aggregate, per_class, matrix


def ordered_probabilities(pipeline, frame: pd.DataFrame) -> np.ndarray:
    model = pipeline.named_steps["model"]
    probabilities = pipeline.predict_proba(frame)
    indexes = {label: index for index, label in enumerate(model.classes_)}
    if set(indexes) != set(LABEL_ORDER):
        raise RuntimeError(f"Model class set/order mismatch: {list(model.classes_)}")
    return probabilities[:, [indexes[label] for label in LABEL_ORDER]]


def metric_row(model_id: str, model_family: str, feature_version: str, split: str, metrics: dict[str, Any], **extra) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "model_family": model_family,
        "feature_version": feature_version,
        "split": split,
        **metrics,
        **extra,
    }

