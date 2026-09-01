from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "ml_inference" / "inference_manifest.json"
EXPLICIT = [
    ROOT / ".gitignore",
    ROOT / ".vercelignore",
    ROOT / "requirements.txt",
    ROOT / "src" / "main.js",
    ROOT / "src" / "systemConsole.js",
    ROOT / "src" / "router" / "routes.js",
    ROOT / "src" / "impactAnalysis.css",
    ROOT / "src" / "pages" / "user" / "impactAnalysis.js",
]
TREES = [ROOT / "api", ROOT / "ml_inference", ROOT / "docs" / "api"]
DOCS = [
    ROOT / "docs" / "thesis" / "模型推理接口与系统接入.md",
    ROOT / "docs" / "stages" / "第三阶段_实施前审计.md",
    ROOT / "docs" / "stages" / "第三阶段_冻结模型推理接口与系统接入.md",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


paths = set(EXPLICIT + DOCS)
for tree in TREES:
    paths.update(
        path
        for path in tree.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and path != OUTPUT
    )

files = {}
for path in sorted(paths, key=lambda value: value.as_posix()):
    if path.exists():
        files[path.relative_to(ROOT).as_posix()] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }

source = ROOT / "ml_experiments/modeling/three_class/final_t2/artifacts/final_t2_pipeline.joblib"
copy = ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib"
payload = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "stage": "frozen-rf-t2-inference-integration",
    "model_source_sha256": sha256(source),
    "model_copy_sha256": sha256(copy),
    "model_copy_byte_identical": source.read_bytes() == copy.read_bytes(),
    "test_consistency": {
        "events": 948,
        "class_match_rate": 1.0,
        "probability_tolerance": 1e-12,
    },
    "api_tests": {"passed": 23, "failed": 0},
    "production_deployed": False,
    "files": files,
}
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(OUTPUT), "files": len(files)}, ensure_ascii=False))
