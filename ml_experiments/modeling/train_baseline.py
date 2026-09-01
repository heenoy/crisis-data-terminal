"""Train auditable Dummy and Random Forest baselines with strict time splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from evaluate import evaluate_predictions, metric_row, ordered_probabilities
from feature_config import (
    EXCLUDED_FIELDS,
    FEATURE_VERSIONS,
    LABEL_ORDER,
    RANDOM_STATE,
    assert_safe_feature_list,
)

TARGET = "impact_level"
SPLITS = {
    "train": (2000, 2019),
    "validation": (2020, 2021),
    "test": (2022, 2023),
    "maturity_holdout": (2024, 2026),
}
NEAR_TIE_MACRO_F1 = 0.002

RF_CANDIDATES = [
    {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": weight}
    for weight in (None, "balanced", "balanced_subsample")
] + [
    {"n_estimators": 300, "max_depth": 20, "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": weight}
    for weight in (None, "balanced", "balanced_subsample")
] + [
    {"n_estimators": 500, "max_depth": 10, "min_samples_leaf": 5, "max_features": 0.5, "class_weight": weight}
    for weight in (None, "balanced", "balanced_subsample")
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["hdi_missing"] = result["hdi"].isna().astype("int8")
    parsed = pd.to_datetime(result["event_date"], errors="coerce")
    month_available = result["date_granularity"].isin(["day", "month"])
    result["event_month"] = parsed.dt.month.where(month_available).astype("Float64")
    result["month_missing"] = result["event_month"].isna().astype("int8")
    return result


def make_split_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    masks = {name: frame["year"].between(start, end) for name, (start, end) in SPLITS.items()}
    membership = sum(mask.astype("int8") for mask in masks.values())
    if not membership.eq(1).all():
        raise RuntimeError("Every row must belong to exactly one temporal split")
    ids = {name: set(frame.loc[mask, "event_id"]) for name, mask in masks.items()}
    for left, left_ids in ids.items():
        for right, right_ids in ids.items():
            if left < right and left_ids & right_ids:
                raise RuntimeError(f"Event ID overlap between {left} and {right}")
    for name, mask in masks.items():
        if set(frame.loc[mask, TARGET].unique()) != set(LABEL_ORDER):
            raise RuntimeError(f"A class is missing from formal split {name}")
    expected = {"train": 10786, "validation": 804, "test": 948, "maturity_holdout": 1044}
    actual = {name: int(mask.sum()) for name, mask in masks.items()}
    if actual != expected:
        raise RuntimeError(f"Temporal split counts changed: {actual}")
    return masks


def version_columns(version: str) -> tuple[list[str], list[str], list[str]]:
    config = FEATURE_VERSIONS[version]
    categorical = list(config["categorical"])
    numeric = list(config["numeric"])
    features = categorical + numeric
    assert_safe_feature_list(features)
    return categorical, numeric, features


def select_feature_frame(engineered: pd.DataFrame, version: str) -> pd.DataFrame:
    _, _, features = version_columns(version)
    missing = sorted(set(features) - set(engineered.columns))
    if missing:
        raise RuntimeError(f"Allowlisted features are missing: {missing}")
    selected = engineered.loc[:, features].copy()
    if list(selected.columns) != features:
        raise RuntimeError("Feature column order changed")
    return selected


def make_preprocessor(version: str) -> ColumnTransformer:
    categorical, numeric, _ = version_columns(version)
    numeric_non_hdi = [field for field in numeric if field != "hdi"]
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    hdi_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    return ColumnTransformer(
        [
            ("categorical", categorical_pipeline, categorical),
            ("numeric", numeric_pipeline, numeric_non_hdi),
            ("hdi", hdi_pipeline, ["hdi"]),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def make_rf_pipeline(version: str, params: dict[str, Any]) -> Pipeline:
    return Pipeline([
        ("preprocessor", make_preprocessor(version)),
        ("model", RandomForestClassifier(**params, random_state=RANDOM_STATE, n_jobs=-1)),
    ])


def evaluate_model(model_id: str, family: str, version: str, split: str, pipeline, x, y, **extra):
    prediction = pipeline.predict(x)
    metrics, per_class, matrix = evaluate_predictions(y, prediction)
    row = metric_row(model_id, family, version, split, metrics, **extra)
    return row, per_class, matrix, prediction


def complexity_score(row: pd.Series) -> float:
    depth = 100 if pd.isna(row["max_depth"]) else float(row["max_depth"])
    return float(row["n_estimators"]) / 1000 + depth / 100 - float(row["min_samples_leaf"]) / 1000


def choose_candidate(comparison: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    rf = comparison[comparison["model_family"].eq("RandomForest")].copy()
    best_macro = float(rf["macro_f1"].max())
    rf["near_best_macro"] = rf["macro_f1"].ge(best_macro - NEAR_TIE_MACRO_F1)
    rf["complexity_score"] = rf.apply(complexity_score, axis=1)
    shortlist = rf[rf["near_best_macro"]].sort_values(
        ["extreme_recall", "high_recall", "macro_f1", "complexity_score", "model_id"],
        ascending=[False, False, False, True, True],
        kind="stable",
    )
    selected_id = str(shortlist.iloc[0]["model_id"])
    comparison = comparison.merge(rf[["model_id", "near_best_macro", "complexity_score"]], on="model_id", how="left")
    comparison["selected"] = comparison["model_id"].eq(selected_id)
    return comparison.loc[comparison["model_id"].eq(selected_id)].iloc[0], comparison


def unknown_category_report(reference: pd.DataFrame, evaluated: pd.DataFrame, version: str, split: str) -> tuple[pd.DataFrame, pd.Series]:
    categorical, _, _ = version_columns(version)
    rows = []
    any_unknown = pd.Series(False, index=evaluated.index)
    for field in categorical:
        known = set(reference[field].dropna().astype(str))
        unknown = ~evaluated[field].astype(str).isin(known)
        any_unknown |= unknown
        unseen_values = sorted(set(evaluated.loc[unknown, field].dropna().astype(str)))
        rows.append({
            "split": split,
            "field": field,
            "sample_count": len(evaluated),
            "unknown_sample_count": int(unknown.sum()),
            "unknown_sample_rate": float(unknown.mean()),
            "unknown_unique_count": len(unseen_values),
            "unknown_values": " | ".join(unseen_values),
        })
    return pd.DataFrame(rows), any_unknown


def prediction_frame(source: pd.DataFrame, prediction, probabilities: np.ndarray, unknown: pd.Series) -> pd.DataFrame:
    result = source[["event_id", "year", TARGET]].copy()
    result = result.rename(columns={TARGET: "true_label"})
    result["predicted_label"] = prediction
    for index, label in enumerate(LABEL_ORDER):
        # Parallel tree aggregation can differ at machine-epsilon scale across
        # runs. A fixed 12-decimal export preserves meaningful probabilities
        # while making prediction artifacts byte-stable for reproducibility QA.
        result[f"probability_{label.lower()}"] = np.round(probabilities[:, index], 12)
    result["hdi_missing"] = source["hdi"].isna().astype("int8")
    result["has_unknown_category"] = unknown.astype("int8")
    return result


def group_error_row(name: str, group: str, source: pd.DataFrame, prediction) -> dict[str, Any]:
    metrics, _, _ = evaluate_predictions(source[TARGET], prediction)
    errors = np.asarray(source[TARGET]) != np.asarray(prediction)
    return {
        "analysis_type": name,
        "group": group,
        "sample_count": len(source),
        "error_count": int(errors.sum()),
        "error_rate": float(errors.mean()),
        "balanced_accuracy": metrics["balanced_accuracy"],
        "macro_f1": metrics["macro_f1"],
        "details": "",
    }


def build_error_analysis(test_source: pd.DataFrame, prediction, unknown: pd.Series) -> pd.DataFrame:
    working = test_source.copy()
    working["predicted_label"] = prediction
    working["is_error"] = working[TARGET].ne(working["predicted_label"])
    working["hdi_missing_group"] = np.where(working["hdi"].isna(), "missing", "present")
    working["unknown_group"] = np.where(unknown, "unknown_category", "known_categories")
    rows: list[dict[str, Any]] = []
    for year, group in working.groupby("year", sort=True):
        rows.append(group_error_row("year_summary", str(int(year)), group, group["predicted_label"]))
    for field, analysis_type in (("disaster_type", "disaster_type_summary"), ("region", "region_summary"), ("hdi_missing_group", "hdi_missing_summary"), ("unknown_group", "unknown_category_summary")):
        for value, group in working.groupby(field, sort=True):
            rows.append(group_error_row(analysis_type, str(value), group, group["predicted_label"]))
    critical = {
        "High_to_Low_or_Moderate": int((working[TARGET].eq("High") & working["predicted_label"].isin(["Low", "Moderate"])).sum()),
        "Extreme_to_Low": int((working[TARGET].eq("Extreme") & working["predicted_label"].eq("Low")).sum()),
        "Extreme_to_Moderate": int((working[TARGET].eq("Extreme") & working["predicted_label"].eq("Moderate")).sum()),
        "Extreme_to_High": int((working[TARGET].eq("Extreme") & working["predicted_label"].eq("High")).sum()),
    }
    for key, count in critical.items():
        rows.append({"analysis_type": "critical_direction", "group": key, "sample_count": "", "error_count": count, "error_rate": "", "balanced_accuracy": "", "macro_f1": "", "details": ""})
    for row in working.loc[working["is_error"], ["event_id", "year", TARGET, "predicted_label", "disaster_type", "region", "hdi_missing_group", "unknown_group"]].itertuples(index=False):
        rows.append({
            "analysis_type": "misclassified_sample", "group": row.event_id, "sample_count": "", "error_count": 1,
            "error_rate": "", "balanced_accuracy": "", "macro_f1": "",
            "details": f"year={row.year}; true={getattr(row, TARGET)}; predicted={row.predicted_label}; type={row.disaster_type}; region={row.region}; hdi={row.hdi_missing_group}; categories={row.unknown_group}",
        })
    return pd.DataFrame(rows)


def raw_field_from_expanded(name: str, version: str) -> str:
    categorical, numeric, _ = version_columns(version)
    if name.startswith("categorical__"):
        remainder = name.removeprefix("categorical__")
        matches = [field for field in categorical if remainder.startswith(field + "_")]
        return max(matches, key=len) if matches else remainder
    if name.startswith("numeric__"):
        return name.removeprefix("numeric__")
    if name.startswith("hdi__"):
        return "hdi"
    return name


def feature_importance_tables(final_pipeline, validation_pipeline, x_validation, y_validation, version: str):
    expanded_names = final_pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    importances = final_pipeline.named_steps["model"].feature_importances_
    if len(expanded_names) != len(importances):
        raise RuntimeError("Expanded feature names and importance length mismatch")
    expanded = pd.DataFrame({"expanded_feature": expanded_names, "importance": importances})
    expanded["original_field"] = expanded["expanded_feature"].map(lambda name: raw_field_from_expanded(name, version))
    expanded = expanded.sort_values("importance", ascending=False, kind="stable").reset_index(drop=True)
    expanded["rank"] = np.arange(1, len(expanded) + 1)
    aggregated = expanded.groupby("original_field", as_index=False)["importance"].sum()
    permutation = permutation_importance(
        validation_pipeline, x_validation, y_validation, scoring="f1_macro", n_repeats=5,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    _, _, raw_features = version_columns(version)
    permutation_frame = pd.DataFrame({
        "original_field": raw_features,
        "validation_permutation_mean": permutation.importances_mean,
        "validation_permutation_std": permutation.importances_std,
    })
    aggregated = aggregated.merge(permutation_frame, on="original_field", how="left")
    return expanded, aggregated.sort_values("importance", ascending=False, kind="stable").reset_index(drop=True)


def markdown_metrics(metrics: dict[str, float]) -> str:
    return "\n".join(f"- {key}: {value:.4f}" for key, value in metrics.items())


def build_report(context: dict[str, Any]) -> str:
    selected = context["selected"]
    validation = context["validation_metrics"]
    test = context["test_metrics"]
    per_test = context["test_per_class"]
    class_lines = "\n".join(
        f"| {row['class']} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {int(row['support'])} |"
        for _, row in per_test.iterrows()
    )
    cm = context["test_matrix"]
    cm_lines = "\n".join(
        f"| {label} | " + " | ".join(str(int(value)) for value in cm.loc[f'true_{label}'].tolist()) + " |"
        for label in LABEL_ORDER
    )
    top = context["aggregated_importance"].head(10)
    top_lines = "\n".join(f"- {row.original_field}: {row.importance:.4f}" for row in top.itertuples())
    tie_note = context["tie_note"]
    return f"""# 灾害事件死亡影响等级预测：Dummy 与 Random Forest 基线报告

