"""Train/validation-only three-class T0-T3 Random Forest increment experiment."""
from __future__ import annotations

import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, cohen_kappa_score, confusion_matrix,
    f1_score, precision_recall_fscore_support, precision_score, recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ARTIFACTS, REPORTS, PREDICTIONS, LOGS = HERE / "artifacts", HERE / "reports", HERE / "predictions", HERE / "logs"
INPUT = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
MAGNITUDE_INPUT = ROOT / "data/emdat_raw.xlsx"
WB_INPUT = ROOT / "ml_experiments/data_preparation/world_bank/event_indicator_matches.csv"
RF_METADATA = ROOT / "ml_experiments/modeling/artifacts/model_metadata.json"
LABELS = ["Low", "Moderate", "Severe"]
RANDOM_STATE = 20260803
BASE_CATEGORICAL = ["country_code", "region", "disaster_type", "disaster_subtype", "date_granularity"]
BASE_NUMERIC = ["year", "date_imputed", "historical_frequency", "hdi", "hdi_missing", "event_month", "month_missing"]
WB_FEATURES = ["population_log", "gdp_per_capita_ppp_log", "population_missing", "gdp_per_capita_missing"]
MAG_FEATURES = ["magnitude_robust_z", "magnitude_missing", "magnitude_group_unknown"]
FEATURES = {
    "T0": BASE_CATEGORICAL + BASE_NUMERIC,
    "T1": BASE_CATEGORICAL + BASE_NUMERIC + WB_FEATURES,
    "T2": BASE_CATEGORICAL + BASE_NUMERIC + MAG_FEATURES,
    "T3": BASE_CATEGORICAL + BASE_NUMERIC + WB_FEATURES + MAG_FEATURES,
}
RF_PARAMS = {"n_estimators": 500, "max_depth": 10, "min_samples_leaf": 5, "max_features": .5,
             "class_weight": "balanced_subsample", "random_state": RANDOM_STATE, "n_jobs": -1}
FORBIDDEN = {"event_id", "total_deaths", "impact_level", "total_affected", "total_damage", "end_date",
             "duration", "date_anomaly", "hdi_match_status", "hdi_source", "hdi_source_year", "hdi_imputed",
             "event_date_upper", "time_batch", "magnitude", "magnitude_scale", "matched_year", "backtrack_years",
             "match_status", "reference_year", "value"}
APPROVED_TYPE_GROUPS = {("Drought", "Km2"), ("Flood", "Km2"), ("Wildfire", "Km2"),
                        ("Storm", "Kph"), ("Earthquake", "Moment Magnitude")}
APPROVED_SUBTYPE_GROUPS = {("Cold wave", "°C"), ("Heat wave", "°C"), ("Severe winter conditions", "°C")}
MIN_MAGNITUDE_N = 20


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    paths: list[Path] = []
    for relative in ["data/raw", "data/processed", "data/processed_hdro", "ml_experiments/modeling",
                     "ml_experiments/data_preparation/world_bank", "ml_experiments/data_preparation/magnitude_audit"]:
        base = ROOT / relative
        if not base.exists(): continue
        for path in base.rglob("*"):
            if not path.is_file(): continue
            try: rel = path.relative_to(HERE)
            except ValueError: rel = None
            if rel is None:
                paths.append(path)
    prep = ROOT / "ml_experiments/data_preparation"
    paths.extend(path for path in prep.glob("*") if path.is_file())
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in sorted(set(paths))}


def label_from_deaths(series: pd.Series) -> pd.Series:
    labels = pd.Series(pd.NA, index=series.index, dtype="string")
    labels.loc[series.between(0, 9, inclusive="both")] = "Low"
    labels.loc[series.between(10, 99, inclusive="both")] = "Moderate"
    labels.loc[series.ge(100)] = "Severe"
    return labels


def split_name(year: int) -> str:
    if 2000 <= year <= 2019: return "train"
    if 2020 <= year <= 2021: return "validation"
    if 2022 <= year <= 2023: return "test_label_audit_only"
    if 2024 <= year <= 2026: return "maturity_label_audit_only"
    return "outside"


def assert_safe_features(features: list[str]) -> None:
    overlap = set(features) & FORBIDDEN
    suspicious = [name for name in features if any(token in name.lower() for token in ("death", "affected", "damage", "casualt"))]
    if overlap or suspicious or len(features) != len(set(features)):
        raise RuntimeError(f"Feature leakage guard failed: overlap={sorted(overlap)}, suspicious={suspicious}")


