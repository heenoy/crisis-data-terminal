from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from config import CATEGORICAL_FEATURES, NUMERIC_FEATURES


class IQRClipper(BaseEstimator, TransformerMixin):
    """Clip numeric features using train-only IQR bounds."""

    def __init__(self, factor: float = 3.0):
        self.factor = factor

    def fit(self, X: Any, y: Any = None) -> "IQRClipper":
        values = np.asarray(X, dtype=float)
        q1 = np.nanpercentile(values, 25, axis=0)
        q3 = np.nanpercentile(values, 75, axis=0)
        iqr = q3 - q1
        self.lower_bounds_ = q1 - self.factor * iqr
        self.upper_bounds_ = q3 + self.factor * iqr
        return self

    def transform(self, X: Any) -> np.ndarray:
        values = np.asarray(X, dtype=float)
        return np.clip(values, self.lower_bounds_, self.upper_bounds_)


@dataclass
class PredictionInterval:
    lower_residual: float
    upper_residual: float
    coverage: float

    def bounds(self, predictions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lower = np.maximum(0.0, predictions + self.lower_residual)
        upper = np.maximum(lower, predictions + self.upper_residual)
        return lower, upper

    def to_dict(self) -> dict[str, float]:
        return {
            "lower_residual": self.lower_residual,
            "upper_residual": self.upper_residual,
            "coverage": self.coverage,
        }


def build_preprocessor() -> ColumnTransformer:
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=5,
                    sparse_output=True,
                ),
            ),
        ]
    )
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("clipper", IQRClipper(factor=3.0)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("categorical", categorical, CATEGORICAL_FEATURES),
            ("numeric", numeric, NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def build_regression_pipeline(regressor: Any) -> TransformedTargetRegressor:
    pipeline = Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("regressor", regressor),
        ]
    )
    return TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def sanitize_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame[CATEGORICAL_FEATURES + NUMERIC_FEATURES].copy()
    for column in CATEGORICAL_FEATURES:
        values = features[column].astype("object")
        features[column] = values.where(pd.notna(values), np.nan)
    for column in NUMERIC_FEATURES:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    return features


def calibrate_interval(
    actual: np.ndarray,
    predicted: np.ndarray,
    coverage: float,
) -> PredictionInterval:
    alpha = 1.0 - coverage
    residuals = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return PredictionInterval(
        lower_residual=float(np.quantile(residuals, alpha / 2)),
        upper_residual=float(np.quantile(residuals, 1 - alpha / 2)),
        coverage=coverage,
    )
