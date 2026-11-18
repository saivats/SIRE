"""Conservative offline checks, independent of SIRE's production validators.

These checks find specified violations; they do not certify engineering truth.
Structured claims are reviewer annotations of the raw answer, not model answers.
"""

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DIMENSIONS = (
    "source_fidelity", "numeric_correctness", "asset_time_correctness",
    "mechanism_completeness", "contradictions_unknowns", "diagnostic_usefulness",
    "clarity", "latency_brevity",
)
BRACKET = re.compile(r"\[([^\[\]\n]+)\]")
CANONICAL = re.compile(r"(?:EV:)?[0-9a-f]{64}|E[1-9][0-9]*")


def finding(code: str, detail: str, critical: bool = True) -> dict:
    """Return an auditable failure without rewriting the observed answer."""
    return {"code": code, "detail": detail, "critical": critical}


def source_checks(text: str, key: dict) -> list[dict]:
    """Check citation-like brackets against an independently reviewed allowlist."""
    failures = []
    allowed = set(key.get("allowed_refs", []))
    required = set(key.get("required_refs", []))
    found = set()
    for match in BRACKET.finditer(text):
        value = match.group(1).strip()
        citation_like = bool(re.match(r"(?i)(?:E\d|EV:|source\b)", value))
        if not citation_like and not CANONICAL.fullmatch(value):
            continue
        parts = [p.strip() for p in value.split(",")]
        for part in parts:
            found.add(part)
            if not CANONICAL.fullmatch(part) or part not in allowed:
                failures.append(finding("invalid_source", part))
    for ref in sorted(required - found):
        failures.append(finding("missing_source", ref))
    # Bare EV identifiers are still references, even without brackets.
    for token in re.findall(r"EV:[\w:-]+", text):
        if not CANONICAL.fullmatch(token) or token not in allowed:
            item = finding("invalid_source", token)
            if item not in failures:
                failures.append(item)
    for token in re.findall(r"\[(?:E\d+|EV:)[^\]\n]*(?=\n|$)", text):
        failures.append(finding("malformed_source", token))
    return failures


def numeric_equal(actual: Any, expected: Any, tolerance: Any = "0") -> bool:
    """Compare finite decimal values; never infer units or percentage scaling."""
    try:
        a, e, t = (Decimal(str(v)) for v in (actual, expected, tolerance))
        return all(v.is_finite() for v in (a, e, t)) and t >= 0 and abs(a-e) <= t
    except (InvalidOperation, ValueError):
        return False


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return result


def claim_checks(claims: list[dict], key: dict) -> list[dict]:
    """Validate human-extracted claims against independent, source-bound facts."""
    failures = []
    facts = {f["id"]: f for f in key.get("facts", [])}
    seen = set()
    for claim in claims:
        identifier = claim.get("fact_id")
        fact = facts.get(identifier)
        if fact is None:
            failures.append(finding("unsupported_fact", str(identifier)))
            continue
        seen.add(identifier)
        for field in ("value", "unit", "asset_id", "channel", "observed_at", "available_at", "statistic",
                      "window_start", "window_end", "locator"):
            if field not in fact:
                continue
            actual = claim.get(field)
            equal = (numeric_equal(actual, fact[field], fact.get("tolerance", "0"))
                     if field == "value" and fact.get("value_type", "number") == "number"
                     else actual == fact[field])
            if not equal:
                failures.append(finding("claim_" + field, str(identifier)))
        refs = set(claim.get("source_refs", []))
        expected_refs = set(fact.get("source_refs", []))
        if not refs or not refs <= set(key.get("allowed_refs", [])):
            failures.append(finding("claim_sources", str(identifier)))
        if expected_refs and not expected_refs <= refs:
            failures.append(finding("claim_missing_source", str(identifier)))
        if key.get("as_of"):
            for field in ("observed_at", "available_at"):
                value = claim.get(field)
                if value:
                    try:
                        if _time(value) > _time(key["as_of"]):
                            failures.append(finding("future_evidence", str(identifier)))
                    except (ValueError, TypeError):
                        failures.append(finding("invalid_timestamp", str(identifier)))
    for identifier in set(key.get("required_fact_ids", [])) - seen:
        failures.append(finding("missing_fact", identifier))
    return failures


def mechanism_checks(text: str) -> list[dict]:
    """Detect known fragments, not grammatical completeness in arbitrary language."""
    value = text.strip()
    failures = []
    if not value or re.search(r"[,;:\-]$|\b(?:of|the|and|because|due to)\s*[.!?]?$", value, re.I):
        failures.append(finding("incomplete_mechanism", value))
    if "progressive degradation of潤" in value:
        failures.append(finding("known_truncated_mechanism", value))
    if any(value.count(a) != value.count(b) for a, b in (("(", ")"), ("[", "]"))):
        failures.append(finding("unbalanced_mechanism", value))
    return failures