## 1. 任务与防泄漏

- 输入：`data/processed_hdro/disaster_model_ready.csv`。
- 目标：预测灾害事件最终死亡影响等级 `impact_level`，顺序固定为 Low、Moderate、High、Extreme。
- 时间划分：训练 2000-2019；验证 2020-2021；测试 2022-2023；2024-2026 成熟度留置区完全未进入模型流程。
- 所有模型特征严格来自白名单：{', '.join(context['features'])}。
- `total_deaths`、影响人数、损失、结束日期、目标及标识符均被程序化泄漏检查阻止。
- 所有预处理器在训练期拟合；最终配置锁定后，仅在 2000-2021 重新拟合一次，再对测试集评估一次。

## 2. 验证集模型选择

- 共比较 2 个 Dummy、18 个 Random Forest 候选；RF-V1 与 RF-V2 各 9 个。
- 主要指标为验证集 macro-F1，差异在 {NEAR_TIE_MACRO_F1:.3f} 内视为近似并列，再参考 Extreme Recall、High Recall 与模型复杂度。
- 最终选择：{selected['model_id']} / {selected['feature_version']}。
- 最终参数：`{json.dumps(context['final_params'], ensure_ascii=False, sort_keys=True)}`。
- {tie_note}

所选 RF 验证指标：
{markdown_metrics(validation)}

