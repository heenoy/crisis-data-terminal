# LightGBM temporal experiment

This directory is isolated from the frozen Random Forest baseline. It reads
`data/processed_hdro/disaster_model_ready.csv`, uses the fixed temporal split,
selects among 18 predefined LightGBM candidates on 2020–2021 only, locks the
configuration, refits on 2000–2021, and evaluates 2022–2023 once. The
2024–2026 maturity holdout is never transformed or scored.

Run with the project experiment environment:

```powershell
& '..\..\disaster_impact_prediction\.venv\Scripts\python.exe' .\train_lightgbm.py
```

All artifacts, reports, and predictions remain under this directory. The
script verifies the formal input and selected frozen RF files are unchanged,
and verifies saved-model predictions after reload without refitting.
