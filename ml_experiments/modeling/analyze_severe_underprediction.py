"""Read-only RF-T2 diagnosis; exact ID gates precede feature decoding/statistics.

No model loading/fitting, network access, threshold search, or full-data summaries.
Run again with --verify to compare generated JSON/CSV bytes without overwriting.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "ml_experiments/modeling"
FINAL = MODEL / "three_class/final_t2"
CV = MODEL / "time_cv_severe_optimization"
OUT = MODEL / "reports"
PREFIX = "severe_underprediction_"
LABELS = ["Low", "Moderate", "Severe"]
PROBS = ["probability_" + x for x in LABELS]
SEED = 20260831  # Analysis is deterministic; no sampling is used.
SHA = "c4960347d423b1b46065c8e2fc57e1e1656fae11e1198af2fe5c6a734392a9d4"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SCOPE = "共享原始数据容器仅用于按event_id白名单提取OOF/Test所需字段，2024—2026年Maturity记录未被提取、保留、统计或分析。"
SMALL_N = 10  # Descriptive warning, not a model or selection threshold.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message + "; STOP, no silent repair")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def csv_bytes(frame):
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode()


def save(name, content, verify):
    path = OUT / (PREFIX + name)
    if verify or path.exists():
        require(path.read_bytes() == content, f"Repeat output differs: {path.name}")
    else:
        with path.open("xb") as f:
            f.write(content)


def predictions():
    oof = pd.read_csv(OUT / "time_cv_oof_predictions.csv")
    oof = oof.loc[oof.model_id.eq("RF_T2")].drop(columns="model_id")
    test = pd.read_csv(FINAL / "predictions/test_predictions.csv")
    test["fold"] = 0
    expected = json.loads((CV / "run1/confusion_matrices.json").read_text())
    for name, frame, n, lo, hi in [("OOF", oof, 3466, 2014, 2021), ("Test", test, 948, 2022, 2023)]:
        require(len(frame) == n and frame.event_id.is_unique, name + " count/ID mismatch")
        require(frame.year.between(lo, hi).all(), name + " year mismatch")
        require(frame.true_label.isin(LABELS).all() and frame.predicted_label.isin(LABELS).all(), "Class mismatch")
        p = frame[PROBS].to_numpy()
        require(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all() and np.allclose(p.sum(1), 1), "Probability invalid")
        require((np.array(LABELS)[p.argmax(1)] == frame.predicted_label).all(), "Prediction/argmax mismatch")
        cm = matrix(frame)
        ref = expected["RF_T2"] if name == "OOF" else pd.read_csv(FINAL / "reports/confusion_matrix_test.csv", index_col=0).values.tolist()
        require(cm == ref, name + " confusion matrix mismatch")
        frame["dataset"] = name
    for fold, counts in [(1, [240, 605, 72]), (2, [230, 568, 61]), (3, [233, 589, 64]), (4, [322, 433, 49])]:
        f = oof[oof.fold.eq(fold)]
        require(f.true_label.value_counts().reindex(LABELS).tolist() == counts, "Fold class mismatch")
        require(matrix(f) == expected[f"RF_T2_fold{fold}"], "Fold prediction mismatch")
        require(f.year.between(2012 + 2 * fold, 2013 + 2 * fold).all(), "Fold year mismatch")
    return pd.concat([oof, test], ignore_index=True).sort_values(["dataset", "event_id"]).reset_index(drop=True)


def matrix(frame):
    return pd.crosstab(frame.true_label, frame.predicted_label).reindex(index=LABELS, columns=LABELS, fill_value=0).values.tolist()


def check_ids(frame, ids, source):
    require(frame.event_id.is_unique and set(frame.event_id) == ids, source + " duplicate or missing IDs")


def gated_csv(path, ids, columns):
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        index = {c: header.index(c) for c in columns}
        id_index = header.index("event_id")
        for row in reader:
            if row[id_index] in ids:
                rows.append([row[index[c]] for c in columns])
    frame = pd.DataFrame(rows, columns=columns)
    check_ids(frame, ids, path.name)
    print(path.name, "fields=", columns, "matched/filtered=", len(frame))
    return frame


def gated_excel(path, ids):
    """Decode only header/ID shared strings, then whitelisted field strings.

    XML container scanning is unavoidable. No non-whitelisted feature values
    are resolved from sharedStrings, collected, or placed in a DataFrame.
    """
    wanted = ["DisNo.", "Location", "Disaster Type", "Disaster Subtype", "Magnitude", "Magnitude Scale", "Start Year"]
    def cells(row):
        return {"".join(c for c in x.get("r") if c.isalpha()): x for x in row}
    def token(cell):
        if cell is None:
            return ("v", "")
        v = cell.find(NS + "v")
        if cell.get("t") == "inlineStr":
            return ("v", "".join(cell.find(NS + "is").itertext()))
        return ("s" if cell.get("t") == "s" else "v", "" if v is None else v.text)
    def strings(z, indices, allowed=None):
        result = {}
        with z.open("xl/sharedStrings.xml") as f:
            i = 0
            for _, e in ET.iterparse(f, events=["end"]):
                if e.tag == NS + "si":
                    if str(i) in indices:
                        value = "".join(t.text or "" for t in e.iter(NS + "t"))
                        if allowed is None or value in allowed:
                            result[str(i)] = value
                    i += 1
                    e.clear()
        return result
    def resolve(t, lookup):
        return lookup[t[1]] if t[0] == "s" else t[1]
    def rows(z):
        with z.open("xl/worksheets/sheet1.xml") as f:
            for _, e in ET.iterparse(f, events=["end"]):
                if e.tag == NS + "row":
                    yield cells(e)
                    e.clear()
    with ZipFile(path) as z:
        first = next(rows(z))
        headers = {col: token(c) for col, c in first.items()}
        lookup = strings(z, {t[1] for t in headers.values() if t[0] == "s"})
        columns = {resolve(t, lookup): col for col, t in headers.items()}
        require(set(wanted).issubset(columns), "Excel fields missing")
        id_tokens = set()
        for i, row in enumerate(rows(z)):
            if i:
                t = token(row.get(columns["DisNo."]))
                if t[0] == "s":
                    id_tokens.add(t[1])
        id_lookup = strings(z, id_tokens, allowed=ids)
        selected = []
        for i, row in enumerate(rows(z)):
            t = token(row.get(columns["DisNo."]))
            event_id = id_lookup.get(t[1], "") if t[0] == "s" else t[1]
            if i and event_id in ids:
                selected.append([token(row.get(columns[k])) for k in wanted])
        lookup = strings(z, {t[1] for row in selected for t in row if t[0] == "s"})
        frame = pd.DataFrame([[resolve(t, lookup) for t in row] for row in selected], columns=["event_id", "Location", "raw_type", "raw_subtype", "magnitude_raw", "magnitude_scale", "raw_year"])
    check_ids(frame, ids, path.name)
    print(path.name, "fields=", wanted, "matched/filtered=", len(frame))
    return frame


def features(pred):
    ids = set(pred.event_id)
    cols = ["event_id", "country_code", "region", "disaster_type", "disaster_subtype", "year", "event_date", "date_granularity", "date_imputed", "historical_frequency", "hdi"]
    data = gated_csv(ROOT / "data/processed_hdro/disaster_hdi_merged.csv", ids, cols + ["total_deaths"])
    require(data.date_imputed.isin(["True", "False"]).all(), "Unexpected date_imputed encoding")
    data["date_imputed"] = data.date_imputed.map({"True": 1, "False": 0})
    for col in ["year", "historical_frequency", "hdi"]:
        data[col] = pd.to_numeric(data[col].replace("", np.nan), errors="raise")
    data = pred.merge(data, on="event_id", suffixes=("", "_source"), validate="one_to_one")
    deaths = pd.to_numeric(data.total_deaths, errors="raise")
    require(deaths.notna().all() and deaths.ge(0).all(), "Whitelisted label source invalid")
    source_labels = np.where(deaths.lt(10), "Low", np.where(deaths.lt(100), "Moderate", "Severe"))
    require(data.true_label.eq(source_labels).all(), "Whitelisted source label conflict")
    data = data.drop(columns="total_deaths")
    require(data.year.eq(data.year_source).all(), "Source/prediction year conflict")
    require(data.year.lt(2024).all(), "Out-of-scope year")
    data = data.drop(columns="year_source")
    raw = gated_excel(ROOT / "data/emdat_raw.xlsx", ids)
    data = data.merge(raw, on="event_id", validate="one_to_one")
    require(data.year.eq(pd.to_numeric(data.raw_year)).all(), "Raw year conflict")
    require(data.disaster_type.eq(data.raw_type).all() and data.disaster_subtype.eq(data.raw_subtype).all(), "Raw disaster field conflict")
    data["event_month"] = pd.to_datetime(data.event_date).dt.month.where(data.date_granularity.isin(["day", "month"]))
    data["hdi_missing"] = data.hdi.isna().astype(int)
    data["month_missing"] = data.event_month.isna().astype(int)
    data["magnitude"] = pd.to_numeric(data.magnitude_raw.str.strip().replace("", np.nan), errors="raise")
    data["magnitude_missing"] = data.magnitude.isna().astype(int)
    # Same eight frozen semantic groups; reuse stored fold/development statistics, never fit them.
    type_groups = {("Drought", "Km2"), ("Flood", "Km2"), ("Wildfire", "Km2"), ("Storm", "Kph"), ("Earthquake", "Moment Magnitude")}
    sub_groups = {("Cold wave", "°C"), ("Heat wave", "°C"), ("Severe winter conditions", "°C")}
    def group(row):
        scale = row.magnitude_scale.strip()
        if (row.raw_type, scale) in type_groups:
            return row.raw_type + " | " + scale
        if (row.raw_subtype, scale) in sub_groups:
            return row.raw_subtype + " | " + scale
        return "UNKNOWN"
    data["magnitude_group"] = data.apply(group, axis=1)
    for fold, frame in data.groupby("fold"):
        stats = pd.read_csv(CV / f"run1/magnitude_fold{fold}.csv") if fold else pd.read_csv(FINAL / "artifacts/development_magnitude_groups.csv").rename(columns={"training_median": "median", "training_iqr": "iqr"})
        stats = stats[stats.eligible].set_index("group_key")
        data.loc[frame.index, "magnitude_group_unknown"] = (~frame.magnitude_group.isin(stats.index)).astype(int)
        data.loc[frame.index, "magnitude_robust_z"] = ((frame.magnitude - frame.magnitude_group.map(stats["median"])) / frame.magnitude_group.map(stats.iqr)).clip(-5, 5)
    # Independently cross-check all shared OOF fields with the existing Development cache.
    oof = data[data.dataset.eq("OOF")].set_index("event_id")
    old = gated_csv(CV / "audit/development_only.csv", set(oof.index), ["event_id", "three_class_label", *cols[1:], "event_month", "hdi_missing", "month_missing", "magnitude"]).set_index("event_id").loc[oof.index]
    require(old.three_class_label.eq(oof.true_label).all(), "OOF label conflict")
    for col in cols[1:] + ["event_month", "hdi_missing", "month_missing", "magnitude"]:
        if pd.api.types.is_numeric_dtype(oof[col]):
            require(np.allclose(pd.to_numeric(old[col].replace("", np.nan)), oof[col], equal_nan=True), "OOF numeric conflict: " + col)
        else:
            require(old[col].eq(oof[col]).all(), "OOF field conflict: " + col)
    data["max_probability"] = data[PROBS].max(axis=1)
    data["low_minus_severe"] = data.probability_Low - data.probability_Severe
    data["moderate_minus_severe"] = data.probability_Moderate - data.probability_Severe
    return data.drop(columns=["raw_type", "raw_subtype", "raw_year", "magnitude_raw", "event_date"]).sort_values(["dataset", "event_id"]).reset_index(drop=True)


def groups(frame):
    severe = frame.true_label.eq("Severe")
    return {"Severe_to_Low": frame[severe & frame.predicted_label.eq("Low")], "Severe_to_Severe": frame[severe & frame.predicted_label.eq("Severe")], "Severe_to_Moderate": frame[severe & frame.predicted_label.eq("Moderate")], "Moderate_to_Low": frame[frame.true_label.eq("Moderate") & frame.predicted_label.eq("Low")], "all_Severe": frame[severe], "all_events": frame}


def summary(series):
    s = series.dropna()
    return dict(n=len(series), valid_n=len(s), missing_n=int(series.isna().sum()), missing_rate=float(series.isna().mean()), **{name: (float(value) if pd.notna(value) else None) for name, value in {"min": s.min(), "q1": s.quantile(.25), "median": s.median(), "q3": s.quantile(.75), "max": s.max(), "mean": s.mean(), "std_ddof1": s.std()}.items()})


def rate(mask):
    return {"count": int(mask.sum()), "denominator": len(mask), "rate": float(mask.mean()) if len(mask) else None}


def missing(frame):
    unknown = r"(?i)^(unknown|unspecified|not specified|n/a|nan|__missing__)?$"
    flags = {c + "_null": frame[c].isna() for c in ["hdi", "event_month", "magnitude_robust_z"]}
    flags.update({c: frame[c].eq(1) for c in ["hdi_missing", "month_missing", "magnitude_missing", "magnitude_group_unknown", "date_imputed"]})
    flags.update(date_not_day=~frame.date_granularity.eq("day"), date_granularity_missing=frame.date_granularity.str.fullmatch(unknown), subtype_missing=frame.disaster_subtype.str.fullmatch(unknown), subtype_broad=frame.disaster_subtype.eq(frame.disaster_type) | frame.disaster_subtype.str.contains("General", case=False), country_unknown_or_malformed=~frame.country_code.str.fullmatch("[A-Z]{3}") | frame.country_code.isin(["UNK", "XXX"]), region_unknown=frame.region.str.fullmatch(unknown))
    return {key: rate(mask) for key, mask in flags.items()}


def category(frame, column):
    rows = []
    total_errors = len(groups(frame)["Severe_to_Low"])
    for level, part in frame.groupby(frame[column].fillna("MISSING").astype(str), sort=True):
        g = groups(part)
        n, e = len(g["all_Severe"]), len(g["Severe_to_Low"])
        rows.append(dict(level=level, severe_to_low=e, true_severe=n, error_rate=e/n if n else None, error_share=e/total_errors if total_errors else None, error_share_denominator=total_errors, correct_severe=len(g["Severe_to_Severe"]), all_events=len(part), small_sample=n < SMALL_N))
    return rows


def location(frame):
    s = frame.Location.str.strip()
    available = s.ne("")
    multi = s.str.contains(r"[,;/]|\band\b", case=False, regex=True) & available
    broad = s.str.contains(r"\b(?:nationwide|countrywide|whole country|entire country|across|provinces|districts|regions|basin|coast|coastal|national)\b", case=False, regex=True) & available
    tier = np.where(~available, "currently_unsuitable_empty", np.where(multi | broad, "substantial_cleaning_or_footprint_needed", "single_description_candidate_not_geocoded"))
    return {"nonempty": rate(available), "unique_nonempty": int(s[available].nunique()), "length_nonempty": summary(s[available].str.len()), "multiple_place_marker": rate(multi), "broad_marker": rate(broad), "semicolon": rate(s.str.contains(";", regex=False)), "comma": rate(s.str.contains(",", regex=False)), "slash": rate(s.str.contains("/", regex=False)), "tier_counts": pd.Series(tier).value_counts().sort_index().to_dict(), "tier_denominator": len(s), "examples": sorted(s[available].unique())[:5]}


def describe(frame):
    g = groups(frame)
    numeric = ["year", "historical_frequency", "hdi", "magnitude_robust_z", *PROBS, "max_probability", "low_minus_severe", "moderate_minus_severe"]
    stats = {name: {c: summary(part[c]) for c in numeric} for name, part in g.items()}
    miss = {name: missing(part) for name, part in g.items()}
    diff = {name: {key: 100 * (miss["Severe_to_Low"][key]["rate"] - value["rate"]) for key, value in miss[name].items()} for name in ["Severe_to_Severe", "all_Severe", "all_events"]}
    effects = {}
    for col in ["year", "historical_frequency", "hdi", "magnitude_robust_z"]:
        a, b = g["Severe_to_Low"][col].dropna().to_numpy(), g["Severe_to_Severe"][col].dropna().to_numpy()
        effects[col] = {"method": "Cliffs delta: P(error > correct)-P(error < correct), observed values only", "error_valid_n": len(a), "correct_valid_n": len(b), "value": float(np.sign(a[:, None]-b).mean()) if len(a) and len(b) else None}
    bins = {}
    for name, part in g.items():
        p = part.probability_Severe
        bins[name] = {label: rate((p >= lo) & (p < hi)) for lo, hi, label in [(0, .1, "[0,.10)"), (.1, .2, "[.10,.20)"), (.2, .3, "[.20,.30)"), (.3, .4, "[.30,.40)"), (.4, 1.01, "[.40,1]")]}
    loc = {name: location(part) for name, part in g.items()}
    cycles = {}
    for name, part in g.items():
        m = part.event_month.dropna()
        angles = (m-1)*2*np.pi/12
        cycles[name] = {"valid_n": len(m), "missing_n": len(part)-len(m), "monthly_counts": {str(i): int(m.eq(i).sum()) for i in range(1, 13)}, "mean_sin": float(np.sin(angles).mean()), "mean_cos": float(np.cos(angles).mean()), "resultant_length": float(np.hypot(np.sin(angles).mean(), np.cos(angles).mean()))}
    cm = np.array(matrix(frame)); tp, support, predicted = int(cm[2, 2]), int(cm[2].sum()), int(cm[:, 2].sum())
    return dict(n=len(frame), class_counts=frame.true_label.value_counts().reindex(LABELS).to_dict(), confusion_matrix=cm.tolist(), group_counts={k: len(v) for k, v in g.items()}, severe_metrics={"true_positive": tp, "true_severe_denominator": support, "predicted_severe_denominator": predicted, "recall": tp/support, "precision": tp/predicted, "f1": 2*tp/(support+predicted), "f2": 5*tp/(4*support+predicted), "severe_to_low": len(g["Severe_to_Low"]), "severe_to_low_rate": len(g["Severe_to_Low"])/support}, numeric=stats, probability_bins=bins, missingness=miss, missingness_difference_pp=diff, effect_sizes=effects, categories={c: category(frame, c) for c in ["disaster_type", "disaster_subtype", "region", "country_code", "year", "event_month", "date_granularity", "magnitude_group"]}, months_circular=cycles, location=loc, location_availability_difference_pp=100*(loc["Severe_to_Low"]["nonempty"]["rate"]-loc["Severe_to_Severe"]["nonempty"]["rate"]))


def figures(data, result, verify):
    folder = OUT / (PREFIX + "figures")
    if not verify:
        folder.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10})
    def finish(fig, name):
        fig.tight_layout()
        if not verify and not (folder / name).exists():
            fig.savefig(folder / name, dpi=160)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (name, frame) in zip(axes, data.groupby("dataset", sort=True)):
        g = groups(frame)
        for key, color in [("Severe_to_Low", "#D55E00"), ("Severe_to_Severe", "#0072B2")]:
            values = np.sort(g[key].probability_Severe)
            ax.step(values, np.arange(1, len(values)+1)/len(values), where="post", label=f"{key} (n={len(values)})", color=color)
        ax.set(xlim=(0, 1), ylim=(0, 1), title=name, xlabel="P(Severe), uncalibrated", ylabel="Cumulative fraction within group")
        ax.legend(fontsize=8)
    finish(fig, "01_probability_ecdf.png")
    fig, axes = plt.subplots(1, 2, figsize=(13, 7))
    for ax, name in zip(axes, ["OOF", "Test"]):
        rows = [r for r in result[name]["categories"]["disaster_type"] if r["true_severe"]]
        rows.sort(key=lambda r: (-r["error_rate"], r["level"]))
        ax.barh(range(len(rows)), [r["error_rate"] for r in rows], color="#D55E00")
        ax.set_yticks(range(len(rows)), [f'{r["level"]} ({r["severe_to_low"]}/{r["true_severe"]})' + (' *' if r['small_sample'] else '') for r in rows], fontsize=8)
        ax.invert_yaxis(); ax.set(xlim=(0, 1), title=name + ": errors / true Severe", xlabel="Severe to Low rate; * denominator < 10")
    finish(fig, "02_disaster_types.png")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name in zip(axes, ["OOF", "Test"]):
        for j, key in enumerate(["Severe_to_Low", "Severe_to_Severe"]):
            values = [result[name]["missingness"][key][c] for c in ["magnitude_missing", "hdi_missing"]]
            bars = ax.bar(np.arange(2)+j*.35, [v["rate"] for v in values], width=.35, label=key)
            ax.bar_label(bars, labels=[f'{v["count"]}/{v["denominator"]}' for v in values], fontsize=9)
        ax.set_xticks([.175, 1.175], ["Magnitude raw missing", "HDI missing"])
        ax.set(ylim=(0, 1.15), title=name, ylabel="Missing fraction"); ax.legend(fontsize=8)
    finish(fig, "03_missingness.png")
    fig, ax = plt.subplots(figsize=(8, 4))
    folds = result["folds"]
    values = [folds[str(i)]["severe_metrics"] for i in range(1, 5)]
    bars = ax.bar(range(1, 5), [v["severe_to_low_rate"] for v in values], color="#0072B2")
    ax.bar_label(bars, labels=[f'{v["severe_to_low"]}/{v["true_severe_denominator"]}' for v in values])
    ax.set(ylim=(0, 1), xticks=range(1, 5), xlabel="OOF fold (2014-15, 2016-17, 2018-19, 2020-21)", ylabel="Severe to Low / true Severe", title="Temporal error recurrence")
    finish(fig, "04_temporal_errors.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    protected = [ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib", FINAL / "artifacts/final_t2_pipeline.joblib"]
    require(all(sha(p) == SHA for p in protected), "Frozen checksum mismatch")
    pred = predictions()
    white = pred[["dataset", "event_id", "year", "fold"]]
    content = csv_bytes(white)
    # Persist the locked allowlist BEFORE opening either shared source container.
    save("whitelist.csv", content, args.verify)
    whitelist_hash = hashlib.sha256(content).hexdigest()
    save("whitelist_sha256.json", json_bytes({"file": PREFIX+"whitelist.csv", "sha256": whitelist_hash, "OOF_n": 3466, "Test_n": 948}), args.verify)
    data = features(pred)
    check_ids(data, set(white.event_id), "Analysis output")
    require(data.loc[data.dataset.eq("OOF"), "year"].between(2014, 2021).all() and data.loc[data.dataset.eq("Test"), "year"].between(2022, 2023).all(), "Output year mismatch")
    result = {"scope": SCOPE, "seed": SEED, "sampling": "none", "class_order": LABELS, "small_sample_denominator_below": SMALL_N, "whitelist_sha256": whitelist_hash, "frozen_sha256": SHA, "model_training": False, "threshold_or_weight_changes": False, "location_method": "Text-marker audit only; no geocoding or verified spelling correction. Single descriptions are candidates, not confirmed directly geocodable places.", "source_prediction_sha256": {"OOF": sha(OUT / "time_cv_oof_predictions.csv"), "Test": sha(FINAL / "predictions/test_predictions.csv")}}
    for name in ["OOF", "Test"]:
        result[name] = describe(data[data.dataset.eq(name)])
    result["folds"] = {str(fold): describe(frame) for fold, frame in data[data.dataset.eq("OOF")].groupby("fold")}
    save("events.csv", csv_bytes(data), args.verify)
    save("profile.json", json_bytes(result), args.verify)
    strata = {}
    for name, frame in data.groupby("dataset", sort=True):
        strata[name] = {}
        for kind, part in frame.groupby("disaster_type", sort=True):
            severe = groups(part)["all_Severe"]
            if not len(severe):
                continue
            strata[name][kind] = {"groups": {k: {"n": len(v), "magnitude_missing": rate(v.magnitude_missing.eq(1)), "hdi_missing": rate(v.hdi_missing.eq(1)), "magnitude_z": summary(v.magnitude_robust_z) if len(v) else None} for k, v in groups(part).items()}, "missing_vs_observed_severe": {str(flag): rate(s.predicted_label.eq("Low")) for flag, s in severe.groupby("magnitude_missing")}, "fold_counts": {str(fold): {"true_severe": len(s), "severe_to_low": int(s.predicted_label.eq("Low").sum())} for fold, s in severe.groupby("fold")}}
    save("stratified.json", json_bytes(strata), args.verify)
    figures(data, result, args.verify)
    require(all(sha(p) == SHA for p in protected), "Frozen checksum changed")
    if args.verify:
        verify_outputs(data, result, whitelist_hash)
    print("Whitelist rows=", len(white), "OOF=", result["OOF"]["n"], "Test=", result["Test"]["n"], "repeat verification=" + str(args.verify))


def verify_outputs(data, result, whitelist_hash):
    """Independent checks on serialized products, not just in-memory frames."""
    import re
    from PIL import Image
    white = pd.read_csv(OUT / (PREFIX + "whitelist.csv"))
    exported = pd.read_csv(OUT / (PREFIX + "events.csv"), keep_default_na=False)
    require(set(exported.event_id) == set(white.event_id) and exported.event_id.is_unique, "Export ID boundary")
    joined = exported.merge(white, on="event_id", suffixes=("", "_white"), validate="one_to_one")
    require(all(joined[c].eq(joined[c + "_white"]).all() for c in ["dataset", "year", "fold"]), "Export scope mismatch")
    for name, lower, upper in [("OOF", 2014, 2021), ("Test", 2022, 2023)]:
        subset = exported[exported.dataset.eq(name)]
        require(subset.year.between(lower, upper).all(), "Export year boundary")
        r = result[name]
        require(matrix(subset) == r["confusion_matrix"], "Serialized confusion matrix")
        for key, part in groups(subset).items():
            require(len(part) == r["group_counts"][key], "Serialized group count")
            bins = r["probability_bins"][key]
            require(sum(x["count"] for x in bins.values()) == len(part), "Probability bin coverage")
            for col in ["hdi_missing", "month_missing", "magnitude_missing", "magnitude_group_unknown", "date_imputed"]:
                require(int(pd.to_numeric(part[col]).eq(1).sum()) == r["missingness"][key][col]["count"], "Serialized missingness count")
        for field, rows in r["categories"].items():
            require(sum(x["true_severe"] for x in rows) == r["class_counts"]["Severe"], "Category severe coverage")
            require(sum(x["severe_to_low"] for x in rows) == r["group_counts"]["Severe_to_Low"], "Category error coverage")
            if field == "year":
                require(all(lower <= int(float(x["level"])) <= upper for x in rows), "JSON year boundary")
            for x in rows:
                require(x["error_rate"] == (x["severe_to_low"]/x["true_severe"] if x["true_severe"] else None), "Category denominator")
                require(x["error_share"] == x["severe_to_low"]/x["error_share_denominator"], "Error share denominator")
    rate_count = 0
    def check_rates(value):
        nonlocal rate_count
        if isinstance(value, dict):
            if {"count", "denominator", "rate"}.issubset(value):
                expected = value["count"]/value["denominator"] if value["denominator"] else None
                require(value["rate"] == expected, "Rate denominator mismatch")
                rate_count += 1
            for v in value.values():
                check_rates(v)
        elif isinstance(value, list):
            for v in value:
                check_rates(v)
    products = sorted(OUT.glob(PREFIX + "*.json"))
    ids = set(white.event_id)
    event_pattern = r"\b\d{4}-\d{4}-[A-Z]{3}\b"
    for path in products:
        if path.name.endswith("verification.json"):
            continue
        text = path.read_text(encoding="utf-8")
        require(set(re.findall(event_pattern, text)).issubset(ids), "JSON contains non-whitelist ID")
        check_rates(json.loads(text))
    report = ROOT / "docs/stages/第三阶段_补充三_Severe严重漏判错误画像与数据缺口诊断.md"
    require(set(re.findall(event_pattern, report.read_text(encoding="utf-8"))).issubset(ids), "Report ID boundary")
    images = {}
    for path in sorted((OUT / (PREFIX + "figures")).glob("*.png")):
        with Image.open(path) as img:
            img.load()
            images[path.name] = list(img.size)
    require(len(images) == 4, "Figure completeness")
    files = [p for p in sorted(OUT.glob(PREFIX + "*")) if p.is_file() and not p.name.endswith("verification.json")]
    save("verification.json", json_bytes({"scope": SCOPE, "whitelist_sha256": whitelist_hash, "rows_checked": len(exported), "OOF_n": 3466, "Test_n": 948, "outside_whitelist_output_events": 0, "out_of_scope_output_years": 0, "label_and_source_field_checks": "passed during extraction", "confusion_matrices": "match existing reports", "json_csv_repeat_bytes_equal": True, "explicit_rate_denominators_checked": rate_count, "png_decode_dimensions": images, "frozen_sha256": SHA, "artifact_sha256": {p.name: sha(p) for p in files}, "script_sha256": sha(Path(__file__)), "report_sha256": sha(report)}), False)


if __name__ == "__main__":
    main()