## 3. 最终测试结果

{markdown_metrics(test)}

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
{class_lines}

测试集混淆矩阵（行是真实类别，列是预测类别，顺序 Low/Moderate/High/Extreme）：

| True | Low | Moderate | High | Extreme |
|---|---:|---:|---:|---:|
{cm_lines}

## 4. 预处理与缺失

- 选择阶段训练期 HDI 中位数：{context['selection_hdi_median']:.6f}，仅由 2000-2019 训练集拟合。
- 最终重拟合期 HDI 中位数：{context['hdi_median']:.6f}，仅由 2000-2021 开发集拟合。
- HDI 缺失指示变量保留；没有按未来或邻近年份填充。
- OneHotEncoder 使用 `handle_unknown="ignore"`。验证集与测试集未知类别统计见 `unknown_category_report.csv`。
- 月份仅在原始日期精度为月或日时提取；年精度事件的 `event_month` 保持缺失，并使用 `month_missing`。

## 5. 错误分析

- High 被预测为 Low/Moderate：{context['critical']['High_to_Low_or_Moderate']}。
- Extreme -> Low：{context['critical']['Extreme_to_Low']}；Extreme -> Moderate：{context['critical']['Extreme_to_Moderate']}；Extreme -> High：{context['critical']['Extreme_to_High']}。
- HDI 缺失/非缺失、未知/已知类别、年份、灾害类型和地区差异见 `error_analysis.csv`。
- 测试结果仅用于最终评价和错误分析，没有返回修改参数。

