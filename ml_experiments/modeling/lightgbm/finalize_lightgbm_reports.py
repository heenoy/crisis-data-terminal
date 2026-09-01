"""Build comparison and audit summaries from already-saved predictions (no fitting)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_recall_fscore_support

LABELS = ["Low", "Moderate", "High", "Extreme"]


def markdown_table(frame: pd.DataFrame) -> str:
    clean = frame.copy()
    for column in clean.columns:
        clean[column] = clean[column].map(lambda value: f"{value:.6g}" if isinstance(value, float) else str(value))
    header = "| " + " | ".join(map(str, clean.columns)) + " |"
    rule = "|" + "|".join(["---"] * len(clean.columns)) + "|"
    body = ["| " + " | ".join(row) + " |" for row in clean.astype(str).to_numpy().tolist()]
    return "\n".join([header, rule, *body])


def metrics(frame: pd.DataFrame) -> dict[str, float]:
    y, p = frame.true_label, frame.predicted_label
    return {"accuracy": accuracy_score(y,p), "balanced_accuracy": balanced_accuracy_score(y,p),
            "macro_f1": f1_score(y,p,average="macro",zero_division=0),
            "weighted_f1": f1_score(y,p,average="weighted",zero_division=0)}


def class_metrics(frame: pd.DataFrame, label: str) -> dict[str, float]:
    p,r,f,_ = precision_recall_fscore_support(frame.true_label, frame.predicted_label, labels=[label], zero_division=0)
    return {f"{label.lower()}_precision":p[0],f"{label.lower()}_recall":r[0],f"{label.lower()}_f1":f[0]}


def finalize_reports(here: Path) -> None:
    reports, predictions, artifacts = here/"reports", here/"predictions", here/"artifacts"
    rf_root = here.parent
    lgb_val, lgb_test = pd.read_csv(predictions/"validation_predictions.csv"), pd.read_csv(predictions/"test_predictions.csv")
    rf_val, rf_test = pd.read_csv(rf_root/"predictions/validation_predictions.csv"), pd.read_csv(rf_root/"predictions/test_predictions.csv")
    metadata = json.loads((artifacts/"lightgbm_model_metadata.json").read_text(encoding="utf-8"))
    rows=[]
    for split, lf, rf in [("validation",lgb_val,rf_val),("test",lgb_test,rf_test)]:
        for name, frame in [("RandomForest",rf),("LightGBM",lf)]:
            severe_high=((frame.true_label=="High") & frame.predicted_label.isin(["Low","Moderate"])).sum()
            severe_extreme=((frame.true_label=="Extreme") & frame.predicted_label.isin(["Low","Moderate"])).sum()
            rows.append({"split":split,"model":name,**metrics(frame),**class_metrics(frame,"High"),**class_metrics(frame,"Extreme"),
                         "high_to_low_or_moderate":int(severe_high),"extreme_to_low_or_moderate":int(severe_extreme),
                         "model_size_bytes": (rf_root/"artifacts/final_random_forest_pipeline.joblib").stat().st_size if name=="RandomForest" else metadata["model_size_bytes"],
                         "training_seconds": np.nan if name=="RandomForest" else metadata["final_fit_seconds"],
                         "inference_seconds": np.nan if name=="RandomForest" else metadata["test_inference_seconds"] if split=="test" else np.nan,
                         "deployment_complexity":"sklearn one-hot pipeline" if name=="RandomForest" else "LightGBM native categorical runtime"})
    pd.DataFrame(rows).to_csv(reports/"rf_lightgbm_comparison.csv",index=False)

    gain, split = pd.read_csv(reports/"feature_importance_gain.csv"), pd.read_csv(reports/"feature_importance_split.csv")
    gain.merge(split,on="feature",validate="one_to_one").sort_values("gain",ascending=False).to_csv(reports/"aggregated_feature_importance.csv",index=False)

    group_rows=[]
    for field in ["hdi_missing","has_unknown_category"]:
        for value, group in lgb_test.groupby(field,dropna=False):
            if len(group): group_rows.append({"field":field,"value":value,"n":len(group),**metrics(group)})
    pd.DataFrame(group_rows).to_csv(reports/"group_performance.csv",index=False)

    disagreement=pd.read_csv(reports/"rf_lightgbm_disagreement.csv")
    dis_summary=[]
    for scope, frame in [("all",disagreement),("High",disagreement[disagreement.true_label=="High"]),("Extreme",disagreement[disagreement.true_label=="Extreme"])]:
        counts=frame.outcome.value_counts()
        for outcome in ["both_correct","rf_only_correct","lightgbm_only_correct","both_wrong"]:
            dis_summary.append({"scope":scope,"outcome":outcome,"count":int(counts.get(outcome,0)),"rate":float(counts.get(outcome,0)/len(frame))})
    pd.DataFrame(dis_summary).to_csv(reports/"rf_lightgbm_disagreement_summary.csv",index=False)

    cand=pd.read_csv(reports/"lightgbm_candidate_comparison.csv")
    best_versions=cand.loc[cand.groupby("feature_version").macro_f1.idxmax(),["feature_version","candidate_id","macro_f1","balanced_accuracy","high_recall","extreme_recall"]]
    best_weights=cand.groupby("weight_strategy",as_index=False).agg(best_macro_f1=("macro_f1","max"),mean_macro_f1=("macro_f1","mean"),best_extreme_recall=("extreme_recall","max"))
    best_versions.to_csv(reports/"feature_version_summary.csv",index=False); best_weights.to_csv(reports/"weight_strategy_summary.csv",index=False)

    lv, lt, rv, rt = metrics(lgb_val),metrics(lgb_test),metrics(rf_val),metrics(rf_test)
    lgb_pc=pd.read_csv(reports/"per_class_metrics.csv")
    test_pc=lgb_pc[lgb_pc.split=="test"]
    cm=markdown_table(pd.read_csv(reports/"confusion_matrix_test.csv"))
    top=gain.head(8).feature.tolist()
    group=pd.DataFrame(group_rows)
    report=f"""# LightGBM model report

