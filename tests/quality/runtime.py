"""Loopback-only runtime capture and original-SIRE chat execution.

No model downloads, model substitution, production imports or answer keys here.
The child runs the unmodified app.api.main:app with a new SIRE_STATE_DIR.
"""

import contextlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Iterator

from .protocol import digest, file_digest, fixture_status, write_new

PROMPT_FILES = (
    "config/app.yaml", "config/conversation.yaml", "config/hypotheses.yaml",
    "config/capabilities.yaml", "config/retrieval.yaml", "config/media.yaml",
    "app/core/prompt_policy.py",
    "app/chat/service.py", "app/providers/adapter.py", "app/providers/ollama.py",
    "app/investigation/engine.py", "app/evidence/context.py",
    "app/orchestration/tools.py", "app/evidence/verification.py",
    "app/investigation/narrative.py", "app/knowledge/case_memory.py",
    "app/orchestration/workspace.py", "app/evidence/measurements.py",
)
REQUEST_FIELDS = {"content", "mode", "voice_response", "linked_asset", "model"}
UPLOAD_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".csv", ".pdf", ".txt", ".md", ".json", ".xlsx"}


def loopback(url: str) -> str:
    """Refuse hosted endpoints, userinfo, query strings and ambiguous hosts."""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Only explicit HTTP loopback base URLs are allowed")
    return url.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never let a local endpoint redirect private requests elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Reject all redirects."""
        raise ValueError("HTTP redirects are disabled")


def open_local(base: str, path: str, data: bytes | None = None,
               content_type: str = "application/json", timeout: float = 360):
    """Open a local request without consulting proxy environment variables."""
    base = loopback(base)
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Relative API path required")
    request = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": content_type})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    return opener.open(request, timeout=timeout)


def api(base: str, path: str, body: dict | None = None, timeout: float = 10) -> dict:
    """Read JSON from the explicit local endpoint."""
    data = json.dumps(body, allow_nan=False).encode() if body is not None else None
    with open_local(base, path, data, timeout=timeout) as response:
        return json.load(response)


def command(args: list[str], root: Path) -> dict:
    """Record bounded, read-only inventory commands with explicit failures."""
    try:
        result = subprocess.run(args, cwd=root, capture_output=True, text=True,
                                timeout=15, check=False)
        return {"returncode": result.returncode, "stdout": result.stdout,
                "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"unavailable": type(exc).__name__}


def capture(root: Path, ollama_url: str) -> dict:
    """Capture installed tags/digests, parameter defaults and checked-in prompts."""
    base = loopback(ollama_url)
    result = {"schema_version": 1, "python": sys.version, "platform": platform.platform(),
              "git": command(["git", "rev-parse", "HEAD"], root),
              "git_status": command(["git", "status", "--porcelain"], root),
              "config_and_prompt_files": {}, "ollama_url": base,
              "environment_overrides": {k: os.environ[k] for k in (
                  "SIRE_TEXT_MODEL", "SIRE_VISION_MODEL", "OLLAMA_NUM_PARALLEL",
                  "OLLAMA_MAX_LOADED_MODELS", "CUDA_VISIBLE_DEVICES") if k in os.environ},
              "gpu": command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                              "--format=csv,noheader"], root),
              "inference_executed_by_capture": False}
    for name in PROMPT_FILES:
        path = root / name
        result["config_and_prompt_files"][name] = (
            {"sha256": file_digest(path), "text": path.read_text(encoding="utf-8")}
            if path.is_file() else {"unavailable": True})
    for endpoint in ("version", "tags", "ps"):
        try:
            result[endpoint] = api(base, "/api/" + endpoint)
        except (OSError, ValueError) as exc:
            result[endpoint] = {"unavailable": type(exc).__name__}
    result["model_details"] = {}
    for model in result.get("tags", {}).get("models", []):
        name = model.get("name") or model.get("model")
        try:
            shown = api(base, "/api/show", {"model": name}, timeout=30)
            result["model_details"][name] = {
                k: shown[k] for k in ("parameters", "template", "details", "model_info", "remote_host", "remote_model") if k in shown}
        except (OSError, ValueError) as exc:
            result["model_details"][name] = {"unavailable": type(exc).__name__}
    return result


def require_local_models(runtime: dict, plan: dict) -> dict:
    """Require actual installed local model identities before allowing any run."""
    config = runtime["config_and_prompt_files"].get("config/app.yaml", {}).get("text", "")
    names = []
    for key, env in (("text_model", "SIRE_TEXT_MODEL"), ("vision_model", "SIRE_VISION_MODEL")):
        match = re.search(r"(?m)^" + key + r":\s*['\"]?([^\s'\"#]+)", config)
        name = os.environ.get(env) or (match.group(1) if match else None)
        if not name:
            raise ValueError("Cannot establish configured model identity: " + key)
        names.append(name)
    names.extend(r["model"] for r in plan["requests"] if r.get("model"))
    installed = {m.get("name", m.get("model")): m for m in runtime.get("tags", {}).get("models", [])}
    selected = {}
    for name in names:
        details = runtime["model_details"].get(name, {})
        if (name not in installed or not installed[name].get("digest") or not details
                or details.get("unavailable") or details.get("remote_host") or details.get("remote_model")
                or "cloud" in name.lower()):
            raise ValueError("Required installed local model not verified: " + name)
        selected[name] = installed[name]["digest"]
    return selected


@contextlib.contextmanager
def isolated_server(root: Path, run_dir: Path, ollama_url: str) -> Iterator[str]:
    """Own an isolated child; never attach to an existing production server."""
    if not (root / "app/api/main.py").is_file():
        raise ValueError("A complete SIRE checkout is required for live execution")
    if "uvicorn" not in sys.modules:
        import importlib.util
        if importlib.util.find_spec("uvicorn") is None:
            raise ValueError("Use SIRE's existing Python environment with uvicorn")
    state = run_dir / "state"
    state.mkdir(exist_ok=False)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, SIRE_STATE_DIR=str(state.resolve()),
               OLLAMA_BASE_URL=loopback(ollama_url), OLLAMA_NO_CLOUD="1",
               PYTHONDONTWRITEBYTECODE="1")
    with (run_dir / "server.log").open("x", encoding="utf-8") as log:
        child = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.api.main:app",
                                  "--host", "127.0.0.1", "--port", str(port)],
                                 cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            started = time.monotonic()
            while time.monotonic() - started < 180:
                if child.poll() is not None:
                    raise RuntimeError("SIRE startup failed; inspect preserved server.log")
                try:
                    api(base, "/api/v1/health", timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("SIRE startup timed out; server.log preserved")
            # Require our child's bind confirmation, not just another server's health.
            if child.poll() is not None or f"Uvicorn running on {base}" not in (run_dir / "server.log").read_text(encoding="utf-8"):
                raise RuntimeError("Evaluation server binding not verified")
            yield base
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)


def upload(base: str, conversation_id: str, path: Path) -> dict:
    """Upload an explicitly reviewed fixture through SIRE's original intake API."""
    boundary = "sire-quality-" + uuid.uuid4().hex
    name = path.name
    if any(c in name for c in ('"', '\r', '\n')):
        raise ValueError("Unsafe multipart filename")
    if path.stat().st_size > 10000000:
        raise ValueError("Fixture exceeds the approved application's upload limit")
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="conversation_id"\r\n\r\n'
            f'{conversation_id}\r\n--{boundary}\r\nContent-Disposition: form-data; '
            f'name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
    data += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    with open_local(base, "/api/v1/attachments", data,
                    "multipart/form-data; boundary=" + boundary) as response:
        return json.load(response)