def origin_checks(supports: list[dict], claimed_count: int | None) -> list[dict]:
    """Count independently established origins, not observations or file names."""
    if any(not row.get("origin_group") for row in supports):
        return [finding("unknown_origin", "Independent origin mapping is missing")]
    count = len({row["origin_group"] for row in supports})
    if claimed_count is not None and claimed_count > count:
        return [finding("duplicate_support", f"Claimed {claimed_count}; unique origins {count}")]
    return []


def schema_checks(value: Any, schema: dict, path: str = "$") -> list[dict]:
    """Validate the documented JSON-schema subset; reject unsupported keywords.

    Supported: type, properties, required, additionalProperties=false, items,
    enum, minItems/maxItems, minLength/maxLength. No coercion or repair.
    """
    supported = {"type", "properties", "required", "additionalProperties", "items",
                 "enum", "minItems", "maxItems", "minLength", "maxLength"}
    if set(schema) - supported:
        raise ValueError("Unsupported schema keyword: " + str(set(schema)-supported))
    if "additionalProperties" in schema and schema["additionalProperties"] is not False:
        raise ValueError("Only additionalProperties=false is supported")
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "number": (int, float), "null": type(None)}
    kind = schema.get("type")
    if kind not in kinds:
        raise ValueError("Explicit supported schema type required")
    valid = isinstance(value, kinds[kind])
    if kind in {"integer", "number"}:
        valid = valid and not isinstance(value, bool) and math.isfinite(value)
    if not valid:
        return [finding("invalid_structure", path + ": expected " + kind)]
    failures = []
    if "enum" in schema and value not in schema["enum"]:
        failures.append(finding("invalid_enum", path))
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                failures.append(finding("missing_field", path + "." + name))
        for name, child in value.items():
            if name in props:
                failures.extend(schema_checks(child, props[name], path + "." + name))
            elif schema.get("additionalProperties") is False:
                failures.append(finding("extra_field", path + "." + name))
    if isinstance(value, (str, list)):
        lo, hi = ("minLength", "maxLength") if isinstance(value, str) else ("minItems", "maxItems")
        if len(value) < schema.get(lo, 0) or len(value) > schema.get(hi, float("inf")):
            failures.append(finding("invalid_length", path))
    if isinstance(value, list) and "items" in schema:
        for i, child in enumerate(value):
            failures.extend(schema_checks(child, schema["items"], f"{path}[{i}]"))
    return failures


def check_answer(text: str, key: dict, annotation: dict | None = None) -> list[dict]:
    """Combine explicit checks; retain manual-review gaps in the scoring layer."""
    annotation = annotation or {}
    failures = source_checks(text, key)
    if "progressive degradation of潤" in text:
        failures.append(finding("known_truncated_mechanism", "Historical fragment in raw answer"))
    # Key authors bind each pattern to a specific claim. We do not guess which
    # of several numbers in a paragraph belongs to a channel or time window.
    for rule in key.get("numeric_rules", []):
        matches = list(re.finditer(rule["pattern"], text, re.I))
        if not matches:
            failures.append(finding("missing_numeric_claim", rule["id"]))
        for match in matches:
            if not numeric_equal(match.group("value"), rule["value"], rule.get("tolerance", "0")):
                failures.append(finding("wrong_numeric_value", rule["id"]))
            if match.group("unit") != rule["unit"]:
                failures.append(finding("wrong_numeric_unit", rule["id"]))
    for pattern in key.get("forbidden_patterns", []):
        if re.search(pattern, text, re.I):
            failures.append(finding("forbidden_claim", pattern))
    for pattern in key.get("required_patterns", []):
        if not re.search(pattern, text, re.I):
            failures.append(finding("missing_required_content", pattern, False))
    if not key.get("confidence_supported", False) and re.search(
        r"(?i)\b(?:confidence|probability|certainty)\s*(?:is|of|:|=)?\s*\d+(?:\.\d+)?\s*%"
        r"|\b\d+(?:\.\d+)?\s*%\s*(?:confident|confidence|certain|probability)", text
    ):
        failures.append(finding("unsupported_confidence", "Percentage confidence in prose"))
    failures.extend(claim_checks(annotation.get("claims", []), key))
    for mechanism in annotation.get("mechanisms", []):
        failures.extend(mechanism_checks(mechanism))
    if "supports" in annotation:
        failures.extend(origin_checks(annotation["supports"], annotation.get("independent_support_count")))
    if "schema" in key:
        try:
            import json
            def unique(items: list) -> dict:
                result = {}
                for name, value in items:
                    if name in result:
                        raise ValueError("Duplicate structured-output field")
                    result[name] = value
                return result

            def finite(value: str) -> None:
                raise ValueError("Non-finite structured-output number: " + value)

            parsed = json.loads(text, object_pairs_hook=unique, parse_constant=finite)
        except (ValueError, TypeError):
            failures.append(finding("invalid_json", "Raw output is not JSON"))
        else:
            failures.extend(schema_checks(parsed, key["schema"]))
    return failures
