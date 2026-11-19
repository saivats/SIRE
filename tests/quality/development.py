"""External-only development pack preparation and independent numeric assessment.

Only development/D01-D04 are accepted. No blind package is opened or extracted.
The numeric oracle comes from the supplied CSV/key, never application summaries.
"""

import csv
import io
import json
import re
import stat
import zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path, PurePosixPath

from .checks import DIMENSIONS, finding, numeric_equal, source_checks
from .protocol import digest, file_digest, read_json, write_new

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PACK_DIMENSIONS = (
    "exact_numbers_and_units", "asset_time_source_integrity",
    "uncertainty_and_conflict_handling", "clarity_and_diagnostic_usefulness",
)


def instance_mapping() -> dict:
    """Read answer-free links to the unchanged 27 public definitions."""
    return read_json(HERE / "development_instances.json")


def inspect_archive(archive: Path) -> dict[str, bytes]:
    """Validate every name before reading any member; refuse sealed material."""
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or sum(i.file_size for i in infos) > 50_000_000:
            raise ValueError("Duplicate names or oversized archive")
        for item in infos:
            name = item.filename
            path = PurePosixPath(name)
            special = name in {
                "verify_numeric_gold.py", "development/README_FOR_CYBERS.md",
                "development/DEVELOPMENT_EXPECTED_FINDINGS.md",
                "development/DEV_EXPECTED_RESULTS.json",
            }
            asset = bool(re.fullmatch(
                r"development/D0[1-4]_[A-Za-z0-9_]+/(?:SCENARIO\.md|sensor_readings\.csv|"
                r"inspection_photo\.jpg|inspection_register\.xlsx|[A-Za-z0-9_]+\.pdf)", name))
            if (path.is_absolute() or ".." in path.parts or "\\" in name
                    or stat.S_ISLNK(item.external_attr >> 16) or not (special or asset)):
                raise ValueError("Not an exclusively approved development archive: " + name)
        return {name: source.read(name) for name in names}