def stream_chat(base: str, body: dict, event_path: Path) -> dict:
    """Preserve each raw SSE line and monotonic receipt time, including errors."""
    started = time.perf_counter()
    text, events, first, done, error = "", [], None, None, None
    with event_path.open("x", encoding="utf-8") as output:
        try:
            with open_local(base, "/api/v1/chat/message", json.dumps(body).encode()) as response:
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    raise ValueError("Expected foreground SSE response")
                for raw in response:
                    elapsed = time.perf_counter() - started
                    line = raw.decode("utf-8")
                    output.write(json.dumps({"seconds": elapsed, "raw": line}, ensure_ascii=False) + "\n")
                    output.flush()
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[5:].strip())
                    events.append(event)
                    if event.get("type") == "delta" and event.get("text"):
                        if first is None and event["text"].strip():
                            first = elapsed
                        text += event["text"]
                    if event.get("type") == "report" and isinstance(event.get("content"), str):
                        # SIRE report.content is the accumulated full answer, not a delta.
                        if first is None and event["content"].strip():
                            first = elapsed
                        text = event["content"]
                    if event.get("type") == "done":
                        done = event
                    if event.get("type") == "error":
                        error = event
        except urllib.error.HTTPError as exc:
            error = {"http_status": exc.code, "body": exc.read().decode("utf-8", errors="replace")}
        except (OSError, ValueError) as exc:
            error = {"exception": type(exc).__name__, "detail": str(exc)}
    status = done.get("status") if done else "incomplete_stream"
    if error:
        status = "error"
    return {"text": text, "events": events, "done": done, "error": error,
            "execution_status": status, "timing": {"first_useful_text_seconds": first,
            "full_response_seconds": time.perf_counter()-started},
            "timing_definition": "First nonempty answer delta/report, not provider TTFT; human usefulness still reviewed."}


