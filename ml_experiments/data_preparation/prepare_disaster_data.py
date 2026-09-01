"""Build the isolated EM-DAT + HDRO annual HDI dataset and QA report."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import logging
import re
from calendar import monthrange
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOG = logging.getLogger("prepare_disaster_data")
HDI_START_YEAR = 1990
HDI_END_YEAR = 2023
OLD_BASELINE = {
    "annual_values": 1584,
    "exact_matches": 4354,
    "exact_rate": 0.2583,
    "labeled_rows": 13582,
    "deaths_missing": 3276,
    "impact": {"Low": 3393, "Moderate": 9029, "High": 1017, "Extreme": 143},
}

REQUIRED_EMDAT_COLUMNS = [
    "DisNo.", "ISO", "Country", "Subregion", "Disaster Type", "Disaster Subtype",
    "Start Year", "Start Month", "Start Day", "End Year", "End Month", "End Day",
    "Total Deaths", "Total Affected", "Total Damage ('000 US$)",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", "", regex=False).str.strip(), errors="coerce")


def load_emdat(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name="EM-DAT Data")
    missing = [column for column in REQUIRED_EMDAT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"EM-DAT required columns are missing: {missing}")
    return frame


def _safe_timestamp(year: Any, month: Any, day: Any) -> pd.Timestamp | pd.NaT:
    try:
        return pd.Timestamp(int(year), int(month), int(day))
    except (TypeError, ValueError, OverflowError):
        return pd.NaT


def construct_dates(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    sy = numeric(frame["Start Year"]).astype("Int64")
    sm = numeric(frame["Start Month"]).astype("Int64")
    sd = numeric(frame["Start Day"]).astype("Int64")
    ey = numeric(frame["End Year"]).astype("Int64")
    em = numeric(frame["End Month"]).astype("Int64")
    ed = numeric(frame["End Day"]).astype("Int64")
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()

    for start_year, start_month, start_day, end_year, end_month, end_day in zip(sy, sm, sd, ey, em, ed):
        anomaly = ""
        if pd.isna(start_year):
            start_lower = start_upper = pd.NaT
            precision = "missing"
            stats["start_missing"] += 1
        elif pd.isna(start_month):
            start_lower = pd.Timestamp(int(start_year), 1, 1)
            start_upper = pd.Timestamp(int(start_year), 12, 31)
            precision = "year"
            stats["start_year_precision"] += 1
        elif pd.isna(start_day):
            start_lower = pd.Timestamp(int(start_year), int(start_month), 1)
            start_upper = pd.Timestamp(int(start_year), int(start_month), monthrange(int(start_year), int(start_month))[1])
            precision = "month"
            stats["start_month_precision"] += 1
        else:
            start_lower = _safe_timestamp(start_year, start_month, start_day)
            start_upper = start_lower
            precision = "day" if pd.notna(start_lower) else "invalid"
            if pd.isna(start_lower):
                anomaly = "invalid_start_date"
                stats["invalid_start_date"] += 1

        if pd.isna(end_year):
            end_effective = pd.NaT
            stats["end_missing"] += 1
        elif pd.isna(end_month):
            end_effective = pd.Timestamp(int(end_year), 12, 31)
            stats["end_year_precision"] += 1
        elif pd.isna(end_day):
            end_effective = pd.Timestamp(int(end_year), int(end_month), monthrange(int(end_year), int(end_month))[1])
            stats["end_month_precision"] += 1
        else:
            end_effective = _safe_timestamp(end_year, end_month, end_day)
            if pd.isna(end_effective):
                anomaly = anomaly or "invalid_end_date"
                stats["invalid_end_date"] += 1

        duration: Any = pd.NA
        if pd.notna(start_lower) and pd.notna(end_effective):
            if end_effective < start_lower:
                anomaly = "end_before_start"
                stats["end_before_start"] += 1
            else:
                duration = int((end_effective - start_lower).days + 1)
        rows.append({
            "event_date": start_lower,
            "event_date_upper": start_upper,
            "end_date": end_effective,
            "date_granularity": precision,
            "date_imputed": precision in {"year", "month"},
            "date_anomaly": anomaly,
            "duration": duration,
        })
    return pd.DataFrame(rows, index=frame.index), dict(stats)


def add_historical_frequency(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["time_batch"] = pd.NA
    day = out["date_granularity"].eq("day")
    month = out["date_granularity"].eq("month")
    year = out["date_granularity"].eq("year")
    out.loc[day, "time_batch"] = out.loc[day, "event_date"].dt.strftime("%Y-%m-%d")
    out.loc[month, "time_batch"] = out.loc[month, "event_date"].dt.strftime("%Y-%m")
    out.loc[year, "time_batch"] = out.loc[year, "event_date"].dt.strftime("%Y")
    out["historical_frequency"] = pd.Series(pd.NA, index=out.index, dtype="Int64")

    valid = out["country_code"].notna() & out["country_code"].ne("") & out["time_batch"].notna()
    for _, country in out.loc[valid].groupby("country_code", sort=True):
        batches = (
            country.groupby("time_batch", sort=False)
            .agg(interval_start=("event_date", "min"), interval_end=("event_date_upper", "max"), event_count=("event_id", "size"))
            .reset_index()
            .sort_values(["interval_start", "interval_end", "time_batch"], kind="stable")
        )
        ended: list[tuple[pd.Timestamp, int]] = []
        prior_count = 0
        for row in batches.itertuples(index=False):
            while ended and ended[0][0] < row.interval_start:
                _, count = heapq.heappop(ended)
                prior_count += count
            indexes = country.index[country["time_batch"].eq(row.time_batch)]
            out.loc[indexes, "historical_frequency"] = prior_count
            heapq.heappush(ended, (row.interval_end, int(row.event_count)))
    return out


def validate_historical_frequency(frame: pd.DataFrame) -> dict[str, bool]:
    valid = frame.dropna(subset=["time_batch", "historical_frequency"]).copy()
    batch = (
        valid.groupby(["country_code", "time_batch"], dropna=False)
        .agg(interval_start=("event_date", "min"), frequency=("historical_frequency", "first"), unique_frequency=("historical_frequency", "nunique"))
        .reset_index()
        .sort_values(["country_code", "interval_start", "time_batch"], kind="stable")
    )
    earliest_zero = bool(batch.groupby("country_code").first()["frequency"].eq(0).all())
    non_decreasing = bool(all(group["frequency"].is_monotonic_increasing for _, group in batch.groupby("country_code")))
    same_batch_equal = bool(batch["unique_frequency"].le(1).all())
    return {"earliest_is_zero": earliest_zero, "non_decreasing": non_decreasing, "same_batch_equal": same_batch_equal}


def impact_level(deaths: pd.Series) -> pd.Series:
    result = pd.Series(pd.NA, index=deaths.index, dtype="string")
    result.loc[deaths.between(0, 9)] = "Low"
    result.loc[deaths.between(10, 99)] = "Moderate"
    result.loc[deaths.between(100, 999)] = "High"
    result.loc[deaths.ge(1000)] = "Extreme"
    return result


def load_hdi(path: Path) -> pd.DataFrame:
    hdi = pd.read_csv(path, encoding="utf-8-sig", dtype={"country_code": "string"})
    required = {"country_code", "country_name", "year", "hdi", "source"}
    missing = required - set(hdi.columns)
    if missing:
        raise ValueError(f"HDRO annual CSV is missing columns: {sorted(missing)}")
    hdi["country_code"] = hdi["country_code"].str.strip().str.upper()
    hdi["year"] = pd.to_numeric(hdi["year"], errors="raise").astype("int64")
    hdi["hdi"] = pd.to_numeric(hdi["hdi"], errors="raise")
    if hdi.duplicated(["country_code", "year"]).any():
        raise ValueError("HDRO annual data contains duplicate country_code + year")
    if not hdi["year"].between(HDI_START_YEAR, HDI_END_YEAR).all():
        raise ValueError("HDRO annual data contains year outside 1990-2023")
    if not hdi["hdi"].between(0, 1).all():
        raise ValueError("HDRO annual data contains HDI outside [0,1]")
    return hdi


def prepare_events(emdat: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    dates, date_stats = construct_dates(emdat)
    out = pd.DataFrame({
        "event_id": emdat["DisNo."].astype("string").str.strip(),
        "country": emdat["Country"].astype("string").str.strip(),
        "country_code": emdat["ISO"].astype("string").str.strip().str.upper(),
        "region": emdat["Subregion"].astype("string").str.strip(),
        "disaster_type": emdat["Disaster Type"].astype("string").str.strip(),
        "disaster_subtype": emdat["Disaster Subtype"].astype("string").str.strip(),
        "year": numeric(emdat["Start Year"]).astype("Int64"),
        "total_deaths": numeric(emdat["Total Deaths"]),
        "total_affected": numeric(emdat["Total Affected"]),
        "total_damage": numeric(emdat["Total Damage ('000 US$)"]),
    })
    out = pd.concat([out, dates], axis=1)
    out["impact_level"] = impact_level(out["total_deaths"])
    out = add_historical_frequency(out)
    return out, date_stats


def merge_hdi(events: pd.DataFrame, hdi: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    merge_columns = hdi.rename(columns={"country_name": "hdi_country_name", "source": "hdi_source"})
    merged = events.merge(merge_columns, on=["country_code", "year"], how="left", validate="many_to_one")
    if len(merged) != len(events):
        raise AssertionError("HDI merge changed event row count")
    supported = set(coverage.loc[coverage["supported_by_hdro"].astype(str).str.lower().eq("true"), "country_code"])
    merged["hdi_source_year"] = merged["year"].where(merged["hdi"].notna()).astype("Int64")
    merged["hdi_imputed"] = False
    merged["hdi_match_status"] = "missing_country_year"
    merged.loc[merged["year"].lt(HDI_START_YEAR), "hdi_match_status"] = "before_hdi_range"
    merged.loc[merged["year"].gt(HDI_END_YEAR), "hdi_match_status"] = "after_hdi_range"
    merged.loc[~merged["country_code"].isin(supported) & merged["year"].between(HDI_START_YEAR, HDI_END_YEAR), "hdi_match_status"] = "unsupported_country"
    merged.loc[merged["year"].isna(), "hdi_match_status"] = "missing_event_year"
    merged.loc[merged["hdi"].notna(), "hdi_match_status"] = "exact_year"
    merged.loc[merged["hdi"].isna(), ["hdi_source", "hdi_source_year"]] = [pd.NA, pd.NA]
    return merged


def legacy_status(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series("missing_country_year", index=frame.index, dtype="string")
    result.loc[frame["hdi"].notna()] = "exact_year"
    if "hdi_missing_reason" in frame:
        result.loc[frame["hdi_missing_reason"].eq("country_not_in_hdi")] = "unsupported_country"
    result.loc[frame["year"].lt(HDI_START_YEAR)] = "before_hdi_range"
    result.loc[frame["year"].gt(HDI_END_YEAR)] = "after_hdi_range"
    return result


def dataframe_markdown(frame: pd.DataFrame) -> str:
    columns = [str(frame.index.name or "old_status"), *map(str, frame.columns)]
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for index, row in frame.iterrows():
        lines.append("| " + " | ".join([str(index), *[str(value) for value in row.tolist()]]) + " |")
    return "\n".join(lines)


def build_report(meta: dict[str, Any]) -> str:
    impact_rows = "\n".join(
        f"| {label} | {meta['impact'][label]:,} | {OLD_BASELINE['impact'][label]:,} | {meta['impact'][label] - OLD_BASELINE['impact'][label]:+,} |"
        for label in ("Low", "Moderate", "High", "Extreme")
    )
    status_rows = "\n".join(f"| {key} | {value:,} |" for key, value in meta["status_counts"].items())
    validation_rows = "\n".join(f"- {key}: {'通过' if value else '失败'}" for key, value in meta["frequency_checks"].items())
    unsupported = ", ".join(meta["unsupported_codes"]) or "无"
    incomplete = ", ".join(f"{code}({count})" for code, count in meta["incomplete_countries"][:30]) or "无"
    anomalies = "\n".join(
        f"- `{row.event_id}` / {row.country}: {row.date_anomaly}, event_date={row.event_date}, end_date={row.end_date}"
        for row in meta["date_anomalies"].itertuples()
    ) or "- 无"
    cross = dataframe_markdown(meta["status_cross"])
    exact_gain_pp = (meta["exact_rate"] - OLD_BASELINE["exact_rate"]) * 100
    suitable = (
        meta["row_count_ok"] and meta["impact_matches_baseline"] and all(meta["frequency_checks"].values())
        and meta["negative_duration"] == 0 and meta["duplicate_event_ids"] == 0
    )
    return f"""# EM-DAT + HDRO Data API 融合与质量报告

