"""Versioned case, oracle, scoring and paired-comparison interfaces (stdlib only)."""

import hashlib
import json
from pathlib import Path
from typing import Any

from .checks import DIMENSIONS, check_answer

BASELINE = "34d41bc46923e1a7d9e089148c3574225aba81fc"
HERE = Path(__file__).resolve().parent


def read_json(path: Path) -> Any:
    """Read UTF-8 JSON, rejecting non-finite numbers and duplicate object keys."""
    def pairs(items: list) -> dict:
        value = {}
        for k, v in items:
            if k in value:
                raise ValueError("Duplicate key: " + k)
            value[k] = v
        return value

    def invalid(value: str) -> None:
        raise ValueError("Non-finite JSON: " + value)

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid)


def digest(value: Any) -> str:
    """Hash canonical JSON for pairing, provenance and annotation binding."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    """Hash local bytes without loading them into application state."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path: Path, value: Any) -> None:
    """Create a result exactly once; never overwrite a failed run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def manifest() -> dict:
    """Load and validate all public definitions, including answer-free holdouts."""
    value = read_json(HERE / "cases/manifest.json")
    cases = value["cases"]
    if value["version"] != 1 or len(cases) != 27:
        raise ValueError("Expected version 1 and exactly 27 definitions")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate case ID")
    for category in "ABCDEFGHI":
        subset = [c for c in cases if c["category"] == category]
        if sorted(c["split"] for c in subset) != ["development", "development", "holdout"]:
            raise ValueError("Each category requires two development and one holdout")
    for case in cases:
        for field in ("required_assets", "expected_fact_spec", "forbidden_claims",
                      "source_validation", "dimensions", "execution", "status"):
            if not case.get(field):
                raise ValueError(case["id"] + " missing " + field)
        if not set(case["dimensions"]) <= set(DIMENSIONS):
            raise ValueError("Unknown scoring dimension")
        if case["split"] == "holdout" and ("requests" in case or "answer_key" in case):
            raise ValueError("Holdout instances and answers must stay external")
    return value


def fixture_status(plan: dict, fixture_root: Path) -> list[str]:
    """Require declared local fixtures, exact byte hashes and independent review."""
    problems = []
    root = fixture_root.resolve()
    for item in plan.get("assets", []):
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root):
            problems.append("fixture_outside_root:" + item["path"])
        elif not path.is_file():
            problems.append("pending_fixtures:" + item["path"])
        elif not item.get("sha256") or file_digest(path) != item["sha256"]:
            problems.append("fixture_hash_mismatch:" + item["path"])
    if plan.get("review_status") != "independent_reviewed" or not plan.get("reviewer"):
        problems.append("pending_independent_review")
    return problems


def score_record(record: dict, key: dict, annotation: dict | None = None) -> dict:
    """Keep factual failures separate from ordinal scores; never infer human grades."""
    if key.get("case_id") != record.get("case_id"):
        raise ValueError("Oracle case differs from record")
    if key.get("input_digest") != record.get("input_digest"):
        raise ValueError("Oracle is not bound to these exact inputs")
    annotation = annotation or {}
    if annotation and annotation.get("record_digest") != digest(record):
        raise ValueError("Annotation is not bound to this raw record")
    scores = annotation.get("scores", {})
    dimensions = key.get("dimensions", list(DIMENSIONS))
    if not set(dimensions) <= set(DIMENSIONS):
        raise ValueError("Unknown rubric dimension")
    if set(scores) - set(dimensions):
        raise ValueError("Scores include a non-applicable dimension")
    for name, value in scores.items():
        if type(value) is not int or not 0 <= value <= 4:
            raise ValueError("Scores must be integer 0-4: " + name)
    findings = check_answer(record.get("text", ""), key, annotation)
    for item in annotation.get("manual_findings", []):
        if not isinstance(item.get("critical"), bool) or not item.get("detail"):
            raise ValueError("Manual findings need detail and a boolean critical flag")
        findings.append(item)
    pending = []
    if key.get("review_status") != "independent_reviewed" or not key.get("reviewer"):
        pending.append("pending_independent_review")
    if not annotation.get("all_claims_reviewed") or not annotation.get("reviewer"):
        pending.append("pending_claim_review")
    if set(scores) != set(dimensions):
        pending.append("pending_rubric_scores")
    if record.get("execution_status") != "complete":
        pending.append("execution_not_complete")
    if len(record.get("turns", [])) > 1 and not annotation.get("all_turns_reviewed"):
        pending.append("pending_prior_turn_review")
    critical = sum(bool(f["critical"]) for f in findings)
    status = "failed" if findings else ("pending_review" if pending else "reviewed_pass")
    return {"schema_version": 1, "case_id": record["case_id"],
            "record_digest": digest(record), "oracle_digest": digest(key),
            "status": status, "findings": findings, "critical_errors": critical,
            "pending": pending, "scores": scores, "applicable_dimensions": dimensions,
            "ordinal_mean": sum(scores.values()) / len(scores) if scores else None,
            "warning": "Ordinal mean is not factual accuracy or a release gate."}


def compare(before: dict, after: dict, before_score: dict | None = None,
            after_score: dict | None = None) -> dict:
    """Pair the same case/inputs; surface runtime differences without hiding them."""
    for field in ("case_id", "input_digest", "variant", "repetition"):
        if before.get(field) != after.get(field):
            raise ValueError("Unpaired records: " + field)
    changes = {}
    for field in ("runtime_digest", "cache_condition", "model_digest", "prompt_digest"):
        if before.get(field) != after.get(field):
            changes[field] = [before.get(field), after.get(field)]
    latencies = {}
    for field in ("first_useful_text_seconds", "full_response_seconds"):
        a, b = before.get("timing", {}).get(field), after.get("timing", {}).get(field)
        latencies[field] = b-a if a is not None and b is not None else None
    quality = None
    if before_score is not None or after_score is not None:
        if not before_score or not after_score:
            raise ValueError("Both score reports are required")
        for report, record in ((before_score, before), (after_score, after)):
            if report.get("record_digest") != digest(record):
                raise ValueError("Score report is not bound to paired record")
        if before_score["applicable_dimensions"] != after_score["applicable_dimensions"]:
            raise ValueError("Cannot compare different applicable dimensions")
        quality = {"before_status": before_score["status"], "after_status": after_score["status"],
                   "critical_error_delta": after_score["critical_errors"]-before_score["critical_errors"],
                   "score_deltas": {k: after_score["scores"][k]-before_score["scores"][k]
                       for k in before_score["scores"] if k in after_score["scores"]}}
    return {"case_id": before["case_id"], "before_digest": digest(before),
            "after_digest": digest(after), "configuration_changes": changes,
            "timing_delta_seconds": latencies,
            "before_status": before.get("execution_status"),
            "after_status": after.get("execution_status"),
            "before_text": before.get("text"), "after_text": after.get("text"),
            "quality_comparison": quality,
            "review_required": True,
            "note": "No causal improvement or accuracy claim follows from a pair alone."}
