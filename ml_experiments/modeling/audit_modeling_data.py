"""Audit model-ready fields and propose strict temporal splits without training."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd

TARGET = "impact_level"
CLASSES = ["Low", "Moderate", "High", "Extreme"]
MAJOR_TYPE_COUNT = 10

AUDIT_RULES: dict[str, tuple[str, str, str]] = {
    "event_id": ("identifier_and_time_proxy", "no", "Keep only for row tracing; exclude from X because DisNo. embeds year/country information."),
    "country": ("duplicate_location_identifier", "no", "Use country_code or region, not both country name and code."),
    "country_code": ("distribution_shift_risk", "conditional", "Categorical encoder fit on training only; handle unseen ISO3 as unknown."),
    "region": ("low_risk_context", "yes", "One-hot encode on training only with unknown-category handling."),
    "disaster_type": ("low_risk_event_context", "yes", "One-hot encode on training only; preserve unknown category."),
    "disaster_subtype": ("sparse_high_cardinality", "conditional", "Group rare levels using training frequencies, then one-hot encode."),
    "year": ("temporal_proxy_not_target_leakage", "yes", "Use numeric trend only after strict temporal split; never random split."),
    "total_deaths": ("direct_target_leakage", "no", "Direct source used to generate impact_level; exclude from every model input."),
    "total_affected": ("post_event_outcome_leakage", "no", "Usually finalized after the event; exclude for onset-time prediction."),
    "total_damage": ("post_event_outcome_leakage", "no", "Economic-loss estimate is post-event and revision-prone; exclude."),
    "event_date": ("start_time_available_with_partial_precision", "conditional", "Derive calendar features while retaining date_granularity/date_imputed; fit transforms on training only."),
    "event_date_upper": ("artificial_precision_boundary", "no", "Audit field only; use date_granularity rather than the constructed upper boundary."),
    "end_date": ("post_event_leakage", "no", "Known only after the event and may be revised; exclude."),
    "date_granularity": ("data_quality_context", "yes", "One-hot encode; preserves day/month/year precision without pretending exactness."),
    "date_imputed": ("data_quality_context", "yes", "Boolean precision indicator; retain alongside date_granularity."),
    "date_anomaly": ("end_date_derived_post_event", "no", "Retain for QA, but exclude from onset-time prediction because it uses end-date information."),
    "duration": ("post_event_leakage", "no", "Derived from event end; exclude from onset-time prediction."),
    "impact_level": ("target", "target_only", "Prediction target; generated only from total_deaths boundaries."),
    "time_batch": ("high_cardinality_duplicate_time", "no", "Audit key only; redundant with start time and precision."),
    "historical_frequency": ("causal_historical_feature", "yes", "Use unchanged; already computed only from clearly prior time intervals."),
    "hdi_country_name": ("duplicate_merge_metadata", "no", "Exclude; duplicate label for country_code."),
    "hdi": ("contemporaneous_context_with_missingness", "yes", "RF: training-only median plus hdi_missing. Native-NaN model: keep NaN plus hdi_missing."),
    "hdi_source": ("missingness_proxy_and_constant", "no", "Exclude; source availability duplicates HDI missingness."),
    "hdi_source_year": ("year_and_missingness_proxy", "no", "Exclude; duplicates event year when HDI exists and encodes missingness otherwise."),
    "hdi_imputed": ("constant_metadata", "no", "Currently always false; retain for audit but exclude from X."),
    "hdi_match_status": ("year_region_missingness_proxy", "no_primary", "Do not use as socioeconomic feature; derive only hdi_missing unless a separately audited missingness experiment is run."),
}

SPLIT_SCHEMES = {
    "A_conservative_backtest": {
        "train": (2000, 2015), "validation": (2016, 2017), "test": (2018, 2020), "maturity_holdback": (2021, 2026),
        "note": "Long historical training window and early stable test; useful robustness backtest but less representative of recent conditions.",
    },
    "B_recommended_stable_recent": {
        "train": (2000, 2019), "validation": (2020, 2021), "test": (2022, 2023), "maturity_holdback": (2024, 2026),
        "note": "Recommended: recent but likely mature test years; 2024-2026 held out because casualty/loss revisions may still be incomplete.",
    },
    "C_rolling_origin_sensitivity": {
        "train": (2000, 2017), "validation": (2018, 2019), "test": (2020, 2022), "maturity_holdback": (2023, 2026),
        "note": "More conservative maturity cutoff and includes pandemic-era distribution shift in test; smaller recent training window.",
    },
}


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return result or "unknown"


def feature_audit(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in frame.columns:
        missing = int(frame[column].isna().sum())
        risk, recommendation, handling = AUDIT_RULES.get(
            column, ("manual_review_required", "no_until_reviewed", "Unknown field: exclude until provenance and availability timing are documented.")
        )
        rows.append({
            "field": column,
            "pandas_dtype": str(frame[column].dtype),
            "missing_count": missing,
            "missing_rate": missing / len(frame),
            "unique_count": int(frame[column].nunique(dropna=True)),
            "leakage_risk": risk,
            "recommended_as_feature": recommendation,
            "recommended_encoding_or_missing_handling": handling,
        })
    return pd.DataFrame(rows)


def yearly_distribution(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    major_types = frame["disaster_type"].value_counts().head(MAJOR_TYPE_COUNT).index.tolist()
    rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year", sort=True):
        row: dict[str, Any] = {
            "year": int(year),
            "sample_count": len(group),
            "hdi_missing_count": int(group["hdi"].isna().sum()),
            "hdi_missing_rate": float(group["hdi"].isna().mean()),
        }
        for label in CLASSES:
            count = int(group[TARGET].eq(label).sum())
            row[f"{label.lower()}_count"] = count
            row[f"{label.lower()}_rate"] = count / len(group)
        for disaster_type in major_types:
            row[f"type_{slug(disaster_type)}_count"] = int(group["disaster_type"].eq(disaster_type).sum())
        rows.append(row)
    return pd.DataFrame(rows), major_types


def split_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scheme, config in SPLIT_SCHEMES.items():
        for subset in ("train", "validation", "test", "maturity_holdback"):
            start, end = config[subset]
            part = frame[frame["year"].between(start, end)]
            row: dict[str, Any] = {
                "scheme": scheme,
                "subset": subset,
                "start_year": start,
                "end_year": end,
                "sample_count": len(part),
                "hdi_missing_count": int(part["hdi"].isna().sum()),
                "hdi_missing_rate": float(part["hdi"].isna().mean()) if len(part) else 0.0,
                "preprocessing_fit_allowed": subset == "train",
                "notes": config["note"],
            }
            for label in CLASSES:
                count = int(part[TARGET].eq(label).sum())
                row[f"{label.lower()}_count"] = count
                row[f"{label.lower()}_rate"] = count / len(part) if len(part) else 0.0
            rows.append(row)
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, divider]
    for _, row in frame[columns].iterrows():
        values = []
        for column in columns:
            value = row[column]
            if column.endswith("_rate"):
                values.append(f"{float(value):.2%}")
            elif isinstance(value, float) and value.is_integer():
                values.append(str(int(value)))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_report(
    frame: pd.DataFrame,
    audit: pd.DataFrame,
    yearly: pd.DataFrame,
    splits: pd.DataFrame,
    major_types: list[str],
) -> str:
    status = frame["hdi_match_status"].value_counts().reindex(
        ["exact_year", "missing_country_year", "unsupported_country", "after_hdi_range"], fill_value=0
    )
    status_lines = "\n".join(
        f"| {name} | {int(count):,} | {int(count) / len(frame):.2%} |" for name, count in status.items()
    )
    split_table = markdown_table(
        splits[splits["subset"].ne("maturity_holdback")],
        ["scheme", "subset", "start_year", "end_year", "sample_count", "low_count", "moderate_count", "high_count", "extreme_count", "hdi_missing_rate"],
    )
    holdback_table = markdown_table(
        splits[splits["subset"].eq("maturity_holdback")],
        ["scheme", "start_year", "end_year", "sample_count", "hdi_missing_rate"],
    )
    included = audit[audit["recommended_as_feature"].isin(["yes", "conditional"])]["field"].tolist()
    excluded = audit[audit["recommended_as_feature"].isin(["no", "no_primary", "target_only"])]["field"].tolist()
    return f"""# 建模前字段审计与严格时间划分报告

