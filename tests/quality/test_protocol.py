"""Protocol regressions use explicitly authored evaluation records, not inference."""

import tempfile
import unittest
from pathlib import Path

from quality.checks import DIMENSIONS
from quality.protocol import (compare, digest, file_digest, fixture_status, manifest,
                              read_json, score_record, write_new)


class ProtocolTests(unittest.TestCase):
    """Coverage, provenance, missing fixtures and scoring gates."""

    def test_manifest_and_holdout_boundary(self):
        cases = manifest()["cases"]
        self.assertEqual(len(cases), 27)
        self.assertEqual(sum(c["split"] == "development" for c in cases), 18)
        self.assertEqual(sum(c["split"] == "holdout" for c in cases), 9)
        self.assertFalse(any(c["status"] == "passed" for c in cases))
        for case in cases:
            if case["split"] == "holdout":
                self.assertNotIn("requests", case)
                self.assertNotIn("answer_key", case)

    def test_eight_rubric_dimensions_and_anchors(self):
        rubric = read_json(Path(__file__).parent / "rubric.json")
        self.assertEqual(set(rubric["dimensions"]), set(DIMENSIONS))
        for dimension in rubric["dimensions"].values():
            self.assertEqual(set(dimension), set("01234"))

    def test_missing_fixture_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"assets": [{"path": "absent.csv", "sha256": "a" * 64}]}
            self.assertEqual(fixture_status(plan, Path(directory)),
                             ["pending_fixtures:absent.csv", "pending_independent_review"])

    def test_fixture_path_escape_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unit.txt").write_text("authored unit control")
            plan = {"assets": [{"path": "unit.txt", "sha256": file_digest(root / "unit.txt")}],
                    "review_status": "independent_reviewed", "reviewer": "unit-test"}
            self.assertEqual(fixture_status(plan, root), [])
            plan["assets"][0]["sha256"] = "bad"
            self.assertTrue(fixture_status(plan, root)[0].startswith("fixture_hash_mismatch"))
            plan["assets"][0]["path"] = "../private.txt"
            self.assertTrue(fixture_status(plan, root)[0].startswith("fixture_outside_root"))

    def record_key(self):
        record = {"case_id": "A1", "input_digest": "unit-control", "text": "Hello.",
                  "execution_status": "complete", "variant": "default", "repetition": 1}
        key = {"case_id": "A1", "input_digest": "unit-control", "dimensions": ["clarity"],
               "review_status": "independent_reviewed", "reviewer": "independent-unit-control"}
        return record, key

    def test_no_auto_pass_or_fabricated_grades(self):
        record, key = self.record_key()
        result = score_record(record, key)
        self.assertEqual(result["status"], "pending_review")
        self.assertIsNone(result["ordinal_mean"])

    def test_critical_error_overrides_fluent_score(self):
        record, key = self.record_key()
        record["text"] = "Claim [E1]"
        annotation = {"record_digest": digest(record), "scores": {"clarity": 4},
                      "all_claims_reviewed": True, "reviewer": "unit-control"}
        result = score_record(record, key, annotation)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["critical_errors"], 1)
        self.assertEqual(result["ordinal_mean"], 4)

    def test_reviewed_pass_requires_bound_review(self):
        record, key = self.record_key()
        annotation = {"record_digest": digest(record), "scores": {"clarity": 3},
                      "all_claims_reviewed": True, "reviewer": "unit-control"}
        self.assertEqual(score_record(record, key, annotation)["status"], "reviewed_pass")
        annotation["record_digest"] = "other"
        with self.assertRaises(ValueError):
            score_record(record, key, annotation)

    def test_wrong_key_and_invalid_grades(self):
        record, key = self.record_key()
        with self.assertRaises(ValueError):
            score_record(record, dict(key, input_digest="other"))
        for grade in (-1, 5, True, 3.5, None):
            with self.assertRaises(ValueError):
                score_record(record, key, {"record_digest": digest(record), "scores": {"clarity": grade}})

    def test_incomplete_execution_and_multiturn_review(self):
        record, key = self.record_key()
        record.update(execution_status="error", turns=[{}, {}])
        result = score_record(record, key)
        self.assertIn("execution_not_complete", result["pending"])
        self.assertIn("pending_prior_turn_review", result["pending"])

    def test_before_after_pairing_and_latency(self):
        before, _ = self.record_key()
        after = dict(before, text="Another authored control")
        before["timing"] = {"full_response_seconds": 2}
        after["timing"] = {"full_response_seconds": 3}
        result = compare(before, after)
        self.assertEqual(result["timing_delta_seconds"]["full_response_seconds"], 1)
        self.assertIsNone(result["timing_delta_seconds"]["first_useful_text_seconds"])
        self.assertTrue(result["review_required"])
        with self.assertRaises(ValueError):
            compare(before, dict(after, input_digest="different"))

    def test_score_comparison_bound_to_records(self):
        before, key = self.record_key()
        after = dict(before, text="Second control.")
        s1, s2 = score_record(before, key), score_record(after, key)
        self.assertEqual(compare(before, after, s1, s2)["quality_comparison"]["critical_error_delta"], 0)
        with self.assertRaises(ValueError):
            compare(before, after, s2, s1)

    def test_write_once_and_strict_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            write_new(path, {"unit": True})
            self.assertEqual(read_json(path), {"unit": True})
            with self.assertRaises(FileExistsError):
                write_new(path, {"replacement": True})
            for raw in ('{"x":NaN}', '{"x":1,"x":2}'):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    read_json(path)


if __name__ == "__main__":
    unittest.main()
