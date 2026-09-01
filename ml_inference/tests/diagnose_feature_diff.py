from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml_inference.feature_builder import FrozenFeatureBuilder, FEATURES
sys.path.insert(0, str(ROOT / "ml_experiments/modeling/three_class/final_t2/explainability/scripts"))
import run_explainability as exact_builder

exact, _ = exact_builder.build_test_features()
exact = exact.set_index("event_id")
raw = pd.read_excel(ROOT / "data/emdat_raw.xlsx", sheet_name="EM-DAT Data", dtype=object, keep_default_na=False,
                    usecols=["DisNo.", "Magnitude", "Magnitude Scale"])
raw.columns = ["event_id", "magnitude", "magnitude_scale"]
raw.event_id = raw.event_id.astype(str)
data = pd.read_csv(ROOT / "data/processed_hdro/disaster_hdi_merged.csv",
                   usecols=["event_id", "country_code", "disaster_type", "disaster_subtype", "year", "total_deaths", "event_date", "date_granularity"])
data = data[data.year.between(2022, 2023) & data.total_deaths.notna()].merge(raw, on="event_id", validate="one_to_one")
builder = FrozenFeatureBuilder(); frames = []; ids = []
probe = data[data.event_id.eq("2022-0423-JPN")].iloc[0]
print("scale_probe", repr(probe.magnitude_scale), [hex(ord(x)) for x in str(probe.magnitude_scale)])
print("group_keys", [(repr(k), [hex(ord(x)) for x in k]) for k in builder.magnitude_groups if "Heat" in k])
for row in data.itertuples(index=False):
    stamp = pd.Timestamp(row.event_date)
    value = stamp.strftime("%Y-%m-%d" if row.date_granularity == "day" else "%Y-%m" if row.date_granularity == "month" else "%Y")
    frame, _ = builder.build({"country_code": row.country_code, "disaster_type": row.disaster_type,
                              "disaster_subtype": row.disaster_subtype, "event_date": value,
                              "date_granularity": row.date_granularity, "magnitude": None if row.magnitude == "" else row.magnitude,
                              "magnitude_scale": None if row.magnitude_scale == "" else row.magnitude_scale})
    frames.append(frame); ids.append(row.event_id)
ours = pd.concat(frames, ignore_index=True); ours.index = ids
for column in FEATURES:
    left = exact.loc[ids, column]; right = ours[column]
    same = (left.isna() & right.isna()) | left.eq(right)
    examples = [{"event_id": idx, "expected": left.loc[idx], "actual": right.loc[idx]} for idx in left.index[~same][:3]]
    print(column, int((~same).sum()), examples)
