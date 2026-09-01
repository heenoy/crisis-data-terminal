"""Audited feature allowlists and leakage guards for baseline modeling."""

from __future__ import annotations

import re

LABEL_ORDER = ["Low", "Moderate", "High", "Extreme"]
RANDOM_STATE = 20260803

CATEGORICAL_V1 = [
    "country_code",
    "region",
    "disaster_type",
    "disaster_subtype",
    "date_granularity",
]

NUMERIC_V1 = [
    "year",
    "date_imputed",
    "historical_frequency",
    "hdi",
    "hdi_missing",
]

CATEGORICAL_V2 = CATEGORICAL_V1.copy()
NUMERIC_V2 = NUMERIC_V1 + ["event_month", "month_missing"]

FEATURE_VERSIONS = {
    "RF-V1": {"categorical": CATEGORICAL_V1, "numeric": NUMERIC_V1},
    "RF-V2": {"categorical": CATEGORICAL_V2, "numeric": NUMERIC_V2},
}

EXCLUDED_FIELDS = [
    "impact_level", "total_deaths", "total_affected", "total_damage", "end_date",
    "duration", "date_anomaly", "hdi_match_status", "hdi_source", "hdi_source_year",
    "hdi_imputed", "event_date_upper", "time_batch", "event_id", "country",
    "hdi_country_name",
]

FORBIDDEN_EXACT = set(EXCLUDED_FIELDS)
FORBIDDEN_PATTERN = re.compile(
    r"(?:death|fatal|casualt|affected|damage|economic_loss|end_date|duration|impact_level)",
    re.IGNORECASE,
)


def assert_safe_feature_list(feature_names: list[str]) -> None:
    duplicates = sorted({name for name in feature_names if feature_names.count(name) > 1})
    if duplicates:
        raise RuntimeError(f"Duplicate features in allowlist: {duplicates}")
    exact = sorted(set(feature_names) & FORBIDDEN_EXACT)
    patterned = sorted(name for name in feature_names if FORBIDDEN_PATTERN.search(name))
    if exact or patterned:
        raise RuntimeError(f"Leakage guard rejected features: exact={exact}, pattern={patterned}")

