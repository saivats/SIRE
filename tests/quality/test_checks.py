"""Authored evaluator unit payloads, never recorded SIRE/model outputs."""

import unittest

from quality.checks import (
    check_answer, claim_checks, mechanism_checks, numeric_equal, origin_checks,
    schema_checks, source_checks,
)


class ChecksTests(unittest.TestCase):
    """Positive and negative controls for independent quality checks."""

    def test_unknown_alias(self):
        self.assertEqual(source_checks("Claim [E1]", {})[0]["code"], "invalid_source")

    def test_fabricated_canonical(self):
        self.assertTrue(source_checks("Claim [EV:" + "a" * 64 + "]", {}))

    def test_malformed_and_pseudo_citations(self):
        for text in ("[EV:not-a-valid-id]", "[source limitations]", "[E1-E2]", "[E1"):
            with self.subTest(text=text):
                self.assertTrue(source_checks(text, {}))

    def test_valid_alias_list(self):
        self.assertEqual(source_checks("[E1, E2]", {"allowed_refs": ["E1", "E2"]}), [])
        self.assertEqual(source_checks("[E1 ]", {"allowed_refs": ["E1"]}), [])

    def test_required_reference(self):
        self.assertEqual(source_checks("No citation", {"required_refs": ["E1"]})[0]["code"], "missing_source")

    def test_ordinary_brackets(self):
        self.assertEqual(source_checks("hello [optional note]", {}), [])

    def test_bare_ev(self):
        self.assertTrue(source_checks("Source EV:fake", {}))

    def test_finite_decimals(self):
        for bad in ("NaN", "Infinity", True, "none"):
            self.assertFalse(numeric_equal(bad, 1))
        self.assertTrue(numeric_equal("0.300", "0.3"))
        self.assertFalse(numeric_equal("0.301", "0.3"))
        self.assertTrue(numeric_equal("0.301", "0.3", "0.001"))
        self.assertFalse(numeric_equal(1, 1, -1))

    def test_numeric_rule_values_and_units(self):
        key = {"numeric_rules": [{"id": "unit-control", "pattern": r"Current: (?P<value>[0-9.]+) (?P<unit>\w+)", "value": 12, "unit": "A"}]}
        self.assertEqual(check_answer("Current: 12 A", key), [])
        codes = {f["code"] for f in check_answer("Current: 13 dB", key)}
        self.assertEqual(codes, {"wrong_numeric_value", "wrong_numeric_unit"})
        self.assertTrue(check_answer("Current unavailable", key))

    def fact_key(self):
        return {"allowed_refs": ["E1"], "as_of": "2026-10-04T04:00:00Z",
                "required_fact_ids": ["point"], "facts": [{"id": "point", "value": "2",
                "unit": "mm/s RMS", "asset_id": "PUMP-001", "statistic": "point",
                "observed_at": "2026-10-04T03:00:00Z", "locator": "row:1", "source_refs": ["E1"]}]}

    def claim(self):
        return {"fact_id": "point", "value": "2", "unit": "mm/s RMS",
                "asset_id": "PUMP-001", "statistic": "point", "observed_at": "2026-10-04T03:00:00Z",
                "locator": "row:1", "source_refs": ["E1"]}

    def test_correct_bound_claim(self):
        self.assertEqual(claim_checks([self.claim()], self.fact_key()), [])

    def test_asset_unit_statistic_value_locator_mismatch(self):
        for field, bad in (("asset_id", "PUMP-008"), ("unit", "A"), ("statistic", "mean"), ("value", 4), ("locator", "row:2")):
            with self.subTest(field=field):
                claim = self.claim()
                claim[field] = bad
                self.assertIn("claim_" + field, [f["code"] for f in claim_checks([claim], self.fact_key())])

    def test_future_observation_and_availability(self):
        for field in ("observed_at", "available_at"):
            claim = self.claim()
            claim[field] = "2026-10-05T00:00:00Z"
            self.assertIn("future_evidence", [f["code"] for f in claim_checks([claim], self.fact_key())])

    def test_naive_time_rejected(self):
        claim = self.claim()
        claim["observed_at"] = "2026-10-04T03:00:00"
        self.assertIn("invalid_timestamp", [f["code"] for f in claim_checks([claim], self.fact_key())])

    def test_missing_and_unsupported_claim(self):
        self.assertEqual(claim_checks([], self.fact_key())[0]["code"], "missing_fact")
        self.assertIn("unsupported_fact", [f["code"] for f in claim_checks([{"fact_id": "invented"}], self.fact_key())])

    def test_missing_claim_sources(self):
        claim = self.claim()
        claim["source_refs"] = []
        self.assertIn("claim_sources", [f["code"] for f in claim_checks([claim], self.fact_key())])

    def test_text_date_and_channel_claims(self):
        key = {"allowed_refs": ["E1"], "facts": [{"id": "date", "value_type": "text", "value": "2026-10-04", "channel": "maintenance"}]}
        claim = {"fact_id": "date", "value": "2026-10-04", "channel": "maintenance", "source_refs": ["E1"]}
        self.assertEqual(claim_checks([claim], key), [])
        claim["value"] = "2026-10-05"
        claim["channel"] = "vibration"
        self.assertEqual({f["code"] for f in claim_checks([claim], key)}, {"claim_value", "claim_channel"})

    def test_historical_fragment(self):
        self.assertTrue(mechanism_checks("progressive degradation of潤"))
        self.assertTrue(mechanism_checks("Wear increases,"))
        self.assertTrue(mechanism_checks("Wear because"))
        self.assertTrue(mechanism_checks("Wear (possible"))
        self.assertEqual(mechanism_checks("Wear may increase friction."), [])

    def test_origin_duplicates_not_independent(self):
        supports = [{"origin_group": "one-image"}] * 4
        self.assertEqual(origin_checks(supports, 1), [])
        self.assertEqual(origin_checks(supports, 4)[0]["code"], "duplicate_support")
        self.assertEqual(origin_checks([{}], 1)[0]["code"], "unknown_origin")

    def test_independent_origins_allowed(self):
        self.assertEqual(origin_checks([{"origin_group": "a"}, {"origin_group": "b"}], 2), [])

    def test_structured_output(self):
        schema = {"type": "object", "required": ["status"], "additionalProperties": False,
                  "properties": {"status": {"type": "string", "enum": ["unknown"]}}}
        self.assertEqual(schema_checks({"status": "unknown"}, schema), [])
        for value in ({}, {"status": "confirmed"}, {"status": "unknown", "invented": 1}, []):
            self.assertTrue(schema_checks(value, schema))

    def test_strict_schema_types_lengths_and_unsupported(self):
        self.assertTrue(schema_checks(True, {"type": "integer"}))
        self.assertTrue(schema_checks(float("nan"), {"type": "number"}))
        self.assertTrue(schema_checks([], {"type": "array", "minItems": 1}))
        self.assertTrue(schema_checks([1], {"type": "array", "items": {"type": "string"}}))
        with self.assertRaises(ValueError):
            schema_checks("a", {"type": "string", "pattern": "a"})
        with self.assertRaises(ValueError):
            schema_checks({}, {"type": "object", "additionalProperties": True})

    def test_invalid_json_preserved(self):
        raw = '{"status":'
        self.assertEqual(check_answer(raw, {"schema": {"type": "object"}})[0]["code"], "invalid_json")
        self.assertEqual(raw, '{"status":')

    def test_duplicate_fields_and_nonfinite_json(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            self.assertEqual(check_answer(raw, {"schema": {"type": "object"}})[0]["code"], "invalid_json")

    def test_fragment_found_without_annotation(self):
        self.assertIn("known_truncated_mechanism", [f["code"] for f in check_answer("progressive degradation of潤", {})])

    def test_confidence_and_prohibited_claim(self):
        for text in ("Confidence: 90%", "90% confident", "Probability of 90%"):
            self.assertIn("unsupported_confidence", [f["code"] for f in check_answer(text, {})])
        self.assertEqual(check_answer("Tentative; no probability available.", {}), [])
        self.assertTrue(check_answer("Confirmed failure", {"forbidden_patterns": ["confirmed failure"]}))


if __name__ == "__main__":
    unittest.main()
