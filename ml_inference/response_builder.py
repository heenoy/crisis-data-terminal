from __future__ import annotations

from typing import Any

import numpy as np

from .feature_builder import FrozenFeatureBuilder
from .loader import get_pipeline

LABEL_ZH = {"Low": "低影响", "Moderate": "中等影响", "Severe": "严重影响"}
DISCLAIMER = "该结果仅用于灾害档案辅助分析，不构成专业预警或决策意见。"
BUILDER = FrozenFeatureBuilder()


def _reference_factors(frame, quality: dict[str, Any]) -> list[str]:
    row = frame.iloc[0]
    factors = [f"灾害类型及子类型：{row.disaster_type} / {row.disaster_subtype}",
               f"国家或地区背景：{row.country_code} / {row.region}",
               f"冻结历史档案频次：{int(row.historical_frequency)}"]
    factors.append("HDI背景信息缺失，模型使用冻结缺失处理。" if quality["hdi_missing"] else f"事件年度HDI背景值：{float(row.hdi):.3f}")
    if quality["magnitude_missing"]:
        factors.append("Magnitude未提供，不展示组内相对位置。")
    elif quality["magnitude_group_unknown"]:
        factors.append("该事件缺少适用的Magnitude组内标准化依据。")
    else:
        factors.append(f"Magnitude同语义组内相对位置：{float(row.magnitude_robust_z):.3f}（不可跨量表比较）")
    factors.append("日期仅有年份，月份作为缺失处理。" if row.month_missing else f"事件月份：{int(row.event_month)}月")
    return factors


def predict_payload(payload: Any) -> dict[str, Any]:
    frame, quality = BUILDER.build(payload)
    pipeline = get_pipeline()
    predicted = str(pipeline.predict(frame)[0])
    raw = pipeline.predict_proba(frame)[0]
    classes = pipeline.named_steps["model"].classes_.tolist()
    # Stable wire representation: suppress only non-deterministic parallel summation noise (~1e-16).
    probabilities = {label: round(float(raw[classes.index(label)]), 12) for label in ["Low", "Moderate", "Severe"]}
    if not np.isclose(sum(probabilities.values()), 1.0, atol=1e-12):
        raise RuntimeError("Prediction probabilities do not sum to one")
    return {"success": True, "prediction": {"level": predicted, "label_zh": LABEL_ZH[predicted], "probabilities": probabilities},
            "input_quality": quality, "reference_factors": _reference_factors(frame, quality),
            "model_info": {"model": "Random Forest T2", "classes": ["Low", "Moderate", "Severe"], "purpose": "辅助分析"},
            "disclaimer": DISCLAIMER}
