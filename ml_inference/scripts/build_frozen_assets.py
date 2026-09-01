"""Build read-only inference assets from frozen project sources; never fit a model."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "ml_inference/frozen_assets"
FINAL = ROOT / "ml_experiments/modeling/three_class/final_t2"
MODEL_SOURCE = FINAL / "artifacts/final_t2_pipeline.joblib"
MODEL_COPY = ASSETS / "final_t2_pipeline.joblib"
MERGED = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
HDI = ROOT / "data/raw/hdro_hdi_annual.csv"
MAG = FINAL / "artifacts/development_magnitude_groups.csv"
FINAL_MANIFEST = FINAL / "manifest.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["files"]["artifacts/final_t2_pipeline.joblib"]
    if sha(MODEL_SOURCE) != expected:
        raise RuntimeError("Frozen model hash differs from final manifest")
    shutil.copyfile(MODEL_SOURCE, MODEL_COPY)
    if sha(MODEL_COPY) != expected:
        raise RuntimeError("Deployment model copy is not byte-identical")

    pipe = joblib.load(MODEL_SOURCE)
    features = pipe.feature_names_in_.tolist()
    classes = pipe.named_steps["model"].classes_.tolist()
    if classes != ["Low", "Moderate", "Severe"] or len(features) != 15:
        raise RuntimeError("Frozen pipeline schema changed")
    categories = pipe.named_steps["preprocessor"].named_transformers_["categorical"].named_steps["onehot"].categories_
    category_fields = ["country_code", "region", "disaster_type", "disaster_subtype", "date_granularity"]
    category_vocab = {name: [str(x) for x in values] for name, values in zip(category_fields, categories)}

    columns = ["event_id", "country", "country_code", "region", "disaster_type", "disaster_subtype", "year",
               "total_deaths", "event_date", "event_date_upper", "time_batch"]
    data = pd.read_csv(MERGED, usecols=columns, dtype={"event_id": "string", "country_code": "string"})
    frozen = data[data.year.le(2023)].copy()
    if frozen.event_id.duplicated().any():
        raise RuntimeError("Frozen historical source contains duplicate event_id")

    # Recognition mappings use the frozen archive through 2023. Development vocab remains separate
    # so the API can disclose categories handled by OneHotEncoder(handle_unknown="ignore").
    development = data[data.year.between(2000, 2021) & data.total_deaths.notna()].copy()
    country_region = (frozen.dropna(subset=["country_code", "country", "region"])
                      .sort_values(["country_code", "year", "event_id"])
                      .groupby("country_code", as_index=False).tail(1)[["country_code", "country", "region"]]
                      .sort_values("country_code"))
    if country_region.country_code.duplicated().any() or not set(category_vocab["country_code"]).issubset(set(country_region.country_code)):
        raise RuntimeError("Country-region mapping is incomplete or ambiguous")
    country_region.to_csv(ASSETS / "country_region.csv", index=False)

    pairs = frozen[["disaster_type", "disaster_subtype"]].dropna().drop_duplicates()
    if pairs.disaster_subtype.duplicated().any():
        raise RuntimeError("Subtype maps to multiple disaster types")
    pairs.sort_values(["disaster_type", "disaster_subtype"]).to_csv(ASSETS / "disaster_type_subtype.csv", index=False)

    # Preserve interval semantics and aggregate only identical country/time batches.
    history = frozen.dropna(subset=["country_code", "time_batch", "event_date", "event_date_upper"])
    history = (history.groupby(["country_code", "time_batch"], as_index=False)
               .agg(interval_start=("event_date", "min"), interval_end=("event_date_upper", "max"), event_count=("event_id", "size"))
               .sort_values(["country_code", "interval_start", "interval_end", "time_batch"]))
    history.to_csv(ASSETS / "historical_frequency_intervals.csv", index=False)

    hdi = pd.read_csv(HDI, usecols=["country_code", "country_name", "year", "hdi", "source"])
    hdi = hdi[hdi.year.between(1990, 2023)].copy()
    if hdi.duplicated(["country_code", "year"]).any():
        raise RuntimeError("HDI lookup is not unique")
    hdi.sort_values(["country_code", "year"]).to_csv(ASSETS / "hdi_annual.csv", index=False)
    shutil.copyfile(MAG, ASSETS / "magnitude_groups.csv")
    (ASSETS / "category_vocabularies.json").write_text(json.dumps(category_vocab, ensure_ascii=False, indent=2), encoding="utf-8")

    source_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in [MODEL_SOURCE, FINAL_MANIFEST, MERGED, HDI, MAG]}
    asset_files = [p for p in ASSETS.iterdir() if p.is_file() and p.name != "asset_manifest.json"]
    asset_manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_builder_version": "frozen-t2-v1",
        "model_source": MODEL_SOURCE.relative_to(ROOT).as_posix(),
        "model_source_sha256": expected,
        "model_copy_sha256": sha(MODEL_COPY),
        "model_copy_byte_identical": sha(MODEL_COPY) == expected,
        "classes": classes,
        "features": features,
        "hdi_range": [1990, 2023],
        "historical_source_cutoff": "2023-12-31",
        "historical_source_scope": "all frozen EM-DAT event intervals through 2023; no labels or outcome fields",
        "development_mapping_range": [2000, 2021],
        "source_hashes": source_hashes,
        "assets": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(asset_files)},
    }
    (ASSETS / "asset_manifest.json").write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "assets": len(asset_files), "history_batches": len(history),
                      "hdi_rows": len(hdi), "model_copy_identical": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
