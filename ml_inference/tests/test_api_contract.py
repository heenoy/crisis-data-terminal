from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml_inference.feature_builder import FEATURES, FrozenFeatureBuilder  # noqa: E402
from ml_inference.loader import get_pipeline  # noqa: E402
from ml_inference.service import health_response, options_response, prediction_response  # noqa: E402


def valid_payload(**updates):
    payload = {"country_code": "CHN", "disaster_type": "Flood", "disaster_subtype": "Flood (General)",
               "event_date": "2023-07-15", "date_granularity": "day", "magnitude": 1000, "magnitude_scale": "Km2"}
    payload.update(updates); return payload


class ImpactApiContractTests(unittest.TestCase):
    def test_01_health(self):
        self.assertEqual(health_response()["status"], "ready")

    def test_02_options(self):
        body = options_response(); self.assertTrue(body["success"]); self.assertGreater(len(body["countries"]), 200)

    def test_03_normal_input(self):
        status, body = prediction_response(valid_payload()); self.assertEqual(status, 200); self.assertTrue(body["success"])

    def test_04_minimum_input_and_missing_magnitude(self):
        payload = valid_payload(); payload.pop("magnitude"); payload.pop("magnitude_scale")
        status, body = prediction_response(payload); self.assertEqual(status, 200); self.assertTrue(body["input_quality"]["magnitude_missing"])

    def test_05_unknown_magnitude_group(self):
        status, body = prediction_response(valid_payload(magnitude_scale="Kph")); self.assertEqual(status, 200); self.assertTrue(body["input_quality"]["magnitude_group_unknown"])

    def test_06_hdi_future_missing(self):
        status, body = prediction_response(valid_payload(event_date="2026", date_granularity="year")); self.assertEqual(status, 200); self.assertTrue(body["input_quality"]["hdi_missing"])

    def test_07_month_precision(self):
        builder = FrozenFeatureBuilder(); frame, _ = builder.build(valid_payload(event_date="2023-07", date_granularity="month"))
        self.assertEqual(frame.iloc[0].event_month, 7); self.assertEqual(frame.iloc[0].date_imputed, 1)

    def test_08_year_precision(self):
        builder = FrozenFeatureBuilder(); frame, _ = builder.build(valid_payload(event_date="2023", date_granularity="year"))
        self.assertTrue(frame.iloc[0].month_missing); self.assertEqual(frame.columns.tolist(), FEATURES)

    def test_09_unknown_country(self):
        status, body = prediction_response(valid_payload(country_code="ZZZ")); self.assertEqual(status, 400); self.assertEqual(body["error"]["code"], "UNKNOWN_COUNTRY_CODE")

    def test_10_invalid_enum(self):
        status, body = prediction_response(valid_payload(disaster_type="Not a type")); self.assertEqual(status, 400); self.assertEqual(body["error"]["code"], "UNKNOWN_DISASTER_TYPE")

    def test_11_invalid_numeric(self):
        status, body = prediction_response(valid_payload(magnitude="not-number")); self.assertEqual(status, 400); self.assertEqual(body["error"]["code"], "INVALID_MAGNITUDE")

    def test_12_empty_request(self):
        status, body = prediction_response({}); self.assertEqual(status, 400); self.assertEqual(body["error"]["code"], "EMPTY_REQUEST")

    def test_13_probability_sum(self):
        _, body = prediction_response(valid_payload()); self.assertAlmostEqual(sum(body["prediction"]["probabilities"].values()), 1.0, places=12)

    def test_14_deterministic_repeated_request(self):
        first = prediction_response(valid_payload())[1]; second = prediction_response(valid_payload())[1]; self.assertEqual(first, second)

    def test_15_json_order_independent(self):
        payload = valid_payload(); reversed_payload = dict(reversed(list(payload.items())))
        self.assertEqual(prediction_response(payload)[1], prediction_response(reversed_payload)[1])

    def test_16_outcome_fields_rejected(self):
        status, body = prediction_response(valid_payload(total_deaths=1)); self.assertEqual(status, 400); self.assertEqual(body["error"]["code"], "UNKNOWN_FIELDS")

    def test_17_error_does_not_leak_internal_details(self):
        _, body = prediction_response(valid_payload(country_code="ZZZ")); text = json.dumps(body, ensure_ascii=False).lower()
        self.assertNotIn("traceback", text); self.assertNotIn("d:\\", text); self.assertNotIn("joblib", text)

    def test_18_model_feature_and_class_order(self):
        pipe = get_pipeline(); self.assertEqual(pipe.feature_names_in_.tolist(), FEATURES); self.assertEqual(pipe.named_steps["model"].classes_.tolist(), ["Low", "Moderate", "Severe"])


if __name__ == "__main__": unittest.main(verbosity=2)