def engineer_base(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    out["hdi_missing"] = out.hdi.isna().astype("int8")
    parsed = pd.to_datetime(out.event_date, errors="coerce")
    month_available = out.date_granularity.isin(["day", "month"])
    out["event_month"] = parsed.dt.month.where(month_available)
    out["month_missing"] = out.event_month.isna().astype("int8")
    out["date_imputed"] = out.date_imputed.astype("int8")
    return out


def load_world_bank(all_event_ids: set[str], development_ids: set[str]) -> pd.DataFrame:
    wb = pd.read_csv(WB_INPUT)
    required = {"event_id", "indicator_code", "value", "matched_year", "backtrack_years", "match_status"}
    if not required.issubset(wb.columns): raise RuntimeError(f"World Bank fields missing: {sorted(required-set(wb.columns))}")
    if wb.duplicated(["event_id", "indicator_code"]).any(): raise RuntimeError("Duplicate World Bank event + indicator key")
    if set(wb.event_id.astype(str)) != all_event_ids: raise RuntimeError("World Bank event IDs do not match frozen event IDs")
    counts = wb.groupby("event_id").indicator_code.nunique()
    if not counts.eq(2).all(): raise RuntimeError("World Bank file is not exactly two indicators per event")
    value = pd.to_numeric(wb.value, errors="coerce")
    invalid = wb.value.notna() & value.isna()
    if invalid.any() or value.dropna().lt(0).any(): raise RuntimeError("World Bank value is nonnumeric or negative")
    wb = wb.loc[wb.event_id.astype(str).isin(development_ids), ["event_id", "indicator_code", "value"]].copy()
    pivot = wb.pivot(index="event_id", columns="indicator_code", values="value")
    expected = {"SP.POP.TOTL", "NY.GDP.PCAP.PP.KD"}
    if set(pivot.columns) != expected: raise RuntimeError(f"Unexpected World Bank indicators: {list(pivot.columns)}")
    out = pd.DataFrame(index=pivot.index)
    out["population_log"] = np.log1p(pivot["SP.POP.TOTL"])
    out["gdp_per_capita_ppp_log"] = np.log1p(pivot["NY.GDP.PCAP.PP.KD"])
    out["population_missing"] = pivot["SP.POP.TOTL"].isna().astype("int8")
    out["gdp_per_capita_missing"] = pivot["NY.GDP.PCAP.PP.KD"].isna().astype("int8")
    return out.reset_index()


def magnitude_group_id(row: pd.Series) -> tuple[str | None, str | None, str | None]:
    scale = row.magnitude_scale
    if (row.raw_disaster_type, scale) in APPROVED_TYPE_GROUPS:
        return "disaster_type+magnitude_scale", row.raw_disaster_type, f"{row.raw_disaster_type} | {scale}"
    if (row.raw_disaster_subtype, scale) in APPROVED_SUBTYPE_GROUPS:
        return "disaster_subtype+magnitude_scale", row.raw_disaster_subtype, f"{row.raw_disaster_subtype} | {scale}"
    return None, None, None


def load_and_fit_magnitude(train_ids: set[str], development_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(MAGNITUDE_INPUT, sheet_name="EM-DAT Data", dtype=object, keep_default_na=False,
                        usecols=["DisNo.", "Disaster Type", "Disaster Subtype", "Magnitude", "Magnitude Scale"])
    raw.columns = ["event_id", "raw_disaster_type", "raw_disaster_subtype", "magnitude_raw", "magnitude_scale"]
    if raw.event_id.eq("").any() or raw.event_id.duplicated().any(): raise RuntimeError("Magnitude event_id is blank or duplicated")
    raw["event_id"] = raw.event_id.astype(str)
    raw = raw[raw.event_id.isin(development_ids)].copy()
    magnitude_text = raw.magnitude_raw.astype(str).str.strip()
    magnitude = pd.to_numeric(raw.magnitude_raw.where(~magnitude_text.eq("")), errors="coerce")
    if ((~magnitude_text.eq("")) & magnitude.isna()).any(): raise RuntimeError("Magnitude has nonnumeric nonblank values")
    raw["magnitude"] = magnitude
    raw["magnitude_scale"] = raw.magnitude_scale.astype(str).str.strip().replace("", pd.NA)
    groups = raw.apply(magnitude_group_id, axis=1, result_type="expand")
    groups.columns = ["grouping_strategy", "semantic_group", "group_key"]
    raw = pd.concat([raw, groups], axis=1)
    train_raw = raw[raw.event_id.isin(train_ids)].copy()
    rows = []
    for (strategy, group_key), group in train_raw.dropna(subset=["group_key"]).groupby(["grouping_strategy", "group_key"]):
        values = group.magnitude.dropna().astype(float)
        q1, median, q3 = values.quantile([.25, .5, .75]) if len(values) else (np.nan, np.nan, np.nan)
        iqr = q3 - q1 if len(values) else np.nan
        eligible = len(values) >= MIN_MAGNITUDE_N and pd.notna(iqr) and iqr > 0
        rows.append({"grouping_strategy": strategy, "group_key": group_key, "training_nonmissing": len(values),
                     "training_q1": q1, "training_median": median, "training_q3": q3, "training_iqr": iqr,
                     "eligible": eligible, "minimum_required": MIN_MAGNITUDE_N})
    vocab = pd.DataFrame(rows).sort_values(["grouping_strategy", "group_key"])
    eligible = vocab[vocab.eligible].set_index("group_key")
    raw["magnitude_missing"] = raw.magnitude.isna().astype("int8")
    raw["magnitude_group_unknown"] = (~raw.group_key.isin(eligible.index)).astype("int8")
    raw["magnitude_robust_z"] = np.nan
    for key, stats in eligible.iterrows():
        mask = raw.group_key.eq(key) & raw.magnitude.notna()
        raw.loc[mask, "magnitude_robust_z"] = ((raw.loc[mask, "magnitude"] - stats.training_median) / stats.training_iqr).clip(-5, 5)
    return raw[["event_id", *MAG_FEATURES]], vocab


def make_pipeline(features: list[str]) -> Pipeline:
    categorical = [name for name in features if name in BASE_CATEGORICAL]
    numeric = [name for name in features if name not in categorical]
    preprocessor = ColumnTransformer([
        ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                                  ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True))]), categorical),
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric),
    ], remainder="drop", verbose_feature_names_out=True)
    return Pipeline([("preprocessor", preprocessor), ("model", RandomForestClassifier(**RF_PARAMS))])


