"""SIRE Phase 2A evaluation CLI: no third-party dependencies or production edits."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from quality.protocol import compare, digest, manifest, read_json, score_record, write_new
from quality.runtime import capture, run_plan


def main(argv: list[str] | None = None) -> int:
    """Run explicit offline or loopback-only operations; no implicit live requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", help="Validate and list the 27 public case definitions")
    prepare = commands.add_parser("prepare", help="Create an answer-free development execution plan")
    prepare.add_argument("case_id")
    prepare.add_argument("--out", type=Path, required=True)
    runtime = commands.add_parser("capture", help="Read local runtime/model metadata; no generation")
    runtime.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    runtime.add_argument("--out", type=Path, required=True)
    run = commands.add_parser("run", help="Start original SIRE in isolated state and run a reviewed plan")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--fixtures", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    score = commands.add_parser("score", help="Offline: compare a record to an independent key")
    score.add_argument("--record", type=Path, required=True)
    score.add_argument("--key", type=Path, required=True)
    score.add_argument("--annotation", type=Path)
    score.add_argument("--out", type=Path, required=True)
    paired = commands.add_parser("compare", help="Pair identical inputs without inferring accuracy")
    paired.add_argument("--before", type=Path, required=True)
    paired.add_argument("--after", type=Path, required=True)
    paired.add_argument("--out", type=Path, required=True)
    paired.add_argument("--before-score", type=Path)
    paired.add_argument("--after-score", type=Path)
    hashing = commands.add_parser("digest", help="Canonical JSON hash for oracle/annotation binding")
    hashing.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            value = manifest()
            for case in value["cases"]:
                print(f'{case["id"]}\t{case["split"]}\t{case["status"]}\t{case["title"]}')
            print("27 definitions; 18 development; 9 holdout. No live results asserted.")
        elif args.command == "prepare":
            case = next(c for c in manifest()["cases"] if c["id"] == args.case_id)
            if case["split"] != "development" or case["execution"] != "chat_api":
                raise ValueError("This definition needs custodian/manual preparation; see its execution notes")
            plan = {"case_id": case["id"], "variant": "default", "repetition": 1,
                    "assets": [], "requests": case["requests"],
                    "review_status": "pending_independent_review", "reviewer": ""}
            write_new(args.out, plan)
            print("Created plan; independently review it and bind required fixture hashes before execution.")
        elif args.command == "capture":
            write_new(args.out, capture(ROOT, args.ollama_url))
            print("Runtime inventory recorded; no inference performed by capture.")
        elif args.command == "run":
            cases = {c["id"]: c for c in manifest()["cases"]}
            result = run_plan(ROOT, args.out, read_json(args.plan), cases,
                              args.fixtures, args.ollama_url)
            print(json.dumps({k: result[k] for k in ("case_id", "execution_status", "pending")}))
            return 0 if result["execution_status"] == "complete" else 2
        elif args.command == "score":
            value = score_record(read_json(args.record), read_json(args.key),
                                 read_json(args.annotation) if args.annotation else None)
            write_new(args.out, value)
            print(json.dumps({k: value[k] for k in ("status", "critical_errors", "pending")}))
            return 0 if value["status"] == "reviewed_pass" else 2
        elif args.command == "compare":
            write_new(args.out, compare(read_json(args.before), read_json(args.after),
                read_json(args.before_score) if args.before_score else None,
                read_json(args.after_score) if args.after_score else None))
            print("Paired texts and timing deltas saved; inspect configuration changes and reviewer scores.")
        elif args.command == "digest":
            print(digest(read_json(args.path)))
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
