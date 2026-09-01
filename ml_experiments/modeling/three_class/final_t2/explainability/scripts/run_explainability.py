"""Post-hoc explainability for the frozen final T2 pipeline. Never fits a model."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import sklearn
from sklearn.inspection import permutation_importance
from sklearn.metrics import f1_score, make_scorer

HERE = Path(__file__).resolve().parents[1]
FINAL = HERE.parent
THREE = FINAL.parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(THREE))
import run_t0_t3_random_forest as base  # noqa: E402

ART, TABLES, FIGURES, REPORTS = (HERE / x for x in ["artifacts", "tables", "figures", "reports"])
PIPELINE = FINAL / "artifacts/final_t2_pipeline.joblib"
FINAL_MANIFEST = FINAL / "manifest.json"
PREDICTIONS = FINAL / "predictions/test_predictions.csv"
INPUT = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
RAW = ROOT / "data/emdat_raw.xlsx"
MAG_STATS = FINAL / "artifacts/development_magnitude_groups.csv"
FEATURES = base.FEATURES["T2"]
LABELS = ["Low", "Moderate", "Severe"]
RANDOM_STATE = 20260804


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def frozen_hashes() -> dict[str, str]:
    roots = [ROOT / "data/raw", ROOT / "data/processed", ROOT / "data/processed_hdro",
             ROOT / "ml_experiments/data_preparation", ROOT / "ml_experiments/modeling"]
    out = {}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and HERE not in p.parents:
                out[p.relative_to(ROOT).as_posix()] = sha(p)
    return dict(sorted(out.items()))


def original_feature(transformed: str) -> str:
    suffix = transformed.split("__", 1)[-1]
    for feature in sorted(FEATURES, key=len, reverse=True):
        if suffix == feature or suffix.startswith(feature + "_"):
            return feature
    raise RuntimeError(f"Cannot map transformed feature: {transformed}")


def build_test_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["event_id", "country", "country_code", "region", "disaster_type", "disaster_subtype",
            "year", "total_deaths", "event_date", "date_granularity", "date_imputed",
            "historical_frequency", "hdi"]
    data = pd.read_csv(INPUT, usecols=cols)
    data = data[data.year.between(2022, 2023)].copy()
    data["three_class_label"] = base.label_from_deaths(data.total_deaths)
    data = data[data.three_class_label.notna()].copy()
    data = base.engineer_base(data)
    if len(data) != 948 or data.event_id.isna().any() or data.event_id.duplicated().any():
        raise RuntimeError("Test integrity failed")

    raw = pd.read_excel(RAW, sheet_name="EM-DAT Data", dtype=object, keep_default_na=False,
                        usecols=["DisNo.", "Disaster Type", "Disaster Subtype", "Magnitude", "Magnitude Scale"])
    raw.columns = ["event_id", "raw_disaster_type", "raw_disaster_subtype", "magnitude_raw", "magnitude_scale"]
    raw["event_id"] = raw.event_id.astype(str)
    raw = raw[raw.event_id.isin(set(data.event_id.astype(str)))].copy()
    magnitude_text = raw.magnitude_raw.astype(str).str.strip()
    raw["magnitude"] = pd.to_numeric(raw.magnitude_raw.where(~magnitude_text.eq("")), errors="coerce")
    if ((~magnitude_text.eq("")) & raw.magnitude.isna()).any():
        raise RuntimeError("Non-numeric Magnitude")
    raw["magnitude_scale"] = raw.magnitude_scale.astype(str).str.strip().replace("", pd.NA)
    groups = raw.apply(base.magnitude_group_id, axis=1, result_type="expand")
    groups.columns = ["grouping_strategy", "semantic_group", "group_key"]
    raw = pd.concat([raw, groups], axis=1)
    vocab = pd.read_csv(MAG_STATS)
    eligible = vocab[vocab.eligible].set_index("group_key")
    raw["magnitude_missing"] = raw.magnitude.isna().astype("int8")
    raw["magnitude_group_unknown"] = (~raw.group_key.isin(eligible.index)).astype("int8")
    raw["magnitude_robust_z"] = np.nan
    for key, stats in eligible.iterrows():
        mask = raw.group_key.eq(key) & raw.magnitude.notna()
        raw.loc[mask, "magnitude_robust_z"] = ((raw.loc[mask, "magnitude"] - stats.training_median) / stats.training_iqr).clip(-5, 5)
    mag = raw[["event_id", "magnitude_robust_z", "magnitude_missing", "magnitude_group_unknown"]]
    data = data.merge(mag, on="event_id", how="left", validate="one_to_one")
    if data[FEATURES].columns.tolist() != FEATURES or data[FEATURES].isna().all(axis=0).any():
        raise RuntimeError("Final feature reconstruction failed")
    return data, vocab


def plot_bar(frame: pd.DataFrame, value: str, path: Path, title: str, error: str | None = None, top: int = 15) -> None:
    show = frame.sort_values(value, ascending=True).tail(top)
    fig, ax = plt.subplots(figsize=(9, 6))
    xerr = show[error] if error else None
    ax.barh(show["feature"], show[value], xerr=xerr, color="#2f6f9f", alpha=.88)
    ax.axvline(0, color="black", linewidth=.8)
    ax.set_title(title); ax.set_xlabel(value); fig.tight_layout()
    fig.savefig(path, dpi=180); plt.close(fig)


def select_cases(data: pd.DataFrame) -> pd.DataFrame:
    definitions = [
        ("Low correct", "Low", "Low"), ("Moderate correct", "Moderate", "Moderate"),
        ("Severe correct", "Severe", "Severe"), ("Severe to Low", "Severe", "Low"),
        ("Moderate to Low", "Moderate", "Low"), ("Low to Severe", "Low", "Severe")]
    chosen = []
    used_countries, used_types = set(), set()
    data = data.copy()
    data["completeness"] = data[["hdi", "event_month", "magnitude_robust_z"]].notna().sum(axis=1)
    for group, true, pred in definitions:
        candidates = data[(data.true_label == true) & (data.predicted_label == pred)].copy()
        candidates["selection_probability"] = candidates[f"probability_{pred}"]
        candidates = candidates.sort_values(["selection_probability", "completeness", "event_id"], ascending=[False, False, True])
        selected = []
        for _, row in candidates.iterrows():
            if len(selected) == 2: break
            if row.country_code not in used_countries and row.disaster_type not in used_types:
                selected.append(row)
        for _, row in candidates.iterrows():
            if len(selected) == 2: break
            if row.event_id not in {x.event_id for x in selected}: selected.append(row)
        for rank, row in enumerate(selected, 1):
            row = row.copy(); row["case_group"] = group; row["selection_rank"] = rank
            chosen.append(row); used_countries.add(row.country_code); used_types.add(row.disaster_type)
    return pd.DataFrame(chosen).drop(columns=["completeness", "selection_probability"])


def summary_tables(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = data.copy(); data["correct"] = data.true_label.eq(data.predicted_label)
    data["max_probability"] = data[[f"probability_{x}" for x in LABELS]].max(axis=1)
    masks = {"all": pd.Series(True, index=data.index), "correct": data.correct, "incorrect": ~data.correct,
             "Severe_to_Low": data.true_label.eq("Severe") & data.predicted_label.eq("Low"),
             "Moderate_to_Low": data.true_label.eq("Moderate") & data.predicted_label.eq("Low"),
             "Low_to_Severe": data.true_label.eq("Low") & data.predicted_label.eq("Severe")}
    numeric = ["year", "historical_frequency", "hdi", "magnitude_robust_z", "max_probability",
               "probability_Low", "probability_Moderate", "probability_Severe"]
    categorical = ["disaster_type", "region", "date_granularity", "date_imputed", "hdi_missing",
                   "magnitude_missing", "magnitude_group_unknown", "month_missing"]
    rows = []
    for group, mask in masks.items():
        frame = data[mask]
        for col in numeric:
            values = frame[col].dropna()
            rows.append({"group": group, "variable": col, "statistic": "valid_n", "level": "", "value": len(values)})
            for stat, value in [("median", values.median()), ("iqr", values.quantile(.75)-values.quantile(.25))]:
                rows.append({"group": group, "variable": col, "statistic": stat, "level": "", "value": value})
        for col in categorical:
            counts = frame[col].fillna("__MISSING__").astype(str).value_counts()
            for level, count in counts.items():
                rows.append({"group": group, "variable": col, "statistic": "count", "level": level, "value": count})
                rows.append({"group": group, "variable": col, "statistic": "proportion", "level": level, "value": count/len(frame) if len(frame) else np.nan})
    error = pd.DataFrame(rows)
    conf_rows = []
    for group, mask in masks.items():
        x = data.loc[mask, "max_probability"]
        conf_rows.append({"group": group, "n": len(x), "median_max_probability": x.median(),
                          "iqr_max_probability": x.quantile(.75)-x.quantile(.25),
                          "high_confidence_errors_ge_0_70": int(((x >= .70) & (~data.loc[mask, "correct"])).sum())})
    for label in LABELS:
        frame = data[data.true_label.eq(label)]
        conf_rows.append({"group": f"true_{label}_mean_probability", "n": len(frame),
                          **{f"mean_probability_{x}": frame[f"probability_{x}"].mean() for x in LABELS}})
    return error, pd.DataFrame(conf_rows)


def main() -> None:
    for d in [ART, TABLES, FIGURES, REPORTS]: d.mkdir(parents=True, exist_ok=True)
    before = frozen_hashes()
    final_manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))
    expected_hash = final_manifest["files"]["artifacts/final_t2_pipeline.joblib"]
    if sha(PIPELINE) != expected_hash: raise RuntimeError("Pipeline hash differs from final manifest")
    pipe = joblib.load(PIPELINE)
    if pipe.feature_names_in_.tolist() != FEATURES or pipe.named_steps["model"].classes_.tolist() != LABELS:
        raise RuntimeError("Frozen feature or class order changed")
    test, mag_vocab = build_test_features()
    frozen_pred = pd.read_csv(PREDICTIONS)
    if len(frozen_pred) != 948 or frozen_pred.event_id.duplicated().any() or set(test.event_id) != set(frozen_pred.event_id):
        raise RuntimeError("Frozen Test predictions integrity failed")
    pred = pipe.predict(test[FEATURES]); proba = base.ordered_probabilities(pipe, test[FEATURES])
    aligned = frozen_pred.set_index("event_id").loc[test.event_id]
    if not np.array_equal(pred, aligned.predicted_label.to_numpy()): raise RuntimeError("Frozen predictions were not reproduced")
    frozen_probs = aligned[[f"probability_{x}" for x in LABELS]].to_numpy()
    if np.max(np.abs(proba-frozen_probs)) > 1e-12: raise RuntimeError("Frozen probabilities were not reproduced")
    test["true_label"] = test.three_class_label
    test["predicted_label"] = pred
    for i, label in enumerate(LABELS): test[f"probability_{label}"] = proba[:, i]

    transformed_names = pipe.named_steps["preprocessor"].get_feature_names_out().tolist()
    origins = [original_feature(x) for x in transformed_names]
    impurity = pd.DataFrame({"transformed_feature": transformed_names, "original_feature": origins,
                             "importance": pipe.named_steps["model"].feature_importances_})
    impurity.to_csv(TABLES / "impurity_importance_transformed.csv", index=False)
    grouped = impurity.groupby("original_feature", as_index=False).importance.sum().rename(columns={"original_feature":"feature"}).sort_values("importance", ascending=False)
    grouped.to_csv(TABLES / "impurity_importance_grouped.csv", index=False)
    plot_bar(grouped, "importance", FIGURES / "impurity_importance_grouped.png", "Grouped impurity importance")

    scorer = make_scorer(f1_score, labels=LABELS, average="macro", zero_division=0)
    perm = permutation_importance(pipe, test[FEATURES], test.true_label, scoring=scorer, n_repeats=30,
                                  random_state=RANDOM_STATE, n_jobs=-1)
    permutation = pd.DataFrame({"feature": FEATURES, "importance_mean": perm.importances_mean,
                                "importance_std": perm.importances_std,
                                "importance_min": perm.importances.min(axis=1),
                                "importance_max": perm.importances.max(axis=1)}).sort_values("importance_mean", ascending=False)
    permutation.to_csv(TABLES / "permutation_importance_test.csv", index=False)
    plot_bar(permutation, "importance_mean", FIGURES / "permutation_importance_test.png",
             "Test permutation importance (Macro F1)", "importance_std")

    cases = select_cases(test)
    rng = np.random.default_rng(RANDOM_STATE)
    sample_ids = set(cases.event_id)
    sample_parts = []
    for label in LABELS:
        candidates = test[test.true_label.eq(label) & ~test.event_id.isin(sample_ids)]
        n = min(100, len(candidates))
        sample_parts.append(candidates.loc[rng.choice(candidates.index.to_numpy(), n, replace=False)])
    shap_sample = pd.concat([cases, *sample_parts], ignore_index=True).drop_duplicates("event_id")
    shap_sample = shap_sample.sort_values("event_id").reset_index(drop=True)
    X_transformed = pipe.named_steps["preprocessor"].transform(shap_sample[FEATURES])
    X_dense = X_transformed.toarray() if hasattr(X_transformed, "toarray") else np.asarray(X_transformed)
    explainer = shap.TreeExplainer(pipe.named_steps["model"])
    explanation = explainer(X_dense, check_additivity=True)
    values = np.asarray(explanation.values)
    if values.shape != (len(shap_sample), len(transformed_names), len(LABELS)):
        raise RuntimeError(f"Unexpected SHAP shape: {values.shape}")
    base_values = np.asarray(explanation.base_values)
    if base_values.shape not in [(len(shap_sample), len(LABELS)), (len(LABELS),)]:
        raise RuntimeError(f"Unexpected SHAP base shape: {base_values.shape}")
    reconstructed = values.sum(axis=1) + base_values
    shap_probability_max_error = float(np.max(np.abs(reconstructed - base.ordered_probabilities(pipe, shap_sample[FEATURES]))))
    if shap_probability_max_error > 1e-6: raise RuntimeError(f"SHAP class axis/additivity failed: {shap_probability_max_error}")

    unique_origins = FEATURES
    global_rows, detail_rows = [], []
    for feature in unique_origins:
        idx = [i for i, x in enumerate(origins) if x == feature]
        for ci, label in enumerate(LABELS):
            v = np.abs(values[:, idx, ci]).sum(axis=1)
            global_rows.append({"feature": feature, "class": label, "mean_abs_shap": v.mean()})
        global_rows.append({"feature": feature, "class": "overall", "mean_abs_shap": np.abs(values[:, idx, :]).sum(axis=1).mean()})
    for fi, name in enumerate(transformed_names):
        for ci, label in enumerate(LABELS):
            detail_rows.append({"transformed_feature": name, "original_feature": origins[fi], "class": label,
                                "mean_abs_shap": np.abs(values[:, fi, ci]).mean()})
    shap_global = pd.DataFrame(global_rows)
    shap_detail = pd.DataFrame(detail_rows)
    shap_global.to_csv(TABLES / "shap_importance_grouped.csv", index=False)
    shap_detail.to_csv(TABLES / "shap_importance_transformed.csv", index=False)
    overall = shap_global[shap_global["class"].eq("overall")].sort_values("mean_abs_shap", ascending=False)
    plot_bar(overall, "mean_abs_shap", FIGURES / "shap_importance_global.png", "Global grouped mean(|SHAP|)")
    pivot = shap_global[~shap_global["class"].eq("overall")].pivot(index="feature", columns="class", values="mean_abs_shap").loc[overall.feature]
    pivot.plot(kind="barh", figsize=(10, 7), color=["#4c78a8", "#f58518", "#e45756"])
    plt.title("Class-specific grouped mean(|SHAP|)"); plt.xlabel("mean absolute SHAP"); plt.tight_layout()
    plt.savefig(FIGURES / "shap_importance_by_class.png", dpi=180); plt.close()

    pd.DataFrame({"event_id": shap_sample.event_id, "true_label": shap_sample.true_label,
                  "predicted_label": shap_sample.predicted_label}).to_csv(ART / "shap_sample.csv", index=False)
    local_rows = []
    sample_index = {eid: i for i, eid in enumerate(shap_sample.event_id)}
    for _, case in cases.iterrows():
        si = sample_index[case.event_id]; ci = LABELS.index(case.predicted_label)
        contributions = {}
        for feature in FEATURES:
            idx = [i for i, x in enumerate(origins) if x == feature]
            contributions[feature] = float(values[si, idx, ci].sum())
            local_rows.append({"event_id": case.event_id, "predicted_class": case.predicted_label,
                               "feature": feature, "signed_shap": contributions[feature],
                               "abs_shap": abs(contributions[feature])})
        top = max(contributions, key=lambda x: abs(contributions[x]))
        cases.loc[cases.event_id.eq(case.event_id), "top_local_shap_feature"] = top
        cases.loc[cases.event_id.eq(case.event_id), "top_local_shap_signed_value"] = contributions[top]
    pd.DataFrame(local_rows).to_csv(TABLES / "selected_case_local_shap.csv", index=False)
    case_cols = ["case_group", "selection_rank", "event_id", "year", "country", "country_code", "region",
                 "disaster_type", "disaster_subtype", "true_label", "predicted_label",
                 "probability_Low", "probability_Moderate", "probability_Severe", "historical_frequency",
                 "hdi", "hdi_missing", "event_month", "month_missing", "magnitude_robust_z",
                 "magnitude_missing", "magnitude_group_unknown", "top_local_shap_feature", "top_local_shap_signed_value"]
    cases[case_cols].to_csv(TABLES / "selected_cases.csv", index=False)
    error, confidence = summary_tables(test)
    error.to_csv(TABLES / "error_group_summary.csv", index=False)
    confidence.to_csv(TABLES / "confidence_summary.csv", index=False)

    config = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "analysis_type": "post-hoc frozen-model explanation",
              "pipeline_sha256": sha(PIPELINE), "pipeline_manifest_sha256": expected_hash,
              "features": FEATURES, "classes": LABELS, "test_n": len(test), "permutation": {"scoring":"macro_f1", "n_repeats":30, "random_state":RANDOM_STATE, "n_jobs":-1},
              "shap": {"version": shap.__version__, "explainer":"TreeExplainer", "sample_n":len(shap_sample),
                       "sampling":"fixed-seed stratified up to 100 per true class plus selected cases", "random_state":RANDOM_STATE,
                       "class_counts": shap_sample.true_label.value_counts().reindex(LABELS).to_dict(),
                       "additivity_probability_max_abs_error": shap_probability_max_error},
              "sklearn": sklearn.__version__, "numpy": np.__version__, "model_refit": False,
              "test_tuning": False, "maturity_used": False}
    write_json(ART / "explainability_config.json", config)
    (REPORTS / "case_selection_rules.md").write_text("""# Case selection rules

