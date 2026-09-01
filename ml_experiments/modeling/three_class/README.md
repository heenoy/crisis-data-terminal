# Three-class T0-T3 Random Forest experiment

This isolated stage compares four feature versions using the frozen Random
Forest configuration. Models fit 2000–2019 and transform/evaluate 2020–2021.
The script audits only event IDs, years and three-class label counts for
2022–2023 and 2024–2026; it never constructs their feature frames or produces
predictions, probabilities, metrics, or confusion matrices.

```powershell
& '..\..\disaster_impact_prediction\.venv\Scripts\python.exe' .\run_t0_t3_random_forest.py
```

T0 is the frozen RF-V2 base. T1 adds frozen lagged World Bank values, T2 adds
training-only semantic-group Magnitude robust z features, and T3 adds both.
No final Train+Validation refit is performed in this stage.
