from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .errors import InferenceError

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "frozen_assets"
FEATURES = [
    "country_code", "region", "disaster_type", "disaster_subtype", "date_granularity",
    "year", "date_imputed", "historical_frequency", "hdi", "hdi_missing",
    "event_month", "month_missing", "magnitude_robust_z", "magnitude_missing",
    "magnitude_group_unknown",
]
ALLOWED_INPUTS = {"country_code", "disaster_type", "disaster_subtype", "event_date",
                  "date_granularity", "magnitude", "magnitude_scale"}
MAX_STRING_LENGTH = 120


@dataclass(frozen=True)
class ParsedDate:
    year: int
    month: int | None
    interval_start: pd.Timestamp
    interval_end: pd.Timestamp
    granularity: str


class FrozenFeatureBuilder:
    def __init__(self, assets_dir: Path = ASSETS):
        self.assets_dir = assets_dir
        self.manifest = json.loads((assets_dir / "asset_manifest.json").read_text(encoding="utf-8"))
        country = pd.read_csv(assets_dir / "country_region.csv", dtype=str)
        pairs = pd.read_csv(assets_dir / "disaster_type_subtype.csv", dtype=str)
        self.country_region = dict(zip(country.country_code, country.region))
        self.country_names = dict(zip(country.country_code, country.country))
        self.valid_pairs = set(zip(pairs.disaster_type, pairs.disaster_subtype))
        self.subtypes_by_type = {key: sorted(group.disaster_subtype.tolist()) for key, group in pairs.groupby("disaster_type")}
        self.vocab = json.loads((assets_dir / "category_vocabularies.json").read_text(encoding="utf-8"))
        history = pd.read_csv(assets_dir / "historical_frequency_intervals.csv",
                              parse_dates=["interval_start", "interval_end"], dtype={"country_code": str})
        self.history = {code: group[["interval_start", "interval_end", "event_count"]].copy()
                        for code, group in history.groupby("country_code", sort=False)}
        hdi = pd.read_csv(assets_dir / "hdi_annual.csv", dtype={"country_code": str})
        self.hdi = {(row.country_code, int(row.year)): float(row.hdi) for row in hdi.itertuples()}
        mag = pd.read_csv(assets_dir / "magnitude_groups.csv")
        self.magnitude_groups = {row.group_key: row for row in mag.itertuples()}

    def public_options(self) -> dict[str, Any]:
        subtype_to_type = {
            subtype: disaster_type
            for disaster_type, subtypes in self.subtypes_by_type.items()
            for subtype in subtypes
        }
        unit_labels = {
            "Km2": "km²",
            "Kph": "km/h",
            "Moment Magnitude": "震级",
            "°C": "°C",
        }
        magnitude_groups = []
        for key, row in sorted(self.magnitude_groups.items()):
            group_name, scale = key.rsplit(" | ", 1)
            strategy = str(row.grouping_strategy)
            disaster_type = group_name if strategy.startswith("disaster_type") else subtype_to_type.get(group_name)
            eligible = bool(row.eligible)
            references = []
            if eligible:
                references = [
                    {"label": "较低参考值", "value": float(row.training_q1)},
                    {"label": "中位参考值", "value": float(row.training_median)},
                    {"label": "较高参考值", "value": float(row.training_q3)},
                ]
            magnitude_groups.append({
                "group_key": key,
                "group_name": group_name,
                "disaster_type": disaster_type,
                "magnitude_scale": scale,
                "unit_label": unit_labels.get(scale, scale),
                "eligible": eligible,
                "sample_count": int(row.training_nonmissing),
                "grouping_strategy": strategy,
                "references": references,
            })
        return {
            "countries": [{"code": code, "name": self.country_names[code], "region": self.country_region[code]} for code in sorted(self.country_region)],
            "disaster_types": [{"type": key, "subtypes": values} for key, values in sorted(self.subtypes_by_type.items())],
            "date_granularities": ["day", "month", "year"],
            "magnitude_scales": ["Km2", "Kph", "Moment Magnitude", "°C"],
            "magnitude_groups": magnitude_groups,
            "hdi_year_range": self.manifest["hdi_range"],
            "historical_source_cutoff": self.manifest["historical_source_cutoff"],
        }

    @staticmethod
    def _text(payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise InferenceError("MISSING_FIELD", f"缺少必填字段：{field}")
        value = value.strip()
        if len(value) > MAX_STRING_LENGTH:
            raise InferenceError("FIELD_TOO_LONG", f"字段过长：{field}")
        return value

    @staticmethod
    def _parse_date(value: str, granularity: str) -> ParsedDate:
        try:
            if granularity == "day":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value): raise ValueError
                parsed = date.fromisoformat(value)
                stamp = pd.Timestamp(parsed)
                return ParsedDate(parsed.year, parsed.month, stamp, stamp, granularity)
            if granularity == "month":
                if not re.fullmatch(r"\d{4}-\d{2}", value): raise ValueError
                year, month = map(int, value.split("-"))
                if not 1 <= month <= 12: raise ValueError
                start = pd.Timestamp(year, month, 1)
                return ParsedDate(year, month, start, start + pd.offsets.MonthEnd(0), granularity)
            if granularity == "year":
                if not re.fullmatch(r"\d{4}", value): raise ValueError
                year = int(value)
                return ParsedDate(year, None, pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31), granularity)
        except (ValueError, OverflowError):
            pass
        raise InferenceError("INVALID_EVENT_DATE", "发生日期与日期精度不匹配或格式无效")

    @staticmethod
    def _normalize_scale(scale: str | None) -> str | None:
        if scale is None: return None
        value = scale.strip()
        aliases = {"Km²": "Km2", "km2": "Km2", "km²": "Km2", "°C": "\u00b0C", "℃": "\u00b0C"}
        return aliases.get(value, value)

    def _magnitude(self, disaster_type: str, subtype: str, magnitude: Any, scale: Any) -> tuple[float, int, int, list[str]]:
        warnings = []
        missing = magnitude is None or magnitude == ""
        numeric = np.nan
        if not missing:
            if isinstance(magnitude, bool):
                raise InferenceError("INVALID_MAGNITUDE", "Magnitude必须为有限数值")
            try: numeric = float(magnitude)
            except (TypeError, ValueError): raise InferenceError("INVALID_MAGNITUDE", "Magnitude必须为有限数值")
            if not math.isfinite(numeric) or abs(numeric) > 1e12:
                raise InferenceError("INVALID_MAGNITUDE", "Magnitude必须为合理范围内的有限数值")
            if not isinstance(scale, str) or not scale.strip():
                raise InferenceError("MISSING_MAGNITUDE_SCALE", "填写Magnitude时必须同时选择量表")
        normalized_scale = self._normalize_scale(scale if isinstance(scale, str) else None)
        type_groups = {("Drought", "Km2"), ("Flood", "Km2"), ("Wildfire", "Km2"),
                       ("Storm", "Kph"), ("Earthquake", "Moment Magnitude")}
        subtype_groups = {("Cold wave", "\u00b0C"), ("Heat wave", "\u00b0C"), ("Severe winter conditions", "\u00b0C")}
        group_key = None
        if (disaster_type, normalized_scale) in type_groups:
            group_key = f"{disaster_type} | {normalized_scale}"
        elif (subtype, normalized_scale) in subtype_groups:
            group_key = f"{subtype} | {normalized_scale}"
        row = self.magnitude_groups.get(group_key)
        eligible = bool(row is not None and row.eligible)
        unknown = int(not eligible)
        z = np.nan
        if missing:
            warnings.append("Magnitude缺失，未计算组内相对位置。")
        elif not eligible:
            warnings.append("当前灾害类型、子类型与量表缺少适用的冻结组内标准化依据。")
        else:
            z = float(np.clip((numeric - float(row.training_median)) / float(row.training_iqr), -5, 5))
        return z, int(missing), unknown, warnings

    def build(self, payload: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
        if not isinstance(payload, dict) or not payload:
            raise InferenceError("EMPTY_REQUEST", "请求体不能为空")
        unknown_fields = sorted(set(payload) - ALLOWED_INPUTS)
        if unknown_fields:
            raise InferenceError("UNKNOWN_FIELDS", f"请求包含不支持的字段：{', '.join(unknown_fields)}")
        country_code = self._text(payload, "country_code").upper()
        disaster_type = self._text(payload, "disaster_type")
        subtype = self._text(payload, "disaster_subtype")
        granularity = self._text(payload, "date_granularity").lower()
        event_date = self._text(payload, "event_date")
        if country_code not in self.country_region:
            raise InferenceError("UNKNOWN_COUNTRY_CODE", "国家或地区代码不在冻结模型支持范围内")
        if disaster_type not in self.subtypes_by_type:
            raise InferenceError("UNKNOWN_DISASTER_TYPE", "灾害类型不在冻结模型支持范围内")
        known_subtypes = {value for values in self.subtypes_by_type.values() for value in values}
        if subtype not in known_subtypes:
            raise InferenceError("UNKNOWN_DISASTER_SUBTYPE", "灾害子类型不在冻结模型支持范围内")
        if (disaster_type, subtype) not in self.valid_pairs:
            raise InferenceError("INVALID_TYPE_SUBTYPE_PAIR", "灾害类型与子类型组合不符合冻结映射")
        if granularity not in {"day", "month", "year"}:
            raise InferenceError("INVALID_DATE_GRANULARITY", "日期精度必须为day、month或year")
        parsed = self._parse_date(event_date, granularity)
        if parsed.year < 1900 or parsed.year > 2100:
            raise InferenceError("YEAR_OUT_OF_SUPPORTED_RANGE", "年份必须位于1900—2100")

        history = self.history.get(country_code)
        historical_frequency = 0 if history is None else int(history.loc[history.interval_end.lt(parsed.interval_start), "event_count"].sum())
        hdi = self.hdi.get((country_code, parsed.year), np.nan)
        hdi_missing = int(pd.isna(hdi))
        z, mag_missing, mag_unknown, warnings = self._magnitude(disaster_type, subtype, payload.get("magnitude"), payload.get("magnitude_scale"))
        unseen = []
        for field, value in [("country_code", country_code), ("region", self.country_region[country_code]),
                             ("disaster_type", disaster_type), ("disaster_subtype", subtype)]:
            if value not in self.vocab[field]: unseen.append(field)
        if unseen:
            warnings.append(f"以下类别未在Development词表中出现，将按冻结编码器的未知类别规则处理：{', '.join(unseen)}。")
        if hdi_missing:
            warnings.append("冻结HDI表中没有该国家或地区对应年度值，模型将使用训练时已冻结的缺失处理。")
        if parsed.year > 2023:
            warnings.append("历史频率仅依据截至2023-12-31的冻结灾害档案计算，不随在线数据库变化。")
        row = {
            "country_code": country_code, "region": self.country_region[country_code],
            "disaster_type": disaster_type, "disaster_subtype": subtype,
            "date_granularity": granularity, "year": parsed.year,
            "date_imputed": int(granularity in {"month", "year"}),
            "historical_frequency": historical_frequency,
            "hdi": hdi, "hdi_missing": hdi_missing,
            "event_month": float(parsed.month) if parsed.month is not None else np.nan,
            "month_missing": int(parsed.month is None),
            "magnitude_robust_z": z, "magnitude_missing": mag_missing,
            "magnitude_group_unknown": mag_unknown,
        }
        frame = pd.DataFrame([row], columns=FEATURES)
        quality = {"missing_fields": [name for name, flag in [("hdi", hdi_missing), ("event_month", row["month_missing"]), ("magnitude", mag_missing)] if flag],
                   "warnings": warnings, "hdi_missing": bool(hdi_missing), "magnitude_missing": bool(mag_missing),
                   "magnitude_group_unknown": bool(mag_unknown), "historical_source_cutoff": "2023-12-31"}
        return frame, quality