## 6. 特征重要性

按原始字段聚合的前十项：
{top_lines}

- 展开后前 30 项见 `expanded_feature_importance.csv`；原字段聚合见 `aggregated_feature_importance.csv`。
- impurity importance 不是因果效应，高基数类别可能分散或放大重要性。
- permutation importance 仅在验证集计算，没有用测试重要性调参。

## 7. 可复现性与结论

- random_state={RANDOM_STATE}；预测、指标、特征顺序、最终参数的可复现签名见 `reproducibility_signature.json`。
- 模型是否优于 most-frequent Dummy（验证 macro-F1）：{'是' if validation['macro_f1'] > context['dummy_macro_f1'] else '否'}。
- 该结果适合作为论文中的 Random Forest 时间外推基线，但类别不平衡下 Extreme 样本仍少，不能过度解释一两个样本造成的召回变化。
- 本阶段没有运行 XGBoost、LightGBM、SMOTE 或深度学习。
"""


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data" / "processed_hdro" / "disaster_model_ready.csv")
    parser.add_argument("--output-root", type=Path, default=root / "ml_experiments" / "modeling")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    reports = output_root / "reports"
    predictions_dir = output_root / "predictions"
    artifacts = output_root / "artifacts"
    for directory in (reports, predictions_dir, artifacts):
        directory.mkdir(parents=True, exist_ok=True)

    input_hash_before = sha256_file(args.input)
    source = pd.read_csv(args.input, encoding="utf-8-sig", low_memory=False)
    engineered = engineer_features(source)
    masks = make_split_masks(engineered)
    split_frames = {name: engineered.loc[mask].copy() for name, mask in masks.items()}
    # Maturity holdout is checked for membership only and intentionally never transformed or predicted.
    train = split_frames["train"]
    validation = split_frames["validation"]
    test = split_frames["test"]
    development = pd.concat([train, validation], axis=0).sort_index()
    y_train, y_validation, y_test, y_development = train[TARGET], validation[TARGET], test[TARGET], development[TARGET]

    comparison_rows: list[dict[str, Any]] = []
    validation_per_class_rows: list[pd.DataFrame] = []
    for strategy in ("most_frequent", "prior"):
        model_id = f"Dummy_{strategy}"
        dummy = DummyClassifier(strategy=strategy, random_state=RANDOM_STATE)
        dummy.fit(np.zeros((len(train), 1)), y_train)
        prediction = dummy.predict(np.zeros((len(validation), 1)))
        metrics, per_class, _ = evaluate_predictions(y_validation, prediction)
        comparison_rows.append(metric_row(model_id, "Dummy", "none", "validation", metrics, strategy=strategy))
        per_class.insert(0, "split", "validation")
        per_class.insert(0, "model_id", model_id)
        validation_per_class_rows.append(per_class)

    for version in FEATURE_VERSIONS:
        x_train = select_feature_frame(train, version)
        x_validation = select_feature_frame(validation, version)
        for index, params in enumerate(RF_CANDIDATES, start=1):
            model_id = f"{version}_C{index:02d}"
            pipeline = make_rf_pipeline(version, params)
            pipeline.fit(x_train, y_train)
            row, per_class, _, _ = evaluate_model(
                model_id, "RandomForest", version, "validation", pipeline, x_validation, y_validation,
                n_estimators=params["n_estimators"], max_depth=params["max_depth"],
                min_samples_leaf=params["min_samples_leaf"], max_features=params["max_features"],
                class_weight=params["class_weight"],
            )
            row["high_recall"] = float(per_class.loc[per_class["class"].eq("High"), "recall"].iloc[0])
            row["extreme_recall"] = float(per_class.loc[per_class["class"].eq("Extreme"), "recall"].iloc[0])
            comparison_rows.append(row)

    comparison = pd.DataFrame(comparison_rows)
    selected, comparison = choose_candidate(comparison)
    selected_version = str(selected["feature_version"])
    selected_params = {
        "n_estimators": int(selected["n_estimators"]),
        "max_depth": None if pd.isna(selected["max_depth"]) else int(selected["max_depth"]),
        "min_samples_leaf": int(selected["min_samples_leaf"]),
        "max_features": float(selected["max_features"]) if str(selected["max_features"]) == "0.5" else str(selected["max_features"]),
        "class_weight": None if pd.isna(selected["class_weight"]) else str(selected["class_weight"]),
    }
    selected_id = str(selected["model_id"])

    x_train = select_feature_frame(train, selected_version)
    x_validation = select_feature_frame(validation, selected_version)
    validation_pipeline = make_rf_pipeline(selected_version, selected_params)
    validation_pipeline.fit(x_train, y_train)
    train_row, train_per_class, _, _ = evaluate_model(selected_id, "RandomForest", selected_version, "train", validation_pipeline, x_train, y_train)
    validation_row, selected_validation_per_class, validation_matrix, validation_prediction = evaluate_model(
        selected_id, "RandomForest", selected_version, "validation", validation_pipeline, x_validation, y_validation
    )
    validation_probabilities = ordered_probabilities(validation_pipeline, x_validation)
    unknown_validation_report, unknown_validation = unknown_category_report(train, validation, selected_version, "validation")
    validation_predictions = prediction_frame(validation, validation_prediction, validation_probabilities, unknown_validation)

    x_development = select_feature_frame(development, selected_version)
    x_test = select_feature_frame(test, selected_version)
    final_pipeline = make_rf_pipeline(selected_version, selected_params)
    final_pipeline.fit(x_development, y_development)
    development_row, development_per_class, _, _ = evaluate_model(selected_id, "RandomForest", selected_version, "development_train", final_pipeline, x_development, y_development)
    test_row, test_per_class, test_matrix, test_prediction = evaluate_model(
        selected_id, "RandomForest", selected_version, "test", final_pipeline, x_test, y_test
    )
    test_probabilities = ordered_probabilities(final_pipeline, x_test)
    unknown_test_report, unknown_test = unknown_category_report(development, test, selected_version, "test")
    test_predictions = prediction_frame(test, test_prediction, test_probabilities, unknown_test)

    expanded_importance, aggregated_importance = feature_importance_tables(
        final_pipeline, validation_pipeline, x_validation, y_validation, selected_version
    )
    error_analysis = build_error_analysis(test, test_prediction, unknown_test)

    validation_metrics = pd.concat([
        comparison.drop(columns=[column for column in ("near_best_macro", "complexity_score", "selected") if column in comparison]),
        pd.DataFrame([train_row]),
    ], ignore_index=True, sort=False)
    test_metrics = pd.DataFrame([development_row, test_row])
    per_class_frames = validation_per_class_rows
    for model_id, split, frame in (
        (selected_id, "train", train_per_class),
        (selected_id, "validation", selected_validation_per_class),
        (selected_id, "development_train", development_per_class),
        (selected_id, "test", test_per_class),
    ):
        item = frame.copy()
        item.insert(0, "split", split)
        item.insert(0, "model_id", model_id)
        per_class_frames.append(item)
    per_class_metrics = pd.concat(per_class_frames, ignore_index=True)
    unknown_report = pd.concat([unknown_validation_report, unknown_test_report], ignore_index=True)

    comparison = comparison.sort_values(["model_family", "macro_f1", "model_id"], ascending=[True, False, True], kind="stable")
    comparison.to_csv(reports / "model_comparison.csv", index=False, encoding="utf-8-sig")
    validation_metrics.to_csv(reports / "validation_metrics.csv", index=False, encoding="utf-8-sig")
    test_metrics.to_csv(reports / "test_metrics.csv", index=False, encoding="utf-8-sig")
    per_class_metrics.to_csv(reports / "per_class_metrics.csv", index=False, encoding="utf-8-sig")
    unknown_report.to_csv(reports / "unknown_category_report.csv", index=False, encoding="utf-8-sig")
    error_analysis.to_csv(reports / "error_analysis.csv", index=False, encoding="utf-8-sig")
    aggregated_importance.to_csv(reports / "aggregated_feature_importance.csv", index=False, encoding="utf-8-sig")
    expanded_importance.head(30).to_csv(reports / "expanded_feature_importance.csv", index=False, encoding="utf-8-sig")
    validation_matrix.to_csv(reports / "confusion_matrix_validation.csv", encoding="utf-8-sig")
    test_matrix.to_csv(reports / "confusion_matrix_test.csv", encoding="utf-8-sig")
    validation_predictions.to_csv(predictions_dir / "validation_predictions.csv", index=False, encoding="utf-8-sig")
    test_predictions.to_csv(predictions_dir / "test_predictions.csv", index=False, encoding="utf-8-sig")

    model_path = artifacts / "final_random_forest_pipeline.joblib"
    joblib.dump(final_pipeline, model_path, compress=3)
    model_hash = sha256_file(model_path)
    selection_hdi_median = float(validation_pipeline.named_steps["preprocessor"].named_transformers_["hdi"].named_steps["imputer"].statistics_[0])
    hdi_median = float(final_pipeline.named_steps["preprocessor"].named_transformers_["hdi"].named_steps["imputer"].statistics_[0])
    expanded_feature_order = final_pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    final_features = version_columns(selected_version)[2]
    metadata = {
        "task": "灾害事件死亡影响等级预测",
        "input_data_path": str(args.input.resolve()),
        "input_data_sha256": input_hash_before,
        "training_time_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "library_versions": {"scikit_learn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__, "joblib": joblib.__version__},
        "temporal_split": {name: {"start_year": years[0], "end_year": years[1], "sample_count": len(split_frames[name])} for name, years in SPLITS.items()},
        "feature_version": selected_version,
        "feature_allowlist": final_features,
        "expanded_feature_order": expanded_feature_order,
        "excluded_fields": EXCLUDED_FIELDS,
        "label_order": LABEL_ORDER,
        "selection_train_hdi_fill_value": selection_hdi_median,
        "final_development_hdi_fill_value": hdi_median,
        "final_model_params": {**selected_params, "random_state": RANDOM_STATE, "n_jobs": -1},
        "random_state": RANDOM_STATE,
        "final_test_metrics": {key: float(value) for key, value in test_row.items() if key in {"accuracy", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"}},
        "model_file_sha256": model_hash,
        "candidate_count": {"Dummy": 2, "RandomForest": 18},
        "selection_rule": f"validation macro-F1; within {NEAR_TIE_MACRO_F1} compare Extreme recall, High recall, then simplicity",
        "maturity_holdout_evaluated": False,
    }
    write_json(artifacts / "model_metadata.json", metadata)

    key_artifacts = [
        reports / "model_comparison.csv", reports / "validation_metrics.csv", reports / "test_metrics.csv",
        reports / "per_class_metrics.csv", reports / "confusion_matrix_validation.csv", reports / "confusion_matrix_test.csv",
        predictions_dir / "validation_predictions.csv", predictions_dir / "test_predictions.csv",
    ]
    signature = {
        "split_counts": {name: len(split_frames[name]) for name in SPLITS},
        "selected_model_id": selected_id,
        "selected_params": selected_params,
        "raw_feature_order": final_features,
        "expanded_feature_order_sha256": json_sha256(expanded_feature_order),
        "artifact_sha256": {str(path.relative_to(output_root)): sha256_file(path) for path in key_artifacts},
    }
    signature_path = artifacts / "reproducibility_signature.json"
    previous_signature = json.loads(signature_path.read_text(encoding="utf-8")) if signature_path.exists() else None
    write_json(signature_path, signature)
    differences = {}
    if previous_signature is not None:
        for key in sorted(set(previous_signature) | set(signature)):
            if previous_signature.get(key) != signature.get(key):
                differences[key] = {"previous": previous_signature.get(key), "current": signature.get(key)}
    write_json(artifacts / "reproducibility_check.json", {
        "previous_run_available": previous_signature is not None,
        "predictions_metrics_features_params_identical": previous_signature == signature if previous_signature is not None else None,
        "differences": differences,
    })

    rf_validation = comparison[comparison["model_family"].eq("RandomForest")].sort_values("macro_f1", ascending=False)
    top_two = rf_validation.head(2)
    macro_gap = float(top_two.iloc[0]["macro_f1"] - top_two.iloc[1]["macro_f1"]) if len(top_two) > 1 else 0.0
    extreme_gap = float(abs(top_two.iloc[0]["extreme_recall"] - top_two.iloc[1]["extreme_recall"])) if len(top_two) > 1 else 0.0
    tie_note = (
        f"前两名验证 macro-F1 差 {macro_gap:.4f}，Extreme recall 差 {extreme_gap:.4f}；"
        "验证集 Extreme 仅 7 条，少量样本即可明显改变召回率，这种差异可能是小样本波动，不应解释为配置存在稳定实质优势。"
        if macro_gap <= 0.01 else f"前两名验证 macro-F1 差 {macro_gap:.4f}；仍需避免把单次时间窗口差异解释为普遍优势。"
    )
    critical_rows = error_analysis[error_analysis["analysis_type"].eq("critical_direction")]
    critical = dict(zip(critical_rows["group"], critical_rows["error_count"].astype(int)))
    context = {
        "selected": selected, "features": final_features, "final_params": selected_params,
        "validation_metrics": {key: float(validation_row[key]) for key in ("accuracy", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1")},
        "test_metrics": {key: float(test_row[key]) for key in ("accuracy", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1")},
        "test_per_class": test_per_class, "test_matrix": test_matrix,
        "selection_hdi_median": selection_hdi_median, "hdi_median": hdi_median,
        "critical": critical, "aggregated_importance": aggregated_importance, "tie_note": tie_note,
        "dummy_macro_f1": float(comparison.loc[comparison["model_id"].eq("Dummy_most_frequent"), "macro_f1"].iloc[0]),
    }
    (reports / "baseline_model_report.md").write_text(build_report(context), encoding="utf-8")

    if sha256_file(args.input) != input_hash_before:
        raise RuntimeError("Input data changed during training")


if __name__ == "__main__":
    main()