def numeric_catalog(content: bytes) -> tuple[dict, list[dict]]:
    """Compute decimal first/last/full-series statistics with original row locators."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    if not {"asset_id", "timestamp_utc"} <= set(fields):
        raise ValueError("Expected explicit asset/time CSV headers")
    groups = defaultdict(list)
    for line, row in enumerate(reader, 2):
        groups[row["asset_id"]].append((line, row))
    result, catalog = {}, []
    for asset, rows in groups.items():
        columns = {}
        for column in fields:
            if column in {"asset_id", "timestamp_utc"}:
                continue
            observed = [(line, row, Decimal(row[column])) for line, row in rows if row[column].strip()]
            if any(not value.is_finite() for _, _, value in observed):
                raise ValueError("Non-finite fixture value")
            facts = {"observed_count": len(observed)}
            if observed:
                values = [v for _, _, v in observed]
                facts.update(first=values[0], last=values[-1],
                    delta_last_minus_first=(values[-1]-values[0]).quantize(Decimal("0.000001")),
                    mean=(sum(values)/len(values)).quantize(Decimal("0.000001")),
                    min=min(values), max=max(values))
            columns[column] = facts
            unit = ("mm/s RMS" if column.endswith("_mm_s_rms") else "degC" if column.endswith("_c")
                    else "m3/h" if column.endswith("_m3_h") else "bar" if column.endswith("_bar") else None)
            for statistic, value in facts.items():
                catalog.append({"id": f"{asset}:{column}:{statistic}", "asset_id": asset,
                    "column": column, "statistic": statistic, "value": str(value),
                    "unit": "count" if statistic == "observed_count" else unit,
                    "source_lines": ([observed[0][0]] if statistic == "first" else
                                     [observed[-1][0]] if statistic == "last" else
                                     [observed[0][0], observed[-1][0]] if statistic == "delta_last_minus_first" else
                                     [line for line, row in rows] if statistic == "observed_count" else
                                     [line for line, _, v in observed if v == value] if statistic in {"min", "max"} else
                                     [line for line, _, _ in observed]),
                    "window_start": rows[0][1]["timestamp_utc"], "window_end": rows[-1][1]["timestamp_utc"]})
        result[asset] = {"row_count": len(rows), "columns": columns}
    return result, catalog


def verify_numeric(content: bytes, expected: dict) -> tuple[dict, list[dict]]:
    """Compare supplied numerical gold against separate Decimal computation."""
    actual, catalog = numeric_catalog(content)
    failures, checks = [], 0
    if set(actual) != set(expected):
        failures.append("asset_set")
    for asset, data in actual.items():
        gold = expected.get(asset, {})
        checks += 1
        if data["row_count"] != gold.get("row_count"):
            failures.append(asset + ":row_count")
        if set(data["columns"]) != set(gold.get("columns", {})):
            failures.append(asset + ":column_set")
        for column, facts in data["columns"].items():
            for name, value in facts.items():
                checks += 1
                target = gold.get("columns", {}).get(column, {}).get(name)
                if not numeric_equal(value, target, "0.0000001"):
                    failures.append(f"{asset}:{column}:{name}")
    return {"status": "passed" if not failures else "failed", "checks": checks,
            "failures": failures}, catalog


def prepare_development(archive: Path, output: Path, reviewer: str) -> dict:
    """Preserve original bytes externally and create input-only, reviewed plans."""
    if not reviewer.strip():
        raise ValueError("Actual integration reviewer is required")
    if output.resolve().is_relative_to(REPO):
        raise ValueError("Development fixtures and keys must stay outside the repository")
    members = inspect_archive(archive)
    expected = json.loads(members["development/DEV_EXPECTED_RESULTS.json"])
    mapping = instance_mapping()
    if set(expected) != set(mapping["instances"]):
        raise ValueError("Expected exactly D01-D04 development keys")
    output.mkdir(parents=True, exist_ok=False)
    inventory = []
    for name, content in members.items():
        destination = output / "original" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(content)
        inventory.append({"path": name, "sha256": file_digest(destination), "bytes": len(content)})
    report = {"version": 1, "archive_sha256": file_digest(archive), "reviewer": reviewer,
              "source_baseline": mapping["source_baseline"], "original_files": inventory, "instances": {}}
    config_path = REPO / "config/app.yaml"
    config = config_path.read_text() if config_path.exists() else ""
    wide = config.split("measurement_wide_fields:", 1)[-1] if "measurement_wide_fields:" in config else ""
    recognized = set(re.findall(r"(?m)^  ([a-zA-Z0-9_]+):", wide))
    for identifier, link in mapping["instances"].items():
        directories = {str(PurePosixPath(n).parent) for n in members if n.startswith("development/" + identifier + "_")}
        if len(directories) != 1:
            raise ValueError("One source directory required for " + identifier)
        directory = directories.pop()
        scenario = members[directory + "/SCENARIO.md"].decode("utf-8")
        questions = re.findall(r"(?m)^\d+\. (.+)$", scenario)
        if len(questions) != 3:
            raise ValueError("Expected three explicit scenario questions")
        data = members[directory + "/sensor_readings.csv"]
        numeric, catalog = verify_numeric(data, expected[identifier]["grounded_numeric_results"])
        if numeric["status"] != "passed":
            write_new(output / "numeric_failure.json", {identifier: numeric})
            raise ValueError("Independent numerical check failed; preserve and review the output directory")
        assets = []
        for name, content in sorted(members.items()):
            if str(PurePosixPath(name).parent) != directory or name.endswith("SCENARIO.md"):
                continue
            basename = PurePosixPath(name).name
            relative = identifier + "/" + basename
            destination = output / "inputs" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(content)
            role = {".csv": "sensor_csv", ".jpg": "inspection_image", ".xlsx": "work_orders", ".pdf": "maintenance_document"}[destination.suffix]
            assets.append({"role": role, "path": relative, "sha256": file_digest(destination)})
        required = set(mapping["required_asset_roles"])
        if not required <= {a["role"] for a in assets}:
            raise ValueError("Missing development source type")
        plans = []
        for index, question in enumerate(questions, 1):
            plan = {"case_id": link["primary_case"], "instance_id": identifier,
                    "variant": f"{identifier}.q{index}.original-bytes", "repetition": 1,
                    "assets": assets, "requests": [{"content": "All supplied files are synthetic development fixtures. " + question + " Answer with source references and state uncertainty.",
                                                     "mode": "chat", "linked_asset": False}],
                    "review_status": "independent_reviewed", "reviewer": reviewer}
            relative = f"plans/{identifier}.q{index}.json"
            write_new(output / relative, plan)
            plans.append({"path": relative, "sha256": file_digest(output / relative)})
        write_new(output / f"evaluator/{identifier}.json", {"instance_id": identifier,
            "numeric_catalog": catalog, "supplied_development_key": expected[identifier],
            "source_csv_sha256": next(a["sha256"] for a in assets if a["role"] == "sensor_csv"),
            "qualitative_status": "Synthetic design expectations; physical causes not established"})
        headers = next(csv.reader(io.StringIO(data.decode("utf-8-sig")) ))
        report["instances"][identifier] = {**link, "assets": assets, "plans": plans,
            "numeric_verification": numeric, "readiness": "ready_for_runtime_preflight",
            "unrecognized_measurement_headers": sorted(set(headers)-recognized-{"asset_id", "timestamp_utc"}),
            "key_storage": "evaluator/" + identifier + ".json",
            "limitations": ["Original bytes retained; no renamed channels or derived replacement uploads.",
                            "Plan review is input/provenance review, not a claim of real diagnosis or live success."]}
    write_new(output / "bundle.json", report)
    return report


def assess_development(record: dict, oracle: dict, annotation: dict, bundle: dict) -> dict:
    """Assess annotated actual claims; keep the two ordinal rubrics independent."""
    identifier = record.get("instance_id")
    if identifier != oracle.get("instance_id") or identifier not in bundle["instances"]:
        raise ValueError("Wrong development instance/key")
    if annotation.get("record_digest") != digest(record):
        raise ValueError("Review must bind the exact raw record")
    if record.get("inputs", {}).get("assets") != bundle["instances"][identifier]["assets"]:
        raise ValueError("Record source files differ from the reviewed bundle")
    refs = {item["requested_id"] for item in record.get("source_resolutions", []) if "response" in item}
    failures = source_checks(record.get("text", ""), {"allowed_refs": sorted(refs)})
    catalog = {item["id"]: item for item in oracle["numeric_catalog"]}
    for claim in annotation.get("numeric_claims", []):
        fact = catalog.get(claim.get("fact_id"))
        if fact is None:
            failures.append(finding("unsupported_numeric_fact", str(claim.get("fact_id"))))
            continue
        if not numeric_equal(claim.get("value"), fact["value"], "0.000001"):
            failures.append(finding("wrong_numeric_value", fact["id"]))
        for field in ("unit", "asset_id", "column", "statistic"):
            if claim.get(field) != fact[field]:
                failures.append(finding("wrong_" + field, fact["id"]))
        if claim.get("source_ref") not in refs:
            failures.append(finding("unresolved_numeric_source", fact["id"]))
    for item in annotation.get("manual_findings", []):
        if not item.get("detail") or type(item.get("critical")) is not bool:
            raise ValueError("Manual finding requires detail and boolean critical")
        failures.append(item)
    ratings = {}
    for field, dimensions, maximum in (("main_scores", DIMENSIONS, 4), ("development_scores", PACK_DIMENSIONS, 3)):
        scores = annotation.get(field, {})
        if set(scores)-set(dimensions) or any(type(v) is not int or not 0 <= v <= maximum for v in scores.values()):
            raise ValueError("Invalid independent rubric score: " + field)
        ratings[field] = scores
    pending = []
    for field in ("all_claims_reviewed", "qualitative_rules_reviewed", "source_entailment_reviewed"):
        if not annotation.get(field):
            pending.append(field)
    if not annotation.get("reviewer"):
        pending.append("reviewer")
    if record.get("execution_status") != "complete":
        pending.append("execution_not_complete")
    if set(ratings["main_scores"]) != set(DIMENSIONS) or set(ratings["development_scores"]) != set(PACK_DIMENSIONS):
        pending.append("rubric_scores")
    return {"instance_id": identifier, "record_digest": digest(record), "oracle_digest": digest(oracle),
            "status": "failed" if failures else "pending_review" if pending else "reviewed_pass",
            "findings": failures, "critical_errors": sum(f["critical"] for f in failures),
            "pending": pending, **ratings, "rubrics_combined": False,
            "limitation": "Numeric annotation checking and reviewed qualitative rules are not physical diagnosis accuracy."}
