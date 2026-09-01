"""Development-only expanding-window experiments. No Test prediction input.

Shared archive containers are scanned to identify rows; only start years
2000-2021 enter data frames. No out-of-period features/labels are used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE / ".dependencies"))
sys.path.insert(0, str(HERE.parent / "three_class"))
sys.path.insert(0, str(HERE.parent / "lightgbm"))
import numpy as np
import pandas as pd
import sklearn
import joblib
import run_t0_t3_random_forest as base
from lightgbm_pipeline import TrainOnlyCategoryMapper, LightGBMNativePipeline
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.utils.class_weight import compute_class_weight

LABELS = base.LABELS
FEATURES = base.FEATURES["T2"]
CFG_PATH = HERE / "config.json"
MERGED = ROOT / "data/processed_hdro/disaster_hdi_merged.csv"
RAW = ROOT / "data/emdat_raw.xlsx"
FROZEN = ROOT / "ml_experiments/modeling/three_class/final_t2/artifacts/final_t2_pipeline.joblib"
EXPECTED_SHA = "c4960347d423b1b46065c8e2fc57e1e1656fae11e1198af2fe5c6a734392a9d4"
LGB_CONFIG = HERE.parent / "lightgbm/artifacts/selected_lightgbm_config.json"


def sha(path):
    return base.sha256(Path(path))


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def read_development_csv():
    # Event IDs need not encode the actual start year. Gate on the year column.
    # CSV row bytes are scanned, but excluded rows never enter a feature frame.
    selected = []
    with MERGED.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        year_index = header.index("year")
        for row in reader:
            if 2000 <= int(row[year_index]) <= 2021:
                selected.append(row)
    cols = ["event_id", "year", "total_deaths", "event_date", "event_date_upper", "country_code", "region",
            "disaster_type", "disaster_subtype", "date_granularity", "date_imputed", "historical_frequency", "hdi"]
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(header)
    writer.writerows(selected)
    df = pd.read_csv(io.StringIO(text.getvalue()), usecols=cols)
    assert df.year.between(2000, 2021).all()
    assert df.event_id.notna().all() and not df.event_id.duplicated().any()
    return df


def load_magnitude(ids):
    # Read the ID cell first; skip all other cells for IDs outside Development.
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with ZipFile(RAW) as z:
        strings = ["".join(e.itertext()) for e in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        def value(cell):
            if cell.get("t") == "inlineStr":
                return "".join(cell.find(ns + "is").itertext())
            v = cell.find(ns + "v")
            if v is None: return ""
            return strings[int(v.text)] if cell.get("t") == "s" else v.text
        rows, columns = [], {}
        with z.open("xl/worksheets/sheet1.xml") as f:
            for _, row in ET.iterparse(f, events=["end"]):
                if row.tag != ns + "row": continue
                cells = {"".join(c for c in cell.get("r", "") if c.isalpha()): cell for cell in row}
                if not columns:
                    columns = {value(cell): key for key, cell in cells.items()}
                    required = ["DisNo.", "Disaster Type", "Disaster Subtype", "Magnitude", "Magnitude Scale"]
                    assert set(required).issubset(columns)
                else:
                    event_id = value(cells[columns["DisNo."]])
                    if event_id in ids:
                        rows.append([event_id] + [value(cells[columns[k]]) if columns[k] in cells else "" for k in required[1:]])
                row.clear()
    out = pd.DataFrame(rows, columns=["event_id", "raw_disaster_type", "raw_disaster_subtype", "magnitude_raw", "magnitude_scale"])
    assert not out.event_id.duplicated().any() and set(out.event_id) == ids
    text = out.magnitude_raw.astype(str).str.strip()
    out["magnitude"] = pd.to_numeric(text.replace("", np.nan), errors="coerce")
    assert not ((text != "") & out.magnitude.isna()).any()
    out["magnitude_scale"] = out.magnitude_scale.str.strip().replace("", None)
    out["group_key"] = out.apply(lambda row: base.magnitude_group_id(row)[2], axis=1)
    return out


def causal_frequency(frame):
    # Independent form of the frozen rule: upper(previous) < lower(current).
    result = pd.Series(index=frame.index, dtype="int64")
    lower = pd.to_datetime(frame.event_date)
    upper = pd.to_datetime(frame.event_date_upper)
    assert lower.notna().all() and upper.notna().all() and (upper >= lower).all()
    for _, group in frame.groupby("country_code"):
        ends = np.sort(upper.loc[group.index].to_numpy())
        result.loc[group.index] = np.searchsorted(ends, lower.loc[group.index].to_numpy(), side="left")
    assert result.notna().all()
    return result.astype(int)


def magnitude_transform(train, target):
    stats = []
    approved = sorted(f"{name} | {scale}" for name, scale in (base.APPROVED_TYPE_GROUPS | base.APPROVED_SUBTYPE_GROUPS))
    for key in approved:
        vals = train.loc[train.group_key.eq(key), "magnitude"].dropna()
        q1, median, q3 = vals.quantile([.25, .5, .75]) if len(vals) else (np.nan,) * 3
        iqr = q3 - q1
        stats.append(dict(group_key=key, n=len(vals), q1=q1, median=median, q3=q3, iqr=iqr,
                          eligible=bool(len(vals) >= 20 and iqr > 0)))
    stats = pd.DataFrame(stats)
    eligible = stats[stats.eligible].set_index("group_key")
    result = target.copy()
    result["magnitude_missing"] = result.magnitude.isna().astype("int8")
    result["magnitude_group_unknown"] = (~result.group_key.isin(eligible.index)).astype("int8")
    result["magnitude_robust_z"] = ((result.magnitude - result.group_key.map(eligible["median"])) /
                                    result.group_key.map(eligible.iqr)).clip(-5, 5)
    return result, stats


def metrics(frame, pred=None):
    y = frame.true_label
    pred = frame.predicted_label.to_numpy() if pred is None else np.asarray(pred)
    out = base.scalar_metrics(y, pred)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=LABELS, zero_division=0)
    for i, name in enumerate(LABELS):
        for metric, val in [("precision", p[i]), ("recall", r[i]), ("f1", f[i]), ("support", int(s[i]))]:
            out[f"{name.lower()}_{metric}"] = val
    out["severe_to_low_rate"] = out["severe_to_low"] / int(s[2])
    return out


def audit(config, output):
    output.mkdir(parents=True, exist_ok=True)
    assert sha(FROZEN) == EXPECTED_SHA
    assert sha(ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib") == EXPECTED_SHA
    old_manifest = json.loads((FROZEN.parent.parent / "manifest.json").read_text(encoding="utf-8"))
    for path in [MERGED, RAW]:
        assert sha(path) == old_manifest["input_hashes"][path.relative_to(ROOT).as_posix()]
    locked = json.loads(LGB_CONFIG.read_text(encoding="utf-8"))
    assert locked["candidate_id"] == "LGBM-V2_P3_low_rate_balanced" and locked["best_iteration"] == 291
    all_dev = read_development_csv()
    recomputed = causal_frequency(all_dev)
    mismatches = int((recomputed != all_dev.historical_frequency).sum())
    if mismatches: raise RuntimeError(f"Historical frequency mismatch: {mismatches}; stop for scope review")
    all_dev["three_class_label"] = base.label_from_deaths(all_dev.total_deaths)
    dev = all_dev[all_dev.three_class_label.notna()].copy()
    assert len(dev) == 11590
    assert dev.three_class_label.value_counts().to_dict() == {"Moderate": 7872, "Low": 2786, "Severe": 932}
    magnitudes = load_magnitude(set(dev.event_id))
    dev = base.engineer_base(dev).merge(magnitudes, on="event_id", validate="one_to_one")
    assert (dev.disaster_type == dev.raw_disaster_type).all()
    assert (dev.disaster_subtype == dev.raw_disaster_subtype).all()
    dev.to_csv(output / "development_only.csv", index=False)
    yearly = pd.crosstab(dev.year, dev.three_class_label).reindex(columns=LABELS, fill_value=0)
    yearly["total"] = yearly.sum(axis=1)
    yearly.to_csv(output / "development_yearly_counts.csv")
    rows, feature_audit = [], []
    for fold in config["folds"]:
        assert fold["train_end"] < fold["validation_start"]
        scoped = all_dev[all_dev.year <= fold["validation_end"]]
        assert causal_frequency(scoped).equals(recomputed.loc[scoped.index])
        for split, start, end in [("train", fold["train_start"], fold["train_end"]),
                                  ("validation", fold["validation_start"], fold["validation_end"])]:
            f = dev[dev.year.between(start, end)]
            counts = f.three_class_label.value_counts().reindex(LABELS, fill_value=0)
            assert counts.min() >= config["minimum_severe_per_fold"]
            rows.append(dict(fold=fold["fold"], split=split, start=start, end=end, n=len(f), **counts.to_dict()))
    pd.DataFrame(rows).to_csv(output / "fold_counts.csv", index=False)
    for fold in config["folds"]:
        training = dev[dev.year.between(fold["train_start"], fold["train_end"])]
        for split, target in [("train", training), ("validation", dev[dev.year.between(fold["validation_start"], fold["validation_end"])])]:
            engineered, stats = magnitude_transform(training, target)
            for name in FEATURES:
                feature_audit.append({"fold": fold["fold"], "split": split, "feature": name,
                    "n": len(target), "missing": int(engineered[name].isna().sum()),
                    "missing_rate": float(engineered[name].isna().mean()), "dtype": str(engineered[name].dtype)})
            if split == "train": stats.to_csv(output / f"magnitude_fold{fold['fold']}.csv", index=False)
    pd.DataFrame(feature_audit).to_csv(output / "fold_feature_availability.csv", index=False)
    dump(output / "audit.json", {"model_sha256": sha(FROZEN), "historical_frequency_mismatches": mismatches,
        "frequency_source_events": len(all_dev), "development_labeled_events": len(dev),
        "input_hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in [MERGED, RAW, LGB_CONFIG]},
        "test_features_labels_read": False, "maturity_features_labels_read": False,
        "archive_access": "shared file bytes scanned; CSV year and XLSX ID are exclusion gates; no Test/Maturity feature/label frame",
        "historical_frequency": "all labeled/unlabeled events in 2000-2021; same country and previous interval upper < current lower; truncated-prefix invariant verified",
        "historical_limitations": "causal within-year sequential archive arrivals assumed; historical HDI/magnitude availability is not a publication-vintage backtest",
        "historical_lgbm_selection": locked["candidate_id"], "historical_lgbm_best_iteration": locked["best_iteration"],
        "test_count_source": "existing frozen declaration only; no new Test file opened"})
    print(yearly.to_string(), flush=True)
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    return dev


def snapshot():
    paths = [FROZEN, ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib", MERGED, RAW,
             ROOT / "vercel.json", ROOT / "requirements.txt", ROOT / "package.json", ROOT / "docs/project-status.md"]
    for directory in ["src", "api", "ml_inference", "supabase"]:
        paths += [p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def probability_frame(validation, proba, model_id, fold):
    assert proba.shape == (len(validation), 3)
    assert np.isfinite(proba).all() and (proba >= 0).all()
    assert np.max(abs(proba.sum(axis=1) - 1)) <= 1e-12
    out = validation[["event_id", "year", "three_class_label"]].copy().reset_index(drop=True)
    out = out.rename(columns={"three_class_label": "true_label"})
    out["model_id"], out["fold"] = model_id, fold
    out["predicted_label"] = np.asarray(LABELS)[proba.argmax(axis=1)]
    for i, label in enumerate(LABELS): out[f"probability_{label}"] = proba[:, i]
    return out


def threshold_prediction(frame, threshold):
    p = frame[[f"probability_{label}" for label in LABELS]].to_numpy()
    return np.asarray(LABELS)[np.where(p[:, 2] >= threshold, 2, p[:, :2].argmax(axis=1))]


def sort_selection(rows):
    return rows.sort_values(["severe_recall", "severe_f1", "macro_f1", "severe_to_low_rate", "default_prediction_disagreement", "candidate_id"],
                            ascending=[False, False, False, True, True, True], kind="stable")


def summarize(oof, config, output):
    fold_metrics, pooled_metrics, matrices = [], [], {}
    for model_id, model_frame in oof.groupby("model_id", sort=True):
        assert not model_frame.event_id.duplicated().any() and len(model_frame) == 3466
        pooled_metrics.append({"model_id": model_id, **metrics(model_frame)})
        matrices[model_id] = confusion_matrix(model_frame.true_label, model_frame.predicted_label, labels=LABELS).tolist()
        for fold, frame in model_frame.groupby("fold"):
            fold_metrics.append({"model_id": model_id, "fold": int(fold), **metrics(frame)})
            matrices[f"{model_id}_fold{fold}"] = confusion_matrix(frame.true_label, frame.predicted_label, labels=LABELS).tolist()
    fm, pm = pd.DataFrame(fold_metrics), pd.DataFrame(pooled_metrics)
    fm.to_csv(output / "fold_metrics.csv", index=False)
    pm.to_csv(output / "pooled_oof_metrics.csv", index=False)
    agg = fm.drop(columns="fold").groupby("model_id").agg(["mean", "std", "min", "max"])
    agg.columns = [f"{metric}_{stat}" for metric, stat in agg.columns]
    agg.to_csv(output / "fold_metric_summary.csv")
    dump(output / "confusion_matrices.json", matrices)
    thresholds = np.round(np.arange(config["threshold_start"], config["threshold_end"] + config["threshold_step"] / 2,
                                    config["threshold_step"]), 2)
    threshold_rows, threshold_selected = [], {}
    for model_id in config["threshold_scope"]:
        frame = oof[oof.model_id.eq(model_id)]
        for t in thresholds:
            for fold, sub in [("pooled", frame), *list(frame.groupby("fold"))]:
                pred = threshold_prediction(sub, t)
                threshold_rows.append(dict(model_id=model_id, fold=str(fold), threshold=float(t),
                    candidate_id=f"{model_id}_t{t:.2f}", default_prediction_disagreement=int((pred != sub.predicted_label).sum()),
                    **metrics(sub, pred)))
    ts = pd.DataFrame(threshold_rows)
    ts.to_csv(output / "severe_threshold_search.csv", index=False)
    for model_id in config["threshold_scope"]:
        eligible = ts[(ts.model_id == model_id) & (ts.fold == "pooled") & (ts.severe_precision >= config["precision_floor"])]
        threshold_selected[model_id] = None if eligible.empty else sort_selection(eligible).iloc[0].to_dict()
    weights = pm[pm.model_id.str.startswith("RF_weight_")].copy()
    weights["multiplier"] = weights.model_id.str.replace("RF_weight_", "", regex=False).astype(float)
    base_frame = oof[oof.model_id.eq("RF_T2")].set_index("event_id")
    weights["default_prediction_disagreement"] = [int((oof[oof.model_id.eq(mid)].set_index("event_id").predicted_label != base_frame.predicted_label).sum()) for mid in weights.model_id]
    weights["candidate_id"] = weights.model_id
    baseline = pm[pm.model_id.eq("RF_T2")].iloc[0]
    weights["eligible_for_retention"] = ((weights.multiplier > 1) & (weights.severe_precision >= config["precision_floor"]) &
                                         (weights.severe_f1 > baseline.severe_f1))
    weights.to_csv(output / "severe_weight_search.csv", index=False)
    eligible = weights[weights.eligible_for_retention]
    weight_selected = None if eligible.empty else sort_selection(eligible).iloc[0].to_dict()
    candidates = [oof[oof.model_id.eq(mid)].copy() for mid in ["RF_T2", "LGBM_T2"]]
    for mid, selected in threshold_selected.items():
        if selected is not None:
            frame = oof[oof.model_id.eq(mid)].copy()
            frame["predicted_label"] = threshold_prediction(frame, selected["threshold"])
            frame["model_id"] = mid + "_threshold"
            candidates.append(frame)
    if weight_selected is not None:
        frame = oof[oof.model_id.eq(weight_selected["model_id"])].copy()
        frame["model_id"] = "RF_selected_weight"
        candidates.append(frame)
        if threshold_selected["RF_T2"] is not None:
            frame = frame.copy()
            frame["predicted_label"] = threshold_prediction(frame, threshold_selected["RF_T2"]["threshold"])
            frame["model_id"] = "RF_weight_threshold"
            candidates.append(frame)
    candidate_oof = pd.concat(candidates, ignore_index=True)
    candidate_oof.to_csv(output / "candidate_oof_predictions.csv", index=False)
    cr, cf = [], []
    for mid, frame in candidate_oof.groupby("model_id"):
        row = {"candidate_id": mid, **metrics(frame)}
        row["default_prediction_disagreement"] = int((frame.set_index("event_id").predicted_label != base_frame.predicted_label).sum())
        cr.append(row)
        for fold, sub in frame.groupby("fold"):
            cf.append({"candidate_id": mid, "fold": int(fold), **metrics(sub)})
    cr = pd.DataFrame(cr)
    eligible = cr[cr.severe_precision >= config["precision_floor"]]
    recommended = "RF_T2" if eligible.empty else sort_selection(eligible).iloc[0].candidate_id
    cr.to_csv(output / "candidate_comparison.csv", index=False)
    pd.DataFrame(cf).to_csv(output / "candidate_fold_metrics.csv", index=False)
    best_frame = candidate_oof[candidate_oof.model_id.eq(recommended)]
    best_cm = confusion_matrix(best_frame.true_label, best_frame.predicted_label, labels=LABELS)
    pd.DataFrame(best_cm, index=LABELS, columns=LABELS).to_csv(output / "selected_oof_confusion_matrix.csv")
    return dict(threshold_selection=threshold_selected, weight_selection=weight_selected,
                recommended_development_candidate=recommended, candidates=cr.to_dict("records"),
                baseline_confusion_matrix=matrices["RF_T2"], selected_confusion_matrix=best_cm.tolist(),
                pooled_oof_metrics=pm.to_dict("records"), fold_metrics=fm.to_dict("records"))


def run(config, output):
    import lightgbm as lgb
    output.mkdir(parents=True, exist_ok=False)
    before = snapshot()
    assert before[FROZEN.relative_to(ROOT).as_posix()] == EXPECTED_SHA
    dev = pd.read_csv(HERE / "audit/development_only.csv")
    assert dev.year.between(2000, 2021).all() and len(dev) == 11590
    base.assert_safe_features(FEATURES)
    assert len(FEATURES) == 15
    locked = json.loads(LGB_CONFIG.read_text(encoding="utf-8"))
    lgb_params = dict(locked["base_parameters"], objective="multiclass", num_class=3,
        random_state=config["random_state"], n_jobs=-1, verbosity=-1, deterministic=True,
        force_col_wise=True, subsample_freq=1)
    lgb_params["n_estimators"] = locked["best_iteration"]
    dump(output / "pre_run_config.json", {"config": config, "config_sha256": sha(CFG_PATH),
        "script_sha256": sha(__file__), "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES, "rf_parameters": base.RF_PARAMS, "lightgbm_parameters": lgb_params,
        "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__, "lightgbm": lgb.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__, "joblib": joblib.__version__},
        "input_development_sha256": sha(HERE / "audit/development_only.csv")})
    dump(output / "protected_hashes_before.json", before)
    all_oof, timing, weight_rows, audits = [], [], [], []
    for fold in config["folds"]:
        train = dev[dev.year.between(fold["train_start"], fold["train_end"])].copy()
        val = dev[dev.year.between(fold["validation_start"], fold["validation_end"])].copy()
        assert train.year.max() < val.year.min() and not (set(train.event_id) & set(val.event_id))
        train_x, stats = magnitude_transform(train, train)
        val_x, val_stats = magnitude_transform(train, val)
        pd.testing.assert_frame_equal(stats, val_stats)
        stats.to_csv(output / f"magnitude_fold{fold['fold']}.csv", index=False)
        X, V, y = train_x[FEATURES], val_x[FEATURES], train.three_class_label
        balanced = dict(zip(LABELS, compute_class_weight("balanced", classes=np.array(LABELS), y=y)))
        for mid, multiplier in [("RF_T2", None)] + [(f"RF_weight_{m:g}", m) for m in config["severe_weight_multipliers"]] + [("LGBM_T2", None)]:
            started = time.perf_counter()
            print(f"fold={fold['fold']} model={mid} train={len(train)} validation={len(val)}", flush=True)
            if mid.startswith("RF"):
                pipe = base.make_pipeline(FEATURES)
                weights = "balanced_subsample"
                if multiplier is not None:
                    weights = dict(balanced)
                    weights["Severe"] *= multiplier
                    pipe.set_params(model__class_weight=weights)
                pipe.fit(X, y)
                proba = base.ordered_probabilities(pipe, V)
                cats = pipe.named_steps["preprocessor"].named_transformers_["categorical"].named_steps["onehot"].categories_
                medians = pipe.named_steps["preprocessor"].named_transformers_["numeric"].named_steps["imputer"].statistics_
                assert np.isfinite(medians).all()
                fitted_info = {"categories": {k: list(v) for k, v in zip(base.BASE_CATEGORICAL, cats)}, "numeric_medians": medians.tolist()}
            else:
                mapper = TrainOnlyCategoryMapper(base.BASE_CATEGORICAL, FEATURES).fit(X)
                encoded = y.map({label: i for i, label in enumerate(LABELS)})
                model = lgb.LGBMClassifier(**lgb_params)
                model.fit(mapper.transform(X), encoded, sample_weight=y.map(balanced).to_numpy(),
                          categorical_feature=base.BASE_CATEGORICAL)
                assert model.classes_.tolist() == [0, 1, 2]
                pipe = LightGBMNativePipeline(mapper, model, LABELS)
                proba = pipe.predict_proba(V)
                weights = balanced
                fitted_info = {"categories": mapper.categories_, "n_estimators": 291, "early_stopping": False}
            audits.append({"model_id": mid, "fold": fold["fold"], "fit_event_ids_sha256": hashlib.sha256("\n".join(train.event_id).encode()).hexdigest(),
                           "validation_event_ids_sha256": hashlib.sha256("\n".join(val.event_id).encode()).hexdigest(),
                           "feature_order": FEATURES, **fitted_info})
            weight_rows.append({"model_id": mid, "fold": fold["fold"], "class_weights": weights})
            timing.append({"model_id": mid, "fold": fold["fold"], "fit_predict_seconds": time.perf_counter() - started})
            all_oof.append(probability_frame(val, proba, mid, fold["fold"]))
    oof = pd.concat(all_oof, ignore_index=True)
    oof.to_csv(output / "time_cv_oof_predictions.csv", index=False, float_format="%.17g")
    pd.DataFrame(timing).to_csv(output / "timings.csv", index=False)
    dump(output / "fold_preprocessing.json", audits)
    dump(output / "actual_class_weights.json", weight_rows)
    summary = summarize(oof, config, output)
    assert snapshot() == before, "Protected inputs changed"
    summary.update({"config_sha256": sha(CFG_PATH), "script_sha256": sha(__file__), "frozen_model_sha256": sha(FROZEN),
                    "test_evaluated": False, "maturity_features_labels_used": False, "oof_events_per_model": 3466,
                    "oof_years": [2014, 2021], "development_rows": 11590, "protected_files_unchanged": len(before)})
    dump(output / "time_cv_severe_optimization.json", summary)
    print("Development run complete; Test not evaluated", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    if args.audit:
        audit(config, args.output)
    else:
        run(config, args.output)


if __name__ == "__main__":
    main()
