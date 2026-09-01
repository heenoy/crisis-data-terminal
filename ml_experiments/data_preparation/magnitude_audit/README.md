# Magnitude scale audit

This isolated audit reads the frozen EM-DAT workbook and current event/year
mapping. It describes Magnitude completeness, scale semantics, robust group
statistics, training-period eligibility, and unsupported groups. It does not
create standardized feature values and does not read targets or outcome fields.

Run with the project experiment environment:

```powershell
& '..\..\disaster_impact_prediction\.venv\Scripts\python.exe' .\audit_magnitude.py
```

All outputs remain in this directory. Full-data medians and IQRs are audit-only;
future feature transformers must fit group statistics on 2000–2019 training
rows and transform later periods without expanding group vocabularies.