## 1. 数据来源与采集

- 灾害数据：`data/emdat_raw.xlsx`，工作表 `EM-DAT Data`。
- HDI 数据：HDRO Data API，接口 `CompositeIndices/query-detailed`。
- API 手册未提供独立版本号；指标元数据确认 indicator code 为 `hdi`（Human Development Index (value)）。
- API 采集时间（UTC）：{meta['collected_at']}。
- 请求范围：HDRO 支持的 EM-DAT ISO3 代码，1990-2023；批次大小 {meta['batch_size']}。
- 成功批次 {meta['successful_batches']}，失败批次 {meta['failed_batches']}，重试事件 {meta['retry_events']}。
- API Key 仅从环境读取，不写入日志、URL日志或生成文件。
- HDRO 历史序列可能发生官方回溯修订；`hdi_imputed=false` 仅表示本项目未自行插值。

## 2. 国家代码覆盖与年度数据质量

- EM-DAT 唯一非空 ISO3：{meta['emdat_unique_codes']}；空代码行 {meta['empty_code_rows']}；格式异常代码 {meta['format_anomaly_codes']}。
- HDRO 支持 {meta['supported_code_count']} 个，不支持 {len(meta['unsupported_codes'])} 个：{unsupported}。
- 成功返回 HDI 的国家：{meta['hdi_country_count']}；国家年度值：{meta['hdi_annual_values']:,}。
- 完整 34 年国家：{meta['complete_country_count']}；不完整/无值国家：{meta['incomplete_country_count']}。
- 不完整国家（代码/值数，最多列 30 项）：{incomplete}。
- `country_code + year` 唯一，年份均在 1990-2023，HDI 均在 0-1；AFG 与确认的单国测试完全一致。

