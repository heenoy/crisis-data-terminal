from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import (
    CALIBRATION_SIZE,
    CATEGORICAL_FEATURES,
    DAMAGE_TARGET_COLUMN,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_DATA_PATH,
    FEATURE_COLUMNS,
    INTERVAL_COVERAGE,
    LEAKAGE_FIELDS,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TARGET_COLUMN,
    TEST_SIZE,
)
from modeling import build_regression_pipeline, calibrate_interval, sanitize_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train EM-DAT disaster impact regressors.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--skip-xgboost", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Use fewer trees for a smoke test.")
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0, engine="openpyxl")
    return pd.read_csv(path)


def correlation_ratio(categories: pd.Series, values: pd.Series) -> float | None:
    valid = categories.notna() & values.notna()
    if valid.sum() < 10:
        return None

    category_values = categories.loc[valid].astype(str)
    numeric_values = values.loc[valid].astype(float)
    codes, uniques = pd.factorize(category_values)
    if len(uniques) < 2 or len(uniques) > 500:
        return None

    overall_mean = numeric_values.mean()
    denominator = float(np.sum((numeric_values - overall_mean) ** 2))
    if denominator == 0:
        return 0.0

    numerator = 0.0
    for code in range(len(uniques)):
        group = numeric_values.iloc[np.flatnonzero(codes == code)]
        numerator += len(group) * float((group.mean() - overall_mean) ** 2)
    return float(np.sqrt(numerator / denominator))


def analyze_fields(frame: pd.DataFrame) -> pd.DataFrame:
    target = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce")
    rows: list[dict[str, Any]] = []
    for column in frame.columns:
        series = frame[column]
        numeric = pd.to_numeric(series, errors="coerce")
        valid_pair = numeric.notna() & target.notna()
        correlation = (
            numeric[valid_pair].corr(target[valid_pair], method="spearman")
            if valid_pair.sum() >= 10
            else np.nan
        )
        non_null_count = max(1, int(series.notna().sum()))
        is_mostly_numeric = numeric.notna().sum() / non_null_count >= 0.8
        category_association = None if is_mostly_numeric else correlation_ratio(series, target)
        rows.append(
            {
                "field": column,
                "dtype": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "missing_rate": float(series.isna().mean()),
                "unique_values": int(series.nunique(dropna=True)),
                "spearman_with_total_deaths": (
                    float(correlation) if pd.notna(correlation) else None
                ),
                "categorical_eta_with_total_deaths": category_association,
                "selected_feature": column in FEATURE_COLUMNS,
                "leakage_excluded": column in LEAKAGE_FIELDS,
                "exclusion_reason": LEAKAGE_FIELDS.get(column, ""),
            }
        )
    return pd.DataFrame(rows)


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def make_random_forest(quick: bool) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=80 if quick else 350,
        max_depth=16,
        min_samples_leaf=2,
        max_features=0.75,
        bootstrap=True,
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )


def make_xgboost(quick: bool) -> Any | None:
    try:
        from xgboost import XGBRegressor
    except ImportError:
        return None

    return XGBRegressor(
        n_estimators=120 if quick else 650,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.05,
        reg_lambda=1.0,
        objective="reg:squarederror",
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )


