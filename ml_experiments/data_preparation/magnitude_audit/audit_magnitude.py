"""Audit EM-DAT Magnitude semantics and design leakage-safe robust scaling groups."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
INPUT = ROOT / "data/emdat_raw.xlsx"
CURRENT = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
MIN_TRAIN_N = 20
CLIP_RANGE = [-5, 5]
MISSING_SCALE = "<MISSING_SCALE>"

SCALE_MEANINGS = {
    "Km2": "area in square kilometres; physical unit is shared, but phenomenon differs across disaster types",
    "Kph": "wind speed in kilometres per hour",
    "Moment Magnitude": "earthquake moment magnitude",
    "°C": "temperature in degrees Celsius; heat and cold have opposite severity directions",
    "Vaccinated": "number vaccinated; response/intervention quantity rather than occurrence-time hazard intensity",
    "m3": "volume in cubic metres; sparse records span heterogeneous accident types",
    MISSING_SCALE: "scale absent; magnitude meaning cannot be established",
}


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
    for relative in ["data/raw", "data/processed", "data/processed_hdro", "ml_experiments/modeling",
                     "ml_experiments/data_preparation/world_bank"]:
        base = ROOT / relative
        if base.exists():
            paths.extend(p for p in base.rglob("*") if p.is_file())
    prep = ROOT / "ml_experiments/data_preparation"
    paths.extend(p for p in prep.glob("*") if p.is_file())
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in sorted(set(paths))}


def time_split(year: Any) -> str:
    value = int(year)
    if 2000 <= value <= 2019: return "train"
    if 2020 <= value <= 2021: return "validation"
    if 2022 <= value <= 2023: return "test"
    if 2024 <= value <= 2026: return "maturity_holdout"
    return "outside_current_split"


def describe(values: pd.Series) -> dict[str, Any]:
    numeric = values.dropna().astype(float)
    if numeric.empty:
        return {"minimum": np.nan, "q1": np.nan, "median": np.nan, "q3": np.nan,
                "iqr": np.nan, "maximum": np.nan, "extreme_outlier_count": 0}
    q1, median, q3 = numeric.quantile([.25, .5, .75])
    iqr = q3 - q1
    if iqr > 0:
        extreme = ((numeric < q1 - 3 * iqr) | (numeric > q3 + 3 * iqr)).sum()
    else:
        extreme = (numeric != median).sum()
    return {"minimum": numeric.min(), "q1": q1, "median": median, "q3": q3,
            "iqr": iqr, "maximum": numeric.max(), "extreme_outlier_count": int(extreme)}


def semantic_assessment(strategy: str, disaster_type: str, disaster_subtype: str, scale: str) -> tuple[bool, str]:
    if scale == MISSING_SCALE:
        return False, "missing magnitude scale"
    if scale == "Vaccinated":
        return False, "response/intervention count; potentially available only after event onset"
    if scale == "m3":
        return False, "only three non-missing values and heterogeneous accident contexts"
    if scale == "°C" and strategy == "disaster_type+magnitude_scale":
        return False, "mixes cold-wave negative temperatures with heat-wave positive temperatures"
    if scale == "°C":
        return True, "subtype separates heat and cold direction; values remain temperatures, not unsigned intensity"
    if scale == "Km2":
        return True, "area unit is consistent within the disaster type; do not merge across disaster types"
    if scale == "Kph":
        return True, "wind-speed unit and direction are consistent within Storm"
    if scale == "Moment Magnitude":
        return True, "moment-magnitude scale is consistent within Earthquake"
    return False, "unrecognized scale semantics"


def recommended_for_group(strategy: str, disaster_type: str, scale: str) -> bool:
    if scale == "°C":
        return strategy == "disaster_subtype+magnitude_scale"
    return strategy == "disaster_type+magnitude_scale"


def make_group_audit(data: pd.DataFrame, strategy: str) -> pd.DataFrame:
    fields = ["disaster_type", "magnitude_scale"] if strategy.startswith("disaster_type+") else ["disaster_subtype", "magnitude_scale"]
    rows = []
    for keys, group in data.groupby(fields, dropna=False, sort=True):
        if not isinstance(keys, tuple): keys = (keys,)
        disaster_type = str(group.disaster_type.iloc[0])
        disaster_subtype = str(group.disaster_subtype.iloc[0])
        scale = str(group.magnitude_scale.iloc[0])
        stats = describe(group.magnitude)
        train = group[group.time_split == "train"]
        train_stats = describe(train.magnitude)
        semantic_ok, semantic_notes = semantic_assessment(strategy, disaster_type, disaster_subtype, scale)
        train_n = int(train.magnitude.notna().sum())
        train_iqr = train_stats["iqr"]
        reasons = []
        if not semantic_ok: reasons.append(semantic_notes)
        if train_n < MIN_TRAIN_N: reasons.append(f"training non-missing sample count {train_n} < {MIN_TRAIN_N}")
        if pd.isna(train_iqr): reasons.append("training IQR unavailable")
        elif train_iqr == 0: reasons.append("training IQR = 0")
        supported = semantic_ok and train_n >= MIN_TRAIN_N and pd.notna(train_iqr) and train_iqr > 0
        recommended = supported and recommended_for_group(strategy, disaster_type, scale)
        row = {
            "grouping_strategy": strategy,
            "group_key": " | ".join(str(x) for x in keys),
            "disaster_type": disaster_type if strategy.startswith("disaster_type+") else "<MULTIPLE_OR_NOT_APPLICABLE>",
            "disaster_subtype": disaster_subtype if strategy.startswith("disaster_subtype+") else "<MULTIPLE_OR_NOT_APPLICABLE>",
            "magnitude_scale": scale, "total_records": len(group),
            "magnitude_nonmissing": int(group.magnitude.notna().sum()),
            "magnitude_missing": int(group.magnitude.isna().sum()),
            "magnitude_nonmissing_rate": group.magnitude.notna().mean(),
            **stats,
            "training_records": len(train), "training_nonmissing": train_n,
            "training_median_audit_only": train_stats["median"], "training_iqr_audit_only": train_iqr,
            "full_data_iqr_zero": bool(pd.notna(stats["iqr"]) and stats["iqr"] == 0),
            "training_iqr_zero": bool(pd.notna(train_iqr) and train_iqr == 0),
            "semantic_consistent": semantic_ok, "semantic_notes": semantic_notes,
            "statistically_supported_from_training": bool(supported),
            "recommended_hybrid_group": bool(recommended),
            "unsupported_reasons": "; ".join(dict.fromkeys(reasons)),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["grouping_strategy", "magnitude_scale", "group_key"])


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    input_hash, current_hash = sha256(INPUT), sha256(CURRENT)
    raw = pd.read_excel(INPUT, sheet_name="EM-DAT Data", dtype=object, keep_default_na=False,
                        usecols=["DisNo.", "Disaster Type", "Disaster Subtype", "Magnitude", "Magnitude Scale", "Start Year"])
    raw.columns = ["event_id", "disaster_type", "disaster_subtype", "magnitude_raw", "magnitude_scale_raw", "start_year"]
    if raw.event_id.eq("").any() or raw.event_id.duplicated().any():
        raise RuntimeError("event_id is blank or non-unique")
    current = pd.read_csv(CURRENT, usecols=["event_id", "year"])
    joined = raw[["event_id", "start_year"]].merge(current, on="event_id", how="outer", validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all() or not pd.to_numeric(joined.start_year).eq(joined.year).all():
        raise RuntimeError("Raw event_id or Start Year does not match the frozen current time field")

    raw_magnitude_text = raw.magnitude_raw.astype(str).str.strip()
    magnitude_blank = raw_magnitude_text.eq("")
    magnitude = pd.to_numeric(raw.magnitude_raw.where(~magnitude_blank), errors="coerce")
    nonnumeric = ~magnitude_blank & magnitude.isna()
    if nonnumeric.any():
        examples = raw.loc[nonnumeric, ["event_id", "magnitude_raw"]].head(10).to_dict("records")
        raise RuntimeError(f"Magnitude contains non-numeric nonblank values: {examples}")
    scale_text = raw.magnitude_scale_raw.astype(str).str.strip()
    scale_blank = scale_text.eq("")
    normalized_scale = scale_text.mask(scale_blank, MISSING_SCALE)
    data = pd.DataFrame({
        "event_id": raw.event_id.astype(str), "disaster_type": raw.disaster_type.astype(str).str.strip(),
        "disaster_subtype": raw.disaster_subtype.astype(str).str.strip(), "magnitude": magnitude,
        "magnitude_scale": normalized_scale, "start_year": pd.to_numeric(raw.start_year).astype(int),
    })
    data["time_split"] = data.start_year.map(time_split)
    if data.disaster_type.eq("").any() or data.disaster_subtype.eq("").any():
        raise RuntimeError("Disaster type or subtype contains blank values; grouping cannot be reliable")
    if (data.magnitude.notna() & data.magnitude_scale.eq(MISSING_SCALE)).any():
        raise RuntimeError("Non-missing Magnitude has no Magnitude Scale; semantic interpretation is unsafe")

    type_coverage = (data.groupby("disaster_type", dropna=False).magnitude
                     .agg(total_records="size", magnitude_nonmissing="count").reset_index())
    type_coverage["magnitude_missing"] = type_coverage.total_records - type_coverage.magnitude_nonmissing
    type_coverage["magnitude_nonmissing_rate"] = type_coverage.magnitude_nonmissing / type_coverage.total_records
    type_coverage.to_csv(HERE / "magnitude_by_disaster_type.csv", index=False)
    subtype_coverage = (data.groupby(["disaster_type", "disaster_subtype"], dropna=False).magnitude
                        .agg(total_records="size", magnitude_nonmissing="count").reset_index())
    subtype_coverage["magnitude_missing"] = subtype_coverage.total_records - subtype_coverage.magnitude_nonmissing
    subtype_coverage["magnitude_nonmissing_rate"] = subtype_coverage.magnitude_nonmissing / subtype_coverage.total_records
    subtype_coverage.to_csv(HERE / "magnitude_by_disaster_subtype.csv", index=False)

    scale_rows = []
    for scale, group in data.groupby("magnitude_scale", dropna=False, sort=True):
        types = sorted(group.disaster_type.unique())
        subtypes = sorted(group.disaster_subtype.unique())
        if scale == "Km2": consistency = "unit consistent, but do not pool across Drought/Flood/Wildfire"
        elif scale == "°C": consistency = "unit consistent; severity direction differs between heat and cold subtypes"
        elif scale == "m3": consistency = "unit label consistent but context heterogeneous and values too sparse"
        elif scale == "Vaccinated": consistency = "count is consistent but represents intervention/response, not hazard magnitude"
        elif scale == MISSING_SCALE: consistency = "meaning unavailable"
        else: consistency = "unit and meaning appear consistent within observed disaster type"
        scale_rows.append({
            "magnitude_scale_raw": "<EMPTY_OR_MISSING>" if scale == MISSING_SCALE else scale,
            "record_count": len(group), "magnitude_nonmissing": int(group.magnitude.notna().sum()),
            "magnitude_missing": int(group.magnitude.isna().sum()), "magnitude_nonmissing_rate": group.magnitude.notna().mean(),
            "disaster_type_count": len(types), "disaster_types": " | ".join(types),
            "disaster_subtype_count": len(subtypes), "scale_meaning": SCALE_MEANINGS.get(scale, "unrecognized"),
            "cross_type": len(types) > 1, "semantic_consistency_assessment": consistency,
            "blank_or_abnormal_category": scale == MISSING_SCALE,
        })
    scale_audit = pd.DataFrame(scale_rows)
    scale_audit.to_csv(HERE / "magnitude_scale_audit.csv", index=False)

    type_groups = make_group_audit(data, "disaster_type+magnitude_scale")
    subtype_groups = make_group_audit(data, "disaster_subtype+magnitude_scale")
    groups = pd.concat([type_groups, subtype_groups], ignore_index=True)
    groups.to_csv(HERE / "magnitude_group_audit.csv", index=False)
    # Keep valid-but-not-selected alternative groups in the full audit; this file
    # is reserved for combinations that genuinely cannot be fitted safely.
    unsupported = groups[~groups.statistically_supported_from_training].copy()
    unsupported.to_csv(HERE / "magnitude_unsupported_groups.csv", index=False)

    # Prospective coverage uses only the training-derived eligibility flags; no z-score is calculated.
    recommended_groups = set(groups.loc[groups.recommended_hybrid_group, ["grouping_strategy", "group_key"]]
                             .itertuples(index=False, name=None))
    def recommended_key(row: pd.Series) -> tuple[str, str]:
        if row.magnitude_scale == "°C":
            return "disaster_subtype+magnitude_scale", f"{row.disaster_subtype} | {row.magnitude_scale}"
        return "disaster_type+magnitude_scale", f"{row.disaster_type} | {row.magnitude_scale}"
    keys = data.apply(recommended_key, axis=1)
    data["recommended_group_supported"] = [key in recommended_groups for key in keys]
    data["potential_standardized"] = data.magnitude.notna() & data.recommended_group_supported
    coverage = (data.groupby("time_split", dropna=False)
                .agg(total_records=("event_id", "size"), magnitude_nonmissing=("magnitude", "count"),
                     potentially_standardizable=("potential_standardized", "sum")).reset_index())
    coverage["standardizable_rate_all_records"] = coverage.potentially_standardizable / coverage.total_records
    coverage["standardizable_rate_among_nonmissing"] = coverage.potentially_standardizable / coverage.magnitude_nonmissing.replace(0, np.nan)
    coverage.to_csv(HERE / "magnitude_standardizable_coverage.csv", index=False)

    anomaly_rows = []
    recommended_group_rows = groups[groups.recommended_hybrid_group]
    for group_row in recommended_group_rows.itertuples(index=False):
        if group_row.grouping_strategy.startswith("disaster_type+"):
            mask = data.disaster_type.eq(group_row.group_key.split(" | ", 1)[0]) & data.magnitude_scale.eq(group_row.magnitude_scale)
        else:
            mask = data.disaster_subtype.eq(group_row.group_key.split(" | ", 1)[0]) & data.magnitude_scale.eq(group_row.magnitude_scale)
        q1, q3, iqr = group_row.q1, group_row.q3, group_row.iqr
        outlier = mask & data.magnitude.notna() & ((data.magnitude < q1 - 3 * iqr) | (data.magnitude > q3 + 3 * iqr))
        for event in data.loc[outlier].itertuples(index=False):
            anomaly_rows.append({"event_id": event.event_id, "disaster_type": event.disaster_type,
                                 "disaster_subtype": event.disaster_subtype, "magnitude": event.magnitude,
                                 "magnitude_scale": event.magnitude_scale, "start_year": event.start_year,
                                 "time_split": event.time_split, "anomaly_type": "outside full-group Q1/Q3 +/- 3*IQR",
                                 "grouping_strategy": group_row.grouping_strategy, "group_key": group_row.group_key})
    anomalies = pd.DataFrame(anomaly_rows, columns=["event_id", "disaster_type", "disaster_subtype", "magnitude",
                                                    "magnitude_scale", "start_year", "time_split", "anomaly_type",
                                                    "grouping_strategy", "group_key"])
    anomalies.to_csv(HERE / "magnitude_anomaly_records.csv", index=False)

    total, nonmissing = len(data), int(data.magnitude.notna().sum())
    possible = int(data.potential_standardized.sum())
    supported_summary = groups[groups.recommended_hybrid_group][["grouping_strategy", "group_key", "training_nonmissing",
                                                                 "training_median_audit_only", "training_iqr_audit_only"]]
    report = f"""# EM-DAT Magnitude scale audit

