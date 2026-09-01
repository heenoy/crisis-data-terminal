from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_DIR.parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "emdat_raw.xlsx"
DEFAULT_ARTIFACT_DIR = EXPERIMENT_DIR / "artifacts"

TARGET_COLUMN = "Total Deaths"
DAMAGE_TARGET_COLUMN = "Total Damage ('000 US$)"
RANDOM_STATE = 42
TEST_SIZE = 0.20
CALIBRATION_SIZE = 0.20
INTERVAL_COVERAGE = 0.90

# Only fields available before or near the beginning of an event are used.
# Impact totals, response outcomes, free text, IDs, and post-event timestamps
# are deliberately excluded to avoid target leakage and brittle memorization.
CATEGORICAL_FEATURES = [
    "Disaster Group",
    "Disaster Subgroup",
    "Disaster Type",
    "Disaster Subtype",
    "ISO",
    "Country",
    "Subregion",
    "Region",
    "Magnitude Scale",
]

NUMERIC_FEATURES = [
    "Start Year",
    "Start Month",
    "Start Day",
    "Magnitude",
    "Latitude",
    "Longitude",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

LEAKAGE_FIELDS = {
    "Total Deaths": "prediction target",
    "No. Injured": "same-event impact outcome unavailable at prediction time",
    "No. Affected": "same-event impact outcome unavailable at prediction time",
    "No. Homeless": "same-event impact outcome unavailable at prediction time",
    "Total Affected": "derived same-event impact outcome",
    "Reconstruction Costs ('000 US$)": "post-event economic outcome",
    "Reconstruction Costs, Adjusted ('000 US$)": "post-event economic outcome",
    "Insured Damage ('000 US$)": "post-event economic outcome",
    "Insured Damage, Adjusted ('000 US$)": "post-event economic outcome",
    "Total Damage ('000 US$)": "post-event economic outcome and future target",
    "Total Damage, Adjusted ('000 US$)": "post-event economic outcome",
    "AID Contribution ('000 US$)": "response outcome that may follow impact assessment",
}
