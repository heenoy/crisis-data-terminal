"""Download and audit World Bank population and GDP-per-capita indicators.

All writes stay below this script's directory. Existing data and model artifacts
are hashed before and after the run and are never modified.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import argparse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
REPORTS = HERE / "reports"
EMDAT = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
START_YEAR, END_YEAR = 1999, 2023
INDICATORS = {
    "SP.POP.TOTL": "Population, total",
    "NY.GDP.PCAP.PP.KD": "GDP per capita, PPP (constant international $)",
}
BASE = "https://api.worldbank.org/v2"
COUNTRY_URL = f"{BASE}/country?format=json&per_page=400"
INDICATOR_URLS = {
    code: f"{BASE}/country/all/indicator/{code}?date={START_YEAR}:{END_YEAR}&format=json&per_page=20000"
    for code in INDICATORS
}
TIMEOUT = (10, 90)
MAX_ATTEMPTS = 3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    paths: list[Path] = []
    for relative in ["data/raw", "data/processed", "data/processed_hdro", "ml_experiments/modeling"]:
        base = ROOT / relative
        if base.exists():
            paths.extend(path for path in base.rglob("*") if path.is_file())
    prep = ROOT / "ml_experiments/data_preparation"
    paths.extend(path for path in prep.glob("*") if path.is_file())
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in sorted(set(paths))}


def request_json(url: str) -> tuple[Any, dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Crisis-Data-Terminal/WorldBank-Audit"})
            with urllib.request.urlopen(request, timeout=TIMEOUT[1]) as response:
                body = response.read()
                status = int(response.status)
                final_url = response.url
                content_type = response.headers.get("Content-Type")
            payload = json.loads(body.decode("utf-8-sig"))
            return payload, {
                "request_url": final_url,
                "downloaded_at_utc": utc_now(),
                "http_status": status,
                "content_type": content_type,
                "attempts": attempt,
            }
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                if attempt < MAX_ATTEMPTS:
                    time.sleep(2 ** (attempt - 1))
                    continue
            raise RuntimeError(f"World Bank API HTTP failure after {attempt} attempts: status={exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError, UnicodeError) as exc:
            last_error = exc
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"World Bank API request failed after {attempt} attempts: {type(exc).__name__}") from exc
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError("World Bank API request failed") from last_error


def validate_envelope(payload: Any, endpoint: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, list) or len(payload) != 2:
        raise RuntimeError(f"Unexpected World Bank response envelope for {endpoint}")
    metadata, records = payload
    if not isinstance(metadata, dict) or not isinstance(records, list):
        raise RuntimeError(f"Unexpected World Bank response types for {endpoint}")
    required_meta = {"page", "pages", "per_page", "total"}
    if not required_meta.issubset(metadata):
        raise RuntimeError(f"World Bank response metadata missing fields for {endpoint}: {sorted(required_meta-set(metadata))}")
    if int(metadata["pages"]) != 1 or int(metadata["page"]) != 1:
        raise RuntimeError(f"Response pagination was not fully captured for {endpoint}: {metadata}")
    if int(metadata["total"]) != len(records):
        raise RuntimeError(f"Response appears truncated for {endpoint}: total={metadata['total']} records={len(records)}")
    return metadata, records


def validate_country(record: dict[str, Any]) -> None:
    required = {"id", "iso2Code", "name", "region", "incomeLevel", "lendingType", "capitalCity"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise RuntimeError("World Bank country metadata record structure changed")
    if not isinstance(record["region"], dict) or "id" not in record["region"] or "value" not in record["region"]:
        raise RuntimeError("World Bank country region structure changed")


def validate_indicator(record: dict[str, Any], expected_code: str) -> None:
    required = {"indicator", "country", "countryiso3code", "date", "value"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise RuntimeError(f"World Bank indicator record structure changed for {expected_code}")
    if not isinstance(record["indicator"], dict) or record["indicator"].get("id") != expected_code:
        raise RuntimeError(f"Unexpected indicator code in {expected_code} response")
    if not isinstance(record["country"], dict) or "value" not in record["country"]:
        raise RuntimeError(f"World Bank country field structure changed for {expected_code}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-snapshot", action="store_true", help="Rebuild cleaned/audit outputs without network access")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    emdat_hash = sha256(EMDAT)
    run_started = utc_now()
    previous_manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8")) if args.from_snapshot and (HERE / "manifest.json").exists() else None
    manifest: dict[str, Any] = {
        "run_started_utc": run_started,
        "api": "World Bank Indicators API v2",
        "year_range": [START_YEAR, END_YEAR],
        "requests": previous_manifest["requests"] if previous_manifest else [],
        "indicators": [{"code": code, "name": name} for code, name in INDICATORS.items()],
        "input": {"path": str(EMDAT.relative_to(ROOT)).replace("\\", "/"), "sha256": emdat_hash},
    }
    if args.from_snapshot:
        country_payload = json.loads((RAW / "world_bank_countries_response.json").read_text(encoding="utf-8"))
    else:
        country_payload, country_request = request_json(COUNTRY_URL)
    _, country_records = validate_envelope(country_payload, "countries")
    for record in country_records:
        validate_country(record)
    country_raw = RAW / "world_bank_countries_response.json"
    if not args.from_snapshot:
        write_json(country_raw, country_payload)
        country_request.update(endpoint="Countries", file=str(country_raw.relative_to(ROOT)).replace("\\", "/"), sha256=sha256(country_raw))
        manifest["requests"].append(country_request)

    response_records: dict[str, list[dict[str, Any]]] = {}
    for code, url in INDICATOR_URLS.items():
        raw_path = RAW / ("population_response.json" if code == "SP.POP.TOTL" else "gdp_per_capita_ppp_response.json")
        if args.from_snapshot:
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            payload, request_info = request_json(url)
        _, records = validate_envelope(payload, code)
        for record in records:
            validate_indicator(record, code)
        if not args.from_snapshot:
            write_json(raw_path, payload)
            request_info.update(endpoint="Indicators", indicator_code=code, indicator_name=INDICATORS[code],
                                file=str(raw_path.relative_to(ROOT)).replace("\\", "/"), sha256=sha256(raw_path))
            manifest["requests"].append(request_info)
        response_records[code] = records

    countries = []
    for record in country_records:
        countries.append({
            "country_code": str(record["id"]).strip(), "country_name": record["name"],
            "iso2_code": record["iso2Code"], "region_code": record["region"]["id"],
            "region_name": record["region"]["value"], "income_level": record["incomeLevel"].get("value"),
            "lending_type": record["lendingType"].get("value"), "capital_city": record["capitalCity"],
            "is_aggregate": str(record["region"]["id"]).strip().upper() == "NA" or str(record["region"]["value"]).strip().lower() == "aggregates",
        })
    country_df = pd.DataFrame(countries)
    economies = country_df[~country_df.is_aggregate].copy()
    if economies.country_code.duplicated().any() or not economies.country_code.str.fullmatch(r"[A-Z]{3}").all():
        raise RuntimeError("World Bank economy ISO3 metadata is non-unique or malformed")
    country_df.to_csv(HERE / "world_bank_country_metadata.csv", index=False)

    annual_rows = []
    for code, records in response_records.items():
        for record in records:
            iso3 = str(record["countryiso3code"] or "").strip()
            if iso3 not in set(economies.country_code):
                continue
            try:
                year = int(record["date"])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"Unparseable year in {code} response") from exc
            if not START_YEAR <= year <= END_YEAR:
                raise RuntimeError(f"Unexpected year {year} in {code} response")
            value = pd.to_numeric(record["value"], errors="coerce") if record["value"] is not None else float("nan")
            if record["value"] is not None and pd.isna(value):
                raise RuntimeError(f"Unparseable value in {code} response for {iso3} {year}")
            annual_rows.append({"country_code": iso3, "country_name": record["country"]["value"],
                                "year": year, "indicator_code": code, "indicator_name": INDICATORS[code],
                                "value": value, "source": "World Bank Indicators API"})
    annual = pd.DataFrame(annual_rows).sort_values(["indicator_code", "country_code", "year"])
    if annual.duplicated(["country_code", "indicator_code", "year"]).any():
        raise RuntimeError("Duplicate country_code + indicator_code + year in cleaned World Bank data")
    annual.to_csv(HERE / "world_bank_indicators_annual.csv", index=False)

    events = pd.read_csv(EMDAT, usecols=["event_id", "country", "country_code", "year"])
    if events.event_id.isna().any() or events.event_id.duplicated().any():
        raise RuntimeError("EM-DAT event_id is null or non-unique")
    event_countries = events[["country_code", "country"]].drop_duplicates()
    country_names = event_countries.groupby("country_code")["country"].agg(lambda values: " | ".join(sorted(set(values.dropna().astype(str)))))
    economy_names = economies.set_index("country_code")["country_name"]
    audit_rows = []
    for code in sorted(events.country_code.dropna().astype(str).unique()):
        format_valid = bool(re.fullmatch(r"[A-Z]{3}", code))
        supported = code in economy_names.index
        issue = "matched" if supported else ("invalid_iso3_format" if not format_valid else "not_in_world_bank_economies")
        audit_rows.append({"country_code": code, "emdat_country_name": country_names.get(code),
                           "world_bank_country_name": economy_names.get(code), "supported_by_world_bank": supported,
                           "issue_type": issue, "notes": "ISO3 exact match" if supported else "No exact ISO3 match; no name-based substitution applied"})
    country_audit = pd.DataFrame(audit_rows)
    country_audit.to_csv(REPORTS / "country_code_audit.csv", index=False)
    country_audit[~country_audit.supported_by_world_bank].to_csv(REPORTS / "unmatched_countries.csv", index=False)

    genuine_count = len(economies)
    coverage_rows = []
    for (code, year), group in annual.groupby(["indicator_code", "year"]):
        available = int(group.value.notna().sum())
        coverage_rows.append({"indicator_code": code, "indicator_name": INDICATORS[code], "year": int(year),
                              "world_bank_economies": genuine_count, "countries_with_value": available,
                              "countries_missing_value": genuine_count - available, "coverage_rate": available / genuine_count})
    coverage = pd.DataFrame(coverage_rows).sort_values(["indicator_code", "year"])
    if len(coverage) != len(INDICATORS) * (END_YEAR - START_YEAR + 1):
        raise RuntimeError("Annual coverage table is incomplete")
    coverage.to_csv(REPORTS / "indicator_yearly_coverage.csv", index=False)

    supported_codes = set(economies.country_code)
    lookup = {(row.country_code, row.indicator_code, int(row.year)): row.value
              for row in annual.itertuples(index=False) if pd.notna(row.value)}
    match_rows = []
    for event in events.itertuples(index=False):
        reference_year = int(event.year) - 1
        for code, name in INDICATORS.items():
            matched_year, value, backtrack = None, None, None
            if event.country_code in supported_codes:
                for years_back in range(4):
                    candidate_year = reference_year - years_back
                    candidate = lookup.get((event.country_code, code, candidate_year))
                    if candidate is not None:
                        matched_year, value, backtrack = candidate_year, float(candidate), years_back
                        break
            if event.country_code not in supported_codes:
                status = "unsupported_country"
            elif matched_year is None:
                status = "missing_within_backtrack_window"
            elif backtrack == 0:
                status = "exact_t_minus_1"
            else:
                status = f"backtracked_{backtrack}_year" + ("s" if backtrack != 1 else "")
            reference_in_range = START_YEAR <= reference_year <= END_YEAR
            if not reference_in_range:
                match_reason = "reference_year_after_download_range" if reference_year > END_YEAR else "reference_year_before_download_range"
            elif matched_year is None:
                match_reason = "no_value_in_permitted_historical_window"
            elif backtrack and backtrack > 0:
                match_reason = "t_minus_1_value_missing"
            else:
                match_reason = "t_minus_1_available"
            match_rows.append({"event_id": event.event_id, "event_year": int(event.year), "country_code": event.country_code,
                               "emdat_country_name": event.country, "indicator_code": code, "indicator_name": name,
                               "reference_year": reference_year, "reference_year_in_download_range": reference_in_range,
                               "matched_year": matched_year, "backtrack_years": backtrack,
                               "value": value, "match_status": status, "match_reason": match_reason})
    matches = pd.DataFrame(match_rows)
    if len(matches) != len(events) * len(INDICATORS) or matches.duplicated(["event_id", "indicator_code"]).any():
        raise RuntimeError("Event-level match output is not one row per event and indicator")
    if ((matches.matched_year.notna()) & (matches.matched_year > matches.reference_year)).any():
        raise RuntimeError("Future-year World Bank value entered event matching")
    if matches.backtrack_years.dropna().gt(3).any():
        raise RuntimeError("Backtracking exceeded three years")
    matches.to_csv(HERE / "event_indicator_matches.csv", index=False)

    summary = matches.groupby(["indicator_code", "indicator_name", "match_status"], dropna=False).size().rename("event_count").reset_index()
    totals = matches.groupby("indicator_code").size().rename("indicator_event_total")
    summary = summary.merge(totals, on="indicator_code", validate="many_to_one")
    summary["event_rate"] = summary.event_count / summary.indicator_event_total
    summary.to_csv(REPORTS / "event_matching_summary.csv", index=False)
    yearly_match = (matches.groupby(["indicator_code", "event_year", "match_status", "match_reason"], dropna=False)
                    .size().rename("event_count").reset_index())
    yearly_totals = matches.groupby(["indicator_code", "event_year"]).size().rename("indicator_year_event_total")
    yearly_match = yearly_match.merge(yearly_totals, on=["indicator_code", "event_year"], validate="many_to_one")
    yearly_match["event_rate"] = yearly_match.event_count / yearly_match.indicator_year_event_total
    yearly_match.to_csv(REPORTS / "event_year_matching_summary.csv", index=False)
    backtrack = matches.groupby(["indicator_code", "backtrack_years"], dropna=False).size().rename("event_count").reset_index()
    backtrack.to_csv(REPORTS / "backtrack_summary.csv", index=False)

    unmatched_events = (matches[matches.match_status.isin(["unsupported_country", "missing_within_backtrack_window"])]
                        .groupby(["indicator_code", "country_code", "emdat_country_name", "match_status"], dropna=False)
                        .size().rename("event_count").reset_index())
    unmatched_events.to_csv(REPORTS / "unmatched_event_countries.csv", index=False)

    manifest["run_completed_utc"] = utc_now()
    manifest["files"] = []
    for path in sorted([p for p in HERE.rglob("*") if p.is_file() and p.name not in {"manifest.json", "world_bank_audit_report.md"} and "__pycache__" not in p.parts]):
        manifest["files"].append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest["quality_checks"] = {
        "emdat_events": len(events), "emdat_unique_iso3": int(events.country_code.nunique()),
        "world_bank_metadata_entities": len(country_df), "world_bank_real_economies": len(economies),
        "aggregate_entities_excluded": int(country_df.is_aggregate.sum()),
        "clean_indicator_rows": len(annual), "event_indicator_rows": len(matches),
        "duplicate_annual_keys": int(annual.duplicated(["country_code", "indicator_code", "year"]).sum()),
        "duplicate_event_indicator_keys": int(matches.duplicated(["event_id", "indicator_code"]).sum()),
        "future_year_matches": int(((matches.matched_year.notna()) & (matches.matched_year > matches.reference_year)).sum()),
    }
    write_json(HERE / "manifest.json", manifest)

    after = protected_hashes()
    if before != after or sha256(EMDAT) != emdat_hash:
        raise RuntimeError("A protected existing input, data, model, report, or preparation script changed")
    supported = int(country_audit.supported_by_world_bank.sum())
    report_lines = [
        "# World Bank Indicators download and matching audit", "",
        f"- API: World Bank Indicators API v2", f"- Download window: {START_YEAR}-{END_YEAR}",
        f"- Run started (UTC): {run_started}", f"- Run completed (UTC): {manifest['run_completed_utc']}",
        f"- EM-DAT input: `{manifest['input']['path']}`", f"- EM-DAT input SHA-256: `{emdat_hash}`", "",
        "## Indicators", "",
        *[f"- `{code}`: {name}" for code, name in INDICATORS.items()], "",
        "## Country entity audit", "",
        f"World Bank metadata returned {len(country_df)} entities. {int(country_df.is_aggregate.sum())} aggregate entities were excluded using the observed metadata marker `region.id == NA` / `region.value == Aggregates`; {len(economies)} countries/economies remained.",
        f"EM-DAT contains {events.country_code.nunique()} unique ISO3 codes: {supported} exact World Bank economy matches and {len(country_audit)-supported} unsupported codes. No country-name fallback was applied.", "",
        "## Matching rule", "",
        "For an event in year t, the target observation is t-1. If absent, the search proceeds only backward through t-2, t-3 and t-4 (maximum backtrack value 3). Future observations are forbidden. No imputation statistic is fitted.", "",
        "## Event matching", "",
    ]
    for code in INDICATORS:
        subset = matches[matches.indicator_code == code]
        matched = subset.value.notna().sum()
        exact = subset.match_status.eq("exact_t_minus_1").sum()
        backfilled = subset.match_status.str.startswith("backtracked_").sum()
        report_lines.append(f"- `{code}`: matched {matched:,}/{len(subset):,} ({matched/len(subset):.2%}); exact t-1 {exact:,}; historical backtracks {backfilled:,}; unmatched {len(subset)-matched:,}.")
    report_lines += ["", "## Reproducibility and limitations", "",
                     "Raw JSON responses are preserved unchanged in the experiment directory. `manifest.json` records request URLs, timestamps and SHA-256 values for every generated artifact.",
                     "World Bank indicator values can be revised retrospectively. This snapshot represents the API response captured at the recorded time. Missing observations remain missing when the permitted historical window contains no value.",
                     "Existing raw/processed data, preparation scripts, Random Forest artifacts and LightGBM artifacts were hash-checked before and after and were not modified."]
    (REPORTS / "world_bank_audit_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    # Add report to manifest only after its content is finalized.
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    report_path = REPORTS / "world_bank_audit_report.md"
    manifest["files"].append({"path": str(report_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(report_path), "bytes": report_path.stat().st_size})
    write_json(HERE / "manifest.json", manifest)
    match_counts = [{"indicator_code": code, "match_status": status, "event_count": int(count)}
                    for (code, status), count in matches.groupby(["indicator_code", "match_status"]).size().items()]
    print(json.dumps({"emdat_events": len(events), "emdat_iso3": int(events.country_code.nunique()),
                      "world_bank_economies": len(economies), "supported_emdat_iso3": supported,
                      "unsupported_emdat_iso3": len(country_audit)-supported,
                      "annual_rows": len(annual), "match_counts": match_counts}, indent=2))


if __name__ == "__main__":
    main()