## Scope and integrity

- Input: `data/emdat_raw.xlsx` (`EM-DAT Data`)
- Input SHA-256: `{input_hash}`
- Current event/time reference: `data/processed_hdro/disaster_hdi_merged.csv`
- Reference SHA-256: `{current_hash}`
- Audit time (UTC): {utc_now()}
- Events: {total:,}; event IDs are unique and map one-to-one to the current dataset.
- `Start Year` differs from current `year` for 0 events.
- No death, impact, damage, affected-population, or target-label field was read.

## Overall completeness

- Non-missing Magnitude: {nonmissing:,} ({nonmissing/total:.2%})
- Missing Magnitude: {total-nonmissing:,} ({(total-nonmissing)/total:.2%})
- Non-numeric nonblank Magnitude: {int(nonnumeric.sum())}
- Non-missing Magnitude with missing scale: {int((data.magnitude.notna() & data.magnitude_scale.eq(MISSING_SCALE)).sum())}
- Scale present but Magnitude missing: {int((data.magnitude.isna() & ~data.magnitude_scale.eq(MISSING_SCALE)).sum()):,}

## Semantic findings

`Km2` crosses Drought, Flood and Wildfire. The physical unit is consistent, but the phenomenon differs, so it must be separated by disaster type. `Kph` is confined to Storm and represents wind speed. `Moment Magnitude` is confined to Earthquake. `°C` is confined to Extreme temperature but mixes heat and cold: a higher signed temperature has opposite severity meaning for cold events, so type-level pooling is unsafe and subtype separation is required. `Vaccinated` is a response/intervention count and is excluded as potential post-event information. `m3` has only three non-missing values across heterogeneous accidents and is excluded.

