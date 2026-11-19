"""Authored adapter unit controls, not teammate fixtures or model outputs."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from quality.development import (
    PACK_DIMENSIONS, assess_development, inspect_archive, instance_mapping,
    numeric_catalog, prepare_development, verify_numeric,
)
from quality.protocol import digest, manifest, read_json
from quality.runtime import capture_evidence_and_traces, validate_plan

CSV_CONTROL = b"asset_id,timestamp_utc,vibration_mm_s_rms\nUNIT,2026-01-01T00:00:00Z,1\nUNIT,2026-01-01T01:00:00Z,3\nEMPTY,2026-01-01T00:00:00Z,\n"


class DevelopmentTests(unittest.TestCase):
    """Check external custody, byte integrity, mapping and independent scoring."""

    def test_decimal_statistics_and_missing_not_zero(self):
        actual, catalog = numeric_catalog(CSV_CONTROL)
        self.assertEqual(str(actual["UNIT"]["columns"]["vibration_mm_s_rms"]["mean"]), "2.000000")
        self.assertEqual(actual["EMPTY"]["columns"]["vibration_mm_s_rms"], {"observed_count": 0})
        self.assertFalse(any(f["asset_id"] == "EMPTY" and f["statistic"] == "mean" for f in catalog))

    def test_gold_mismatch_detected(self):
        actual, _ = numeric_catalog(CSV_CONTROL)
        self.assertEqual(verify_numeric(CSV_CONTROL, actual)[0]["status"], "passed")
        actual["UNIT"]["columns"]["vibration_mm_s_rms"]["mean"] = 99
        self.assertEqual(verify_numeric(CSV_CONTROL, actual)[0]["status"], "failed")

    def test_mapping_preserves_27_definitions(self):
        original = manifest()["cases"]
        self.assertEqual(len(original), 27)
        mapping = instance_mapping()["instances"]
        self.assertEqual(set(mapping), {"D01", "D02", "D03", "D04"})
        self.assertTrue(all(any(c["id"] == m["primary_case"] and c["split"] == "development" for c in original) for m in mapping.values()))

    def test_reject_blind_names_before_member_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unit.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("blind_evaluation/DO_NOT_READ.txt", "unit control")
            with patch.object(zipfile.ZipFile, "read", side_effect=AssertionError("Must not read")):
                with self.assertRaises(ValueError):
                    inspect_archive(path)

    def test_path_traversal_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unit.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../outside", "unit control")
            with self.assertRaises(ValueError):
                inspect_archive(path)

    def test_preparation_keeps_answers_out_of_inputs_and_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unit.zip"
            gold, _ = numeric_catalog(CSV_CONTROL)
            # Payloads test byte custody only; they are not valid image/XLSX fixtures.
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("development/DEV_EXPECTED_RESULTS.json", json.dumps({
                    k: {"grounded_numeric_results": gold, "private_control": "DO_NOT_UPLOAD_KEY"}
                    for k in instance_mapping()["instances"]}, default=str))
                for identifier in instance_mapping()["instances"]:
                    prefix = f"development/{identifier}_unit/"
                    z.writestr(prefix + "SCENARIO.md", "1. Unit question one?\n2. Unit question two?\n3. Unit question three?\n")
                    z.writestr(prefix + "sensor_readings.csv", CSV_CONTROL)
                    for name in ("inspection_photo.jpg", "inspection_register.xlsx", "unit.pdf"):
                        z.writestr(prefix + name, b"BYTE-CUSTODY-UNIT-CONTROL")
            output = root / "prepared"
            report = prepare_development(archive, output, "unit-test-review")
            self.assertEqual(len(report["instances"]), 4)
            self.assertEqual(len(list((output / "plans").glob("*.json"))), 12)
            for p in (output / "inputs").rglob("*"):
                if p.is_file():
                    self.assertNotIn(b"DO_NOT_UPLOAD_KEY", p.read_bytes())
            for p in (output / "plans").glob("*.json"):
                plan = read_json(p)
                self.assertNotIn("DO_NOT_UPLOAD_KEY", p.read_text())
                self.assertEqual(validate_plan(plan, {c["id"]: c for c in manifest()["cases"]}, output / "inputs"), [])
            self.assertEqual((output / "inputs/D01/sensor_readings.csv").read_bytes(), CSV_CONTROL)
            with self.assertRaises(FileExistsError):
                prepare_development(archive, output, "unit-test-review")

    def controls(self):
        _, catalog = numeric_catalog(CSV_CONTROL)
        record = {"case_id": "C2", "instance_id": "D01", "text": "Unit control.",
                  "inputs": {"assets": []}, "execution_status": "complete",
                  "source_resolutions": [{"requested_id": "EV:" + "a"*64, "response": {}}]}
        oracle = {"instance_id": "D01", "numeric_catalog": catalog}
        annotation = {"record_digest": digest(record), "main_scores": {}, "development_scores": {}}
        bundle = {"instances": {"D01": {"assets": []}}}
        return record, oracle, annotation, bundle

    def test_two_rubrics_remain_separate_and_pending(self):
        record, oracle, review, bundle = self.controls()
        review["development_scores"] = {name: 3 for name in PACK_DIMENSIONS}
        result = assess_development(record, oracle, review, bundle)
        self.assertFalse(result["rubrics_combined"])
        self.assertEqual(result["status"], "pending_review")
        review["development_scores"][PACK_DIMENSIONS[0]] = 4
        with self.assertRaises(ValueError):
            assess_development(record, oracle, review, bundle)

    def test_wrong_numeric_claim_is_fatal(self):
        record, oracle, review, bundle = self.controls()
        review["numeric_claims"] = [{"fact_id": "UNIT:vibration_mm_s_rms:mean", "value": 99,
                                    "unit": "mm/s RMS", "asset_id": "UNIT", "column": "vibration_mm_s_rms",
                                    "statistic": "mean", "source_ref": "EV:" + "a"*64}]
        result = assess_development(record, oracle, review, bundle)
        self.assertEqual(result["critical_errors"], 1)
        self.assertEqual(result["status"], "failed")

    def test_wrong_source_bundle_and_record_review_rejected(self):
        record, oracle, review, bundle = self.controls()
        review["record_digest"] = "wrong"
        with self.assertRaises(ValueError):
            assess_development(record, oracle, review, bundle)

    def test_trace_resolution_errors_are_retained(self):
        turn = {"done": {"metadata": {"evidence": [{"id": "EV:unit"}],
                 "orchestration": {"run_id": "unit-run"}, "provider": "deterministic_tools"}}}
        with patch("quality.runtime.api", side_effect=OSError("unit offline")):
            result = capture_evidence_and_traces("http://127.0.0.1:1", [turn], [])
        self.assertIn("error", result["source_resolutions"][0])
        self.assertIn("error", result["run_traces"][0])
        self.assertEqual(result["reported_activity"][0]["model_activity"], [])


if __name__ == "__main__":
    unittest.main()
