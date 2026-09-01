# Three-class Random Forest T0-T3 train/validation report

## Integrity and scope

- Task labels are fixed from `total_deaths`: Low 0-9, Moderate 10-99, Severe >=100.
- Event IDs are unique. Train and validation do not overlap.
- Models are fitted on 2000-2019 only and evaluated on 2020-2021 only.
- 2022-2023 and 2024-2026 were used solely for label-count integrity; no feature frame, transform, prediction, probability, metric, or confusion matrix was produced for either set.
- The frozen four-class RF parameters are reused exactly. Only label names/class cardinality and internally derived `balanced_subsample` weights necessarily differ.

## Label distribution

- train: labeled 10,786; Low 2,464, Moderate 7,439, Severe 883; missing label 2,459.
- validation: labeled 804; Low 322, Moderate 433, Severe 49; missing label 299.
- test_label_audit_only: labeled 948; Low 305, Moderate 524, Severe 119; missing label 258.
- maturity_label_audit_only: labeled 1,044; Low 302, Moderate 633, Severe 109; missing label 260.

## Feature versions

- T0: frozen RF-V2 no-leakage base features.
- T1: T0 + lagged World Bank population/GDP log features and missing indicators.
- T2: T0 + training-only semantic-group Magnitude robust z and missing/unknown indicators.
- T3: T0 + both approved increments.

World Bank match years, backtrack fields and status text are audit metadata only and never enter a model. Raw Magnitude never enters a model. `magnitude_robust_z` is only a within-semantic-group relative position and must not be interpreted uniformly as “larger means more severe”.

## Validation results

- T0: accuracy 0.7239, balanced accuracy 0.6231, macro-F1 0.6041, weighted-F1 0.7225, Severe P/R/F1 0.2909/0.3265/0.3077, Severe->Low 17, QWK 0.5100.
- T1: accuracy 0.7177, balanced accuracy 0.6256, macro-F1 0.6023, weighted-F1 0.7162, Severe P/R/F1 0.2881/0.3469/0.3148, Severe->Low 16, QWK 0.5178.
- T2: accuracy 0.7239, balanced accuracy 0.6362, macro-F1 0.6165, weighted-F1 0.7210, Severe P/R/F1 0.3396/0.3673/0.3529, Severe->Low 17, QWK 0.5250.
- T3: accuracy 0.7276, balanced accuracy 0.6315, macro-F1 0.6161, weighted-F1 0.7252, Severe P/R/F1 0.3400/0.3469/0.3434, Severe->Low 16, QWK 0.5187.

The fixed selection hierarchy recommends **T2** for configuration lock. This is a validation-only feature decision; no final Train+Validation refit or Test prediction has been performed.

## Reproducibility

Each pipeline, feature order, category vocabulary, numeric imputer statistics, Magnitude training vocabulary/statistics, validation prediction and confusion matrix is saved independently. Reloaded pipelines reproduce validation class predictions exactly. `manifest.json` records SHA-256 values. Frozen data, RF, LightGBM, World Bank and Magnitude-audit artifacts were hash-checked before and after and were unchanged.