## Recommended grouping design

Use a semantic hybrid group key:

1. `disaster_type + magnitude_scale` for `Km2`, `Kph`, and `Moment Magnitude`.
2. `disaster_subtype + magnitude_scale` for `°C`, keeping Heat wave, Cold wave and Severe winter conditions separate.
3. Do not standardize `Vaccinated`, `m3`, missing scales, training groups with fewer than {MIN_TRAIN_N} valid values, zero/undefined training IQR, or unknown groups.

The audit identifies {len(supported_summary)} recommended groups. Based solely on training-period eligibility, {possible:,}/{nonmissing:,} non-missing observations ({possible/nonmissing:.2%}) and {possible:,}/{total:,} all events ({possible/total:.2%}) could receive a future robust-z value. This is a prospective coverage audit, not a transformed feature.

## Leakage-safe future transformation contract

During a future experiment, fit group vocabularies, medians and IQRs on 2000–2019 training rows only. Transform validation/test without updating categories or statistics:

`magnitude_robust_z = clip((magnitude - training_group_median) / training_group_IQR, -5, 5)`

- Keep `magnitude_missing` and `magnitude_group_unknown`.
- Raw `magnitude` must not enter the formal model.
- Missing magnitude, unknown groups, training count below {MIN_TRAIN_N}, or zero/undefined training IQR produce no standardized value.
- Validation, test and maturity-holdout rows never supplement training groups or statistics.
- The descriptive full-data medians/IQRs in the audit CSV are diagnostics only and must never be reused as model parameters.