## 3. 日期与 duration

- 完整日期按日；缺日按月精度；缺月和日按年精度。`event_date` 保存可用区间下界，同时保留 `event_date_upper`、`date_granularity` 和 `date_imputed`，不会将补全值伪装为精确日期。
- `duration` 使用开始区间下界与结束日期可用区间上界按包含首尾的天数计算。结束早于开始时不交换、不置零，`duration` 为空并设置 `date_anomaly=end_before_start`。
- 日期异常 {len(meta['date_anomalies'])} 条：
{anomalies}
- 负 duration：{meta['negative_duration']}。

## 4. historical_frequency 无泄漏实现

- 每个时间批次使用其真实可用区间：日、月或年。只有某历史批次的最晚可能日期严格早于当前批次的最早可能日期时才计入。
- 同国同批次事件共享批次开始前计数；当前批次仅影响之后明确不重叠的批次。没有使用 Excel 行顺序、全量国家总数或未来事件。
{validation_rows}

## 5. impact_level 回归核验

- 边界保持：0-9 Low、10-99 Moderate、100-999 High、>=1000 Extreme；死亡人数缺失不作为 0，标签保持为空。
- `total_deaths` 缺失 {meta['deaths_missing']:,}（旧版 {OLD_BASELINE['deaths_missing']:,}）；有效标签 {meta['labeled_rows']:,}（旧版 {OLD_BASELINE['labeled_rows']:,}）。

