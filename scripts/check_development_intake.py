"""Exercise real source-only development intake and profile APIs in fresh isolated state."""

import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
from statistics import mean
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.api.main import create_app


def checked(response):
    """Reject API failures while preserving the public error for the operator."""
    if not response.is_success:
        raise ValueError(f"HTTP {response.status_code}: {response.text}")
    return response.json()


def run(bundle: Path, out: Path) -> None:
    """Verify every supplied cell and compare series statistics to the original CSV."""
    out = out.resolve()
    if out.is_relative_to(ROOT) or out.is_relative_to(bundle.resolve()):
        raise ValueError("Choose a fresh output directory outside the repository and prepared bundle")
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((bundle / "bundle.json").read_text())
    summary = []
    for case in ("D01", "D02", "D03", "D04"):
        folder = out / case
        record = {"case": case, "mode": "deterministic intake", "receipts": [], "checks": []}
        folder.mkdir()
        start = perf_counter()
        try:
            with TestClient(create_app(folder / "state", probe_model=False)) as client:
                cid = checked(client.post("/api/v1/conversations", json={}))["id"]
                record["conversation_id"] = cid
                for asset in manifest["instances"][case]["assets"]:
                    root = (bundle / "inputs" / case).resolve()
                    path = (bundle / "inputs" / asset["path"]).resolve()
                    if path.parent != root or path.suffix not in {".jpg", ".xlsx", ".pdf", ".csv"}:
                        raise ValueError("Unexpected source path or format")
                    content = path.read_bytes()
                    if hashlib.sha256(content).hexdigest() != asset["sha256"]:
                        raise ValueError(f"Source hash mismatch: {path.name}")
                    receipt = checked(client.post("/api/v1/attachments", data={"conversation_id": cid},
                                                  files={"file": (path.name, content)}))
                    record["receipts"].append(receipt)
                    if receipt["metadata"]["original_sha256"] != asset["sha256"] or receipt["ingestion_status"] != "ready":
                        raise ValueError(f"Incomplete intake: {path.name}")
                    if asset["role"] != "sensor_csv":
                        continue
                    profile = checked(client.post("/api/v1/intelligence/execute", json={
                        "tool_id": "measurements.profile", "arguments": {"conversation_id": cid, "attachment_id": receipt["id"]}}))
                    record["profile"] = profile
                    source = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
                    expected = {(i, field) for i, row in enumerate(source, 1)
                                for field, value in row.items() if field not in ("asset_id", "timestamp_utc") and value}
                    observed = set()
                    for g in profile["result"]["groups"]:
                        item = checked(client.get("/api/v1/evidence/" + g["evidence_id"]))["evidence"]
                        values = []
                        for sample in item["observation"]["rows"]:
                            n, field = sample["source_row"], sample["source_field"]
                            row = source[n - 1]
                            if (
                                (n, field) in observed
                                or row["asset_id"] != g["asset_id"]
                                or float(row[field]) != sample["value"]
                                or datetime.fromisoformat(row["timestamp_utc"]) != datetime.fromisoformat(sample["observed_at"])
                            ):
                                raise ValueError("Asset, locator or value differs from source")
                            observed.add((n, field))
                            values.append((datetime.fromisoformat(row["timestamp_utc"]), float(row[field])))
                        values = [v for _, v in sorted(values)]
                        if [g["first_value"], g["last_value"], g["full_mean"]] != [values[0], values[-1], mean(values)]:
                            raise ValueError("Chronological endpoints or mean differ from source")
                        delta = values[-1] - values[0]
                        percent = delta / values[0] * 100 if values[0] else None
                        if (g["endpoint_delta"], g["endpoint_percent_delta"], g["baseline_mean"], g["recent_mean"]) != (
                            delta, percent, mean(values[:24]), mean(values[-6:])
                        ):
                            raise ValueError("Endpoint and window comparisons differ from the source series")
                        record["checks"].append({"id": g["evidence_id"], "verified_samples": len(values)})
                    if expected != observed:
                        raise ValueError("Populated development sensor cells differ from typed coverage")
                if not record["checks"]:
                    raise ValueError("No measurement series verified")
                record["knowledge"] = checked(client.get("/api/v1/knowledge/sources", params={"conversation_id": cid}))
        except Exception as exc:
            record["error"] = str(exc)
        finally:
            record["elapsed_seconds"] = perf_counter() - start
            (folder / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        summary.append({"case": case, "files": len(record["receipts"]), "groups": len(record["checks"]),
                        "samples": sum(row["verified_samples"] for row in record["checks"]),
                        "elapsed_seconds": record["elapsed_seconds"], "error": record.get("error")})
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if any(row["error"] for row in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle, args.out)