## Fixed groups and quota

Six groups are defined before inspection: correct Low, correct Moderate, correct Severe, Severe→Low, Moderate→Low, and Low→Severe. The quota is two events per group. If a group contains fewer than two candidates, all available candidates are retained and the quota is not borrowed from another group.

## Completeness score and ordering

The completeness score is the count of non-missing values among exactly three fields: `hdi`, `event_month`, and `magnitude_robust_z`. Each non-missing field contributes one point, so the score ranges from 0 to 3. Within each group, candidates are stably sorted by: (1) probability assigned to the predicted class, descending; (2) completeness score, descending; and (3) `event_id`, ascending. Thus all remaining ties are resolved by `event_id`.

## Diversity pass and fallback

Two global sets, used country codes and used disaster types, are maintained across groups in the fixed group order above. On the first pass through a group's sorted candidates, an event is selected only when both its `country_code` and `disaster_type` have not appeared in any previously selected event. Candidates failing either condition are skipped during this pass. Each selected event immediately adds its country code and disaster type to the global sets.

If fewer than two events have been selected after the diversity pass, a second pass traverses the same sorted candidate list and selects the earliest not-yet-selected events without applying country or disaster-type restrictions until the quota is filled or candidates are exhausted. No manual case substitution is permitted.
""", encoding="utf-8")

    top_perm = permutation.head(3).feature.tolist(); top_shap = overall.head(3).feature.tolist(); top_imp = grouped.head(3).feature.tolist()
    severe_low_high = int(((test.true_label == "Severe") & (test.predicted_label == "Low") & (test.probability_Low >= .70)).sum())
    report = f"""# Frozen final T2 post-hoc explainability report

