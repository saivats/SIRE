"""Regression contracts for uploaded industrial rows and their source-verified statistics."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.errors import SireError
from app.evidence.measurements import parse


class MeasurementContracts(unittest.TestCase):
    def test_unknown_header_duplicate_and_forged_locator(self):
        self.assertIsNone(parse(b"asset_id,timestamp_utc,temperature_guess\na,t,3", ".csv"))
        head = "asset_id,timestamp_utc,vibration_mm_s_rms,"
        for second in ("vibration_mm_s_rms", "vibration_mm_s"):
            with self.subTest(second=second), self.assertRaises(SireError):
                parse((head + second + "\na,2025-01-01T00:00Z,4,5").encode(), ".csv")
        rows = parse(b"asset_id,timestamp,channel,value,unit,source_row,source_field\na,2025-01-01T00:00Z,x,1,bar,100,other", ".csv")
        self.assertEqual((rows[0]["source_row"], rows[0]["source_field"]), (1, "value"))

    def test_source_verified_series_and_window_statistics(self):
        csv = b"""asset_id,timestamp_utc,pressure_drop_bar,surface_temp_c,vibration_mm_s_rms
A,2025-01-01T02:00Z,2,22,
B,2025-01-01T00:00Z,0,18,1
A,2025-01-01T00:00Z,4,20,
A,2025-01-01T01:00Z,3,21,
"""
        with TemporaryDirectory() as tmp, TestClient(create_app(Path(tmp), probe_model=False)) as client:
            cid = client.post("/api/v1/conversations", json={}).json()["id"]
            upload = client.post("/api/v1/attachments", data={"conversation_id": cid}, files={"file": ("test.csv", csv)})
            upload.raise_for_status()
            aid = upload.json()["id"]
            reply = client.post("/api/v1/intelligence/execute", json={"tool_id": "measurements.profile", "arguments": {"attachment_id": aid, "conversation_id": cid}})
            reply.raise_for_status()
            profile = reply.json()["result"]
            groups = {(g["asset_id"], g["channel"]): g for g in profile["groups"]}
            self.assertNotIn(("A", "vibration"), groups)
            self.assertEqual(profile["missing_cells"], [{"asset_id": "A", "source_field": "vibration_mm_s_rms", "blank_count": 3}])
            self.assertIsNone(groups["B", "pressure_drop"]["endpoint_percent_delta"])
            g = groups["A", "pressure_drop"]
            self.assertEqual((g["first_value"], g["last_value"], g["endpoint_delta"], g["endpoint_percent_delta"], g["full_mean"], g["delta"]), (4, 2, -2, -50, 3, 0))
            self.assertEqual((g["first_sample"]["source_row"], g["last_sample"]["source_row"]), (3, 1))
            claims = [
                {"category": "derived_statistic", "source_ids": [g["evidence_id"]], "asset_id": "A", "channel": "pressure_drop", "value": value, "unit": unit, "statistic": statistic}
                for statistic, value, unit in [("endpoint_percent_delta", -50, "%"), ("endpoint_percent_delta", -50, "bar"), ("full_mean", 3, "bar"), ("percent_delta", -50, "%")]
            ]
            result = client.post("/api/v1/evidence/verify", json={"conversation_id": cid, "claims": claims})
            result.raise_for_status()
            self.assertEqual([c["status"] for c in result.json()["verifications"]], ["verified_exact", "contradicted", "verified_exact", "contradicted"])

    def test_narrated_quantities_require_the_cited_asset(self):
        from app.evidence.ledger import Ledger
        from app.evidence.verification import screen_numeric_prose
        from app.storage.database import Store

        with TemporaryDirectory() as tmp:
            ledger = Ledger(Store(Path(tmp) / "test.sqlite3"))
            rows = [
                {"asset_id": "PUMP-011", "channel": "pressure", "value": v,
                 "observed_at": f"2025-01-01T0{i}:00:00+00:00", "unit": "bar"}
                for i, v in enumerate([4, 3, 2])
            ]
            record = ledger.add("real_uploaded", "Test pressure", {"rows": rows},
                                {"asset_id": "PUMP-011", "channel": "pressure"}, unit="bar")
            cite = f"[{record.id}]"
            for text in ("PUMP-011 full-series mean 3 bar", "PUMP-011 first-to-last decrease 50%"):
                self.assertEqual(screen_numeric_prose(f"{text} {cite}", ledger)[0]["status"], "verified_exact")
            with self.assertRaises(SireError):
                screen_numeric_prose(f"PUMP-012 full-series mean 3 bar {cite}", ledger)
