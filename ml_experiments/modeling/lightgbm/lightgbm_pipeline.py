"""Serializable train-only categorical mapping for native LightGBM features."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MISSING = "__MISSING__"
UNKNOWN = "__UNKNOWN__"


@dataclass
class TrainOnlyCategoryMapper:
    categorical_features: list[str]
    feature_order: list[str]
    categories_: dict[str, list[str]] = field(default_factory=dict)
    known_: dict[str, set[str]] = field(default_factory=dict)

    def fit(self, frame: pd.DataFrame) -> "TrainOnlyCategoryMapper":
        self.categories_.clear()
        self.known_.clear()
        for column in self.categorical_features:
            values = frame[column].astype("string").fillna(MISSING)
            known = sorted(v for v in values.unique().tolist() if v not in {MISSING, UNKNOWN})
            self.categories_[column] = [MISSING, UNKNOWN, *known]
            self.known_[column] = set(known)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.categories_:
            raise RuntimeError("Category mapper has not been fitted")
        out = frame.loc[:, self.feature_order].copy()
        for column in self.categorical_features:
            values = out[column].astype("string").fillna(MISSING)
            values = values.where(values.isin(self.known_[column]) | values.eq(MISSING), UNKNOWN)
            out[column] = pd.Categorical(values, categories=self.categories_[column], ordered=False)
        for column in self.feature_order:
            if column not in self.categorical_features:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        return out

    def unknown_mask(self, frame: pd.DataFrame) -> pd.Series:
        mask = pd.Series(False, index=frame.index)
        for column in self.categorical_features:
            values = frame[column].astype("string")
            mask |= values.notna() & ~values.isin(self.known_[column])
        return mask

    def unknown_report(self, frame: pd.DataFrame, split: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for column in self.categorical_features:
            values = frame[column].astype("string")
            unknown = values.notna() & ~values.isin(self.known_[column])
            rows.append({
                "split": split,
                "field": column,
                "training_category_count": len(self.known_[column]),
                "unknown_count": int(unknown.sum()),
                "unknown_rate": float(unknown.mean()),
                "missing_count": int(values.isna().sum()),
                "missing_rate": float(values.isna().mean()),
            })
        return rows


@dataclass
class LightGBMNativePipeline:
    mapper: TrainOnlyCategoryMapper
    model: Any
    label_order: list[str]

    def predict_indices(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict(self.mapper.transform(frame)), dtype=int)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        indices = self.predict_indices(frame)
        labels = np.asarray(self.label_order, dtype=object)
        return labels[indices]

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict_proba(self.mapper.transform(frame)), dtype=float)
