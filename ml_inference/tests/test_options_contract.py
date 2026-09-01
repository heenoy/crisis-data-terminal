from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from ml_inference.feature_builder import FrozenFeatureBuilder
from ml_inference.service import options_http_response, options_response


class OptionsContractTests(unittest.TestCase):
    def test_normal_options_are_nonempty(self):
        body = options_response()
        self.assertTrue(body["success"])
        self.assertGreater(len(body["countries"]), 200)
        self.assertGreater(len(body["disaster_types"]), 1)

    def test_country_codes_match_feature_builder_contract(self):
        body = options_response()
        builder = FrozenFeatureBuilder()
        self.assertEqual({item["code"] for item in body["countries"]}, set(builder.country_region))

    def test_magnitude_references_come_from_frozen_group_statistics(self):
        body = options_response()
        earthquake = next(item for item in body["magnitude_groups"] if item["group_key"] == "Earthquake | Moment Magnitude")
        self.assertEqual(earthquake["disaster_type"], "Earthquake")
        self.assertEqual(earthquake["unit_label"], "震级")
        self.assertEqual([item["value"] for item in earthquake["references"]], [5.8, 6.4, 7.0])
        drought = next(item for item in body["magnitude_groups"] if item["group_key"] == "Drought | Km2")
        self.assertFalse(drought["eligible"])
        self.assertEqual(drought["references"], [])

    def test_empty_country_list_is_rejected(self):
        with patch("ml_inference.service.BUILDER.public_options", return_value={"countries": [], "disaster_types": [{"type": "Flood", "subtypes": []}], "magnitude_scales": []}):
            status, body = options_http_response()
        self.assertEqual(status, 500)
        self.assertEqual(body["error"]["code"], "OPTIONS_UNAVAILABLE")

    def test_missing_frozen_asset_is_sanitized(self):
        with patch("ml_inference.service.BUILDER.public_options", side_effect=FileNotFoundError("D:/private/frozen.csv")):
            status, body = options_http_response()
        self.assertEqual(status, 500)
        self.assertNotIn("private", str(body).lower())
        self.assertNotIn("traceback", str(body).lower())

    def test_invalid_structure_is_rejected(self):
        with patch("ml_inference.service.BUILDER.public_options", return_value={"countries": "bad", "disaster_types": [], "magnitude_scales": []}):
            status, body = options_http_response()
        self.assertEqual(status, 500)
        self.assertFalse(body["success"])

    def test_repeated_requests_are_stable(self):
        self.assertEqual(options_response(), options_response())

    def test_options_do_not_import_training_modules(self):
        options_response()
        self.assertFalse(any(name.endswith("train_final_t2") or name.endswith("run_t0_t3_random_forest") for name in sys.modules))


if __name__ == "__main__":
    unittest.main(verbosity=2)
