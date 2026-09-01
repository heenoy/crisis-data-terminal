# Final T2 three-class Random Forest

This directory contains the locked T2 Development (2000–2021) refit and the single formal out-of-time Test (2022–2023) evaluation. It does not use World Bank features and does not read, transform, predict, or evaluate the 2024–2026 maturity holdout.

Run from the project root with the project Python environment:

```powershell
.\ml_experiments\disaster_impact_prediction\.venv\Scripts\python.exe .\ml_experiments\modeling\three_class\final_t2\train_final_t2.py
```

The script verifies frozen inputs, uses only the fixed T2 allowlist, fits all preprocessing and Magnitude statistics on Development, evaluates Test without refitting, saves the model, and verifies reproducibility by reloading it and repeating predictions.
