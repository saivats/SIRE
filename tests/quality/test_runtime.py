"""Test harness transport controls only; no SIRE or model inference is performed."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quality.protocol import manifest, read_json
from quality.runtime import (NoRedirect, capture, loopback, open_local, run_plan,
                             require_local_models, stream_chat, validate_plan)


class Response(io.BytesIO):
    """Explicit test-only SSE byte source, never passed to production."""

    headers = {"Content-Type": "text/event-stream"}


class RuntimeTests(unittest.TestCase):
    """Test safety boundaries and truthful execution-state recording."""

    def test_loopback_only(self):
        self.assertEqual(loopback("http://127.0.0.1:11434/"), "http://127.0.0.1:11434")
        for url in ("https://example.com", "http://localhost:8000", "http://127.0.0.1.evil", "http://user@127.0.0.1", "http://127.0.0.1?remote=x", "http://127.0.0.1/api"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                loopback(url)

    def test_redirect_and_absolute_path_rejected(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com")
        with self.assertRaises(ValueError):
            open_local("http://127.0.0.1:8000", "//example.com")

    def plan(self):
        return {"case_id": "A1", "variant": "unit-control", "repetition": 1, "assets": [],
                "requests": [{"content": "hi"}], "review_status": "independent_reviewed",
                "reviewer": "unit-test-only"}

    def cases(self):
        return {c["id"]: c for c in manifest()["cases"]}

    def test_valid_plan_and_missing_role(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(validate_plan(self.plan(), self.cases(), Path(directory)), [])
            plan = dict(self.plan(), case_id="B1")
            self.assertIn("pending_fixtures:bearing_photo", validate_plan(plan, self.cases(), Path(directory)))

    def test_holdout_and_manual_case_refused(self):
        for identifier in ("A3", "F1"):
            with self.assertRaises(ValueError):
                validate_plan(dict(self.plan(), case_id=identifier), self.cases(), Path("."))

    def test_answer_key_and_state_ids_not_in_request(self):
        for addition in ({"answer_key": {"fact": 1}}, {"requests": [{"content": "hi", "conversation_id": "production"}]},
                         {"assets": [{"role": "a", "path": "a", "sha256": "b", "expected": "secret"}]}):
            with self.assertRaises(ValueError):
                validate_plan(dict(self.plan(), **addition), self.cases(), Path("."))

    def test_pending_fixture_does_not_launch_server(self):
        with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.isolated_server") as server:
            output = Path(directory) / "run"
            record = run_plan(Path(directory), output, dict(self.plan(), case_id="B1"),
                              self.cases(), Path(directory), "http://127.0.0.1:11434")
            self.assertEqual(record["execution_status"], "pending")
            self.assertEqual(read_json(output / "record.json")["text"], "")
            server.assert_not_called()

    def test_stream_complete_and_first_answer(self):
        lines = [{"type": "tool", "status": "running"}, {"type": "delta", "text": "Unit control."},
                 {"type": "done", "status": "complete", "metadata": {}}]
        raw = "".join("data: " + json.dumps(x) + "\n\n" for x in lines).encode()
        with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.open_local", return_value=Response(raw)):
            path = Path(directory) / "events.jsonl"
            result = stream_chat("http://127.0.0.1:1", {}, path)
            self.assertEqual(result["text"], "Unit control.")
            self.assertEqual(result["execution_status"], "complete")
            self.assertIsNotNone(result["timing"]["first_useful_text_seconds"])
            self.assertIn("Unit control.", path.read_text())

    def test_partial_stream_and_error_not_repaired(self):
        raw = b'data: {"type":"delta","text":"Incomplete,"}\n\ndata: {"type":"error","code":"response_limit"}\n\n'
        with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.open_local", return_value=Response(raw)):
            result = stream_chat("http://127.0.0.1:1", {}, Path(directory) / "events")
            self.assertEqual(result["text"], "Incomplete,")
            self.assertEqual(result["execution_status"], "error")
            self.assertEqual(result["error"]["code"], "response_limit")

    def test_investigation_report_replaces_accumulated_text(self):
        events = [{"type": "delta", "text": "Facts. "},
                  {"type": "report", "content": "Facts. Investigation control."},
                  {"type": "done", "status": "complete"}]
        raw = "".join("data: " + json.dumps(e) + "\n\n" for e in events).encode()
        with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.open_local", return_value=Response(raw)):
            result = stream_chat("http://127.0.0.1:1", {}, Path(directory) / "events")
            self.assertEqual(result["text"], "Facts. Investigation control.")

    def test_missing_done_and_invalid_json(self):
        for raw, status in ((b'data: {"type":"delta","text":"Unit control"}\n', "incomplete_stream"),
                            (b'data: {bad\n', "error")):
            with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.open_local", return_value=Response(raw)):
                result = stream_chat("http://127.0.0.1:1", {}, Path(directory) / "events")
                self.assertEqual(result["execution_status"], status)

    def test_capture_unavailable_does_not_generate(self):
        with tempfile.TemporaryDirectory() as directory, patch("quality.runtime.api", side_effect=OSError("unavailable")) as requests, patch("quality.runtime.command", return_value={"unavailable": "unit-test"}):
            result = capture(Path(directory), "http://127.0.0.1:11434")
            self.assertFalse(result["inference_executed_by_capture"])
            self.assertEqual(result["tags"], {"unavailable": "OSError"})
            self.assertEqual([c.args[1] for c in requests.call_args_list], ["/api/version", "/api/tags", "/api/ps"])

    def test_model_identity_and_remote_models(self):
        runtime = {"config_and_prompt_files": {"config/app.yaml": {"text": "text_model: local-text\nvision_model: local-vision\n"}},
                   "tags": {"models": [{"name": "local-text", "digest": "text-control"}, {"name": "local-vision", "digest": "vision-control"}]},
                   "model_details": {"local-text": {"details": {}}, "local-vision": {"details": {}}}}
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(len(require_local_models(runtime, self.plan())), 2)
            runtime["model_details"]["local-text"]["remote_host"] = "remote.example"
            with self.assertRaises(ValueError):
                require_local_models(runtime, self.plan())

    def test_audio_upload_not_mistaken_for_isolated_text_run(self):
        plan = dict(self.plan(), assets=[{"role": "audio", "path": "example.wav", "sha256": "unit-control"}])
        with self.assertRaises(ValueError):
            validate_plan(plan, self.cases(), Path("."))

    def test_cli_inventory_and_holdout_prepare(self):
        script = Path(__file__).resolve().parents[2] / "scripts/eval_quality.py"
        result = subprocess.run([sys.executable, "-B", str(script), "inventory"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("27 definitions; 18 development; 9 holdout", result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", str(script), "prepare", "A3", "--out", str(Path(directory) / "holdout.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((Path(directory) / "holdout.json").exists())


if __name__ == "__main__":
    unittest.main()
