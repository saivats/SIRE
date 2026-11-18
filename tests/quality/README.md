# Quality evaluation interface

This directory is evaluation code, not application code. It uses Python's standard
library, can be collected by pytest, and can run without pytest or SIRE dependencies:

```powershell
py -3.12 -B -m unittest discover -s tests/quality -t tests -v
py -3.12 -B scripts/eval_quality.py inventory
```

If pytest is already installed, avoid importing the application's parent conftest:

```powershell
$env:PYTHONPATH = (Resolve-Path tests).Path
python -m pytest --confcutdir=tests/quality tests/quality
```

`manifest.json` contains **definitions**, not benchmark outcomes. The 18 development
definitions and nine holdout definitions cover A–I. Assets and concrete independent
keys are still outstanding. A1/A2 can be prepared without engineering files, but
their input variants and capability keys still require independent review. E1/G1
have evaluator unit regressions; those are not live application regressions.

## Execution plans contain inputs only

`prepare A1 --out <new-path>` creates an unreviewed plan. After actual independent
review, the reviewer edits `review_status` and `reviewer`. Do not sign off missing
fixtures. Each supplied asset requires its declared role and exact SHA-256:

```json
{
  "case_id": "B1",
  "variant": "reviewer-assigned-instance-id",
  "repetition": 1,
  "assets": [
    {"role": "bearing_photo", "path": "relative-image.jpg", "sha256": "actual-file-sha256"}
  ],
  "requests": [{"content": "Describe what is visible and what remains uncertain.", "mode": "chat"}],
  "review_status": "pending_independent_review",
  "reviewer": ""
}
```

This is a **format example**, not an existing fixture or completed review. Relative
paths must stay inside the explicit fixture root. Only selected files are uploaded.
Keep keys in a different directory outside that root, the repository, retrieval
indexes and application state. Do not upload annotation documents as sources.

The runner supports chat, investigate, image/document/CSV intake, foreground SSE,
multi-turn requests and voice-ready **text**. Requests cannot supply existing
production conversation IDs. Audio/video/XLSX, scenario setup, prior-case histories,
prediction preparation and seeded failure histories require the manual/API method
in the case definition. These are explicit pending integrations, not simulated
successes. A plain `run` of a manual or holdout case is rejected.

## Independent answer-key interface

Keys are created **after independent extraction** from fixture bytes and source
locators, never from the evaluated answer or production summary/validation code.
Use a separate reviewer, retain their working and record actual provenance. For
CSV use independent decimal arithmetic, row selection and units; for PDFs/XLSX
verify actual pages/cells; for visual/causal judgments use human annotation.

Bind `input_digest` to the value in the real record. Bind actual source IDs using
the saved intake/evidence trace; do not create a fake reference just to satisfy
the checker. One key may be resolved separately for each run's real dynamic IDs.
The following deliberately contains **non-executable format markers**:

```json
{
  "case_id": "C2",
  "input_digest": "copy-from-reviewed-real-record",
  "review_status": "pending_independent_review",
  "reviewer": "",
  "dimensions": ["source_fidelity", "numeric_correctness", "asset_time_correctness", "clarity"],
  "not_applicable_reasons": {"mechanism_completeness": "No mechanism requested"},
  "allowed_refs": ["actual-in-scope-reference"],
  "required_refs": ["actual-in-scope-reference"],
  "as_of": "actual-ISO8601-cutoff-with-timezone",
  "facts": [
    {
      "id": "reviewer-fact-id",
      "value": "actual-decimal",
      "tolerance": "0",
      "unit": "actual-unit",
      "asset_id": "actual-asset",
      "observed_at": "actual-ISO8601-time-with-timezone",
      "available_at": "actual-ISO8601-availability-with-timezone",
      "statistic": "point",
      "locator": "actual-row-cell-or-page",
      "source_refs": ["actual-in-scope-reference"]
    }
  ],
  "required_fact_ids": ["reviewer-fact-id"],
  "forbidden_patterns": [],
  "required_patterns": [],
  "confidence_supported": false
}
```