def validate_plan(plan: dict, cases: dict, fixture_root: Path) -> list[str]:
    """Block undeclared cases, leaked oracle fields and unsupported execution paths."""
    allowed = {"case_id", "instance_id", "variant", "repetition", "assets", "requests", "review_status", "reviewer"}
    if set(plan) - allowed:
        raise ValueError("Execution plan must not contain answers or undeclared fields")
    case = cases[plan["case_id"]]
    if case["split"] != "development":
        raise ValueError("Holdout execution is custodian-controlled; this runner is development-only")
    if case["execution"] != "chat_api":
        raise ValueError("Case requires the documented manual/API preparation and recorded-output review")
    if not plan.get("requests"):
        raise ValueError("At least one real user request is required")
    for request in plan["requests"]:
        if set(request) - REQUEST_FIELDS or not isinstance(request.get("content"), str):
            raise ValueError("Only approved chat request fields are accepted")
    for asset in plan.get("assets", []):
        if set(asset) != {"role", "path", "sha256"}:
            raise ValueError("Assets require only role, path and sha256; no answer labels")
        if Path(asset["path"]).suffix.lower() not in UPLOAD_SUFFIXES:
            raise ValueError("Audio/video and unsupported formats require separate isolated manual preparation")
    problems = fixture_status(plan, fixture_root)
    roles = {a["role"] for a in plan.get("assets", [])}
    required_roles = case.get("required_asset_roles", [])
    if plan.get("instance_id"):
        from .development import instance_mapping
        mapping = instance_mapping()
        instance = mapping["instances"].get(plan["instance_id"])
        if not instance or instance["primary_case"] != plan["case_id"]:
            raise ValueError("Unknown or incorrectly mapped development instance")
        required_roles = mapping["required_asset_roles"]
    for role in set(required_roles) - roles:
        problems.append("pending_fixtures:" + role)
    return problems


