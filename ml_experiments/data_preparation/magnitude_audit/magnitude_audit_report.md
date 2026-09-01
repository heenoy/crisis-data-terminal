# EM-DAT Magnitude scale audit

## Scope and integrity

- Input: `data/emdat_raw.xlsx` (`EM-DAT Data`)
- Input SHA-256: `f7c4993adcc8eeecf8806fb68cd0426649ea320482a7ac6636fbfd01fa9afe45`
- Current event/time reference: `data/processed_hdro/disaster_hdi_merged.csv`
- Reference SHA-256: `075738f8debb621dca42c8fc1d9f940a7078ed54377f00fe78f7fd09fe9c4caa`
- Audit time (UTC): 2026-08-04T07:39:26.652104+00:00
- Events: 16,858; event IDs are unique and map one-to-one to the current dataset.
- `Start Year` differs from current `year` for 0 events.
- No death, impact, damage, affected-population, or target-label field was read.

## Overall completeness

- Non-missing Magnitude: 3,392 (20.12%)
- Missing Magnitude: 13,466 (79.88%)
- Non-numeric nonblank Magnitude: 0
- Non-missing Magnitude with missing scale: 0
- Scale present but Magnitude missing: 7,198

## Semantic findings

`Km2` crosses Drought, Flood and Wildfire. The physical unit is consistent, but the phenomenon differs, so it must be separated by disaster type. `Kph` is confined to Storm and represents wind speed. `Moment Magnitude` is confined to Earthquake. `°C` is confined to Extreme temperature but mixes heat and cold: a higher signed temperature has opposite severity meaning for cold events, so type-level pooling is unsafe and subtype separation is required. `Vaccinated` is a response/intervention count and is excluded as potential post-event information. `m3` has only three non-missing values across heterogeneous accidents and is excluded.

## Recommended grouping design

Use a semantic hybrid group key:

1. `disaster_type + magnitude_scale` for `Km2`, `Kph`, and `Moment Magnitude`.
2. `disaster_subtype + magnitude_scale` for `°C`, keeping Heat wave, Cold wave and Severe winter conditions separate.
3. Do not standardize `Vaccinated`, `m3`, missing scales, training groups with fewer than 20 valid values, zero/undefined training IQR, or unknown groups.

The audit identifies 8 recommended groups. Based solely on training-period eligibility, 3,369/3,392 non-missing observations (99.32%) and 3,369/16,858 all events (19.98%) could receive a future robust-z value. This is a prospective coverage audit, not a transformed feature.

## Leakage-safe future transformation contract

During a future experiment, fit group vocabularies, medians and IQRs on 2000–2019 training rows only. Transform validation/test without updating categories or statistics:

`magnitude_robust_z = clip((magnitude - training_group_median) / training_group_IQR, -5, 5)`

- Keep `magnitude_missing` and `magnitude_group_unknown`.
- Raw `magnitude` must not enter the formal model.
- Missing magnitude, unknown groups, training count below 20, or zero/undefined training IQR produce no standardized value.
- Validation, test and maturity-holdout rows never supplement training groups or statistics.
- The descriptive full-data medians/IQRs in the audit CSV are diagnostics only and must never be reused as model parameters.

## Limitations

Magnitude is populated for only 20.12% of events, and scale presence does not imply value presence. Robust scaling improves comparability within a semantic group but does not make different physical quantities equivalent and does not establish causality. Temperature remains a signed physical measurement; subtype separation avoids direct heat/cold pooling but does not convert temperature into hazard severity.
