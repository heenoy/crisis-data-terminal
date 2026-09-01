"""Synthetic invariants; never read held-out Test or Maturity records."""
import json
import unittest

import numpy as np
import pandas as pd

import time_cv_oof_threshold_class_weight as exp


class TimeCVTests(unittest.TestCase):
    def test_time_folds_disjoint_validation(self):
        cfg = json.loads(exp.CFG_PATH.read_text())
        years = []
        for fold in cfg["folds"]:
            self.assertLess(fold["train_end"], fold["validation_start"])
            years += list(range(fold["validation_start"], fold["validation_end"] + 1))
        self.assertEqual(len(years), len(set(years)))
        self.assertEqual(max(years), 2021)

    def test_frequency_future_and_overlapping_dates(self):
        df = pd.DataFrame({"country_code": ["AAA"] * 4,
            "event_date": ["2010-01-01", "2010-01-01", "2010-02-01", "2011-01-01"],
            "event_date_upper": ["2010-01-01", "2010-12-31", "2010-02-01", "2011-01-01"]})
        self.assertEqual(exp.causal_frequency(df).tolist(), [0, 0, 1, 3])
        self.assertEqual(exp.causal_frequency(df.iloc[:3]).tolist(), [0, 0, 1])

    def test_magnitude_fold_fit_only(self):
        train = pd.DataFrame({"group_key": ["Storm | Kph"] * 20, "magnitude": np.arange(20, dtype=float)})
        val = pd.DataFrame({"group_key": ["Storm | Kph", "Unknown"], "magnitude": [9999., 8.]})
        out, stats = exp.magnitude_transform(train, val)
        row = stats[stats.group_key.eq("Storm | Kph")].iloc[0]
        self.assertEqual(row["median"], 9.5)
        self.assertEqual(out.magnitude_robust_z.iloc[0], 5.)
        self.assertTrue(np.isnan(out.magnitude_robust_z.iloc[1]))
        self.assertEqual(out.magnitude_group_unknown.tolist(), [0, 1])

    def test_magnitude_too_small_or_zero_iqr(self):
        for values in [np.arange(19), np.ones(20)]:
            train = pd.DataFrame({"group_key": ["Storm | Kph"] * len(values), "magnitude": values})
            out, _ = exp.magnitude_transform(train, train)
            self.assertTrue(out.magnitude_robust_z.isna().all())

    def test_threshold_fixed_class_order(self):
        f = pd.DataFrame({"probability_Low": [.4, .2], "probability_Moderate": [.35, .5], "probability_Severe": [.25, .3]})
        self.assertEqual(exp.threshold_prediction(f, .3).tolist(), ["Low", "Severe"])

    def test_feature_allowlist(self):
        self.assertEqual(len(exp.FEATURES), 15)
        exp.base.assert_safe_features(exp.FEATURES)
        with self.assertRaises(RuntimeError): exp.base.assert_safe_features(exp.FEATURES + ["total_deaths"])

    def test_frozen_original_and_serving_copy(self):
        self.assertEqual(exp.sha(exp.FROZEN), exp.EXPECTED_SHA)
        self.assertEqual(exp.sha(exp.ROOT / "ml_inference/frozen_assets/final_t2_pipeline.joblib"), exp.EXPECTED_SHA)


if __name__ == "__main__":
    unittest.main()
