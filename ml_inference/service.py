from __future__ import annotations

from typing import Any

from .errors import InferenceError
from .response_builder import BUILDER, predict_payload


def prediction_response(payload: Any) -> tuple[int, dict[str, Any]]:
    try:
        return 200, predict_payload(payload)
    except InferenceError as exc:
        return exc.status, {"success": False, "error": {"code": exc.code, "message": exc.message}}
    except Exception:
        return 500, {"success": False, "error": {"code": "INFERENCE_FAILED", "message": "模型辅助分析暂时不可用，请稍后重试。"}}


def health_response() -> dict[str, Any]:
    return {"success": True, "status": "ready", "model": "Random Forest T2",
            "classes": ["Low", "Moderate", "Severe"], "purpose": "辅助分析"}


def options_response() -> dict[str, Any]:
    options = BUILDER.public_options()
    countries = options.get("countries")
    disaster_types = options.get("disaster_types")
    scales = options.get("magnitude_scales")
    if not isinstance(countries, list) or not countries:
        raise ValueError("countries unavailable")
    if not isinstance(disaster_types, list) or not disaster_types:
        raise ValueError("disaster types unavailable")
    if not isinstance(scales, list):
        raise ValueError("magnitude scales malformed")
    if any(not isinstance(item, dict) or not isinstance(item.get("code"), str) for item in countries):
        raise ValueError("country contract malformed")
    if any(not isinstance(item, dict) or not isinstance(item.get("type"), str) or not isinstance(item.get("subtypes"), list) for item in disaster_types):
        raise ValueError("disaster type contract malformed")
    return {"success": True, **options}


def options_http_response() -> tuple[int, dict[str, Any]]:
    try:
        return 200, options_response()
    except Exception:
        return 500, {"success": False, "error": {"code": "OPTIONS_UNAVAILABLE", "message": "输入选项暂时无法载入，请稍后重试。"}}