def run_plan(root: Path, output: Path, plan: dict, cases: dict,
             fixture_root: Path, ollama_url: str) -> dict:
    """Run one independently prepared development instance in a fresh child/state."""
    problems = validate_plan(plan, cases, fixture_root)
    output.mkdir(parents=True, exist_ok=False)
    inputs = {k: plan.get(k) for k in ("case_id", "variant", "assets", "requests")}
    if plan.get("instance_id"):
        inputs["instance_id"] = plan["instance_id"]
    record = {"schema_version": 1, "case_id": plan["case_id"],
              "variant": plan.get("variant", "default"), "repetition": plan.get("repetition", 1),
              "input_digest": digest(inputs), "inputs": inputs,
              "execution_status": "pending", "text": "", "pending": problems,
              "cache_condition": "fresh_application_state; Ollama residency recorded, not forced"}
    if plan.get("instance_id"):
        record["instance_id"] = plan["instance_id"]
    write_new(output / "plan.json", plan)
    if problems:
        write_new(output / "record.json", record)
        return record
    try:
        record["stage"] = "runtime_preflight"
        runtime = capture(root, ollama_url)
        write_new(output / "runtime.json", runtime)
        record["runtime_digest"] = digest(runtime)
        record["prompt_digest"] = digest(runtime["config_and_prompt_files"])
        record["selected_model_digests"] = require_local_models(runtime, plan)
        record["model_digest"] = digest(record["selected_model_digests"])
        record["stage"] = "application_execution"
        with isolated_server(root, output, ollama_url) as base:
            record["qa_url"] = base
            conversation = api(base, "/api/v1/conversations", {"title": "quality:" + plan["case_id"]})
            cid = conversation["id"]
            attachments = []
            record["attachments"] = attachments
            for index, item in enumerate(plan.get("assets", []), 1):
                receipt = upload(base, cid, fixture_root / item["path"])
                attachments.append(receipt)
                write_new(output / f"attachment-{index}.json", receipt)
            write_new(output / "attachments.json", attachments)
            turns = []
            for i, request in enumerate(plan["requests"]):
                body = dict(request, conversation_id=cid, request_id=uuid.uuid4().hex,
                            attachment_ids=[a["id"] for a in attachments])
                turn = stream_chat(base, body, output / f"turn-{i+1}.sse.jsonl")
                turn["request"] = body
                turns.append(turn)
                write_new(output / f"turn-{i+1}.json", turn)
                if turn["execution_status"] != "complete":
                    break
            record["turns"] = turns
            record.update({k: turns[-1][k] for k in ("text", "execution_status", "timing")})
            record["conversation"] = api(base, f"/api/v1/conversations/{cid}")
            saved = [m for m in record["conversation"].get("messages", []) if m.get("role") == "assistant"]
            if saved and saved[-1].get("content") != record["text"]:
                record["delivery_mismatch"] = True
                record["execution_status"] = "delivery_mismatch"
            record["providers"] = api(base, "/api/v1/providers")
            record.update(capture_evidence_and_traces(base, turns, attachments))
            record["ollama_after"] = api(ollama_url, "/api/ps")
    except Exception as exc:
        record["execution_status"] = "blocked_runtime" if record.get("stage") == "runtime_preflight" else "error"
        if record["execution_status"] == "blocked_runtime":
            record["model_inference_executed"] = False
        record["error"] = {"exception": type(exc).__name__, "detail": str(exc)}
    write_new(output / "record.json", record)
    return record


def capture_evidence_and_traces(base: str, turns: list[dict], attachments: list[dict]) -> dict:
    """Resolve real IDs through the original read-only APIs; preserve resolution errors."""
    identifiers, run_ids, activity = set(), set(), []
    for receipt in attachments:
        identifiers.update(receipt.get("metadata", {}).get("evidence_ids", []))
    for turn in turns:
        metadata = (turn.get("done") or {}).get("metadata", {})
        identifiers.update(e["id"] for e in metadata.get("evidence", []) if e.get("id"))
        identifiers.update(re.findall(r"\[((?:EV|SRC):[a-fA-F0-9]{16,64})\]", turn.get("text", "")))
        run_id = metadata.get("orchestration", {}).get("run_id")
        if run_id:
            run_ids.add(run_id)
        activity.append({"model_activity": metadata.get("model_activity", []),
                         "provider": metadata.get("provider"),
                         "validation_profile": metadata.get("validation_profile")})
    def resolve(identifier: str, path: str) -> dict:
        try:
            return {"requested_id": identifier, "response": api(base, path)}
        except (OSError, ValueError) as exc:
            return {"requested_id": identifier, "error": {"type": type(exc).__name__, "detail": str(exc)}}
    return {
        "source_resolutions": [resolve(i, "/api/v1/evidence/" + urllib.parse.quote(i, safe="")) for i in sorted(identifiers)],
        "run_traces": [resolve(i, "/api/v1/runs/" + urllib.parse.quote(i, safe="") + "/trace") for i in sorted(run_ids)],
        "reported_activity": activity,
    }