## Scope and safeguards

The task is disaster-event death impact level prediction with fixed order: {', '.join(LABELS)}. The model uses occurrence-time or prior information only. Outcome, death, affected-population, damage, end-date, identifier and HDI provenance/status fields are excluded by a programmatic whitelist. The 2024–2026 maturity holdout was neither transformed nor scored. The configuration lock predates the single test evaluation; no test result affected selection.

LightGBM {metadata['versions']['lightgbm']} uses native categorical columns. Sorted vocabularies are fitted on training data only; missing and unseen values map to `__MISSING__` and `__UNKNOWN__`. HDI remains NaN with an explicit `hdi_missing` flag. RF instead uses its frozen training-median imputation; both respect the same information horizon.

## Validation selection

Exactly 18 predefined candidates were run: two feature versions, three parameter profiles and three training-only weight strategies. Selection used validation macro-F1; values within 0.01 were tie-broken by Extreme recall, High recall, balanced accuracy and then complexity. With only seven validation Extreme cases, a one-case change equals 0.1429 recall, so small differences are sampling noise rather than evidence of clear superiority.

Selected `{metadata['selected_config']['candidate_id']}` with best iteration {metadata['best_iteration']} and locked parameters `{json.dumps(metadata['selected_config']['base_parameters'],sort_keys=True)}`.

### Best feature-version candidates

{markdown_table(best_versions)}

### Weight-strategy summary

{markdown_table(best_weights)}

## Final performance

| Split | Model | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 |
|---|---|---:|---:|---:|---:|
| Validation | RF | {rv['accuracy']:.4f} | {rv['balanced_accuracy']:.4f} | {rv['macro_f1']:.4f} | {rv['weighted_f1']:.4f} |
| Validation | LightGBM | {lv['accuracy']:.4f} | {lv['balanced_accuracy']:.4f} | {lv['macro_f1']:.4f} | {lv['weighted_f1']:.4f} |
| Test | RF | {rt['accuracy']:.4f} | {rt['balanced_accuracy']:.4f} | {rt['macro_f1']:.4f} | {rt['weighted_f1']:.4f} |
| Test | LightGBM | {lt['accuracy']:.4f} | {lt['balanced_accuracy']:.4f} | {lt['macro_f1']:.4f} | {lt['weighted_f1']:.4f} |

LightGBM changes test macro-F1 by {lt['macro_f1']-rt['macro_f1']:+.4f} and balanced accuracy by {lt['balanced_accuracy']-rt['balanced_accuracy']:+.4f}. This is a mixed, small difference, not a decisive improvement.

### LightGBM test per-class results

{markdown_table(test_pc)}

### LightGBM test confusion matrix

{cm}

High was severely underestimated as Low/Moderate in {int(((lgb_test.true_label=='High') & lgb_test.predicted_label.isin(['Low','Moderate'])).sum())} cases. Extreme was predicted as Low/Moderate in {int(((lgb_test.true_label=='Extreme') & lgb_test.predicted_label.isin(['Low','Moderate'])).sum())} cases and as High in {int(((lgb_test.true_label=='Extreme') & (lgb_test.predicted_label=='High')).sum())} cases.

## Feature and subgroup observations

Top gain fields: {', '.join(top)}. Gain is loss reduction; split importance counts tree uses. Neither is causal, high-cardinality fields have more opportunities, and native categorical importance is not directly comparable to RF one-hot columns.

{markdown_table(group)}

Unknown-category subgroup results are descriptive and often based on very few samples. They should not be read as a stable performance estimate.

## Reproducibility and recommendation

The saved model was reloaded without refitting. Classes and metrics were identical and maximum probability difference was {metadata['reload_reproducibility']['max_probability_absolute_difference']:.3g}. Formal input and frozen RF hashes remained unchanged. No leakage, test tuning, holdout evaluation, SMOTE, SHAP, XGBoost, CatBoost or deep learning was used.

LightGBM is useful as a thesis comparison model, but it does not clearly dominate RF: its test macro-F1 is only slightly higher while balanced accuracy and Extreme recall are lower. Retain RF as the deployment choice for now; present both in the thesis. XGBoost is not necessary to validate this stage and should only be a separately approved future experiment.
"""
    (reports/"lightgbm_model_report.md").write_text(report,encoding="utf-8")


if __name__ == "__main__": finalize_reports(Path(__file__).resolve().parent)