The frozen pipeline was loaded without fitting. Its SHA-256 matches the final manifest. Test contains 948 unique labeled events and predictions reproduce the frozen output. No Maturity data was used.

## Global importance

- Grouped impurity top 3: {', '.join(top_imp)}.
- Test permutation top 3 by Macro-F1 decrease: {', '.join(top_perm)}.
- Class-balanced grouped SHAP top 3: {', '.join(top_shap)}.

Impurity importance sums split-gain allocations and may favor high-cardinality fields. Permutation importance measures performance change on this finite Test set and can be negative. SHAP describes how the frozen model distributes output around its baseline; it is not causal evidence.

## SHAP audit

TreeExplainer {shap.__version__} was applied to {len(shap_sample)} fixed, class-balanced Test events using the already-fitted preprocessor. Class counts are {config['shap']['class_counts']}. Equal class counts prevent the larger Moderate class from dominating the summary. Therefore, “global SHAP” here means class-balanced grouped mean absolute SHAP and is not the Test-prevalence-weighted global importance for all 948 events. Output shape was checked as sample × 331 transformed features × 3 classes; additive reconstruction maximum error was {shap_probability_max_error:.3g}.

## Cases and errors

Twelve cases selected by the archived stable rules cover three correct groups and Severe→Low, Moderate→Low, Low→Severe. Test contains 31 Severe→Low, 147 Moderate→Low and 14 Low→Severe events. Severe→Low errors with predicted Low output probability ≥0.70: {severe_low_high}. Probabilities were not calibrated and indicate relative model output strength, not reliable calibrated confidence.

Interpretations are model-behavior descriptions only. A large local contribution means that a feature affected this fitted model's output for the event; it does not mean the feature caused real-world mortality.
"""
    (REPORTS / "explainability_report.md").write_text(report, encoding="utf-8")
    after = frozen_hashes()
    if before != after: raise RuntimeError("Frozen artifacts changed during explanation")
    thesis_document = ROOT / "docs/thesis/模型解释与典型案例分析.md"
    files = [p for p in HERE.rglob("*") if p.is_file() and p.name != "explainability_manifest.json"]
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "frozen_files_verified_unchanged": len(before),
                "model_refit": False, "test_tuning": False, "maturity_used": False,
                "files": {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(files)},
                "thesis_document": {"path": thesis_document.relative_to(ROOT).as_posix(), "sha256": sha(thesis_document)}}
    write_json(HERE / "explainability_manifest.json", manifest)
    print(json.dumps({"status":"ok", "permutation_top3":top_perm, "shap_top3":top_shap,
                      "cases":len(cases), "severe_to_low_high_confidence":severe_low_high,
                      "shap_sample_n":len(shap_sample)}, ensure_ascii=False))


if __name__ == "__main__": main()
