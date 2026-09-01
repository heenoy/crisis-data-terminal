# Final locked T2 three-class Random Forest report

Generated: 2026-08-04T09:12:44.986309+00:00

## Scope and integrity

- Development: 2000-2021, 11,590 labeled events; Test: 2022-2023, 948 labeled events.
- T2 was locked before Test access. No World Bank features or raw Magnitude entered the model.
- Maturity 2024-2026 was discarded at input filtering and never entered a feature frame; predictions/probabilities/metrics: 0/0/0.
- Test received transform/predict only. All fitted statistics and vocabularies came from Development.

## Final features

country_code, region, disaster_type, disaster_subtype, date_granularity, year, date_imputed, historical_frequency, hdi, hdi_missing, event_month, month_missing, magnitude_robust_z, magnitude_missing, magnitude_group_unknown

## Metrics

| Split | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 | QWK | Severe->Low | Low->Severe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 0.716825 | 0.747000 | 0.649183 | 0.733864 | 0.541429 | 104 | 176 |
| Test | 0.715190 | 0.713700 | 0.681101 | 0.717867 | 0.543424 | 31 | 14 |

Test minus locked T2 Validation: accuracy -0.008691, balanced accuracy +0.077459, macro F1 +0.064627, weighted F1 -0.003112. These are descriptive differences only; no post-Test tuning was performed.

## Test confusion matrix

Rows are true classes and columns are predicted classes in fixed order Low, Moderate, Severe.

| True \ Predicted | Low | Moderate | Severe |
|---|---:|---:|---:|
| Low | 277 | 14 | 14 |
| Moderate | 147 | 329 | 48 |
| Severe | 31 | 16 | 72 |

## Reproducibility

The saved model was reloaded and predictions repeated. Class predictions and metrics were identical; maximum Test probability difference was 3.33e-16.