Optional `numeric_rules` bind a case-specific regular expression with named
`value` and `unit` groups to a known fact: fields `id`, `pattern`, `value`, `unit`,
optional decimal `tolerance`. Test patterns on both correct and incorrect answers.
They are deliberately scoped, not a claim that all numerical prose is parsed.
No implicit unit conversion is performed. Unit aliases/conversions need an
independent documented normalization policy before key creation.

Optional `schema` uses the strict subset documented in `schema_checks`; unsupported
keywords fail loudly. This validates an agreed **evaluation** contract and does
not change SIRE's schemas. Do not apply a proposed future schema to current prose
and interpret that as a current production regression without labelling it.

## Reviewer annotation interface

Compute `record_digest` with `digest <record.json>`. Preserve each review as a new
file. A second reviewer scores blinded A/B labels independently; adjudication is
another file, never a replacement. Reviewers inspect **all output claims**, not
only required expected facts. Interpretations require entailment/engineering review.

```json
{
  "record_digest": "actual-canonical-record-digest",
  "reviewer": "actual-independent-reviewer",
  "all_claims_reviewed": false,
  "all_turns_reviewed": false,
  "scores": {},
  "claims": [],
  "mechanisms": [],
  "supports": [],
  "independent_support_count": 0,
  "manual_findings": []
}
```

Each `claims` entry has `fact_id`, actual extracted `value`, `unit`, `asset_id`,
`observed_at`, optional `available_at`/window fields, `statistic`, `locator`,
`source_refs`. Copy what the answer actually claims; do not silently correct it.
`mechanisms` are verbatim strings. Each support has a reviewed `origin_group`.
Use `value_type: "text"` in a fact for exact nonnumeric values such as maintenance
dates; numeric facts default to decimal comparison. Include `channel` where relevant.
`independent_support_count` is the count the answer claims, not a corrected count.
Manual findings contain `code`, `detail`, and boolean `critical`.

`scores` maps applicable rubric dimensions to integers 0–4. N/A is an omitted
dimension with a reason fixed in the key before seeing results. Missing scores
or incomplete claim review yield `pending_review`. A critical factual error
remains a failure even with perfect clarity. The ordinal mean is not accuracy.
For multi-turn records the automatic text checks target the **final answer**;
review earlier turns explicitly and record their violations as manual findings.

## Recorded-output interface for manual cases

Never author substitute model text. Export original API/SSE responses from the
isolated run and retain hashes, requests, fixture hashes and source traces. Adapt
them into a new record with the same public interface:

- `schema_version=1`, `case_id`, `variant`, `repetition`;
- `inputs` (actual user requests and asset byte hashes), `input_digest=digest(inputs)`;
- `text` verbatim, `execution_status` from actual completion/partial/error;
- `timing.first_useful_text_seconds` and `full_response_seconds` only if measured,
  otherwise null; `runtime_digest`, `prompt_digest`, `model_digest` when captured;
- references/hashes to preserved raw response files, actual model activity and trace.

Independent reviewer checks the adapter against originals. An imported record is
not proof that inference ran; original trace/model activity is required. The score
command is deliberately offline and never sends records or keys to a model.

## Holdout custody and reporting

Public A3–I3 entries are high-level definitions, not an already sealed dataset.
The fourth teammate must create unseen instances and independent keys externally,
split by asset/unit/session/source origin (not rows), then freeze file hashes before
development tuning. Keep nine cases sealed until prompt/config freeze. Developers
receive inputs only at the agreed final trial; custodians retain keys. Evaluate once,
record every failure, and retire an exposed holdout into development before creating
a new holdout. H1's 12 regime/pathway combinations are parameterized runs, not 12
additional independent case categories. Record all repetitions and cache conditions.

Report counts of attempted/completed/failed/pending cases, critical errors by kind,
per-dimension reviewer scores and paired measured latency. Do not calculate a global
accuracy percentage from this purposive 27-definition suite or from evaluator unit tests.

The CLI never marks a definition passed from test-harness success, never repairs an
answer and never executes holdout plans. Exact Windows commands and current limits
are in `docs/FINAL_LLM_QUALITY.md`.
