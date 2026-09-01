# World Bank indicator snapshot and audit

This isolated experiment downloads World Bank Indicators API v2 data for
`SP.POP.TOTL` and `NY.GDP.PCAP.PP.KD` over 1999–2023. It excludes aggregate
entities using World Bank country metadata, matches EM-DAT by exact ISO3 code,
and audits event-year availability using only `t-1` and up to three earlier
years.

It does not alter the project data directories, preparation pipeline, or model
artifacts. Run with the project experiment Python environment:

```powershell
& '..\..\disaster_impact_prediction\.venv\Scripts\python.exe' .\fetch_and_audit_world_bank.py
```

Raw API responses are in `raw/`; cleaned tables are in this directory; audit
tables and the narrative report are in `reports/`; request URLs, timestamps,
hashes, and quality checks are in `manifest.json`.