## Limitations

Magnitude is populated for only {nonmissing/total:.2%} of events, and scale presence does not imply value presence. Robust scaling improves comparability within a semantic group but does not make different physical quantities equivalent and does not establish causality. Temperature remains a signed physical measurement; subtype separation avoids direct heat/cold pooling but does not convert temperature into hazard severity.
"""
    (HERE / "magnitude_audit_report.md").write_text(report, encoding="utf-8")

    output_paths = sorted(p for p in HERE.glob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {
        "created_at_utc": utc_now(),
        "input": {"path": str(INPUT.relative_to(ROOT)).replace("\\", "/"), "sha256": input_hash,
                  "sheet": "EM-DAT Data", "rows": total},
        "current_time_reference": {"path": str(CURRENT.relative_to(ROOT)).replace("\\", "/"), "sha256": current_hash,
                                   "field_mapping": "DisNo. -> event_id; Start Year -> year", "year_mismatches": 0},
        "time_split": {"train": "2000-2019", "validation": "2020-2021", "test": "2022-2023",
                       "maturity_holdout": "2024-2026"},
        "audit_counts": {"total": total, "magnitude_nonmissing": nonmissing, "magnitude_missing": total-nonmissing,
                         "nonnumeric_nonblank": int(nonnumeric.sum()), "scale_blank_or_missing": int(scale_blank.sum()),
                         "scale_present_magnitude_missing": int((data.magnitude.isna() & ~data.magnitude_scale.eq(MISSING_SCALE)).sum()),
                         "recommended_group_count": len(supported_summary), "potentially_standardizable": possible},
        "recommended_rule": {"primary": "disaster_type + magnitude_scale",
                             "temperature_exception": "disaster_subtype + magnitude_scale for °C",
                             "excluded_scales": ["Vaccinated", "m3", MISSING_SCALE],
                             "minimum_training_nonmissing": MIN_TRAIN_N, "require_positive_training_iqr": True,
                             "clip_range": CLIP_RANGE, "fit_scope": "training only (2000-2019)",
                             "raw_magnitude_model_input": False,
                             "indicators": ["magnitude_missing", "magnitude_group_unknown"]},
        "files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size}
                  for path in output_paths],
        "protected_files_checked": len(before),
    }
    write_json(HERE / "manifest.json", manifest)

    after = protected_hashes()
    if before != after or sha256(INPUT) != input_hash or sha256(CURRENT) != current_hash:
        raise RuntimeError("A frozen input, data, model, or World Bank artifact changed")
    print(json.dumps({"events": total, "magnitude_nonmissing": nonmissing, "magnitude_missing": total-nonmissing,
                      "recommended_groups": len(supported_summary), "potentially_standardizable": possible,
                      "coverage_among_nonmissing": possible/nonmissing, "extreme_outlier_records": len(anomalies)}, indent=2))


if __name__ == "__main__":
    main()