## 1. 数据范围

- 正式输入：`data/processed_hdro/disaster_model_ready.csv`，{len(frame):,} 行、{len(frame.columns)} 列。
- 灾害年份：{int(frame['year'].min())}-{int(frame['year'].max())}。
- 本轮只做审计与切分建议，没有训练、拟合或保存任何模型。
- `impact_level` 仅由 `total_deaths` 生成：0-9 Low、10-99 Moderate、100-999 High、>=1000 Extreme；死亡人数缺失时标签为空，已在 model-ready 中排除。

## 2. 泄漏结论

- `total_deaths` 是直接目标来源，绝对禁止进入模型输入。当前没有 `casualties` 字段，也没有其他 death-related 派生特征。
- `total_affected`、`total_damage`、`end_date`、`duration` 与 `date_anomaly` 通常只能在事件发生后确认，若目标是在事件发生时预测影响等级，应排除。
- `hdi_match_status` 不是直接目标泄漏，但明显代理年份、地区和 HDI 可得性；不作为主要社会经济特征。模型只增加 `hdi_missing = hdi.isna()`。
- 推荐/条件推荐字段：{', '.join(included)}。
- 排除或仅作目标/审计字段：{', '.join(excluded)}。
- 完整逐字段结论见 `feature_audit.csv`。