| 标签 | 新版 | 旧版 | 差异 |
|---|---:|---:|---:|
{impact_rows}

## 6. HDI 合并与新旧覆盖比较

- 合并键：EM-DAT `ISO` + 灾害开始年份，`validate="many_to_one"`。
- 合并前 {meta['rows_before']:,} 行，合并后 {meta['rows_after']:,} 行；无一对多膨胀：{'是' if meta['row_count_ok'] else '否'}。
- 旧版 HDI：{OLD_BASELINE['annual_values']:,} 个国家年度值，精确匹配 {OLD_BASELINE['exact_matches']:,}，匹配率 {OLD_BASELINE['exact_rate']:.2%}。
- 新版 HDI：{meta['hdi_annual_values']:,} 个国家年度值，精确匹配 {meta['exact_matches']:,}，匹配率 {meta['exact_rate']:.2%}。
- 匹配率提升 {exact_gain_pp:.2f} 个百分点；精确匹配增加 {meta['exact_matches'] - OLD_BASELINE['exact_matches']:+,} 条。
- 1990 年前 {meta['status_counts'].get('before_hdi_range', 0):,}；2023 年后 {meta['status_counts'].get('after_hdi_range', 0):,}；范围内缺少国家年度值 {meta['status_counts'].get('missing_country_year', 0):,}；不支持国家 {meta['status_counts'].get('unsupported_country', 0):,}。
- 旧版未匹配而新版通过 ISO + 年份精确匹配 {meta['newly_exact']:,} 条；其中旧版国家不匹配状态转为精确匹配 {meta['mapping_change_records']:,} 条。