def scalar_metrics(y: pd.Series, pred: np.ndarray) -> dict[str, Any]:
    return {
        "accuracy": accuracy_score(y, pred), "balanced_accuracy": balanced_accuracy_score(y, pred),
        "macro_precision": precision_score(y, pred, average="macro", labels=LABELS, zero_division=0),
        "macro_recall": recall_score(y, pred, average="macro", labels=LABELS, zero_division=0),
        "macro_f1": f1_score(y, pred, average="macro", labels=LABELS, zero_division=0),
        "weighted_f1": f1_score(y, pred, average="weighted", labels=LABELS, zero_division=0),
        "quadratic_weighted_kappa": cohen_kappa_score(y, pred, labels=LABELS, weights="quadratic"),
        "severe_to_low": int(((y.to_numpy() == "Severe") & (pred == "Low")).sum()),
        "low_to_severe": int(((y.to_numpy() == "Low") & (pred == "Severe")).sum()),
    }


def per_class(y: pd.Series, pred: np.ndarray, experiment: str, split: str) -> pd.DataFrame:
    precision, recall, f1, support = precision_recall_fscore_support(y, pred, labels=LABELS, zero_division=0)
    return pd.DataFrame([{"experiment_id": experiment, "split": split, "class": label,
                          "precision": precision[i], "recall": recall[i], "f1": f1[i], "support": int(support[i])}
                         for i, label in enumerate(LABELS)])


