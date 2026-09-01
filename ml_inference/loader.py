from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "frozen_assets"
MANIFEST = json.loads((ASSETS / "asset_manifest.json").read_text(encoding="utf-8"))
MODEL_PATH = ASSETS / "final_t2_pipeline.joblib"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


if _sha(MODEL_PATH) != MANIFEST["model_source_sha256"]:
    raise RuntimeError("Frozen inference model integrity check failed")

PIPELINE = joblib.load(MODEL_PATH)
if PIPELINE.feature_names_in_.tolist() != MANIFEST["features"]:
    raise RuntimeError("Frozen inference feature order changed")
if PIPELINE.named_steps["model"].classes_.tolist() != MANIFEST["classes"]:
    raise RuntimeError("Frozen inference class order changed")


def get_pipeline():
    return PIPELINE
