"""Auditable LightGBM temporal baseline for disaster death-impact classes."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix,
    f1_score, precision_recall_fscore_support, precision_score, recall_score,
)

from lightgbm_pipeline import LightGBMNativePipeline, TrainOnlyCategoryMapper

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
INPUT = ROOT / "data/processed_hdro/disaster_model_ready.csv"
RF_ROOT = HERE.parent
ARTIFACTS, REPORTS, PREDICTIONS = HERE / "artifacts", HERE / "reports", HERE / "predictions"
LABELS = ["Low", "Moderate", "High", "Extreme"]
LABEL_TO_INT = {label: index for index, label in enumerate(LABELS)}
RANDOM_STATE = 20260803
CAT = ["country_code", "region", "disaster_type", "disaster_subtype", "date_granularity"]
V1 = CAT + ["year", "date_imputed", "historical_frequency", "hdi", "hdi_missing"]
V2 = V1 + ["event_month", "month_missing"]
FEATURES = {"LGBM-V1": V1, "LGBM-V2": V2}
FORBIDDEN = {
    "impact_level", "total_deaths", "total_affected", "total_damage", "end_date", "duration",
    "date_anomaly", "hdi_match_status", "hdi_source", "hdi_source_year", "hdi_imputed",
    "event_date_upper", "time_batch", "event_id", "casualties", "country", "hdi_country_name",
}
PROFILES = {
    "P1_conservative": dict(learning_rate=.05, n_estimators=500, num_leaves=15, max_depth=8,
                            min_child_samples=80, subsample=1.0, colsample_bytree=.7,
                            reg_alpha=.1, reg_lambda=5),
    "P2_medium": dict(learning_rate=.05, n_estimators=500, num_leaves=31, max_depth=12,
                      min_child_samples=40, subsample=.8, colsample_bytree=1.0,
                      reg_alpha=0, reg_lambda=1),
    "P3_low_rate": dict(learning_rate=.03, n_estimators=800, num_leaves=63, max_depth=-1,
                        min_child_samples=20, subsample=.8, colsample_bytree=.7,
                        reg_alpha=.1, reg_lambda=5),
}
RF_FILES = [
    RF_ROOT / "artifacts/final_random_forest_pipeline.joblib",
    RF_ROOT / "artifacts/model_metadata.json",
    RF_ROOT / "predictions/validation_predictions.csv",
    RF_ROOT / "predictions/test_predictions.csv",
    RF_ROOT / "reports/baseline_model_report.md",
    RF_ROOT / "reports/model_comparison.csv",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def engineer(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()
    parsed = pd.to_datetime(data["event_date"], errors="coerce")
    granular = data["date_granularity"].astype("string").str.lower()
    month_known = granular.isin(["month", "day"])
    data["event_month"] = parsed.dt.month.where(month_known)
    data["month_missing"] = data["event_month"].isna().astype("int8")
    data["hdi_missing"] = data["hdi"].isna().astype("int8")
    data["date_imputed"] = data["date_imputed"].astype("int8")
    return data


def ensure_no_leakage(features: list[str]) -> None:
    overlap = set(features) & FORBIDDEN
    suspicious = [c for c in features if any(t in c.lower() for t in ("death", "affected", "damage", "casualt"))]
    if overlap or suspicious or len(features) != len(set(features)):
        raise RuntimeError(f"Leakage/feature-list violation: overlap={sorted(overlap)}, suspicious={suspicious}")


def class_weights(y: pd.Series, strategy: str) -> tuple[dict[int, float], np.ndarray]:
    counts = y.value_counts().reindex(range(4), fill_value=0)
    if (counts == 0).any():
        raise RuntimeError(f"A training class is absent: {counts.to_dict()}")
    balanced = len(y) / (4 * counts.astype(float))
    if strategy == "none": values = pd.Series(1.0, index=counts.index)
    elif strategy == "balanced": values = balanced
    elif strategy == "mild_sqrt":
        values = np.sqrt(balanced)
        values = values / values.min()
    else: raise ValueError(strategy)
    mapping = {int(k): float(v) for k, v in values.items()}
    return mapping, y.map(mapping).to_numpy(float)


def scalar_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y, pred),
        "balanced_accuracy": balanced_accuracy_score(y, pred),
        "macro_precision": precision_score(y, pred, average="macro", zero_division=0),
        "macro_recall": recall_score(y, pred, average="macro", zero_division=0),
        "macro_f1": f1_score(y, pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(y, pred, average="weighted", zero_division=0),
    }


def detailed_metrics(y: np.ndarray, pred: np.ndarray, split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(4), zero_division=0)
    rows = [{"split": split, "class": LABELS[i], "precision": p[i], "recall": r[i], "f1": f[i], "support": int(s[i])} for i in range(4)]
    cm = pd.DataFrame(confusion_matrix(y, pred, labels=range(4)), index=LABELS, columns=LABELS)
    cm.index.name, cm.columns.name = "true_label", "predicted_label"
    return pd.DataFrame(rows), cm


def model_params(profile: dict[str, Any], estimators: int | None = None) -> dict[str, Any]:
    params = dict(profile)
    if estimators is not None: params["n_estimators"] = int(estimators)
    params.update(objective="multiclass", num_class=4, random_state=RANDOM_STATE, n_jobs=-1,
                  verbosity=-1, deterministic=True, force_col_wise=True,
                  subsample_freq=1 if params["subsample"] < 1 else 0)
    return params


def prediction_frame(base: pd.DataFrame, y: np.ndarray, pred: np.ndarray, proba: np.ndarray,
                     unknown: pd.Series) -> pd.DataFrame:
    out = base[["event_id", "year", "disaster_type", "region", "hdi_missing"]].copy().reset_index(drop=True)
    out["true_label"] = [LABELS[i] for i in y]
    out["predicted_label"] = [LABELS[i] for i in pred]
    for i, label in enumerate(LABELS): out[f"probability_{label.lower()}"] = proba[:, i]
    out["has_unknown_category"] = unknown.to_numpy(bool)
    return out


def error_rows(pred: pd.DataFrame) -> pd.DataFrame:
    work = pred.copy()
    work["is_error"] = work.true_label.ne(work.predicted_label)
    work["severe_underestimate"] = ((work.true_label == "High") & work.predicted_label.isin(["Low", "Moderate"])) | ((work.true_label == "Extreme") & work.predicted_label.isin(["Low", "Moderate"]))
    rows = []
    for field in ["year", "disaster_type", "region", "hdi_missing", "has_unknown_category"]:
        for value, group in work.groupby(field, dropna=False):
            rows.append({"group_field": field, "group_value": value, "n": len(group), "errors": int(group.is_error.sum()),
                         "error_rate": group.is_error.mean(), "severe_underestimates": int(group.severe_underestimate.sum())})
    return pd.DataFrame(rows)


def main() -> None:
    start = time.perf_counter()
    for directory in (ARTIFACTS, REPORTS, PREDICTIONS): directory.mkdir(parents=True, exist_ok=True)
    protected_before = {str(p.relative_to(ROOT)): sha256(p) for p in RF_FILES}
    input_hash = sha256(INPUT)
    data = engineer(pd.read_csv(INPUT))
    if data.event_id.isna().any() or data.event_id.duplicated().any(): raise RuntimeError("event_id is null or non-unique")
    if set(data.impact_level.dropna().unique()) != set(LABELS): raise RuntimeError("Unexpected label set")
    for f in FEATURES.values(): ensure_no_leakage(f)

    split_masks = {
        "train": data.year.between(2000, 2019), "validation": data.year.between(2020, 2021),
        "test": data.year.between(2022, 2023), "maturity_holdout": data.year.between(2024, 2026),
    }
    expected = {"train": 10786, "validation": 804, "test": 948, "maturity_holdout": 1044}
    counts = {k: int(v.sum()) for k, v in split_masks.items()}
    if counts != expected: raise RuntimeError(f"Temporal split changed: {counts}")
    membership = sum(mask.astype(int) for mask in split_masks.values())
    relevant = data.year.between(2000, 2026)
    if not (membership[relevant] == 1).all(): raise RuntimeError("Temporal sets overlap or omit eligible rows")
    id_sets = {k: set(data.loc[m, "event_id"]) for k, m in split_masks.items()}
    if any(id_sets[a] & id_sets[b] for i, a in enumerate(id_sets) for b in list(id_sets)[i+1:]): raise RuntimeError("event_id overlap")

    train = data.loc[split_masks["train"]].copy(); val = data.loc[split_masks["validation"]].copy()
    y_train = train.impact_level.map(LABEL_TO_INT).astype(int); y_val = val.impact_level.map(LABEL_TO_INT).astype(int)
    candidate_rows, validation_payloads, unknown_rows = [], {}, []
    print(f"Validated split counts: {counts}; running {len(FEATURES)*len(PROFILES)*3} candidates")
    for feature_version, feature_list in FEATURES.items():
        mapper = TrainOnlyCategoryMapper(CAT, feature_list).fit(train[feature_list])
        xt, xv = mapper.transform(train), mapper.transform(val)
        unknown_rows.extend(mapper.unknown_report(val, "validation"))
        for profile_id, profile in PROFILES.items():
            for weight_strategy in ("none", "balanced", "mild_sqrt"):
                candidate_id = f"{feature_version}_{profile_id}_{weight_strategy}"
                weights, sample_weight = class_weights(y_train, weight_strategy)
                model = lgb.LGBMClassifier(**model_params(profile))
                t0 = time.perf_counter()
                model.fit(xt, y_train, sample_weight=sample_weight, categorical_feature=CAT,
                          eval_set=[(xv, y_val)], eval_metric="multi_logloss",
                          callbacks=[lgb.early_stopping(50, verbose=False)])
                elapsed = time.perf_counter() - t0
                pred = model.predict(xv).astype(int); proba = model.predict_proba(xv)
                metrics = scalar_metrics(y_val.to_numpy(), pred)
                per, _ = detailed_metrics(y_val.to_numpy(), pred, "validation")
                by_class = {f"{row['class'].lower()}_{metric}": row[metric] for _, row in per.iterrows() for metric in ("precision", "recall", "f1")}
                row = {"feature_version": feature_version, "candidate_id": candidate_id,
                       "profile": profile_id, "parameters": json.dumps(profile, sort_keys=True),
                       "weight_strategy": weight_strategy, "actual_class_weights": json.dumps({LABELS[k]: v for k,v in weights.items()}, sort_keys=True),
                       "best_iteration": int(model.best_iteration_), "training_seconds": elapsed, **metrics, **by_class}
                candidate_rows.append(row)
                validation_payloads[candidate_id] = (mapper, model, pred, proba, per)
                print(f"{candidate_id}: macro_f1={metrics['macro_f1']:.4f}, extreme_recall={by_class['extreme_recall']:.4f}, best_iter={model.best_iteration_}")

    candidates = pd.DataFrame(candidate_rows)
    max_macro = candidates.macro_f1.max()
    shortlist = candidates[candidates.macro_f1 >= max_macro - .01].copy()
    complexity = {"P1_conservative": 0, "P2_medium": 1, "P3_low_rate": 2}
    shortlist["complexity_rank"] = shortlist.profile.map(complexity)
    selected = shortlist.sort_values(["extreme_recall", "high_recall", "balanced_accuracy", "complexity_rank", "macro_f1"], ascending=[False, False, False, True, False]).iloc[0]
    selected_id = str(selected.candidate_id)
    selected_profile = PROFILES[str(selected.profile)]
    selected_best_iteration = int(selected.best_iteration)
    lock = {
        "locked_at_utc": datetime.now(timezone.utc).isoformat(), "selection_used_test": False,
        "selection_rule": "max validation macro-F1; within 0.01 prefer Extreme recall, then High recall, balanced accuracy, lower complexity",
        "candidate_id": selected_id, "feature_version": selected.feature_version, "profile": selected.profile,
        "weight_strategy": selected.weight_strategy, "validation_metrics": scalar_metrics(y_val.to_numpy(), validation_payloads[selected_id][2]),
        "best_iteration": selected_best_iteration, "final_n_estimators_rule": "selected validation best_iteration",
        "base_parameters": selected_profile,
    }
    candidates.to_csv(REPORTS / "lightgbm_candidate_comparison.csv", index=False)
    write_json(ARTIFACTS / "selected_lightgbm_config.json", lock)
    # From this point onward the locked configuration is immutable and test evaluation may occur once.
    test_evaluation_started = datetime.now(timezone.utc).isoformat()

    feature_list = FEATURES[str(selected.feature_version)]
    dev = pd.concat([train, val], axis=0).sort_index(); test = data.loc[split_masks["test"]].copy()
    y_dev = dev.impact_level.map(LABEL_TO_INT).astype(int); y_test = test.impact_level.map(LABEL_TO_INT).astype(int)
    if set(y_test.unique()) != set(range(4)): raise RuntimeError("A formal test class is absent")
    final_mapper = TrainOnlyCategoryMapper(CAT, feature_list).fit(dev[feature_list])
    xdev, xtest = final_mapper.transform(dev), final_mapper.transform(test)
    final_weights, final_sample_weight = class_weights(y_dev, str(selected.weight_strategy))
    final_model = lgb.LGBMClassifier(**model_params(selected_profile, selected_best_iteration))
    final_fit_start = time.perf_counter(); final_model.fit(xdev, y_dev, sample_weight=final_sample_weight, categorical_feature=CAT)
    final_fit_seconds = time.perf_counter() - final_fit_start
    infer_start = time.perf_counter(); test_pred = final_model.predict(xtest).astype(int); test_proba = final_model.predict_proba(xtest)
    test_inference_seconds = time.perf_counter() - infer_start
    pipeline = LightGBMNativePipeline(final_mapper, final_model, LABELS)
    joblib.dump(pipeline, ARTIFACTS / "final_lightgbm_pipeline.joblib")

    # Validation output is from the selected train-only candidate; test output is final dev-refit model.
    val_mapper, _, val_pred, val_proba, val_per = validation_payloads[selected_id]
    val_unknown = val_mapper.unknown_mask(val[feature_list]); test_unknown = final_mapper.unknown_mask(test[feature_list])
    val_out = prediction_frame(val, y_val.to_numpy(), val_pred, val_proba, val_unknown)
    test_out = prediction_frame(test, y_test.to_numpy(), test_pred, test_proba, test_unknown)
    val_out.to_csv(PREDICTIONS / "validation_predictions.csv", index=False); test_out.to_csv(PREDICTIONS / "test_predictions.csv", index=False)
    val_metrics = scalar_metrics(y_val.to_numpy(), val_pred); test_metrics = scalar_metrics(y_test.to_numpy(), test_pred)
    pd.DataFrame([{"split":"validation", **val_metrics}]).to_csv(REPORTS / "validation_metrics.csv", index=False)
    pd.DataFrame([{"split":"test", **test_metrics}]).to_csv(REPORTS / "test_metrics.csv", index=False)
    test_per, test_cm = detailed_metrics(y_test.to_numpy(), test_pred, "test")
    pd.concat([val_per, test_per]).to_csv(REPORTS / "per_class_metrics.csv", index=False)
    _, val_cm = detailed_metrics(y_val.to_numpy(), val_pred, "validation")
    val_cm.to_csv(REPORTS / "confusion_matrix_validation.csv"); test_cm.to_csv(REPORTS / "confusion_matrix_test.csv")
    unknown_rows.extend(final_mapper.unknown_report(test, "test"))
    pd.DataFrame(unknown_rows).drop_duplicates(["split","field"], keep="last").to_csv(REPORTS / "unknown_category_report.csv", index=False)
    error_rows(test_out).to_csv(REPORTS / "error_analysis.csv", index=False)

    names = final_model.booster_.feature_name(); gain = final_model.booster_.feature_importance("gain"); split = final_model.booster_.feature_importance("split")
    gain_df = pd.DataFrame({"feature": names, "gain": gain, "gain_normalized": gain / gain.sum()}).sort_values("gain", ascending=False)
    split_df = pd.DataFrame({"feature": names, "split": split, "split_normalized": split / split.sum()}).sort_values("split", ascending=False)
    gain_df.to_csv(REPORTS / "feature_importance_gain.csv", index=False); split_df.to_csv(REPORTS / "feature_importance_split.csv", index=False)

    # RF comparison only after locked LightGBM test evaluation.
    rf_test = pd.read_csv(RF_ROOT / "predictions/test_predictions.csv")
    disagreement = test_out[["event_id","year","true_label","predicted_label"]].rename(columns={"predicted_label":"lightgbm_prediction"}).merge(
        rf_test[["event_id","predicted_label"]].rename(columns={"predicted_label":"rf_prediction"}), on="event_id", validate="one_to_one")
    disagreement["rf_correct"] = disagreement.rf_prediction.eq(disagreement.true_label)
    disagreement["lightgbm_correct"] = disagreement.lightgbm_prediction.eq(disagreement.true_label)
    disagreement["outcome"] = np.select([
        disagreement.rf_correct & disagreement.lightgbm_correct, disagreement.rf_correct & ~disagreement.lightgbm_correct,
        ~disagreement.rf_correct & disagreement.lightgbm_correct], ["both_correct", "rf_only_correct", "lightgbm_only_correct"], default="both_wrong")
    disagreement.to_csv(REPORTS / "rf_lightgbm_disagreement.csv", index=False)
    rf_ref = {"validation": {"accuracy":.6853,"balanced_accuracy":.5389,"macro_f1":.4825,"weighted_f1":.6903},
              "test": {"accuracy":.6487,"balanced_accuracy":.5890,"macro_f1":.5244,"weighted_f1":.6605}}
    comparison = []
    for split, lgb_metrics in [("validation", val_metrics), ("test", test_metrics)]:
        for model_name, metrics in [("RandomForest",rf_ref[split]),("LightGBM",lgb_metrics)]: comparison.append({"split":split,"model":model_name,**metrics})
    pd.DataFrame(comparison).to_csv(REPORTS / "rf_lightgbm_comparison.csv", index=False)

    # Reload reproducibility: no refit and no reselection.
    loaded = joblib.load(ARTIFACTS / "final_lightgbm_pipeline.joblib")
    reload_pred = loaded.predict_indices(test[feature_list]); reload_proba = loaded.predict_proba(test[feature_list])
    repro = {"predicted_classes_identical": bool(np.array_equal(test_pred, reload_pred)),
             "max_probability_absolute_difference": float(np.max(np.abs(test_proba-reload_proba))),
             "metrics_identical": scalar_metrics(y_test.to_numpy(), reload_pred) == test_metrics,
             "tolerance": 1e-12}
    if not repro["predicted_classes_identical"] or not repro["metrics_identical"] or repro["max_probability_absolute_difference"] > 1e-12:
        raise RuntimeError(f"Reload reproducibility failed: {repro}")
    write_json(ARTIFACTS / "reload_reproducibility.json", repro)

    model_path = ARTIFACTS / "final_lightgbm_pipeline.joblib"
    protected_after = {str(p.relative_to(ROOT)): sha256(p) for p in RF_FILES}
    if protected_before != protected_after or sha256(INPUT) != input_hash: raise RuntimeError("Frozen RF artifact or formal input changed")
    metadata = {
        "input_path": str(INPUT.relative_to(ROOT)), "input_sha256": input_hash,
        "script_sha256": sha256(Path(__file__)), "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_first_evaluation_utc": test_evaluation_started,
        "versions": {"python":platform.python_version(),"lightgbm":lgb.__version__,"scikit_learn":sklearn.__version__,"pandas":pd.__version__,"numpy":np.__version__},
        "time_split": {"train":"2000-2019","validation":"2020-2021","test":"2022-2023","maturity_holdout":"2024-2026 excluded"},
        "split_counts": counts, "feature_whitelist": feature_list, "all_feature_versions": FEATURES,
        "excluded_fields": sorted(FORBIDDEN), "label_order": LABELS,
        "category_mapping": "sorted training/development categories; explicit __MISSING__ and __UNKNOWN__; validation/test never expand vocabulary",
        "category_vocabularies": final_mapper.categories_, "hdi_missing_handling":"hdi remains NaN for native LightGBM handling; hdi_missing retained",
        "class_weight_method": selected.weight_strategy, "final_actual_class_weights": {LABELS[k]:v for k,v in final_weights.items()},
        "candidate_profiles": PROFILES, "candidate_count":len(candidates), "selected_config":lock,
        "final_parameters": final_model.get_params(), "best_iteration":selected_best_iteration,"random_state":RANDOM_STATE,
        "validation_metrics":val_metrics,"test_metrics":test_metrics,"final_fit_seconds":final_fit_seconds,
        "test_inference_seconds":test_inference_seconds,"model_sha256":sha256(model_path),"model_size_bytes":model_path.stat().st_size,
        "reload_reproducibility":repro,"frozen_rf_hashes_before_after":protected_before,
        "total_runtime_seconds":time.perf_counter()-start,
    }
    write_json(ARTIFACTS / "lightgbm_model_metadata.json", metadata)
    report = f"""# LightGBM model report\n\n## Scope and safeguards\n\nThis experiment predicts disaster-event death impact level using only occurrence-time or prior information. The fixed label order is {', '.join(LABELS)}. No outcome, death, affected-population, damage, end-date, identifier, or HDI provenance/status field entered the feature matrix. The maturity holdout (2024-2026) was excluded. The selected configuration was locked before the test set was evaluated.\n\nLightGBM {lgb.__version__} used native categorical features with vocabularies learned from training data only. Missing categories map to `__MISSING__`, unseen categories to `__UNKNOWN__`. HDI remains NaN and is handled natively; `hdi_missing` is retained. This differs from the frozen Random Forest training-median imputation but uses the same information horizon.\n\n## Candidate selection\n\nEighteen predefined candidates were evaluated: two feature versions, three parameter profiles, and three training-only class-weight strategies. Selection used validation macro-F1, with differences below 0.01 treated as practically close and tie-breaking by Extreme recall, High recall, balanced accuracy, then lower complexity. Small Extreme-class changes may reflect one or two observations and are not proof of substantive superiority.\n\nSelected: **{selected_id}**, best iteration **{selected_best_iteration}**.\n\n## Performance\n\n| Split | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 |\n|---|---:|---:|---:|---:|\n| Validation | {val_metrics['accuracy']:.4f} | {val_metrics['balanced_accuracy']:.4f} | {val_metrics['macro_f1']:.4f} | {val_metrics['weighted_f1']:.4f} |\n| Test | {test_metrics['accuracy']:.4f} | {test_metrics['balanced_accuracy']:.4f} | {test_metrics['macro_f1']:.4f} | {test_metrics['weighted_f1']:.4f} |\n\nThe test set was evaluated once after configuration lock; its results were not used to revise parameters. Feature importance is predictive, not causal. Gain measures loss reduction while split importance counts uses in trees; high-cardinality categories have more split opportunities, and native categorical importance is not directly comparable to RF one-hot column importance.\n\n## Reproducibility\n\nReloaded-model class predictions and metrics are identical; maximum probability difference is {repro['max_probability_absolute_difference']:.3g}. Frozen RF artifacts and the formal input retained their pre-run SHA-256 hashes.\n"""
    (REPORTS / "lightgbm_model_report.md").write_text(report, encoding="utf-8")
    from finalize_lightgbm_reports import finalize_reports
    finalize_reports(HERE)
    # Ensure every generated CSV is parseable.
    for path in list(REPORTS.glob("*.csv")) + list(PREDICTIONS.glob("*.csv")): pd.read_csv(path)
    print(json.dumps({"selected":selected_id,"best_iteration":selected_best_iteration,"validation":val_metrics,"test":test_metrics,"reproducibility":repro}, indent=2))


if __name__ == "__main__": main()
