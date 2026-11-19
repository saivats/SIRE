"""Direct merged-backend smoke regressions; explicit unit controls, no inference.

These complement, rather than replace, the existing pytest backend suite.
All database writes use TemporaryDirectory. The one proposal is a mocked unit
transport response and must never be reported as a Qwen result.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

try:
    from app.chat.conversation import fast_route, history_turns
    from app.core.errors import SireError
    from app.evidence.context import restore_text
    from app.evidence.ledger import Ledger
    from app.evidence.verification import Claim, screen_numeric_prose, verify_claim
    from app.investigation import engine
    from app.investigation.narrative import issues
    from app.investigation.schemas import Case, Hypothesis, Proposal
    from app.knowledge.case_memory import _comparison_details
    from app.orchestration.workspace import _render_similar_cases
    from app.storage.database import Store
    IMPORT_ERROR = None
except ImportError as exc:
    IMPORT_ERROR = str(exc)


@unittest.skipIf(IMPORT_ERROR is not None, "Backend dependencies unavailable: " + str(IMPORT_ERROR))
class MergedBackendTests(unittest.TestCase):
    """Exercise the actual imported production functions after the merge."""

    def test_signed_percentage_and_window(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Store(Path(directory) / "unit.sqlite3"))
            rows = [{"asset_id": "UNIT-CONTROL", "channel": "pressure", "unit": "bar",
                     "quality": "good", "observed_at": f"2026-01-{i+1:02d}T00:00:00+00:00",
                     "value": 1.0 if i < 24 else 2.0} for i in range(30)]
            source = ledger.add("real_uploaded", "Authored unit control", {"rows": rows},
                                {"test_only": True}, unit="bar", available_at=rows[-1]["observed_at"],
                                method="uploaded_descriptive_first24_recent6_v1")
            claim = Claim(category="derived_statistic", source_ids=[source.id], value=100,
                          unit="%", statistic="percent_delta", asset_id="UNIT-CONTROL",
                          channel="pressure", window_start=rows[0]["observed_at"],
                          window_end=rows[-1]["observed_at"])
            self.assertEqual(verify_claim(claim, ledger).status, "verified_exact")
            self.assertEqual(verify_claim(claim.model_copy(update={"value": -100}), ledger).status, "contradicted")
            self.assertEqual(screen_numeric_prose(f"Pressure increased by 100% [{source.id}].", ledger)[0]["status"], "verified_exact")
            with self.assertRaises(SireError):
                screen_numeric_prose(f"Pressure decreased by 100% [{source.id}].", ledger)

    def test_narrative_fragments_and_control(self):
        for text in ("Progressive degradation of潤", "Progressive wear due to", "Wear increases,"):
            self.assertTrue(issues(text))
        self.assertEqual(issues("Wear may increase friction."), [])

    def test_rejection_preserves_original_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "unit.sqlite3")
            cid = store.create_conversation()["id"]
            candidate = Hypothesis(id="unit-control", mechanism="Progressive degradation due to",
                                   assumptions=[], expected_signs=[], supporting_evidence_ids=[],
                                   contradicting_evidence_ids=[], missing_tests=[])
            proposal = Proposal(hypotheses=[candidate], follow_up_queries=[], unresolved=[])
            with patch.object(engine.ollama, "generate_async", AsyncMock(return_value=proposal)):
                result = asyncio.run(engine.investigate(store, Case(question="Authored unit control",
                    conversation_id=cid, evidence=[]), asyncio.Event()))
            self.assertEqual(result.hypotheses, [])
            rejected = result.hypothesis_revisions[0]["quality_rejections"][0]
            self.assertEqual(rejected["candidate"]["mechanism"], candidate.mechanism)
            self.assertTrue(rejected["reasons"])

    def test_comparison_detail_and_rendering(self):
        def case(asset, value):
            return {"asset_id": asset, "scenario_id": "unit-control", "as_of": "2026-01-01T00:00:00Z",
                    "summaries": [{"asset_id": asset, "channels": {"pressure": {
                        "available": True, "recent_mean": value, "delta": 1, "unit": "bar"}}}]}
        details = _comparison_details(case("UNIT-A", 2), case("UNIT-B", 1))
        self.assertEqual(details["differing_readings"][0]["selected_value"], 2)
        text = "\n".join(_render_similar_cases([dict(details, case_id="UNIT-PRIOR", asset_id="UNIT-B",
            confirmation_status="provisional", overlap_score=0.5, shared_mechanisms=["unit mechanism"],
            different_mechanisms=[], evidence_ids=["EV:" + "a" * 64], evidence_strength="provisional_only",
            retrieval_reason="Unit control overlap")]))
        for token in ("UNIT-PRIOR", "UNIT-A", "UNIT-B", "selected 2 vs prior 1 bar", "provisional_only"):
            self.assertIn(token, text)
        self.assertIn("No earlier time-eligible", _render_similar_cases([])[0])

    def test_evidence_aliases(self):
        with self.assertRaises(SireError):
            restore_text("Claim [E1]", {})
        source = "EV:" + "a" * 64
        self.assertEqual(restore_text("Claim [E1]", {"E1": source}), "Claim [" + source + "]")

    def test_conversation_excludes_failed_history(self):
        history = [{"role": "user", "content": "Question"},
                   {"role": "assistant", "content": "Failed claim [E1]", "status": "error", "metadata": {}},
                   {"role": "user", "content": "Hello"},
                   {"role": "assistant", "content": "Hello [E2]", "status": "complete", "metadata": {}}]
        turns = history_turns(history)
        self.assertEqual(len(turns), 2)
        self.assertNotIn("E2", turns[-1]["content"])
        self.assertEqual(fast_route("hi"), "social")
        self.assertEqual(fast_route("What is SIRE?"), "overview")


if __name__ == "__main__":
    unittest.main()
