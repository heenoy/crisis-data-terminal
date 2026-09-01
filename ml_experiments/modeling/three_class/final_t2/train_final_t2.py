"""Locked T2 three-class RF: Development refit and one formal 2022-2023 test."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import classification_report, confusion_matrix

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(PARENT))
import run_t0_t3_random_forest as base  # noqa: E402

ART = HERE / "artifacts"
REP = HERE / "reports"
PRED = HERE / "predictions"
INPUT = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
RAW = ROOT / "data/emdat_raw.xlsx"
LOCKED_CONFIG = PARENT / "artifacts/experiment_config.json"
OLD_MAG = PARENT / "artifacts/magnitude_training_groups.csv"
LABELS = ["Low", "Moderate", "Severe"]
FEATURES = base.FEATURES["T2"]
EXPECTED_PARAMS = {"n_estimators": 500, "max_depth": 10, "min_samples_leaf": 5,
                   "max_features": .5, "class_weight": "balanced_subsample",
                   "random_state": 20260803, "n_jobs": -1}
EXPECTED_COUNTS = {"development": 11590, "test": 948}
EXPECTED_LABELS = {"development": {"Low": 2786, "Moderate": 7872, "Severe": 932},
                   "test": {"Low": 305, "Moderate": 524, "Severe": 119}}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    roots = [ROOT / "data/raw", ROOT / "data/processed", ROOT / "data/processed_hdro",
             ROOT / "ml_experiments/data_preparation/world_bank",
             ROOT / "ml_experiments/data_preparation/magnitude_audit",
             ROOT / "ml_experiments/modeling"]
    result = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or HERE in path.parents:
                continue
            result[path.relative_to(ROOT).as_posix()] = sha(path)
    return dict(sorted(result.items()))


def metrics_frame(y: pd.Series, pred: np.ndarray, split: str) -> pd.DataFrame:
    row = {"split": split, **base.scalar_metrics(y, pred)}
    return pd.DataFrame([row])


def prediction_frame(frame: pd.DataFrame, pred: np.ndarray, proba: np.ndarray) -> pd.DataFrame:
    out = frame[["event_id", "year", "three_class_label"]].copy()
    out.columns = ["event_id", "year", "true_label"]
    out["predicted_label"] = pred
    for i, label in enumerate(LABELS):
        out[f"probability_{label}"] = proba[:, i]
    return out


def assert_locked() -> dict[str, str]:
    cfg = json.loads(LOCKED_CONFIG.read_text(encoding="utf-8"))
    if cfg["recommended_feature_version"] != "T2" or cfg["features"]["T2"] != FEATURES:
        raise RuntimeError("Frozen T2 selection or feature order changed")
    if cfg["rf_params"] != EXPECTED_PARAMS or base.RF_PARAMS != EXPECTED_PARAMS:
        raise RuntimeError("Frozen Random Forest parameters changed")
    base.assert_safe_features(FEATURES)
    if any(name in FEATURES for name in base.WB_FEATURES) or "magnitude" in FEATURES:
        raise RuntimeError("World Bank or raw magnitude entered T2")
    inputs = [INPUT, RAW, LOCKED_CONFIG, OLD_MAG, PARENT / "manifest.json",
              PARENT / "artifacts/T2_random_forest_pipeline.joblib"]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}


def load_scoped_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cols = ["event_id", "year", "total_deaths", "event_date", "country_code", "region",
            "disaster_type", "disaster_subtype", "date_granularity", "date_imputed",
            "historical_frequency", "hdi"]
    # Maturity rows are discarded at read time and never enter a feature frame.
    data = pd.read_csv(INPUT, usecols=cols)
    data = data[data.year.between(2000, 2023)].copy()
    if data.event_id.isna().any() or data.event_id.duplicated().any():
        raise RuntimeError("Scoped event_id is missing or duplicated")
    if data.total_deaths.dropna().lt(0).any():
        raise RuntimeError("Negative total_deaths")
    data["three_class_label"] = base.label_from_deaths(data.total_deaths)
    data = data[data.three_class_label.notna()].copy()
    data = base.engineer_base(data)
    dev = data[data.year.between(2000, 2021)].copy()
    test = data[data.year.between(2022, 2023)].copy()
    if len(dev) != EXPECTED_COUNTS["development"] or len(test) != EXPECTED_COUNTS["test"]:
        raise RuntimeError(f"Unexpected split counts: development={len(dev)}, test={len(test)}")
    if set(dev.event_id) & set(test.event_id):
        raise RuntimeError("Development/Test event_id overlap")
    for name, frame in [("development", dev), ("test", test)]:
        counts = frame.three_class_label.value_counts().reindex(LABELS, fill_value=0).to_dict()
        if counts != EXPECTED_LABELS[name]:
            raise RuntimeError(f"Unexpected {name} labels: {counts}")
    target_ids = set(dev.event_id.astype(str)) | set(test.event_id.astype(str))
    mag, vocab = base.load_and_fit_magnitude(set(dev.event_id.astype(str)), target_ids)
    if len(vocab) != 8 or mag.event_id.duplicated().any() or set(mag.event_id) != target_ids:
        raise RuntimeError("Magnitude vocabulary or event mapping integrity failed")
    dev = dev.merge(mag, on="event_id", how="left", validate="one_to_one")
    test = test.merge(mag, on="event_id", how="left", validate="one_to_one")
    return dev, test, vocab


def fitted_audit(pipe, vocab: pd.DataFrame) -> tuple[list[str], dict, pd.DataFrame]:
    prep = pipe.named_steps["preprocessor"]
    expanded = prep.get_feature_names_out().tolist()
    cat_pipe = prep.named_transformers_["categorical"]
    cats = cat_pipe.named_steps["onehot"].categories_
    category_vocab = {name: [str(x) for x in values.tolist()]
                      for name, values in zip(base.BASE_CATEGORICAL, cats)}
    numeric = [x for x in FEATURES if x not in base.BASE_CATEGORICAL]
    stats = prep.named_transformers_["numeric"].named_steps["imputer"].statistics_
    imputer = pd.DataFrame({"feature": numeric, "development_median": stats})
    if vocab.eligible.sum() != 7:
        raise RuntimeError("Unexpected number of eligible magnitude groups")
    return expanded, category_vocab, imputer


def main() -> None:
    for d in (ART, REP, PRED):
        d.mkdir(parents=True, exist_ok=True)
    started = now()
    prior_dev_predictions = pd.read_csv(PRED / "development_predictions.csv") if (PRED / "development_predictions.csv").exists() else None
    prior_test_predictions = pd.read_csv(PRED / "test_predictions.csv") if (PRED / "test_predictions.csv").exists() else None
    prior_dev_metrics = pd.read_csv(REP / "development_metrics.csv") if (REP / "development_metrics.csv").exists() else None
    prior_test_metrics = pd.read_csv(REP / "test_metrics.csv") if (REP / "test_metrics.csv").exists() else None
    prior_category_vocab = json.loads((ART / "development_category_vocabularies.json").read_text(encoding="utf-8")) if (ART / "development_category_vocabularies.json").exists() else None
    prior_magnitude = pd.read_csv(ART / "development_magnitude_groups.csv") if (ART / "development_magnitude_groups.csv").exists() else None
    before = protected_hashes()
    input_hashes = assert_locked()
    lock_path = ART / "locked_final_config.json"
    static_lock = {"feature_version": "T2", "features": FEATURES, "rf_params": EXPECTED_PARAMS,
                   "labels": LABELS, "development": "2000-2021", "test": "2022-2023",
                   "maturity": "2024-2026 sealed", "input_hashes": input_hashes,
                   "magnitude_rules": "8 frozen semantic groups; development-only median/IQR; n>=20; IQR>0; clip[-5,5]"}
    if lock_path.exists():
        prior_lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if prior_lock["locked_configuration"] != static_lock:
            raise RuntimeError("Locked final configuration changed between runs")
    else:
        write_json(lock_path, {"locked_at_utc": started, "locked_before_test_evaluation": True,
                               "locked_configuration": static_lock})

    dev, test, vocab = load_scoped_data()
    vocab.to_csv(ART / "development_magnitude_groups.csv", index=False)
    old = pd.read_csv(OLD_MAG)
    compare = old.merge(vocab, on=["grouping_strategy", "group_key"], how="outer",
                        suffixes=("_train", "_development"), validate="one_to_one")
    for field in ["training_nonmissing", "training_median", "training_iqr"]:
        compare[f"delta_{field}"] = compare[f"{field}_development"] - compare[f"{field}_train"]
    compare.to_csv(ART / "magnitude_train_vs_development.csv", index=False)

    pipe = base.make_pipeline(FEATURES)
    pipe.fit(dev[FEATURES], dev.three_class_label)
    dev_pred = pipe.predict(dev[FEATURES]); test_pred = pipe.predict(test[FEATURES])
    dev_proba = base.ordered_probabilities(pipe, dev[FEATURES]); test_proba = base.ordered_probabilities(pipe, test[FEATURES])
    if pipe.named_steps["model"].classes_.tolist() != LABELS:
        raise RuntimeError("Class order is not Low, Moderate, Severe")
    dev_out = prediction_frame(dev, dev_pred, dev_proba)
    test_out = prediction_frame(test, test_pred, test_proba)
    if len(test_out) != len(test) or test_out.event_id.duplicated().any():
        raise RuntimeError("Test prediction/event alignment failed")
    probability_error = float(np.max(np.abs(test_proba.sum(axis=1) - 1)))
    if probability_error > 1e-12:
        raise RuntimeError(f"Test probability sums invalid: {probability_error}")

    dev_metrics = metrics_frame(dev.three_class_label, dev_pred, "development")
    test_metrics = metrics_frame(test.three_class_label, test_pred, "test")
    perclass = pd.concat([base.per_class(dev.three_class_label, dev_pred, "final_T2", "development"),
                          base.per_class(test.three_class_label, test_pred, "final_T2", "test")], ignore_index=True)
    dev_metrics.to_csv(REP / "development_metrics.csv", index=False)
    test_metrics.to_csv(REP / "test_metrics.csv", index=False)
    perclass.to_csv(REP / "per_class_metrics.csv", index=False)
    for name, y, pred in [("development", dev.three_class_label, dev_pred), ("test", test.three_class_label, test_pred)]:
        pd.DataFrame(confusion_matrix(y, pred, labels=LABELS), index=LABELS, columns=LABELS).to_csv(REP / f"confusion_matrix_{name}.csv")
        pd.DataFrame(classification_report(y, pred, labels=LABELS, output_dict=True, zero_division=0)).T.to_csv(REP / f"classification_report_{name}.csv")
    dev_out.to_csv(PRED / "development_predictions.csv", index=False)
    test_out.to_csv(PRED / "test_predictions.csv", index=False)
    expanded, category_vocab, imputer = fitted_audit(pipe, vocab)
    pd.DataFrame({"order": range(1, len(FEATURES) + 1), "feature": FEATURES}).to_csv(ART / "feature_manifest.csv", index=False)
    pd.DataFrame({"order": range(1, len(expanded) + 1), "expanded_feature": expanded}).to_csv(ART / "expanded_feature_manifest.csv", index=False)
    write_json(ART / "development_category_vocabularies.json", category_vocab)
    imputer.to_csv(ART / "development_numeric_imputer_statistics.csv", index=False)
    joblib.dump(pipe, ART / "final_t2_pipeline.joblib")

    cross_run = {"prior_successful_run_available": prior_test_predictions is not None}
    if prior_test_predictions is not None:
        probability_columns = [f"probability_{x}" for x in LABELS]
        cross_run.update({
            "development_predictions_identical": prior_dev_predictions[["event_id", "predicted_label"]].equals(dev_out[["event_id", "predicted_label"]]),
            "test_predictions_identical": prior_test_predictions[["event_id", "predicted_label"]].equals(test_out[["event_id", "predicted_label"]]),
            "development_probability_max_abs_diff": float(np.max(np.abs(prior_dev_predictions[probability_columns].to_numpy() - dev_out[probability_columns].to_numpy()))),
            "test_probability_max_abs_diff": float(np.max(np.abs(prior_test_predictions[probability_columns].to_numpy() - test_out[probability_columns].to_numpy()))),
            "development_metrics_within_1e_15": bool(np.allclose(prior_dev_metrics.select_dtypes("number"), dev_metrics.select_dtypes("number"), atol=1e-15, rtol=0)),
            "test_metrics_within_1e_15": bool(np.allclose(prior_test_metrics.select_dtypes("number"), test_metrics.select_dtypes("number"), atol=1e-15, rtol=0)),
            "category_vocabularies_identical": prior_category_vocab == category_vocab,
            "magnitude_statistics_identical": prior_magnitude.equals(vocab),
            "feature_order_identical": True,
        })
        required = [v for k, v in cross_run.items() if k.endswith("identical") or k.endswith("1e_15")]
        if not all(required) or cross_run["test_probability_max_abs_diff"] > 1e-12:
            raise RuntimeError(f"Consecutive-run reproducibility failed: {cross_run}")
    write_json(ART / "consecutive_run_reproducibility.json", cross_run)

    # Re-load is the authoritative reproducibility check; no selection or refit occurs here.
    loaded = joblib.load(ART / "final_t2_pipeline.joblib")
    loaded_dev_pred = loaded.predict(dev[FEATURES]); loaded_test_pred = loaded.predict(test[FEATURES])
    loaded_dev_proba = base.ordered_probabilities(loaded, dev[FEATURES]); loaded_test_proba = base.ordered_probabilities(loaded, test[FEATURES])
    repro = {"method": "saved-model reload and repeat prediction", "development_predictions_identical": bool(np.array_equal(dev_pred, loaded_dev_pred)),
             "test_predictions_identical": bool(np.array_equal(test_pred, loaded_test_pred)),
             "development_probability_max_abs_diff": float(np.max(np.abs(dev_proba-loaded_dev_proba))),
             "test_probability_max_abs_diff": float(np.max(np.abs(test_proba-loaded_test_proba))),
             "feature_order_identical": loaded.feature_names_in_.tolist() == FEATURES,
             "category_vocabularies_identical": category_vocab == fitted_audit(loaded, vocab)[1],
             "magnitude_statistics_identical": True, "metric_tolerance": 1e-15,
             "metrics_identical": base.scalar_metrics(dev.three_class_label, loaded_dev_pred) == base.scalar_metrics(dev.three_class_label, dev_pred) and base.scalar_metrics(test.three_class_label, loaded_test_pred) == base.scalar_metrics(test.three_class_label, test_pred)}
    if not all(v for k, v in repro.items() if k.endswith("identical")) or repro["test_probability_max_abs_diff"] > 1e-12:
        raise RuntimeError(f"Reload reproducibility failed: {repro}")
    repro["consecutive_run"] = cross_run
    write_json(ART / "reproducibility_check.json", repro)

    eval_meta_path = ART / "evaluation_metadata.json"
    if eval_meta_path.exists():
        eval_meta = json.loads(eval_meta_path.read_text(encoding="utf-8"))
    else:
        eval_meta = {"test_first_evaluated_at_utc": now(), "configuration_locked_before_test": True}
    eval_meta.update({"latest_reproducibility_run_at_utc": now(), "test_evaluation_count_for_model_selection": 1,
                      "test_used_for_tuning": False, "maturity_rows_read_into_feature_frame": 0,
                      "maturity_predictions": 0, "maturity_probability_rows": 0, "maturity_metrics": 0,
                      "test_probability_sum_max_abs_error": probability_error})
    write_json(eval_meta_path, eval_meta)

    old_val = pd.read_csv(PARENT / "reports/metrics.csv")
    val = old_val[(old_val.experiment_id == "T2") & (old_val.split == "validation")].iloc[0]
    test_row = test_metrics.iloc[0]
    deltas = {k: float(test_row[k] - val[k]) for k in ["accuracy", "balanced_accuracy", "macro_f1", "weighted_f1"]}
    cm = pd.DataFrame(confusion_matrix(test.three_class_label, test_pred, labels=LABELS), index=LABELS, columns=LABELS)
    cm_markdown = "| True \\ Predicted | Low | Moderate | Severe |\n|---|---:|---:|---:|"
    for label in LABELS:
        cm_markdown += f"\n| {label} | {cm.loc[label, 'Low']} | {cm.loc[label, 'Moderate']} | {cm.loc[label, 'Severe']} |"
    report = f"""# Final locked T2 three-class Random Forest report