def ordered_probabilities(pipeline: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    probabilities = pipeline.predict_proba(frame)
    classes = pipeline.named_steps["model"].classes_.tolist()
    if set(classes) != set(LABELS): raise RuntimeError(f"Model class order/contents changed: {classes}")
    return probabilities[:, [classes.index(label) for label in LABELS]]


def main() -> None:
    started = utc_now(); t0 = time.perf_counter()
    for directory in (ARTIFACTS, REPORTS, PREDICTIONS, LOGS): directory.mkdir(parents=True, exist_ok=True)
    signature_path = ARTIFACTS / "reproducibility_signature.json"
    previous_signature = json.loads(signature_path.read_text(encoding="utf-8")) if signature_path.exists() else None
    reference_predictions_path = ARTIFACTS / "reproducibility_reference_validation_predictions.csv"
    reference_predictions = pd.read_csv(reference_predictions_path) if reference_predictions_path.exists() else None
    before = protected_hashes()
    input_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
                    for path in [INPUT, MAGNITUDE_INPUT, WB_INPUT, RF_METADATA]}
    frozen_meta = json.loads(RF_METADATA.read_text(encoding="utf-8"))
    if frozen_meta.get("feature_version") != "RF-V2" or frozen_meta.get("final_model_params") != RF_PARAMS:
        raise RuntimeError("Frozen Random Forest configuration cannot be reproduced exactly")
    if frozen_meta.get("feature_allowlist") != FEATURES["T0"]:
        raise RuntimeError("Frozen RF-V2 base feature allowlist changed")
    for features in FEATURES.values(): assert_safe_features(features)

    # Full-period access is limited to event IDs, year, and deaths for label integrity.
    label_source = pd.read_csv(INPUT, usecols=["event_id", "year", "total_deaths"])
    if label_source.event_id.isna().any() or label_source.event_id.duplicated().any(): raise RuntimeError("event_id is null or duplicated")
    if label_source.total_deaths.dropna().lt(0).any(): raise RuntimeError("total_deaths contains negative values")
    label_source["three_class_label"] = label_from_deaths(label_source.total_deaths)
    label_source["split"] = label_source.year.map(split_name)
    split_order = ["train", "validation", "test_label_audit_only", "maturity_label_audit_only"]
    distribution_rows = []
    for split in split_order:
        frame = label_source[label_source.split.eq(split)]
        for label in LABELS:
            distribution_rows.append({"split": split, "class": label, "all_events": len(frame),
                                      "labeled_events": int(frame.three_class_label.notna().sum()),
                                      "missing_label_events": int(frame.three_class_label.isna().sum()),
                                      "class_count": int(frame.three_class_label.eq(label).sum()),
                                      "class_rate_among_labeled": float(frame.three_class_label.eq(label).sum() / frame.three_class_label.notna().sum())})
    distribution = pd.DataFrame(distribution_rows)
    distribution.to_csv(REPORTS / "label_distribution.csv", index=False)
    expected_labeled = {"train": 10786, "validation": 804, "test_label_audit_only": 948, "maturity_label_audit_only": 1044}
    actual_labeled = {split: int(label_source.loc[label_source.split.eq(split), "three_class_label"].notna().sum()) for split in split_order}
    if actual_labeled != expected_labeled: raise RuntimeError(f"Label counts changed: {actual_labeled}")

    # Only train and validation rows proceed into feature construction. Chunk
    # filtering occurs before engineering, so later-period features are not retained.
    required_feature_columns = sorted(set(["event_id", "year", "total_deaths", "event_date", *FEATURES["T0"]]) - {"hdi_missing", "event_month", "month_missing"})
    development_chunks = []
    for chunk in pd.read_csv(INPUT, usecols=required_feature_columns, chunksize=4000, low_memory=False):
        keep = chunk.year.between(2000, 2021) & chunk.total_deaths.notna()
        development_chunks.append(chunk.loc[keep].copy())
    development = engineer_base(pd.concat(development_chunks, ignore_index=True))
    development["three_class_label"] = label_from_deaths(development.total_deaths)
    development["split"] = development.year.map(split_name)
    train = development[development.split.eq("train")].copy(); validation = development[development.split.eq("validation")].copy()
    if set(train.event_id) & set(validation.event_id): raise RuntimeError("Train/validation event overlap")
    all_ids = set(label_source.event_id.astype(str)); development_ids = set(development.event_id.astype(str)); train_ids = set(train.event_id.astype(str))
    wb_features = load_world_bank(all_ids, development_ids)
    magnitude_features, magnitude_vocab = load_and_fit_magnitude(train_ids, development_ids)
    if not set(magnitude_vocab.loc[magnitude_vocab.eligible, "group_key"]).issubset({f"{a} | {b}" for a,b in APPROVED_TYPE_GROUPS | APPROVED_SUBTYPE_GROUPS}):
        raise RuntimeError("Magnitude fitted an unapproved semantic group")
    magnitude_vocab.to_csv(ARTIFACTS / "magnitude_training_groups.csv", index=False)
    magnitude_vocab_hash = sha256(ARTIFACTS / "magnitude_training_groups.csv")
    development = development.merge(wb_features, on="event_id", how="left", validate="one_to_one")
    development = development.merge(magnitude_features, on="event_id", how="left", validate="one_to_one")
    if len(development) != len(train) + len(validation): raise RuntimeError("Incremental feature merge changed row count")
    train = development[development.split.eq("train")].copy(); validation = development[development.split.eq("validation")].copy()
    y_train, y_validation = train.three_class_label.astype(str), validation.three_class_label.astype(str)
    incremental_coverage_rows = []
    for split, frame in [("train", train), ("validation", validation)]:
        incremental_coverage_rows.append({
            "split": split, "records": len(frame),
            "population_missing": int(frame.population_missing.sum()),
            "population_available": int((~frame.population_log.isna()).sum()),
            "gdp_per_capita_missing": int(frame.gdp_per_capita_missing.sum()),
            "gdp_per_capita_available": int((~frame.gdp_per_capita_ppp_log.isna()).sum()),
            "magnitude_missing": int(frame.magnitude_missing.sum()),
            "magnitude_group_unknown": int(frame.magnitude_group_unknown.sum()),
            "magnitude_robust_z_available": int(frame.magnitude_robust_z.notna().sum()),
        })
    pd.DataFrame(incremental_coverage_rows).to_csv(REPORTS / "incremental_feature_coverage.csv", index=False)

    feature_rows, metric_rows, class_rows, prediction_frames, category_vocabularies, imputer_rows = [], [], [], [], {}, []
    log_lines = [f"{started} start", f"input hashes: {json.dumps(input_hashes, sort_keys=True)}",
                 f"labeled split counts: {actual_labeled}", "Test and maturity features are not constructed or transformed."]
    for experiment, features in FEATURES.items():
        x_train, x_validation = train[features].copy(), validation[features].copy()
        if list(x_train.columns) != features or list(x_validation.columns) != features: raise RuntimeError("Feature order changed")
        pipeline = make_pipeline(features)
        fit_start = time.perf_counter(); pipeline.fit(x_train, y_train); fit_seconds = time.perf_counter() - fit_start
        train_pred = pipeline.predict(x_train); val_pred = pipeline.predict(x_validation)
        val_proba = ordered_probabilities(pipeline, x_validation)
        for split, y, pred in [("train", y_train, train_pred), ("validation", y_validation, val_pred)]:
            row = {"experiment_id": experiment, "split": split, "fit_seconds": fit_seconds, **scalar_metrics(y, pred)}
            severe = per_class(y, pred, experiment, split)
            severe_row = severe[severe["class"].eq("Severe")].iloc[0]
            row.update(severe_precision=severe_row.precision, severe_recall=severe_row.recall, severe_f1=severe_row.f1)
            metric_rows.append(row); class_rows.append(severe)
            matrix = pd.DataFrame(confusion_matrix(y, pred, labels=LABELS), index=LABELS, columns=LABELS)
            matrix.index.name, matrix.columns.name = "true_label", "predicted_label"
            matrix.to_csv(REPORTS / f"confusion_matrix_{experiment}_{split}.csv")
        pred_frame = validation[["event_id", "year"]].copy().reset_index(drop=True)
        pred_frame["true_label"] = y_validation.to_numpy(); pred_frame["predicted_label"] = val_pred
        for index, label in enumerate(LABELS): pred_frame[f"probability_{label.lower()}"] = val_proba[:, index]
        pred_frame["experiment_id"] = experiment
        pred_frame.to_csv(PREDICTIONS / f"validation_predictions_{experiment}.csv", index=False)
        prediction_frames.append(pred_frame)
        feature_rows.extend({"experiment_id": experiment, "feature_order": index + 1, "feature": feature,
                             "feature_role": "categorical" if feature in BASE_CATEGORICAL else "numeric"}
                            for index, feature in enumerate(features))
        pre = pipeline.named_steps["preprocessor"]
        onehot = pre.named_transformers_["categorical"].named_steps["onehot"]
        category_vocabularies[experiment] = {column: [str(value) for value in values]
                                             for column, values in zip(BASE_CATEGORICAL, onehot.categories_)}
        numeric_columns = [name for name in features if name not in BASE_CATEGORICAL]
        stats = pre.named_transformers_["numeric"].named_steps["imputer"].statistics_
        imputer_rows.extend({"experiment_id": experiment, "feature": name, "training_median": float(value)}
                            for name, value in zip(numeric_columns, stats))
        joblib.dump(pipeline, ARTIFACTS / f"{experiment}_random_forest_pipeline.joblib")
        reloaded = joblib.load(ARTIFACTS / f"{experiment}_random_forest_pipeline.joblib")
        if not np.array_equal(val_pred, reloaded.predict(x_validation)):
            raise RuntimeError(f"Reloaded {experiment} validation predictions differ")
        log_lines.append(f"{utc_now()} {experiment} fit={fit_seconds:.3f}s validation_macro_f1={metric_rows[-1]['macro_f1']:.6f}")

    metrics = pd.DataFrame(metric_rows); per_class_table = pd.concat(class_rows, ignore_index=True)
    metrics.to_csv(REPORTS / "metrics.csv", index=False); per_class_table.to_csv(REPORTS / "per_class_metrics.csv", index=False)
    pd.DataFrame(feature_rows).to_csv(REPORTS / "feature_manifest.csv", index=False)
    pd.DataFrame(imputer_rows).to_csv(ARTIFACTS / "training_numeric_imputer_statistics.csv", index=False)
    write_json(ARTIFACTS / "training_category_vocabularies.json", category_vocabularies)
    all_predictions = pd.concat(prediction_frames, ignore_index=True)
    all_predictions.to_csv(PREDICTIONS / "validation_predictions_all.csv", index=False)

    wide = all_predictions.pivot(index=["event_id", "year", "true_label"], columns="experiment_id", values="predicted_label").reset_index()
    wide["any_prediction_changed"] = wide[["T0","T1","T2","T3"]].nunique(axis=1).gt(1)
    for experiment in ["T1","T2","T3"]: wide[f"{experiment}_changed_from_T0"] = wide[experiment].ne(wide.T0)
    changed = wide[wide.any_prediction_changed].copy()
    changed.to_csv(PREDICTIONS / "validation_prediction_changes.csv", index=False)

    validation_metrics = metrics[metrics.split.eq("validation")].set_index("experiment_id")
    comparisons = [("T1_vs_T0","T1","T0","World Bank contribution"), ("T2_vs_T0","T2","T0","Magnitude contribution"),
                   ("T3_vs_T0","T3","T0","All enhancements contribution"),
                   ("T3_vs_T1","T3","T1","Magnitude incremental to World Bank"),
                   ("T3_vs_T2","T3","T2","World Bank incremental to Magnitude")]
    contribution_rows = []
    delta_fields = ["accuracy","balanced_accuracy","macro_f1","weighted_f1","severe_precision","severe_recall","severe_f1","quadratic_weighted_kappa"]
    for comparison_id, enhanced, baseline, interpretation in comparisons:
        row = {"comparison": comparison_id, "enhanced": enhanced, "baseline": baseline, "interpretation": interpretation}
        row.update({f"delta_{field}": float(validation_metrics.loc[enhanced,field] - validation_metrics.loc[baseline,field]) for field in delta_fields})
        row["delta_severe_to_low"] = int(validation_metrics.loc[enhanced,"severe_to_low"] - validation_metrics.loc[baseline,"severe_to_low"])
        row["delta_low_to_severe"] = int(validation_metrics.loc[enhanced,"low_to_severe"] - validation_metrics.loc[baseline,"low_to_severe"])
        contribution_rows.append(row)
    contributions = pd.DataFrame(contribution_rows)
    contributions.to_csv(REPORTS / "incremental_contribution.csv", index=False)

    complexity = {"T0":0,"T1":1,"T2":1,"T3":2}
    ranking = validation_metrics.reset_index().copy(); ranking["complexity_rank"] = ranking.experiment_id.map(complexity)
    selected = ranking.sort_values(["macro_f1","severe_recall","severe_f1","balanced_accuracy","severe_to_low","complexity_rank"],
                                   ascending=[False,False,False,False,True,True], kind="stable").iloc[0]
    selected_id = str(selected.experiment_id)
    config = {
        "created_at_utc": started, "stage": "train_validation_only", "test_predictions_generated": False,
        "maturity_used": False, "label_order": LABELS, "label_rule": {"Low":"0-9","Moderate":"10-99","Severe":">=100"},
        "time_split": {"train":"2000-2019","validation":"2020-2021","test":"2022-2023 label distribution audit only",
                       "maturity_holdout":"2024-2026 label distribution audit only"},
        "features": FEATURES, "rf_params": RF_PARAMS, "frozen_rf_differences": ["label order changed to Low/Moderate/Severe; class weights are recalculated internally by balanced_subsample for three classes"],
        "selection_rule": "validation macro-F1; then Severe recall, Severe F1, balanced accuracy, Severe->Low count, complexity",
        "recommended_feature_version": selected_id, "magnitude_training_groups_sha256": magnitude_vocab_hash,
        "world_bank_transform": "frozen event match values; log1p; no match metadata as features",
        "magnitude_transform": "training-only semantic group median/IQR, min n=20, IQR>0, clip [-5,5]",
    }
    write_json(ARTIFACTS / "experiment_config.json", config)

    report_rows = validation_metrics.reset_index()[["experiment_id","accuracy","balanced_accuracy","macro_f1","weighted_f1",
                                                     "severe_precision","severe_recall","severe_f1","severe_to_low","low_to_severe",
                                                     "quadratic_weighted_kappa"]]
    label_lines = []
    for split in split_order:
        rows = distribution[distribution.split.eq(split)].set_index("class")
        label_lines.append(f"- {split}: labeled {int(rows.labeled_events.iloc[0]):,}; Low {int(rows.loc['Low','class_count']):,}, Moderate {int(rows.loc['Moderate','class_count']):,}, Severe {int(rows.loc['Severe','class_count']):,}; missing label {int(rows.missing_label_events.iloc[0]):,}.")
    metric_lines = [f"- {r.experiment_id}: accuracy {r.accuracy:.4f}, balanced accuracy {r.balanced_accuracy:.4f}, macro-F1 {r.macro_f1:.4f}, weighted-F1 {r.weighted_f1:.4f}, Severe P/R/F1 {r.severe_precision:.4f}/{r.severe_recall:.4f}/{r.severe_f1:.4f}, Severe->Low {int(r.severe_to_low)}, QWK {r.quadratic_weighted_kappa:.4f}." for r in report_rows.itertuples(index=False)]
    report = f"""# Three-class Random Forest T0-T3 train/validation report

## Integrity and scope

- Task labels are fixed from `total_deaths`: Low 0-9, Moderate 10-99, Severe >=100.
- Event IDs are unique. Train and validation do not overlap.
- Models are fitted on 2000-2019 only and evaluated on 2020-2021 only.
- 2022-2023 and 2024-2026 were used solely for label-count integrity; no feature frame, transform, prediction, probability, metric, or confusion matrix was produced for either set.
- The frozen four-class RF parameters are reused exactly. Only label names/class cardinality and internally derived `balanced_subsample` weights necessarily differ.

## Label distribution

{chr(10).join(label_lines)}

## Feature versions

- T0: frozen RF-V2 no-leakage base features.
- T1: T0 + lagged World Bank population/GDP log features and missing indicators.
- T2: T0 + training-only semantic-group Magnitude robust z and missing/unknown indicators.
- T3: T0 + both approved increments.

World Bank match years, backtrack fields and status text are audit metadata only and never enter a model. Raw Magnitude never enters a model. `magnitude_robust_z` is only a within-semantic-group relative position and must not be interpreted uniformly as “larger means more severe”.

## Validation results

{chr(10).join(metric_lines)}

The fixed selection hierarchy recommends **{selected_id}** for configuration lock. This is a validation-only feature decision; no final Train+Validation refit or Test prediction has been performed.

## Reproducibility

Each pipeline, feature order, category vocabulary, numeric imputer statistics, Magnitude training vocabulary/statistics, validation prediction and confusion matrix is saved independently. Reloaded pipelines reproduce validation class predictions exactly. `manifest.json` records SHA-256 values. Frozen data, RF, LightGBM, World Bank and Magnitude-audit artifacts were hash-checked before and after and were unchanged.
"""
    (REPORTS / "three_class_t0_t3_report.md").write_text(report, encoding="utf-8")
    log_lines.append(f"{utc_now()} selected_validation_feature_version={selected_id}")
    (LOGS / "experiment.log").write_text("\n".join(log_lines)+"\n", encoding="utf-8")

    metric_signature_columns = [column for column in metrics.columns if column != "fit_seconds"]
    class_signature_text = all_predictions[["experiment_id","event_id","year","true_label","predicted_label"]].to_csv(index=False)
    signature = {
        "signature_version": 2,
        "validation_class_prediction_sha256": hashlib.sha256(class_signature_text.encode("utf-8")).hexdigest(),
        "metrics": metrics[metric_signature_columns].to_dict("records"),
        "feature_manifest_sha256": sha256(REPORTS / "feature_manifest.csv"),
        "category_vocabularies_sha256": sha256(ARTIFACTS / "training_category_vocabularies.json"),
        "magnitude_training_groups_sha256": magnitude_vocab_hash,
        "recommended_feature_version": selected_id,
    }
    reproducible = None
    max_probability_difference = None
    if reference_predictions is not None and previous_signature is not None and previous_signature.get("signature_version") == 2:
        key_columns = ["experiment_id","event_id","year","true_label","predicted_label"]
        probability_columns = [f"probability_{label.lower()}" for label in LABELS]
        old = reference_predictions.sort_values(["experiment_id","event_id"]).reset_index(drop=True)
        new = all_predictions.sort_values(["experiment_id","event_id"]).reset_index(drop=True)
        classes_identical = old[key_columns].equals(new[key_columns])
        max_probability_difference = float(np.max(np.abs(old[probability_columns].to_numpy(float) - new[probability_columns].to_numpy(float))))
        static_hashes_identical = all(previous_signature.get(key) == signature.get(key) for key in
                                      ["validation_class_prediction_sha256","feature_manifest_sha256",
                                       "category_vocabularies_sha256","magnitude_training_groups_sha256",
                                       "recommended_feature_version"])
        previous_metrics = pd.DataFrame(previous_signature["metrics"])[metric_signature_columns]
        current_metrics = metrics[metric_signature_columns]
        text_columns = ["experiment_id","split"]
        numeric_columns = [column for column in metric_signature_columns if column not in text_columns]
        metrics_identical = (previous_metrics[text_columns].equals(current_metrics[text_columns]) and
                             np.allclose(previous_metrics[numeric_columns].to_numpy(float), current_metrics[numeric_columns].to_numpy(float), rtol=0, atol=1e-15))
        reproducible = classes_identical and metrics_identical and static_hashes_identical and max_probability_difference <= 1e-12
        if not reproducible:
            raise RuntimeError(f"Consecutive-run reproducibility failed: classes={classes_identical}, metrics={metrics_identical}, static={static_hashes_identical}, max_probability_diff={max_probability_difference}")
    else:
        all_predictions.to_csv(reference_predictions_path, index=False)
    write_json(signature_path, signature)
    write_json(ARTIFACTS / "reproducibility_check.json", {
        "previous_run_available": reference_predictions is not None and previous_signature is not None and previous_signature.get("signature_version") == 2,
        "predictions_metrics_features_vocabularies_identical": reproducible,
        "predicted_classes_identical": reproducible if reproducible is not None else None,
        "metric_tolerance": 1e-15,
        "probability_tolerance": 1e-12,
        "max_probability_absolute_difference": max_probability_difference,
    })

    after = protected_hashes()
    if before != after or any(sha256(ROOT / path) != digest for path,digest in input_hashes.items()):
        raise RuntimeError("A frozen input or artifact changed")
    output_files = sorted(path for path in HERE.rglob("*") if path.is_file() and path.name != "manifest.json" and "__pycache__" not in path.parts)
    manifest = {
        "created_at_utc": utc_now(), "input_sha256": input_hashes, "script_sha256": sha256(Path(__file__)),
        "python": platform.python_version(), "libraries": {"pandas":pd.__version__,"numpy":np.__version__,"scikit_learn":sklearn.__version__,"joblib":joblib.__version__},
        "frozen_files_checked": len(before), "recommended_feature_version": selected_id,
        "test_prediction_files": [], "test_metrics_computed": False, "maturity_features_constructed": False,
        "runtime_seconds": time.perf_counter()-t0,
        "files": [{"path":str(path.relative_to(ROOT)).replace("\\","/"),"sha256":sha256(path),"bytes":path.stat().st_size} for path in output_files],
    }
    write_json(HERE / "manifest.json", manifest)
    for path in list(REPORTS.glob("*.csv")) + list(PREDICTIONS.glob("*.csv")) + list(ARTIFACTS.glob("*.csv")):
        pd.read_csv(path)
    print(json.dumps({"label_counts": actual_labeled, "recommended": selected_id,
                      "validation": report_rows.set_index("experiment_id").to_dict("index"),
                      "validation_prediction_changes": len(changed), "test_predictions_generated": False}, indent=2))


if __name__ == "__main__":
    main()
