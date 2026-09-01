"""EXPLORATORY / NOT FOR MODEL SELECTION / NOT DEPLOYED.

Development-only scope, conservative candidate linkage, and as-of availability audit.
No model or prediction imports. Commands: scope, download, match, blocked, verify.
The archived run stopped on network failure; matching code was NOT executed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = HERE / "data/raw"
PROCESSED = HERE / "data/processed"
REPORTS = HERE / "reports"
CHECKS = HERE / "checksums"
FLAGS = ["EXPLORATORY", "NOT FOR MODEL SELECTION", "NOT DEPLOYED"]
FROZEN = ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib"
EXPECTED_SHA = "c4960347d423b1b46065c8e2fc57e1e1656fae11e1198af2fe5c6a734392a9d4"
URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.since1980.list.v04r01.csv"
DOCUMENTS = {
    "column_documentation.pdf": "https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf",
    "technical_details.pdf": "https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf",
    "official_metadata.html": "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C01552",
}
IB_FILE = RAW / "ibtracs.v04r01.2000_2021.source_rows.csv"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RULES = {
    "flags": FLAGS, "version": 1,
    "emdat_scope": "year 2000..2021 AND disaster_type == Storm AND disaster_subtype == Tropical cyclone; include unlabeled events",
    "time_window_days": 3,
    "time_window_reason": "Candidate retrieval allowance around EM-DAT start-date interval, fixed before linkage; accommodates date-only timing and early/late impacts, not fitted to labels",
    "date_precision": "day is one UTC calendar day; month/year intervals preserved, never impute a matching day",
    "name_rule": "Unicode ASCII uppercase tokens; exact token overlap after removing storm descriptors and numbers; no fuzzy matching or learned aliases",
    "track_type": "MAIN only", "nature": "TS or SS within candidate window",
    "region_rule": "EM-DAT UN subregion to plausible IBTrACS basins; coarse consistency only, not confirmed country impact",
    "high": "Unique date/name/region consistent SID plus independently verified event-country footprint and reliable Location; no such spatial verification in this bounded audit",
    "medium": "One plausible SID with exact name token, day-level start and compatible basin; country/Location impact is the single unresolved evidence dimension",
    "ambiguous": "More than one plausible SID; a single candidate lacking sufficient name/date evidence remains UNMATCHED, with its evidence preserved",
    "unmatched": "No plausible candidate under the fixed rule; no forced nearest or fuzzy fallback",
    "unique_reliable": "HIGH_CONFIDENCE only; MEDIUM reported separately as provisional, not confirmed linkage",
    "end_date": "Retained for potential human review only; never used by matcher or features",
    "spatial_distances": "None. No geocoding; existing public/world.geo.json lacks verified source metadata and is not used for high-confidence spatial evidence",
    "intensity_eligibility": "Needs matched event-country time AND archived issuance/revision timestamp <= prediction cutoff; best-track ISO_TIME alone is insufficient",
}
REGION_BASINS = {
    "Eastern Asia": ["WP"], "South-eastern Asia": ["WP", "NI", "SI"],
    "Southern Asia": ["NI", "WP"], "Western Asia": ["NI"],
    "Sub-Saharan Africa": ["SI", "NI", "NA"], "Northern Africa": ["NA", "NI"],
    "Latin America and the Caribbean": ["NA", "EP", "SA"], "Northern America": ["NA", "EP"],
    "Australia and New Zealand": ["SI", "SP"], "Melanesia": ["SP", "SI"],
    "Micronesia": ["WP", "EP", "SP"], "Polynesia": ["SP", "EP"],
    "Western Europe": ["NA"], "Northern Europe": ["NA"], "Southern Europe": ["NA"],
}
STOPWORDS = set("TROPICAL CYCLONE CYCLONES TYPHOON TYPHOONS HURRICANE HURRICANES STORM STORMS SEVERE SUPER DEPRESSION TD TS AND THE OF NAMED UNNAMED NOT KNOWN UNKNOWN NO NAME WITH ALSO CALLED AKA CATEGORY CAT WIND WINDS".split())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def output(path, content, verify=False):
    if path.exists():
        require(path.read_bytes() == content, "Existing output differs: " + str(path))
    else:
        require(not verify, "Missing verification output: " + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as f:
            f.write(content)


def dump(path, obj, verify=False):
    output(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode(), verify)


def table(path, frame, verify=False):
    output(path, frame.to_csv(index=False, lineterminator="\n", float_format="%.12g").encode(), verify)


def ratio(n, d):
    return dict(numerator=int(n), denominator=int(d), proportion=float(n/d) if d else None)


def extract_raw(ids):
    fields = ["DisNo.", "Disaster Type", "Disaster Subtype", "Event Name", "ISO", "Location", "Start Year", "Start Month", "Start Day", "End Year", "End Month", "End Day", "Magnitude", "Magnitude Scale"]
    def token(c):
        if c is None:
            return ("v", "")
        if c.get("t") == "inlineStr":
            return ("v", "".join(c.find(NS+"is").itertext()))
        v = c.find(NS+"v")
        return ("s" if c.get("t") == "s" else "v", v.text if v is not None else "")
    def rows(z):
        with z.open("xl/worksheets/sheet1.xml") as f:
            for _, e in ET.iterparse(f, events=["end"]):
                if e.tag == NS+"row":
                    yield {re.sub(r"\d", "", c.get("r")): token(c) for c in e}
                    e.clear()
    def strings(z, indices, allowed=None):
        result = {}
        with z.open("xl/sharedStrings.xml") as f:
            i = 0
            for _, e in ET.iterparse(f, events=["end"]):
                if e.tag == NS+"si":
                    if str(i) in indices:
                        value = "".join(t.text or "" for t in e.iter(NS+"t"))
                        if allowed is None or value in allowed:
                            result[str(i)] = value
                    i += 1
                    e.clear()
        return result
    with ZipFile(ROOT / "data/emdat_raw.xlsx") as z:
        header = next(rows(z))
        values = strings(z, {t[1] for t in header.values() if t[0] == "s"})
        columns = {(values[t[1]] if t[0] == "s" else t[1]): c for c, t in header.items()}
        require(set(fields).issubset(columns), "Missing EM-DAT fields")
        id_refs = set()
        for row in rows(z):
            t = row.get(columns["DisNo."], ("v", ""))
            if t[0] == "s":
                id_refs.add(t[1])
        id_values = strings(z, id_refs, ids)
        selected = []
        for row in rows(z):
            t = row.get(columns["DisNo."], ("v", ""))
            event_id = id_values.get(t[1], "") if t[0] == "s" else t[1]
            if event_id in ids:
                selected.append([row.get(columns[k], ("v", "")) for k in fields])
        values = strings(z, {t[1] for row in selected for t in row if t[0] == "s"})
        frame = pd.DataFrame([[values[t[1]] if t[0] == "s" else t[1] for t in row] for row in selected], columns=["event_id", "raw_type", "raw_subtype", "event_name", "raw_country", "Location", "start_year", "start_month", "start_day", "end_year", "end_month", "end_day", "emdat_magnitude", "emdat_magnitude_scale"])
    require(frame.event_id.is_unique and set(frame.event_id) == ids, "Raw IDs missing or duplicate")
    return frame


def scope(verify=False):
    # Shared container: decode the year gate, then only Development fields.
    selected, storm_types = [], Counter()
    dev_n = labeled_n = severe_n = 0
    cols = ["event_id", "year", "country_code", "region", "disaster_type", "disaster_subtype", "event_date", "event_date_upper", "date_granularity"]
    with (ROOT / "data/processed_hdro/disaster_hdi_merged.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f); header = next(reader)
        ix = {c: header.index(c) for c in cols + ["total_deaths"]}
        for row in reader:
            if not 2000 <= int(row[ix["year"]]) <= 2021:
                continue
            dev_n += 1
            deaths = row[ix["total_deaths"]]
            labeled_n += bool(deaths)
            is_severe = bool(deaths) and float(deaths) >= 100
            severe_n += is_severe
            kind, sub = row[ix["disaster_type"]], row[ix["disaster_subtype"]]
            if kind == "Storm":
                storm_types[sub] += 1
            if kind == "Storm" and sub == "Tropical cyclone":
                selected.append([row[ix[c]] for c in cols] + [int(is_severe), bool(deaths)])
    frame = pd.DataFrame(selected, columns=cols+["is_severe_description_only", "label_available_description_only"]).sort_values("event_id")
    require(frame.event_id.is_unique, "Duplicate Development scope ID")
    table(CHECKS / "development_cyclone_whitelist.csv", frame[["event_id", "year"]], verify)
    raw = extract_raw(set(frame.event_id))
    frame = frame.merge(raw, on="event_id", validate="one_to_one")
    require(frame.disaster_type.eq(frame.raw_type).all() and frame.disaster_subtype.eq(frame.raw_subtype).all(), "Disaster source conflict")
    require(frame.country_code.eq(frame.raw_country).all() and pd.to_numeric(frame.year).eq(pd.to_numeric(frame.start_year)).all(), "Country/year source conflict")
    frame = frame.drop(columns=["raw_type", "raw_subtype", "raw_country"])
    table(REPORTS / "emdat_tropical_cyclone_scope.csv", frame, verify)
    summary = dict(flags=FLAGS, rule=RULES["emdat_scope"], development_all_events=dev_n, development_labeled_events=labeled_n, development_all_severe=severe_n, tropical_cyclone_events=len(frame), tropical_cyclone_severe=int(frame.is_severe_description_only.sum()), tropical_cyclone_labeled=int(frame.label_available_description_only.sum()), storm_subtypes=dict(sorted(storm_types.items())), year_counts=frame.year.value_counts().sort_index().to_dict(), country_counts=frame.country_code.value_counts().sort_index().to_dict(), name_available=ratio(frame.event_name.str.strip().ne("").sum(), len(frame)), location_available=ratio(frame.Location.str.strip().ne("").sum(),len(frame)), date_precision=frame.date_granularity.value_counts().sort_index().to_dict(), whitelist_sha256=sha(CHECKS / "development_cyclone_whitelist.csv"), test_used=False, maturity_extracted=False)
    dump(REPORTS / "scope_summary.json", summary, verify)
    dump(CHECKS / "matching_rules_locked.json", {**RULES, "region_basins": REGION_BASINS, "name_stopwords": sorted(STOPWORDS)}, verify)
    print(json.dumps(summary, ensure_ascii=False))


def download():
    require((REPORTS / "scope_summary.json").exists(), "Report scope before external matching")
    require(not IB_FILE.exists(), "Raw subset already exists; do not overwrite or re-download")
    RAW.mkdir(parents=True, exist_ok=True)
    received = 0
    # Retain byte-exact official header/units and only 2000..2021 timestamp rows.
    # This is explicitly an HTTP-stream subset, NOT the full official CSV hash.
    with urlopen(Request(URL, headers={"User-Agent": "CrisisDataTerminal-ExploratoryAudit/1.0"}), timeout=60) as response:
        require(response.status == 200, "Official source unavailable; STOP")
        metadata = dict(flags=FLAGS, dataset="International Best Track Archive for Climate Stewardship (IBTrACS)", publisher="NOAA National Centers for Environmental Information", version="v04r01", url=URL, downloaded_utc=datetime.now(timezone.utc).isoformat(), last_modified=response.headers.get("Last-Modified"), etag=response.headers.get("ETag"), source_content_length=response.headers.get("Content-Length"), raw_path=str(IB_FILE.relative_to(ROOT)), temporal_subset="2000-01-01 <= ISO_TIME < 2022-01-01", preservation="Byte-exact selected source lines with original header and units; not the complete source CSV", license_or_use="Official NCEI metadata: cite Gahtan et al. 2024 DOI 10.25921/82ty-9e16 and Knapp et al. 2010 DOI 10.1175/2009BAMS2755.1; NOAA provides no accuracy/completeness warranty", access_constraints_url=DOCUMENTS["official_metadata.html"])
        with IB_FILE.open("xb") as f:
            header = response.readline(); units = response.readline()
            received += len(header)+len(units)
            require(header.decode("utf-8-sig").split(",")[6] == "ISO_TIME", "Unexpected official CSV schema")
            f.write(header); f.write(units)
            for line in response:
                received += len(line)
                prefix = line.split(b",", 7)
                timestamp = prefix[6].strip()
                if b"2000-01-01" <= timestamp < b"2022-01-01":
                    f.write(line)
    metadata.update(saved_bytes=IB_FILE.stat().st_size, sha256=sha(IB_FILE), response_bytes=received)
    require(received == int(metadata["source_content_length"]), "Incomplete HTTP source stream")
    dump(CHECKS / "source_manifest.json", metadata)
    docs = {}
    for name, url in DOCUMENTS.items():
        with urlopen(url, timeout=60) as r:
            body = r.read()
        output(RAW / name, body)
        docs[name] = dict(url=url, bytes=len(body), sha256=sha(RAW/name))
    dump(CHECKS / "documentation_manifest.json", docs)
    print(json.dumps({k: metadata[k] for k in ["version", "saved_bytes", "sha256", "temporal_subset"]}))


def tokens(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    return set(re.findall(r"[A-Z]+", text)) - STOPWORDS


def match(verify=False):
    # Deliberately do not load the descriptive severity flag into the matcher.
    fields = ["event_id", "year", "country_code", "region", "event_name", "event_date", "event_date_upper", "date_granularity", "Location"]
    events = pd.read_csv(REPORTS / "emdat_tropical_cyclone_scope.csv", usecols=fields, keep_default_na=False)
    scope_summary = json.loads((REPORTS / "scope_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((CHECKS / "source_manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("download_complete", True), "Incomplete official source: matching forbidden")
    require(sha(IB_FILE) == manifest["sha256"], "External raw checksum changed")
    cols = ["SID", "NAME", "ISO_TIME", "BASIN", "NATURE", "LAT", "LON", "TRACK_TYPE", "DIST2LAND", "LANDFALL", "IFLAG", "WMO_AGENCY", "WMO_WIND", "WMO_PRES", "USA_AGENCY", "USA_RECORD", "USA_WIND", "USA_PRES", "USA_SSHS", "TOKYO_WIND", "TOKYO_PRES", "CMA_WIND", "CMA_PRES", "HKO_WIND", "HKO_PRES", "NEWDELHI_WIND", "NEWDELHI_PRES", "REUNION_WIND", "REUNION_PRES", "BOM_WIND", "BOM_PRES"]
    tracks = pd.read_csv(IB_FILE, skiprows=[1], usecols=cols, keep_default_na=False, dtype=str)
    for c in cols:
        tracks[c] = tracks[c].str.strip()
    tracks["time"] = pd.to_datetime(tracks.ISO_TIME, utc=True)
    require(tracks.time.dt.year.between(2000, 2021).all(), "External timestamp outside Development")
    tracks = tracks[tracks.TRACK_TYPE.eq("MAIN")].copy()
    for c in ["LAT", "LON", "DIST2LAND", "LANDFALL", "USA_SSHS"] + [c for c in cols if c.endswith(("_WIND", "_PRES"))]:
        tracks[c] = pd.to_numeric(tracks[c].replace("", np.nan), errors="raise")
    require(not tracks.duplicated(["SID", "ISO_TIME"]).any(), "Multiple MAIN records per SID/time")
    candidate_rows, audits, field_rows = [], [], []
    for event in events.itertuples(index=False):
        lower = pd.Timestamp(event.event_date, tz="UTC") - pd.Timedelta(days=RULES["time_window_days"])
        upper = pd.Timestamp(event.event_date_upper, tz="UTC") + pd.Timedelta(days=RULES["time_window_days"]+1)
        near = tracks[tracks.time.ge(lower) & tracks.time.lt(upper) & tracks.NATURE.isin(["TS", "SS"])]
        ename = tokens(event.event_name)
        basins = set(REGION_BASINS.get(event.region, []))
        candidates = []
        for sid, part in near.groupby("SID", sort=True):
            names = set().union(*(tokens(x) for x in part.NAME.unique())) - {"NOT", "NAMED"}
            name_match = bool(ename & names)
            basin_match = bool(set(part.BASIN) & basins)
            # Retain exact-name conflicts as audit evidence, not as accepted matches.
            if not (name_match or basin_match):
                continue
            plausible = basin_match and (name_match or not ename)
            diff = (part.time-pd.Timestamp(event.event_date,tz="UTC")).dt.total_seconds()/86400
            row = dict(event_id=event.event_id, SID=sid, ibtracs_names="|".join(sorted(part.NAME.unique())), minimum_absolute_start_date_difference_days=float(abs(diff).min()), exact_name_token=name_match, common_name_tokens="|".join(sorted(ename & names)), basin_compatible=basin_match, basins="|".join(sorted(part.BASIN.unique())), country_confirmed=False, location_verified=False, global_landfall_marker=bool(part.LANDFALL.eq(0).any()), usa_landfall_record=bool(part.USA_RECORD.eq("L").any()), event_country_landfall_confirmed=False, plausible_candidate=plausible, conflict_reason="country_footprint_and_Location_unverified" if basin_match else "name_matches_but_basin_conflicts")
            if plausible:
                candidates.append((row, part))
            candidate_rows.append(row)
        n = len(candidates)
        confidence = "AMBIGUOUS" if n > 1 else "UNMATCHED"
        if n == 1 and candidates[0][0]["exact_name_token"] and event.date_granularity == "day":
            confidence = "MEDIUM_CONFIDENCE"
        chosen = candidates[0][0]["SID"] if confidence == "MEDIUM_CONFIDENCE" else ""
        audits.append(dict(event_id=event.event_id, year=event.year, country_code=event.country_code, candidate_count=n, confidence=confidence, provisional_sid=chosen, accepted_sid="", manual_intervention_required=True, conflict_reason="no_candidate_under_locked_rule" if not n else ("multiple_plausible_SIDs" if n > 1 else "country_Location_unverified" if confidence == "MEDIUM_CONFIDENCE" else "name_or_date_precision_unresolved")))
        if chosen:
            part = candidates[0][1]
            # Window records, NOT a landfall or pre-event feature selection.
            row = dict(event_id=event.event_id, provisional_sid=chosen, window_records=len(part), wind_present_in_window=bool(part.WMO_WIND.notna().any()), pressure_present_in_window=bool(part.WMO_PRES.notna().any()), usa_category_present_in_window=bool(part.USA_SSHS.notna().any()), global_landfall_marker_records=int(part.LANDFALL.eq(0).sum()), usa_landfall_records=int(part.USA_RECORD.eq("L").sum()), event_country_landfall_time="", as_of_publication_verified=False, eligible=False, reason="NO_COUNTRY_LANDFALL_TIME_AND_NO_AS_OF_ISSUANCE_PROVENANCE")
            field_rows.append(row)
    candidates = pd.DataFrame(candidate_rows)
    audit = pd.DataFrame(audits).sort_values("event_id")
    candidates = candidates.merge(audit[["event_id", "candidate_count", "confidence"]], on="event_id", validate="many_to_one").sort_values(["event_id", "SID"])
    table(REPORTS / "cyclone_match_candidates.csv", candidates, verify)
    table(REPORTS / "cyclone_match_audit.csv", audit, verify)
    available = pd.DataFrame(field_rows)
    table(PROCESSED / "provisional_window_field_presence.csv", available, verify)
    counts = {k: int(audit.confidence.eq(k).sum()) for k in ["HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "AMBIGUOUS", "UNMATCHED", "OUT_OF_SCOPE"]}
    by_year, by_country = {}, {}
    for col, dest in [("year", by_year), ("country_code", by_country)]:
        for key, group in audit.groupby(col, sort=True):
            dest[str(key)] = {"high": ratio(group.confidence.eq("HIGH_CONFIDENCE").sum(), len(group)), "medium": ratio(group.confidence.eq("MEDIUM_CONFIDENCE").sum(),len(group)), "high_plus_medium": ratio(group.confidence.isin(["HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE"]).sum(),len(group))}
    medium = audit[audit.confidence.eq("MEDIUM_CONFIDENCE")]
    multi = medium.groupby("provisional_sid").country_code.nunique()
    multisids = set(multi[multi.gt(1)].index)
    # Raw fields are not standardized into a model column; agencies remain separate.
    agencies = {"USA": 1, "TOKYO": 10, "CMA": 2, "HKO": 10, "NEWDELHI": 3, "REUNION": 10, "BOM": 10}
    agency_stats = {}
    for agency, averaging in agencies.items():
        a = tracks[agency+"_WIND"]; b = tracks[agency+"_PRES"]
        agency_stats[agency] = dict(wind_average_minutes=averaging, wind_unit="knots", pressure_unit="mb (=hPa)", wind_present=ratio(a.notna().sum(),len(tracks)), pressure_present=ratio(b.notna().sum(),len(tracks)))
    overlap = tracks.USA_WIND.notna() & tracks.TOKYO_WIND.notna()
    difference = tracks.loc[overlap,"USA_WIND"] - tracks.loc[overlap,"TOKYO_WIND"]
    field_audit = dict(flags=FLAGS, units_conversion_applied=False, possible_speed_conversion="knots * 1852 / 3600 = m/s; preserves averaging duration, no 1/3/10-minute equivalence conversion", priority="No agency fallback/merging; preserve separate columns. WMO_AGENCY attribution required for WMO_WIND.", agency_coverage_development_main_track_points=agency_stats, usa_tokyo_overlap_points=int(overlap.sum()), usa_tokyo_unequal_wind=ratio(difference.ne(0).sum(),len(difference)), usa_tokyo_difference_median_knots=float(difference.median()), difference_interpretation="Different averaging periods and agency analyses; not automatically an erroneous record", interpolation_flags=tracks.IFLAG.value_counts().sort_index().to_dict(), track_time_min=tracks.ISO_TIME.min(), track_time_max=tracks.ISO_TIME.max(), provisional_window_presence={c: ratio(available[c].sum(),len(available)) for c in ["wind_present_in_window", "pressure_present_in_window", "usa_category_present_in_window"]}, qualified_event_country_landfall_wind=ratio(0,len(events)), qualified_event_country_landfall_pressure=ratio(0,len(events)), qualified_event_country_landfall_category=ratio(0,len(events)), as_of_timing_proven=ratio(0,len(events)), conclusion="ISO_TIME is observation time, not issuance time. MAIN best tracks are retrospective; no point-in-time release provenance was obtained. Zero means verified eligible count, not that historical observations never existed.")
    dump(REPORTS / "field_availability.json", field_audit, verify)
    summary = dict(flags=FLAGS, feasibility="LIMITED_FEASIBILITY", emdat_tropical_cyclone_events=len(events), confidence_counts=counts, confidence_rates={k:ratio(v,len(events)) for k,v in counts.items()}, unique_reliable_match_rate=ratio(counts["HIGH_CONFIDENCE"],len(events)), high_plus_medium=ratio(counts["HIGH_CONFIDENCE"]+counts["MEDIUM_CONFIDENCE"],len(events)), qualified_intensity_coverage=ratio(0,len(events)), manual_intervention=ratio(len(audit),len(events)), multi_candidate_conflicts=ratio(audit.candidate_count.gt(1).sum(),len(events)), ambiguous_single_candidate=int((audit.confidence.eq("AMBIGUOUS") & audit.candidate_count.eq(1)).sum()), provisional_multi_country_sids=len(multisids), provisional_multi_country_event_rows=int(medium.provisional_sid.isin(multisids).sum()), by_year=by_year, by_country=by_country, future_cv_eligible_events=0, development_all_severe=scope_summary["development_all_severe"], scope_severe_coverage=ratio(scope_summary["tropical_cyclone_severe"],scope_summary["development_all_severe"]), eligible_severe_coverage=ratio(0,scope_summary["development_all_severe"]), stop_reasons=["HIGH_CONFIDENCE_BELOW_70_PERCENT", "QUALIFIED_INTENSITY_BELOW_60_PERCENT", "MANUAL_INTERVENTION_ABOVE_20_PERCENT", "COUNTRY_LANDFALL_AND_AS_OF_TIMING_UNRESOLVED"], not_a_best_possible_matching_rate=True, test_used=False, maturity_extracted=False, models_trained=0, model_metrics_computed=False, frozen_sha256=sha(FROZEN), rules_sha256=sha(CHECKS/"matching_rules_locked.json"), raw_sha256=sha(IB_FILE))
    if summary["high_plus_medium"]["proportion"] < .8:
        summary["stop_reasons"].append("HIGH_PLUS_MEDIUM_BELOW_80_PERCENT")
    dump(REPORTS / "feasibility_summary.json", summary, verify)
    require(sha(FROZEN) == EXPECTED_SHA, "Frozen model checksum changed")
    if not verify:
        plot(summary)
    print(json.dumps({k:summary[k] for k in ["feasibility","emdat_tropical_cyclone_events","confidence_counts","qualified_intensity_coverage","stop_reasons"]},ensure_ascii=False))


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = REPORTS / "figures/matching_coverage.png"
    require(not path.exists(), "Figure already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = summary["confidence_counts"]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(list(counts), list(counts.values()), color=["#009E73", "#0072B2", "#E69F00", "#D55E00", "#999999"])
    ax.bar_label(bars, labels=[f'{n}/{summary["emdat_tropical_cyclone_events"]}' for n in counts.values()], padding=4)
    ax.set(xlim=(0,max(counts.values())*1.25), xlabel="EM-DAT Development event rows", title="EXPLORATORY: conservative matching evidence\nNOT FOR MODEL SELECTION / NOT DEPLOYED")
    fig.tight_layout(); fig.savefig(path,dpi=160); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["scope", "download", "match", "blocked", "verify"])
    args = p.parse_args()
    require(sha(FROZEN) == EXPECTED_SHA, "Frozen checksum mismatch")
    if args.phase == "scope":
        scope()
    elif args.phase == "download":
        download()
    elif args.phase == "match":
        match()
    elif args.phase == "blocked":
        blocked()
    else:
        scope(True)
        if (RAW / "ibtracs.v04r01.2000_2021.INCOMPLETE.csv").exists():
            blocked(True)
        else:
            match(True)
        print("Deterministic CSV/JSON byte comparison PASS")


def blocked(verify=False):
    """Archive an unmeasured audit, never turn a network failure into zero matches."""
    partial = RAW / "ibtracs.v04r01.2000_2021.INCOMPLETE.csv"
    require(partial.exists(), "No incomplete source evidence")
    s = json.loads((REPORTS / "scope_summary.json").read_text(encoding="utf-8"))
    # Check the persisted partial contains no out-of-period data; do not use it for matching.
    with partial.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); next(reader)
        retained = 0
        for row in reader:
            require("2000-01-01" <= row["ISO_TIME"] < "2022-01-01", "Partial source temporal boundary")
            retained += 1
    src = dict(flags=FLAGS, dataset="International Best Track Archive for Climate Stewardship (IBTrACS)", publisher="NOAA NCEI", version="v04r01", download_url=URL, attempted_date="2026-08-31", source_last_modified="2026-08-30T08:59:48Z", source_content_length_from_head=143681274, download_complete=False, error="PermissionError: [Errno 13] Permission denied during HTTP response iteration; stopped without mirror or additional network retry", raw_file=partial.relative_to(ROOT).as_posix(), saved_bytes=partial.stat().st_size, sha256_partial_only=sha(partial), retained_development_track_rows=retained, usable_for_analysis=False, intended_time_coverage="2000-01-01 <= ISO_TIME < 2022-01-01", dataset_time_coverage_documented="1840s to present; NOT downloaded in full", use_information="Official NCEI metadata requires dataset/paper attribution and disclaims accuracy/completeness warranty", documentation_urls=DOCUMENTS, note="Official documentation was read through web tools. No offline PDF download was completed. SHA-256 is only for the incomplete local file, not the complete official dataset.")
    dump(CHECKS / "source_manifest.json", src, verify)
    unknown = lambda d: dict(numerator=None, denominator=d, proportion=None, measured=False, reason="INCOMPLETE_OFFICIAL_DOWNLOAD")
    summary = dict(flags=FLAGS, feasibility="LIMITED_FEASIBILITY", assessment_status="INCOMPLETE_NETWORK_BLOCKED", grade_scope="This execution is limited to scope/documentation audit; NOT a conclusion that the dataset is unmatchable", emdat_tropical_cyclone_events=s["tropical_cyclone_events"], confidence_counts={k:None for k in ["HIGH_CONFIDENCE","MEDIUM_CONFIDENCE","AMBIGUOUS","UNMATCHED","OUT_OF_SCOPE"]}, unique_reliable_match_rate=unknown(s["tropical_cyclone_events"]), high_plus_medium=unknown(s["tropical_cyclone_events"]), qualified_intensity_coverage=unknown(s["tropical_cyclone_events"]), manual_intervention=unknown(s["tropical_cyclone_events"]), multi_candidate_conflicts=unknown(s["tropical_cyclone_events"]), multi_country_events=None, future_development_cv_eligible_events=None, by_year={k:unknown(v) for k,v in s["year_counts"].items()}, by_country={k:unknown(v) for k,v in s["country_counts"].items()}, development_all_severe=s["development_all_severe"], tropical_cyclone_severe=s["tropical_cyclone_severe"], scope_severe_coverage=ratio(s["tropical_cyclone_severe"],s["development_all_severe"]), eligible_severe_coverage=unknown(s["development_all_severe"]), stop_reasons=["NETWORK_TRANSFER_FAILED"], numeric_stop_thresholds_evaluable=False, formal_feature_experiment_recommended=False, match_executed=False, test_used=False, maturity_extracted=False, models_trained=0, model_metrics_computed=False, frozen_sha256=sha(FROZEN), rules_sha256=sha(CHECKS/"matching_rules_locked.json"))
    dump(REPORTS / "feasibility_summary.json", summary, verify)
    field_rows = [
        ("NAME / SID", "D", "Identification, not intensity; archival SID/name availability at event cutoff not proven"),
        ("ISO_TIME", "A/B", "UTC observation/valid time, NOT issuance timestamp; before/at/after depends on event-country cutoff"),
        ("BASIN / SUBBASIN", "A/B", "Ocean basin, not affected-country identification"),
        ("LAT / LON", "A/B+D", "Observed track position may be later revised/interpolated; as-of availability unproven"),
        ("DIST2LAND", "A/B+D", "Distance to a global land mask, not event-country coastline"),
        ("LANDFALL", "B/C", "Minimum distance until next timestep, usually 3h; uses future position relative to current row; POST-EVENT / NOT ELIGIBLE as an as-of flag"),
        ("USA_RECORD=L", "D", "Coastline crossing record, not a country mapping or a proven contemporaneous bulletin"),
        ("event-country landfall time", "D", "Not directly established by the inspected schema; multiple landfalls/countries require separate linkage"),
        ("landfall sustained wind / pressure / category", "D", "Needs verified event-country landfall time and issuance provenance, not lifetime max/min"),
        ("first country-nearby intensity", "D", "Needs authoritative geometry, preregistered proximity rule and as-of record; none created"),
        ("WMO_WIND / WMO_PRES / WMO_AGENCY", "A/B+D", "Per-observation official agency values; averaging periods differ; no averaging adjustment in WMO_WIND; retrospective release time unproven"),
        ("agency WIND / PRES", "A/B+D", "Keep agency, averaging period, unit and interpolation flags separate; no silent fallback"),
        ("lifetime maximum wind", "C", "POST-EVENT / NOT ELIGIBLE"),
        ("lifetime minimum pressure", "C", "POST-EVENT / NOT ELIGIBLE"),
        ("final duration / complete track", "C", "POST-EVENT / NOT ELIGIBLE"),
        ("TRACK_TYPE MAIN / IFLAG", "C/D", "MAIN has reanalysis; P/I flags indicate interpolation using other timestamps; not point-in-time publication evidence"),
    ]
    audit = dict(flags=FLAGS, empirical_coverage_measured=False, field_timing_definitions={"A":"before or at landfall if proven available at cutoff", "B":"during event", "C":"post-event", "D":"availability timing unresolved"}, timing_audit=[dict(field=f,category=c,note=n) for f,c,n in field_rows], agency_averaging_minutes={"USA":1,"TOKYO":10,"NEWDELHI":3,"REUNION":10,"BOM":10,"NADI":10,"WELLINGTON":10,"CMA":2,"HKO":10,"KMA":10}, wind_unit="knots", pressure_unit="mb (numerically equal to hPa)", possible_unit_conversion="knots * 1852 / 3600 = m/s; no averaging-period conversion authorized", conversion_applied=False, agency_priority="No unified field produced. WMO values retain WMO_AGENCY; native agency columns separate, missing remains missing.", missing_quality="CSV blanks are missing; IFLAG O original, P interpolated position+intensity, I intensity interpolated, V other variables interpolated. MAIN is reanalyzed; PROVISIONAL is not final.", timezone="UTC", temporal_granularity="Common reporting 6h, some 3h or special observations; merged positions generally 3h/interpolated", multiple_landfalls="No automatic strongest/first-global-landfall selection; must associate event-country and define cutoff before any future feature work", qualified_landfall_wind=unknown(s["tropical_cyclone_events"]), qualified_landfall_pressure=unknown(s["tropical_cyclone_events"]), qualified_landfall_category=unknown(s["tropical_cyclone_events"]), timing_clear_coverage=unknown(s["tropical_cyclone_events"]), sources=DOCUMENTS)
    dump(REPORTS / "field_availability.json", audit, verify)
    if not verify:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        path = REPORTS / "figures/development_scope.png"
        require(not path.exists(), "Scope figure exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(12,4))
        years, values = list(s["year_counts"]), list(s["year_counts"].values())
        bars=ax.bar(years,values,color="#0072B2"); ax.bar_label(bars,fontsize=8)
        ax.tick_params(axis="x",rotation=45)
        ax.set(ylabel="EM-DAT event rows",title=f'EXPLORATORY: Development scope, n={s["tropical_cyclone_events"]}\nNOT FOR MODEL SELECTION / NOT DEPLOYED; matching not measured')
        fig.tight_layout(); fig.savefig(path,dpi=160); plt.close(fig)
    print("NETWORK STOP: matching/qualified coverage remain unmeasured, not zero")


if __name__ == "__main__":
    main()