## 3. HDI 缺失机制

| hdi_match_status | 数量 | 比例 |
|---|---:|---:|
{status_lines}

- Random Forest：在严格切分后，仅用训练集 HDI 中位数拟合填充器，并同时添加 `hdi_missing`；验证集和测试集只能调用该训练期参数。
- 原生支持 NaN 的模型：保留 NaN，并保留 `hdi_missing`。
- 禁止使用全数据中位数、未来年份、邻近年份或测试期统计量补齐。

## 4. 年度和灾害类型分布

- 年度表覆盖每年样本数、四类目标数量/比例、HDI 缺失率，以及全局数量最高的十类灾害：{', '.join(major_types)}。
- 详细数据见 `yearly_target_distribution.csv`。
- 2026 年只有 {int(yearly.loc[yearly['year'].eq(2026), 'sample_count'].iloc[0]):,} 条，且 2024-2026 的伤亡和损失可能继续修订，不作为推荐测试集。

## 5. 严格时间划分候选

{split_table}

成熟度留置区：

{holdback_table}

### 建议

推荐 `B_recommended_stable_recent`：2000-2019 训练、2020-2021 验证、2022-2023 测试，2024-2026 留置。它在保持严格时间顺序的同时，使用相对近期且更可能稳定的测试年份。

所有编码器、稀有类别规则、HDI 中位数、缺失处理器及任何特征选择都只能在训练集拟合。验证集用于调参，测试集在最终选择确定前保持封存。`historical_frequency` 直接使用现有因果实现，不重新累计或随机重排。

## 6. 训练前仍需确认

1. 明确预测时点为事件发生时；若预测时点不同，重新审查事后字段可用性。
2. 确认采用推荐时间切分，并将 2024-2026 保持为成熟度留置区。
3. 确认主基线特征清单及高基数国家/灾害亚型的编码策略。
4. 在训练流水线中用断言阻止 `total_deaths`、目标列和事后字段进入 X。
"""


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data" / "processed_hdro" / "disaster_model_ready.csv")
    parser.add_argument("--output-dir", type=Path, default=root / "ml_experiments" / "modeling" / "reports")
    args = parser.parse_args()
    frame = pd.read_csv(args.input, encoding="utf-8-sig", low_memory=False)
    if TARGET not in frame.columns or frame.empty:
        raise ValueError("Model-ready input is empty or missing impact_level")
    if frame[TARGET].isna().any():
        raise ValueError("Model-ready input unexpectedly contains missing target labels")
    if set(frame[TARGET].unique()) - set(CLASSES):
        raise ValueError("Unexpected impact_level class found")

    audit = feature_audit(frame)
    yearly, major_types = yearly_distribution(frame)
    splits = split_candidates(frame)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_dir / "feature_audit.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(output_dir / "yearly_target_distribution.csv", index=False, encoding="utf-8-sig")
    splits.to_csv(output_dir / "temporal_split_candidates.csv", index=False, encoding="utf-8-sig")
    (output_dir / "modeling_audit_report.md").write_text(
        build_report(frame, audit, yearly, splits, major_types), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