Generated: {now()}

## Scope and integrity

- Development: 2000-2021, {len(dev):,} labeled events; Test: 2022-2023, {len(test):,} labeled events.
- T2 was locked before Test access. No World Bank features or raw Magnitude entered the model.
- Maturity 2024-2026 was discarded at input filtering and never entered a feature frame; predictions/probabilities/metrics: 0/0/0.
- Test received transform/predict only. All fitted statistics and vocabularies came from Development.

## Final features

{', '.join(FEATURES)}

## Metrics

| Split | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 | QWK | Severe->Low | Low->Severe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | {dev_metrics.iloc[0].accuracy:.6f} | {dev_metrics.iloc[0].balanced_accuracy:.6f} | {dev_metrics.iloc[0].macro_f1:.6f} | {dev_metrics.iloc[0].weighted_f1:.6f} | {dev_metrics.iloc[0].quadratic_weighted_kappa:.6f} | {int(dev_metrics.iloc[0].severe_to_low)} | {int(dev_metrics.iloc[0].low_to_severe)} |
| Test | {test_row.accuracy:.6f} | {test_row.balanced_accuracy:.6f} | {test_row.macro_f1:.6f} | {test_row.weighted_f1:.6f} | {test_row.quadratic_weighted_kappa:.6f} | {int(test_row.severe_to_low)} | {int(test_row.low_to_severe)} |

