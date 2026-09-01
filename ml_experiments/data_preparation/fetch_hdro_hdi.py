"""Fetch HDRO metadata and, after schema validation, annual HDI data.

The API key is read from HDRO_API_KEY (process environment first, then the
project .env file). It is never written to logs or output files.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from country_aliases import EMDAT_NONSTANDARD_SPECIAL_CODES, HISTORICAL_ISO3_CODES

LOG = logging.getLogger("fetch_hdro_hdi")
BASE_URL = "https://hdrdata.org/api"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3
START_YEAR = 1990
END_YEAR = 2023


def load_api_key(project_root: Path) -> str:
    key = os.environ.get("HDRO_API_KEY", "").strip()
    if key:
        return key
    env_path = project_root / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == "HDRO_API_KEY":
                key = value.strip().strip('"').strip("'")
                if key:
                    return key
    raise RuntimeError("HDRO_API_KEY was not found in the environment or project .env")


def api_get_json(
    endpoint: str,
    params: dict[str, str],
    api_key: str,
    timeout: float,
    request_stats: list[dict[str, Any]] | None = None,
) -> Any:
    safe_endpoint = endpoint.strip("/")
    query = urlencode({**params, "apikey": api_key})
    request = Request(
        f"{BASE_URL}/{safe_endpoint}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Crisis-Data-Terminal/1.0"},
        method="GET",
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type", "")
                payload = response.read()
            if status != 200:
                raise RuntimeError(f"HDRO endpoint {safe_endpoint} returned HTTP {status}")
            if "json" not in content_type.lower():
                raise RuntimeError(f"HDRO endpoint {safe_endpoint} did not return JSON")
            try:
                result = json.loads(payload.decode("utf-8-sig"))
                if request_stats is not None:
                    request_stats.append({"attempts": attempt, "retry_events": attempt - 1, "status": "success"})
                return result
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"HDRO endpoint {safe_endpoint} returned invalid JSON") from exc
        except HTTPError as exc:
            if exc.code == 429 and attempt < MAX_ATTEMPTS:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 0.0) if retry_after else 2 ** (attempt - 1)
                except ValueError:
                    delay = 2 ** (attempt - 1)
                delay += random.uniform(0.0, 0.25)
                LOG.warning("Rate limited by %s (attempt %d/%d); retrying shortly", safe_endpoint, attempt, MAX_ATTEMPTS)
                time.sleep(delay)
                continue
            if 500 <= exc.code < 600 and attempt < MAX_ATTEMPTS:
                LOG.warning("HDRO %s returned HTTP %d (attempt %d/%d); retrying", safe_endpoint, exc.code, attempt, MAX_ATTEMPTS)
                time.sleep(2 ** (attempt - 1) + random.uniform(0.0, 0.25))
                continue
            if request_stats is not None:
                request_stats.append({"attempts": attempt, "retry_events": attempt - 1, "status": f"http_{exc.code}"})
            raise RuntimeError(f"HDRO endpoint {safe_endpoint} failed with HTTP {exc.code}") from None
        except (TimeoutError, URLError):
            if attempt < MAX_ATTEMPTS:
                LOG.warning("HDRO %s request failed (attempt %d/%d); retrying", safe_endpoint, attempt, MAX_ATTEMPTS)
                time.sleep(2 ** (attempt - 1) + random.uniform(0.0, 0.25))
                continue
            if request_stats is not None:
                request_stats.append({"attempts": attempt, "retry_events": attempt - 1, "status": "network_failure"})
            raise RuntimeError(f"HDRO endpoint {safe_endpoint} failed after {MAX_ATTEMPTS} attempts") from None
    raise AssertionError("unreachable")


def validate_metadata_payload(payload: Any, label: str) -> None:
    if not isinstance(payload, (list, dict)):
        raise ValueError(f"{label} metadata must be a JSON array or object, got {type(payload).__name__}")
    if isinstance(payload, list) and not payload:
        raise ValueError(f"{label} metadata returned an empty JSON array")
    if isinstance(payload, dict) and not payload:
        raise ValueError(f"{label} metadata returned an empty JSON object")


def structural_summary(payload: Any) -> str:
    if isinstance(payload, list):
        first = payload[0] if payload else None
        keys = sorted(first) if isinstance(first, dict) else []
        return f"array[{len(payload)}], first-item keys={keys}"
    if isinstance(payload, dict):
        return f"object keys={sorted(payload)}"
    return type(payload).__name__


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_metadata(api_key: str, raw_dir: Path, timeout: float) -> tuple[Any, Any]:
    LOG.info("Requesting HDRO Metadata/Indicators")
    indicators = api_get_json("Metadata/Indicators", {}, api_key, timeout)
    validate_metadata_payload(indicators, "Indicators")
    LOG.info("Indicators response: %s", structural_summary(indicators))
    write_json(raw_dir / "hdro_indicators.json", indicators)

    LOG.info("Requesting HDRO Metadata/Countries")
    countries = api_get_json("Metadata/Countries", {}, api_key, timeout)
    validate_metadata_payload(countries, "Countries")
    LOG.info("Countries response: %s", structural_summary(countries))
    write_json(raw_dir / "hdro_countries.json", countries)
    return indicators, countries


def exact_hdi_indicator_code(indicators: Any) -> str:
    if not isinstance(indicators, list) or not all(isinstance(item, dict) for item in indicators):
        raise ValueError("Indicators metadata schema changed; expected an array of objects")
    matches = [
        item for item in indicators
        if str(item.get("name", "")).strip().casefold() == "human development index (value)"
    ]
    if len(matches) != 1 or not str(matches[0].get("code", "")).strip():
        raise ValueError(f"Expected exactly one verified Human Development Index (value), found {len(matches)}")
    return str(matches[0]["code"]).strip()


def fetch_single_country_raw(
    api_key: str, raw_dir: Path, timeout: float, country_code: str, indicator_code: str
) -> Any:
    years = ",".join(str(year) for year in range(START_YEAR, END_YEAR + 1))
    LOG.info("Requesting single-country HDI coverage test: %s, %d-%d", country_code, START_YEAR, END_YEAR)
    payload = api_get_json(
        "CompositeIndices/query-detailed",
        {"countryOrAggregation": country_code, "year": years, "indicator": indicator_code},
        api_key,
        timeout,
    )
    if not isinstance(payload, (list, dict)):
        raise ValueError(f"HDI response must be a JSON array or object, got {type(payload).__name__}")
    LOG.info("Single-country raw response: %s", structural_summary(payload))
    write_json(raw_dir / "hdro_hdi_response.json", payload)
    return payload


def normalize_hdi_response(payload: Any, expected_indicator_code: str) -> list[dict[str, Any]]:
    """Normalize the observed query-detailed schema after strict validation."""
    if not isinstance(payload, list) or not payload:
        raise ValueError("HDI query-detailed response must be a non-empty JSON array")
    required = {"countryIsoCode", "country", "year", "indicatorCode", "actualValue"}
    normalized: list[dict[str, Any]] = []
    for position, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"HDI response item {position} is not an object")
        missing = required - item.keys()
        if missing:
            raise ValueError(f"HDI response item {position} is missing fields: {sorted(missing)}")
        indicator_code = str(item["indicatorCode"]).strip()
        if indicator_code.casefold() != expected_indicator_code.casefold():
            raise ValueError(f"Unexpected indicator code at response item {position}: {indicator_code}")
        country_code = str(item["countryIsoCode"]).strip().upper()
        if not country_code or len(country_code) != 3:
            raise ValueError(f"Invalid countryIsoCode at response item {position}")
        try:
            year = int(str(item["year"]).strip())
            hdi = float(str(item["actualValue"]).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid year or actualValue at response item {position}") from exc
        if not START_YEAR <= year <= END_YEAR:
            raise ValueError(f"HDI response year {year} is outside requested range")
        if not 0.0 <= hdi <= 1.0:
            raise ValueError(f"HDI actualValue {hdi} is outside [0, 1]")
        normalized.append({
            "country_code": country_code,
            "country_name": str(item["country"]).strip(),
            "year": year,
            "hdi": hdi,
            "source": "HDRO_API",
        })
    keys = [(row["country_code"], row["year"]) for row in normalized]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate country_code + year values found; refusing output: {duplicates[:10]}")
    return sorted(normalized, key=lambda row: (row["country_code"], row["year"]))


def write_annual_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["country_code", "country_name", "year", "hdi", "source"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def copy_single_country_snapshots(raw_dir: Path) -> None:
    pairs = (
        (raw_dir / "hdro_hdi_annual.csv", raw_dir / "hdro_hdi_annual_AFG_test.csv"),
        (raw_dir / "hdro_hdi_response.json", raw_dir / "hdro_hdi_response_AFG_test.json"),
    )
    for source, target in pairs:
        if not target.exists():
            if not source.exists():
                raise FileNotFoundError(f"Confirmed AFG snapshot source is missing: {source.name}")
            shutil.copy2(source, target)


def load_emdat_country_codes(emdat_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    import pandas as pd

    frame = pd.read_excel(emdat_path, sheet_name="EM-DAT Data", usecols=["ISO", "Country", "Historic"])
    iso = frame["ISO"].astype("string").str.strip().str.upper()
    stats = {
        "emdat_rows": len(frame),
        "empty_code_rows": int(iso.isna().sum() + iso.eq("").sum()),
    }
    records: list[dict[str, Any]] = []
    populated = frame.loc[iso.notna() & iso.ne("")].copy()
    populated["_code"] = iso.loc[populated.index]
    for code, group in populated.groupby("_code", sort=True):
        names = sorted(set(group["Country"].dropna().astype(str).str.strip()))
        historic_values = {str(value).strip().casefold() for value in group["Historic"].dropna()}
        records.append({
            "country_code": str(code),
            "emdat_country_name": " | ".join(name for name in names if name),
            "historic": "yes" in historic_values,
            "event_count": len(group),
        })
    stats["unique_nonempty_codes"] = len(records)
    stats["format_anomaly_codes"] = sum(not re.fullmatch(r"[A-Z]{3}", row["country_code"]) for row in records)
    return records, stats


def build_country_coverage(
    emdat_records: list[dict[str, Any]], countries: Any, stats: dict[str, int]
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    if not isinstance(countries, list) or not all(isinstance(item, dict) for item in countries):
        raise ValueError("Countries metadata schema changed; expected an array of objects")
    hdro_names = {
        str(item.get("code", "")).strip().upper(): str(item.get("name", "")).strip()
        for item in countries if str(item.get("code", "")).strip()
    }
    coverage: list[dict[str, Any]] = []
    supported_codes: list[str] = []
    issue_counts: Counter[str] = Counter()
    for row in emdat_records:
        code = row["country_code"]
        format_ok = bool(re.fullmatch(r"[A-Z]{3}", code))
        supported = format_ok and code in hdro_names
        if supported:
            issue_type = "supported"
            notes = "Exact ISO3 code present in HDRO Countries metadata"
            supported_codes.append(code)
        elif not format_ok:
            issue_type = "format_anomaly"
            notes = "Code is not exactly three ASCII uppercase letters"
        elif code in HISTORICAL_ISO3_CODES or row["historic"]:
            issue_type = "historical_country"
            notes = HISTORICAL_ISO3_CODES.get(code, "EM-DAT marks this code as historic; HDRO has no matching country code")
        elif code in EMDAT_NONSTANDARD_SPECIAL_CODES:
            issue_type = "nonstandard_special_code"
            notes = EMDAT_NONSTANDARD_SPECIAL_CODES[code]
        else:
            issue_type = "unsupported_special_or_territory"
            notes = "Well-formed EM-DAT code absent from HDRO Countries metadata; likely territory or special code"
        issue_counts[issue_type] += 1
        coverage.append({
            "country_code": code,
            "emdat_country_name": row["emdat_country_name"],
            "hdro_country_name": hdro_names.get(code, ""),
            "supported_by_hdro": str(supported).lower(),
            "issue_type": issue_type,
            "notes": notes,
        })
    stats.update({
        "supported_codes": len(supported_codes),
        "unsupported_codes": len(emdat_records) - len(supported_codes),
        "historical_codes": issue_counts["historical_country"],
        "nonstandard_special_codes": issue_counts["nonstandard_special_code"],
        "special_or_territory_codes": issue_counts["unsupported_special_or_territory"],
    })
    return coverage, sorted(supported_codes), stats


def write_dict_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def load_batch_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "api": "HDRO CompositeIndices/query-detailed",
            "indicator_code": "hdi",
            "requested_years": [START_YEAR, END_YEAR],
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "completed_codes": [],
            "batches": [],
            "records": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Staging batch JSON has an unexpected structure")
    return payload


def fetch_batches(
    api_key: str,
    raw_dir: Path,
    timeout: float,
    supported_codes: list[str],
    indicator_code: str,
    batch_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    staging_json = raw_dir / "hdro_hdi_response.batch.json"
    state = load_batch_state(staging_json)
    if state.get("indicator_code") != indicator_code or state.get("requested_years") != [START_YEAR, END_YEAR]:
        raise ValueError("Existing staging state has incompatible indicator or year range")
    completed = set(str(code) for code in state.get("completed_codes", []))
    pending = [code for code in supported_codes if code not in completed]
    years = ",".join(str(year) for year in range(START_YEAR, END_YEAR + 1))
    LOG.info("Bulk plan: %d supported countries, %d already completed, %d pending", len(supported_codes), len(completed), len(pending))
    for batch_number, country_batch in enumerate(chunks(pending, batch_size), start=1):
        request_stats: list[dict[str, Any]] = []
        LOG.info("Fetching batch %d: %d countries", batch_number, len(country_batch))
        entry: dict[str, Any] = {"country_codes": country_batch, "status": "pending", "row_count": 0}
        try:
            payload = api_get_json(
                "CompositeIndices/query-detailed",
                {
                    "countryOrAggregation": ",".join(country_batch),
                    "year": years,
                    "indicator": indicator_code,
                },
                api_key,
                timeout,
                request_stats,
            )
            rows = normalize_hdi_response(payload, indicator_code)
            returned_codes = {row["country_code"] for row in rows}
            unexpected = sorted(returned_codes - set(country_batch))
            if unexpected:
                raise ValueError(f"Batch returned country codes not requested: {unexpected}")
            raw_records = payload if isinstance(payload, list) else []
            state["records"].extend(raw_records)
            completed.update(country_batch)
            entry.update({
                "status": "success",
                "row_count": len(rows),
                "returned_country_count": len(returned_codes),
                "countries_without_rows": sorted(set(country_batch) - returned_codes),
            })
        except Exception as exc:
            entry.update({"status": "failed", "error": str(exc)})
            LOG.error("Batch %d failed safely: %s", batch_number, str(exc))
        entry["request_stats"] = request_stats
        state["batches"].append(entry)
        state["completed_codes"] = sorted(completed)
        write_json(staging_json, state)
    normalized = normalize_hdi_response(state["records"], indicator_code)
    write_annual_csv(raw_dir / "hdro_hdi_annual.staging.csv", normalized)
    return state, normalized


def build_country_summary(
    supported_codes: list[str], countries: Any, normalized: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    names = {str(item.get("code", "")).strip().upper(): str(item.get("name", "")).strip() for item in countries}
    by_country: dict[str, list[int]] = {code: [] for code in supported_codes}
    for row in normalized:
        by_country.setdefault(row["country_code"], []).append(int(row["year"]))
    summary: list[dict[str, Any]] = []
    requested = set(range(START_YEAR, END_YEAR + 1))
    for code in supported_codes:
        years = sorted(by_country.get(code, []))
        counts = Counter(years)
        missing = sorted(requested - set(years))
        summary.append({
            "country_code": code,
            "country_name": names.get(code, ""),
            "min_year": min(years) if years else "",
            "max_year": max(years) if years else "",
            "annual_value_count": len(years),
            "missing_years": ",".join(map(str, missing)),
            "has_discontinuous_years": str(bool(missing)).lower(),
            "duplicate_year_count": sum(count - 1 for count in counts.values() if count > 1),
        })
    return summary


def validate_and_promote_batch(
    raw_dir: Path,
    state: dict[str, Any],
    normalized: list[dict[str, Any]],
    supported_codes: list[str],
    countries: Any,
) -> dict[str, Any]:
    failures = [batch for batch in state["batches"] if batch.get("status") == "failed"]
    if failures:
        raise RuntimeError(f"{len(failures)} batch(es) failed; staging files retained and formal files not updated")
    keys = [(row["country_code"], row["year"]) for row in normalized]
    duplicate_count = sum(count - 1 for count in Counter(keys).values() if count > 1)
    if duplicate_count:
        raise ValueError(f"Found {duplicate_count} duplicate country_code + year rows")
    if any(not START_YEAR <= int(row["year"]) <= END_YEAR for row in normalized):
        raise ValueError("Found an HDI year outside 1990-2023")
    if any(not 0.0 <= float(row["hdi"]) <= 1.0 for row in normalized):
        raise ValueError("Found an HDI value outside [0, 1]")
    if any(not row["country_code"] or row["year"] == "" or row["hdi"] == "" or not row["source"] for row in normalized):
        raise ValueError("Required normalized HDI field is empty")

    afg_test = read_csv_rows(raw_dir / "hdro_hdi_annual_AFG_test.csv")
    afg_bulk = [row for row in normalized if row["country_code"] == "AFG"]
    canonical_test = [(row["country_code"], int(row["year"]), float(row["hdi"])) for row in afg_test]
    canonical_bulk = [(row["country_code"], int(row["year"]), float(row["hdi"])) for row in afg_bulk]
    if canonical_bulk != canonical_test:
        raise ValueError("Bulk AFG data does not exactly match the confirmed single-country test")

    summary = build_country_summary(supported_codes, countries, normalized)
    write_dict_csv(
        raw_dir / "hdro_hdi_country_summary.csv",
        summary,
        ["country_code", "country_name", "min_year", "max_year", "annual_value_count", "missing_years", "has_discontinuous_years", "duplicate_year_count"],
    )
    shutil.copy2(raw_dir / "hdro_hdi_annual.staging.csv", raw_dir / "hdro_hdi_annual.csv")
    formal_response = {
        key: state[key] for key in ("api", "indicator_code", "requested_years", "collected_at_utc", "completed_codes", "batches", "records")
    }
    write_json(raw_dir / "hdro_hdi_response.json", formal_response)
    return {
        "country_count": len({row["country_code"] for row in normalized}),
        "annual_value_count": len(normalized),
        "complete_country_count": sum(int(row["annual_value_count"]) == END_YEAR - START_YEAR + 1 for row in summary),
        "incomplete_country_count": sum(int(row["annual_value_count"]) != END_YEAR - START_YEAR + 1 for row in summary),
        "successful_batches": sum(batch.get("status") == "success" for batch in state["batches"]),
        "failed_batches": 0,
        "retry_events": sum(stat.get("retry_events", 0) for batch in state["batches"] for stat in batch.get("request_stats", [])),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("metadata", "single-raw", "single-test", "coverage", "bulk"), default="metadata")
    parser.add_argument("--country", default="AFG", help="Single ISO3 used only by the coverage test")
    parser.add_argument("--raw-dir", type=Path, default=project_root / "data" / "raw")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    api_key = load_api_key(project_root)
    LOG.info("HDRO_API_KEY detected")
    raw_dir = args.raw_dir.resolve()
    indicators, countries = fetch_metadata(api_key, raw_dir, args.timeout)
    LOG.info("Metadata snapshots saved")
    if args.stage in {"coverage", "bulk"}:
        if not 10 <= args.batch_size <= 25:
            raise ValueError("--batch-size must be between 10 and 25")
        copy_single_country_snapshots(raw_dir)
        emdat_records, coverage_stats = load_emdat_country_codes(project_root / "data" / "emdat_raw.xlsx")
        coverage, supported_codes, coverage_stats = build_country_coverage(emdat_records, countries, coverage_stats)
        write_dict_csv(
            raw_dir / "hdro_country_coverage.csv",
            coverage,
            ["country_code", "emdat_country_name", "hdro_country_name", "supported_by_hdro", "issue_type", "notes"],
        )
        LOG.info(
            "Country coverage: %d unique non-empty EM-DAT codes; %d supported; %d unsupported; %d empty rows",
            coverage_stats["unique_nonempty_codes"], coverage_stats["supported_codes"],
            coverage_stats["unsupported_codes"], coverage_stats["empty_code_rows"],
        )
        if args.stage == "coverage":
            return
        indicator_code = exact_hdi_indicator_code(indicators)
        LOG.info("Verified HDI indicator code from metadata: %s", indicator_code)
        state, normalized = fetch_batches(api_key, raw_dir, args.timeout, supported_codes, indicator_code, args.batch_size)
        batch_stats = validate_and_promote_batch(raw_dir, state, normalized, supported_codes, countries)
        write_json(raw_dir / "hdro_collection_summary.json", {"coverage": coverage_stats, "batch": batch_stats})
        LOG.info(
            "Bulk validation passed: %d countries, %d annual values, %d complete countries",
            batch_stats["country_count"], batch_stats["annual_value_count"], batch_stats["complete_country_count"],
        )
        LOG.info("Formal HDRO files promoted after validation")
        return
    if args.stage in {"single-raw", "single-test"}:
        country_code = args.country.strip().upper()
        valid_country_codes = {str(item.get("code", "")).strip().upper() for item in countries if isinstance(item, dict)}
        if country_code not in valid_country_codes:
            raise ValueError(f"Test country {country_code} is not present in Countries metadata")
        indicator_code = exact_hdi_indicator_code(indicators)
        LOG.info("Verified HDI indicator code from metadata: %s", indicator_code)
        payload = fetch_single_country_raw(api_key, raw_dir, args.timeout, country_code, indicator_code)
        if args.stage == "single-raw":
            LOG.info("Single-country raw snapshot saved; normalization intentionally deferred until schema inspection")
        else:
            rows = normalize_hdi_response(payload, indicator_code)
            write_annual_csv(raw_dir / "hdro_hdi_annual.csv", rows)
            years = sorted(row["year"] for row in rows)
            LOG.info("Single-country normalized rows: %d; year coverage: %d-%d", len(rows), min(years), max(years))
            LOG.info("Single-country annual CSV saved; bulk collection is paused pending user confirmation")


if __name__ == "__main__":
    main()
