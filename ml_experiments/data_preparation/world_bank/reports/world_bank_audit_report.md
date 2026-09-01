# World Bank Indicators download and matching audit

- API: World Bank Indicators API v2
- Download window: 1999-2023
- Run started (UTC): 2026-08-04T07:29:24.393248+00:00
- Run completed (UTC): 2026-08-04T07:29:25.265424+00:00
- EM-DAT input: `data/processed_hdro/disaster_hdi_merged.csv`
- EM-DAT input SHA-256: `075738f8debb621dca42c8fc1d9f940a7078ed54377f00fe78f7fd09fe9c4caa`

## Indicators

- `SP.POP.TOTL`: Population, total
- `NY.GDP.PCAP.PP.KD`: GDP per capita, PPP (constant international $)

## Country entity audit

World Bank metadata returned 295 entities. 78 aggregate entities were excluded using the observed metadata marker `region.id == NA` / `region.value == Aggregates`; 217 countries/economies remained.
EM-DAT contains 223 unique ISO3 codes: 205 exact World Bank economy matches and 18 unsupported codes. No country-name fallback was applied.

## Matching rule

For an event in year t, the target observation is t-1. If absent, the search proceeds only backward through t-2, t-3 and t-4 (maximum backtrack value 3). Future observations are forbidden. No imputation statistic is fitted.

## Event matching

- `SP.POP.TOTL`: matched 16,694/16,858 (99.03%); exact t-1 16,001; historical backtracks 693; unmatched 164.
- `NY.GDP.PCAP.PP.KD`: matched 16,319/16,858 (96.80%); exact t-1 15,643; historical backtracks 676; unmatched 539.

## Reproducibility and limitations

Raw JSON responses are preserved unchanged in the experiment directory. `manifest.json` records request URLs, timestamps and SHA-256 values for every generated artifact.
World Bank indicator values can be revised retrospectively. This snapshot represents the API response captured at the recorded time. Missing observations remain missing when the permitted historical window contains no value.
Existing raw/processed data, preparation scripts, Random Forest artifacts and LightGBM artifacts were hash-checked before and after and were not modified.
