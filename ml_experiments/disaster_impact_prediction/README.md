# Disaster Impact Prediction Experiment

Independent Python experiment for predicting EM-DAT `Total Deaths`. It does not
import or modify the Vite frontend.

## Leakage policy

The model only uses fields plausibly available before or near event onset:

- hazard hierarchy: group, subgroup, type, subtype
- geography: ISO, country, subregion, region, latitude, longitude
- time: start year, month, day
- hazard intensity: magnitude and magnitude scale

Same-event outcomes such as injured, affected, homeless, aid contribution,
damage, and reconstruction cost are excluded. These fields correlate with
deaths but would normally be unknown when an early prediction is requested.

Missing numeric values use train-set medians and missing indicators. Categorical
values use the train-set most frequent value, then one-hot encoding with rare
category grouping. Numeric feature outliers are clipped using train-only
three-IQR bounds. The target is modeled as `log1p(Total Deaths)` and converted
back to the original scale for MAE, RMSE, R², and output.

The 90% prediction interval uses calibration residual quantiles from a held-out
portion of the training set. The test set is never used to construct the
interval.

## Setup

```powershell
cd ml_experiments/disaster_impact_prediction
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Train

```powershell
.\.venv\Scripts\python train.py
```

Use `--skip-xgboost` when XGBoost is unavailable, or `--quick` for a smoke test.

Generated artifacts:

- `artifacts/training_report.json`
- `artifacts/field_analysis.csv`
- `artifacts/*_prediction_samples.csv`
- `artifacts/*_feature_importance.csv`
- `artifacts/*_feature_importance.png`
- `artifacts/models/*.joblib`

## Predict one event

```powershell
.\.venv\Scripts\python predict.py `
  --model artifacts/models/random_forest.joblib `
  --input example_event.json
```

For website integration, expose prediction through a Python API service rather
than loading model binaries in the browser. The Vite application can call that
service, while Supabase stores model metadata, versions, and prediction history.