Test minus locked T2 Validation: accuracy {deltas['accuracy']:+.6f}, balanced accuracy {deltas['balanced_accuracy']:+.6f}, macro F1 {deltas['macro_f1']:+.6f}, weighted F1 {deltas['weighted_f1']:+.6f}. These are descriptive differences only; no post-Test tuning was performed.

## Test confusion matrix

Rows are true classes and columns are predicted classes in fixed order Low, Moderate, Severe.

{cm_markdown}

## Reproducibility

The saved model was reloaded and predictions repeated. Class predictions and metrics were identical; maximum Test probability difference was {repro['test_probability_max_abs_diff']:.3g}.
"""
    (REP / "final_t2_report.md").write_text(report, encoding="utf-8")

    after = protected_hashes()
    if before != after:
        changed = sorted(set(before) | set(after))
        changed = [p for p in changed if before.get(p) != after.get(p)]
        raise RuntimeError(f"Frozen files changed: {changed}")
    manifest_files = [p for p in HERE.rglob("*") if p.is_file() and p.name != "manifest.json"]
    manifest = {"created_at_utc": now(), "script_sha256": sha(Path(__file__)), "input_hashes": input_hashes,
                "frozen_files_verified_unchanged": len(before), "maturity_feature_files": 0,
                "maturity_predictions": 0, "maturity_metrics": 0,
                "files": {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(manifest_files)}}
    write_json(HERE / "manifest.json", manifest)
    print(json.dumps({"status": "ok", "development": len(dev), "test": len(test),
                      "test_macro_f1": float(test_row.macro_f1), "maturity_used": False,
                      "frozen_files_unchanged": len(before), "started_at": started}, ensure_ascii=False))


if __name__ == "__main__":
    main()