def plot_importance(importance: pd.DataFrame, output_path: Path, model_name: str) -> None:
    top = importance.head(15).sort_values("importance_mean")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top["feature"], top["importance_mean"], xerr=top["importance_std"], color="#38a95b")
    ax.set_title(f"{model_name} - permutation feature importance")
    ax.set_xlabel("MAE increase after permutation")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def train_model(
    model_name: str,
    estimator: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    output_dir: Path,
) -> dict[str, Any]:
    X_fit, X_cal, y_fit, y_cal = train_test_split(
        X_train,
        y_train,
        test_size=CALIBRATION_SIZE,
        random_state=RANDOM_STATE,
    )

    model = build_regression_pipeline(estimator)
    model.fit(X_fit, y_fit)

    calibration_prediction = np.maximum(0.0, model.predict(X_cal))
    interval = calibrate_interval(y_cal.to_numpy(), calibration_prediction, INTERVAL_COVERAGE)

    # Refit the point model on the complete 80% training partition after the
    # interval has been calibrated. The untouched 20% test partition remains
    # reserved for final metrics.
    model.fit(X_train, y_train)

    prediction = np.maximum(0.0, model.predict(X_test))
    lower, upper = interval.bounds(prediction)
    result_metrics = metrics(y_test.to_numpy(), prediction)
    result_metrics["interval_coverage"] = float(
        np.mean((y_test.to_numpy() >= lower) & (y_test.to_numpy() <= upper))
    )
    result_metrics["mean_interval_width"] = float(np.mean(upper - lower))

    sample_count = min(12, len(X_test))
    samples = X_test.head(sample_count).copy()
    samples.insert(0, "actual_total_deaths", y_test.head(sample_count).to_numpy())
    samples.insert(1, "predicted_total_deaths", np.rint(prediction[:sample_count]).astype(int))
    samples.insert(2, "interval_90_lower", np.rint(lower[:sample_count]).astype(int))
    samples.insert(3, "interval_90_upper", np.rint(upper[:sample_count]).astype(int))
    samples.to_csv(output_dir / f"{model_name}_prediction_samples.csv", index=False)

    perm = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="neg_mean_absolute_error",
        n_repeats=5,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    importance = pd.DataFrame(
        {
            "feature": X_test.columns,
            "importance_mean": perm.importances_mean,
            "importance_std": perm.importances_std,
        }
    ).sort_values("importance_mean", ascending=False)
    importance.to_csv(output_dir / f"{model_name}_feature_importance.csv", index=False)
    plot_importance(
        importance,
        output_dir / f"{model_name}_feature_importance.png",
        model_name,
    )

    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "interval": interval.to_dict(),
            "features": FEATURE_COLUMNS,
            "target": TARGET_COLUMN,
        },
        models_dir / f"{model_name}.joblib",
        compress=3,
    )

    return {
        "model": model_name,
        "metrics": result_metrics,
        "prediction_interval": interval.to_dict(),
        "top_features": importance.head(10).to_dict(orient="records"),
        "sample_file": f"{model_name}_prediction_samples.csv",
        "importance_plot": f"{model_name}_feature_importance.png",
    }


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    frame = load_data(args.data)
    if TARGET_COLUMN not in frame:
        raise KeyError(f"Missing target column: {TARGET_COLUMN}")

    field_analysis = analyze_fields(frame)
    field_analysis.to_csv(args.output / "field_analysis.csv", index=False)

    target = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce")
    valid = target.notna() & (target >= 0)
    modeling_frame = frame.loc[valid].copy()
    target = target.loc[valid].astype(float)
    features = sanitize_features(modeling_frame)

    X_train, X_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    estimators: list[tuple[str, Any]] = [
        ("random_forest", make_random_forest(args.quick)),
    ]
    if not args.skip_xgboost:
        xgboost = make_xgboost(args.quick)
        if xgboost is not None:
            estimators.append(("xgboost", xgboost))

    results = [
        train_model(name, estimator, X_train, y_train, X_test, y_test, args.output)
        for name, estimator in estimators
    ]

    report = {
        "data_path": str(args.data.resolve()),
        "total_rows": int(len(frame)),
        "modeled_rows": int(len(modeling_frame)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "target": TARGET_COLUMN,
        "future_target": DAMAGE_TARGET_COLUMN,
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
        },
        "excluded_leakage_fields": LEAKAGE_FIELDS,
        "split": {
            "train": 1 - TEST_SIZE,
            "test": TEST_SIZE,
            "calibration_fraction_within_train": CALIBRATION_SIZE,
            "random_state": RANDOM_STATE,
        },
        "target_summary": {
            key: float(value)
            for key, value in target.describe(percentiles=[0.5, 0.9, 0.95, 0.99]).to_dict().items()
        },
        "models": results,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (args.output / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