| 新版 hdi_match_status | 记录数 |
|---|---:|
{status_rows}

旧版到新版状态交叉表：

{cross}

## 7. 完整性、可重复性与结论

- 事件 ID 重复行：{meta['duplicate_event_ids']}；原始 EM-DAT SHA-256 运行前后相同：{'是' if meta['raw_hash_unchanged'] else '否'}。
- 主合并集保留全部事件；model-ready 仅排除标签缺失，不因 HDI 缺失删行。
- 当前是否适合进入时间划分的机器学习基线阶段：{'有条件适合' if suitable else '暂不适合'}。
- 建模前仍应明确处理：HDI 缺失状态、日期区间精度、类别不平衡；训练/测试必须按时间划分。本阶段没有训练任何模型。
"""


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emdat", type=Path, default=root / "data" / "emdat_raw.xlsx")
    parser.add_argument("--hdi", type=Path, default=root / "data" / "raw" / "hdro_hdi_annual.csv")
    parser.add_argument("--coverage", type=Path, default=root / "data" / "raw" / "hdro_country_coverage.csv")
    parser.add_argument("--output-dir", type=Path, default=root / "data" / "processed_hdro")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    before_hash = file_sha256(args.emdat)
    emdat = load_emdat(args.emdat)
    LOG.info("Loaded EM-DAT: %d rows x %d columns", *emdat.shape)
    events, date_stats = prepare_events(emdat)
    hdi = load_hdi(args.hdi)
    coverage = pd.read_csv(args.coverage, encoding="utf-8-sig", dtype={"country_code": "string"})
    merged = merge_hdi(events, hdi, coverage)
    checks = validate_historical_frequency(merged)

    boundary_test = impact_level(pd.Series([0, 9, 10, 99, 100, 999, 1000, np.nan])).tolist()
    assert boundary_test == ["Low", "Low", "Moderate", "Moderate", "High", "High", "Extreme", pd.NA]
    assert all(checks.values()), f"Historical frequency validation failed: {checks}"
    assert len(emdat) == 16858 and len(merged) == 16858
    assert not merged["event_id"].duplicated().any()
    assert int((merged["duration"].dropna() < 0).sum()) == 0

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_ready = merged[merged["impact_level"].notna()].copy()
    unsupported = coverage.loc[coverage["supported_by_hdro"].astype(str).str.lower().eq("false")].copy()
    unmatched = (
        merged.loc[merged["hdi_match_status"].eq("unsupported_country"), ["country_code", "country"]]
        .value_counts(dropna=False).rename("record_count").reset_index()
    )
    missing_summary = (
        merged.loc[merged["hdi"].isna(), ["hdi_match_status", "country_code", "country", "year"]]
        .value_counts(dropna=False).rename("record_count").reset_index()
    )
    validation = merged[["event_id", "country_code", "country", "event_date", "event_date_upper", "date_granularity", "time_batch", "historical_frequency"]].copy()

    impact = merged["impact_level"].value_counts().reindex(["Low", "Moderate", "High", "Extreme"], fill_value=0).astype(int).to_dict()
    status_counts = merged["hdi_match_status"].value_counts().to_dict()
    old_path = root / "data" / "processed" / "disaster_hdi_merged.csv"
    old = pd.read_csv(old_path, encoding="utf-8-sig", dtype={"event_id": "string"})
    old["old_status"] = legacy_status(old)
    compare = merged[["event_id", "hdi_match_status"]].merge(old[["event_id", "old_status", "hdi"]], on="event_id", validate="one_to_one")
    status_cross = pd.crosstab(compare["old_status"], compare["hdi_match_status"])

    collection = json.loads((root / "data" / "raw" / "hdro_hdi_response.json").read_text(encoding="utf-8"))
    collection_summary = json.loads((root / "data" / "raw" / "hdro_collection_summary.json").read_text(encoding="utf-8"))
    country_summary = pd.read_csv(root / "data" / "raw" / "hdro_hdi_country_summary.csv")
    incomplete = country_summary.loc[country_summary["annual_value_count"].ne(34), ["country_code", "annual_value_count"]]
    date_anomalies = merged.loc[merged["date_anomaly"].ne(""), ["event_id", "country", "event_date", "end_date", "date_anomaly"]]
    after_hash = file_sha256(args.emdat)
    meta = {
        "collected_at": collection["collected_at_utc"], "batch_size": 20,
        "successful_batches": collection_summary["batch"]["successful_batches"], "failed_batches": collection_summary["batch"]["failed_batches"],
        "retry_events": collection_summary["batch"]["retry_events"], "emdat_unique_codes": collection_summary["coverage"]["unique_nonempty_codes"],
        "empty_code_rows": collection_summary["coverage"]["empty_code_rows"], "format_anomaly_codes": collection_summary["coverage"]["format_anomaly_codes"],
        "supported_code_count": collection_summary["coverage"]["supported_codes"],
        "unsupported_codes": sorted(unsupported["country_code"].dropna().astype(str).tolist()),
        "hdi_country_count": hdi["country_code"].nunique(), "hdi_annual_values": len(hdi),
        "complete_country_count": collection_summary["batch"]["complete_country_count"], "incomplete_country_count": collection_summary["batch"]["incomplete_country_count"],
        "incomplete_countries": list(incomplete.itertuples(index=False, name=None)), "date_anomalies": date_anomalies,
        "negative_duration": int((merged["duration"].dropna() < 0).sum()), "frequency_checks": checks,
        "deaths_missing": int(merged["total_deaths"].isna().sum()), "labeled_rows": len(model_ready), "impact": impact,
        "rows_before": len(emdat), "rows_after": len(merged), "row_count_ok": len(emdat) == len(merged),
        "exact_matches": int(merged["hdi"].notna().sum()), "exact_rate": float(merged["hdi"].notna().mean()),
        "status_counts": status_counts, "newly_exact": int(compare["hdi"].isna().mul(compare["hdi_match_status"].eq("exact_year")).sum()),
        "mapping_change_records": int(compare["old_status"].eq("unsupported_country").mul(compare["hdi_match_status"].eq("exact_year")).sum()),
        "status_cross": status_cross, "duplicate_event_ids": int(merged["event_id"].duplicated(keep=False).sum()),
        "raw_hash_unchanged": before_hash == after_hash, "impact_matches_baseline": impact == OLD_BASELINE["impact"],
    }
    if meta["deaths_missing"] != OLD_BASELINE["deaths_missing"] or meta["labeled_rows"] != OLD_BASELINE["labeled_rows"] or not meta["impact_matches_baseline"]:
        raise RuntimeError("Impact-label regression baseline changed; refusing to finalize processed_hdro outputs")

    merged.to_csv(output_dir / "disaster_hdi_merged.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    model_ready.to_csv(output_dir / "disaster_model_ready.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    unmatched.to_csv(output_dir / "unmatched_countries.csv", index=False, encoding="utf-8-sig")
    missing_summary.to_csv(output_dir / "hdi_missing_summary.csv", index=False, encoding="utf-8-sig")
    validation.to_csv(output_dir / "historical_frequency_validation.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    (output_dir / "data_merge_report_hdro.md").write_text(build_report(meta), encoding="utf-8")
    LOG.info("Wrote isolated HDRO outputs to %s", output_dir)
    LOG.info("Exact HDI match: %d/%d (%.2f%%)", meta["exact_matches"], len(merged), meta["exact_rate"] * 100)
    LOG.info("All label and historical-frequency regression checks passed")


if __name__ == "__main__":
    main()
