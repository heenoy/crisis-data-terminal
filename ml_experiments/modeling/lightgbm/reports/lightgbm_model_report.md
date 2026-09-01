# LightGBM model report

## Scope and safeguards

The task is disaster-event death impact level prediction with fixed order: Low, Moderate, High, Extreme. The model uses occurrence-time or prior information only. Outcome, death, affected-population, damage, end-date, identifier and HDI provenance/status fields are excluded by a programmatic whitelist. The 2024–2026 maturity holdout was neither transformed nor scored. The configuration lock predates the single test evaluation; no test result affected selection.

LightGBM 4.6.0 uses native categorical columns. Sorted vocabularies are fitted on training data only; missing and unseen values map to `__MISSING__` and `__UNKNOWN__`. HDI remains NaN with an explicit `hdi_missing` flag. RF instead uses its frozen training-median imputation; both respect the same information horizon.

## Validation selection

Exactly 18 predefined candidates were run: two feature versions, three parameter profiles and three training-only weight strategies. Selection used validation macro-F1; values within 0.01 were tie-broken by Extreme recall, High recall, balanced accuracy and then complexity. With only seven validation Extreme cases, a one-case change equals 0.1429 recall, so small differences are sampling noise rather than evidence of clear superiority.

Selected `LGBM-V2_P3_low_rate_balanced` with best iteration 291 and locked parameters `{"colsample_bytree": 0.7, "learning_rate": 0.03, "max_depth": -1, "min_child_samples": 20, "n_estimators": 800, "num_leaves": 63, "reg_alpha": 0.1, "reg_lambda": 5, "subsample": 0.8}`.

### Best feature-version candidates

| feature_version | candidate_id | macro_f1 | balanced_accuracy | high_recall | extreme_recall |
|---|---|---|---|---|---|
| LGBM-V1 | LGBM-V1_P3_low_rate_balanced | 0.46556 | 0.494658 | 0.166667 | 0.285714 |
| LGBM-V2 | LGBM-V2_P3_low_rate_balanced | 0.489817 | 0.500571 | 0.190476 | 0.285714 |

### Weight-strategy summary

| weight_strategy | best_macro_f1 | mean_macro_f1 | best_extreme_recall |
|---|---|---|---|
| balanced | 0.489817 | 0.471708 | 0.285714 |
| mild_sqrt | 0.457125 | 0.443622 | 0.285714 |
| none | 0.378952 | 0.374191 | 0 |

## Final performance

| Split | Model | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 |
|---|---|---:|---:|---:|---:|
| Validation | RF | 0.6853 | 0.5389 | 0.4825 | 0.6903 |
| Validation | LightGBM | 0.7164 | 0.5006 | 0.4898 | 0.7157 |
| Test | RF | 0.6487 | 0.5890 | 0.5244 | 0.6605 |
| Test | LightGBM | 0.6709 | 0.5397 | 0.5306 | 0.6759 |

LightGBM changes test macro-F1 by +0.0061 and balanced accuracy by -0.0493. This is a mixed, small difference, not a decisive improvement.

### LightGBM test per-class results

| split | class | precision | recall | f1 | support |
|---|---|---|---|---|---|
| test | Low | 0.575949 | 0.895082 | 0.700899 | 305 |
| test | Moderate | 0.925287 | 0.614504 | 0.738532 | 524 |
| test | High | 0.299065 | 0.367816 | 0.329897 | 87 |
| test | Extreme | 0.473684 | 0.28125 | 0.352941 | 32 |

### LightGBM test confusion matrix

| true_label | Low | Moderate | High | Extreme |
|---|---|---|---|---|
| Low | 273 | 12 | 19 | 1 |
| Moderate | 149 | 322 | 48 | 5 |
| High | 37 | 14 | 32 | 4 |
| Extreme | 15 | 0 | 8 | 9 |

High was severely underestimated as Low/Moderate in 51 cases. Extreme was predicted as Low/Moderate in 15 cases and as High in 8 cases.

## Feature and subgroup observations

Top gain fields: country_code, disaster_subtype, historical_frequency, hdi, disaster_type, year, event_month, region. Gain is loss reduction; split importance counts tree uses. Neither is causal, high-cardinality fields have more opportunities, and native categorical importance is not directly comparable to RF one-hot columns.

| field | value | n | accuracy | balanced_accuracy | macro_f1 | weighted_f1 |
|---|---|---|---|---|---|---|
| hdi_missing | 0 | 938 | 0.66951 | 0.539357 | 0.529977 | 0.674845 |
| hdi_missing | 1 | 10 | 0.8 | 0.75 | 0.761905 | 0.780952 |
| has_unknown_category | False | 947 | 0.671595 | 0.540399 | 0.53122 | 0.676327 |
| has_unknown_category | True | 1 | 0 | 0 | 0 | 0 |

Unknown-category subgroup results are descriptive and often based on very few samples. They should not be read as a stable performance estimate.

## Reproducibility and recommendation

The saved model was reloaded without refitting. Classes and metrics were identical and maximum probability difference was 0. Formal input and frozen RF hashes remained unchanged. No leakage, test tuning, holdout evaluation, SMOTE, SHAP, XGBoost, CatBoost or deep learning was used.

LightGBM is useful as a thesis comparison model, but it does not clearly dominate RF: its test macro-F1 is only slightly higher while balanced accuracy and Extreme recall are lower. Retain RF as the deployment choice for now; present both in the thesis. XGBoost is not necessary to validate this stage and should only be a separately approved future experiment.
