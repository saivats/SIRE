# SIRE LLM quality — Phase 2A handoff

Status: evaluation infrastructure and baseline preparation only. Production prompt
tuning and Phase 2B are not started. Approved production baseline:
`34d41bc46923e1a7d9e089148c3574225aba81fc`.
Branch: `saivats/SIRE:feature/final-cybers-llm-quality`.
Use `git rev-parse HEAD` for the exact evaluation commit; the commit cannot embed
its own final hash. The user's `saivats.md` and approved Phase 1 audit define scope.

## Implemented work

All additions are under `tests/quality/`, `scripts/eval_quality.py` and this document.
No existing application/configuration files are changed. The framework provides:

- 27 versioned case definitions: 18 development, nine externally custodied holdouts;
- independently supplied byte-hashed fixtures, oracle/annotation interfaces and an
  eight-dimensional 0–4 rubric with explicit anchors and critical-error gates;
- checks for fabricated/malformed/stale references, exact decimal values/units,
  asset/time/window/locator mismatches, future evidence, missing facts, known
  mechanism fragments, duplicate origin support, structured output and confidence;
- immutable-by-convention, create-once result files: failures are retained, not repaired;
- real original-pipeline chat runner using an owned loopback uvicorn child and fresh
  `SIRE_STATE_DIR`; public/private answer keys never enter its request path;
- read-only Ollama/runtime/config/source capture and before/after paired reports,
  including optional reviewer score deltas and explicit configuration differences.

The code uses the standard library. It introduces no requirements or dependencies.
JSON is used for portable machine-readable manifests/rubric; production YAML is
captured verbatim with hashes. Unit tests are unittest tests also collectable by pytest.

## Actual validation evidence and limits

The implementation environment is Linux with Python 3.12.14. Ollama, nvidia-smi,
pytest, ruff and black were unavailable. No dependencies or models were installed.
The deterministic suite was run using:

```text
python -B -m unittest discover -s tests/quality -t tests -v
```

Final deterministic result: **51 tests passed, 0 failures**, in **0.265 seconds**
as reported by unittest in this environment. This is test-harness execution time,
not SIRE model latency. The case inventory and syntax/JSON/allowed-path checks also
passed for all 13 added files.
Unit payloads and mocked transport bytes are explicitly labelled test controls,
not Qwen outputs. No full application suite, Windows smoke test, physical device,
ASR/TTS test, specialist inference or live Ollama/Qwen run was executed here.
Ruff/Black checks remain to be run with the team's existing developer tools.

**No baseline accuracy, model latency, hallucination rate or improvement is claimed.**
The committed historical application test counts in older reports are not results
of this evaluation. All 27 live case definitions remain unexecuted in this environment.

Limitations of automatic checking:

- Reference existence/syntax does not establish source entailment. Reviewers bind
  actual IDs to source bytes, scope and locators, then assess the claim.
- Numeric regexes are claim-specific; unrecognized numerical prose is not certified.
  Review all claims and dates, including A/dB/temperature and percentage contexts.
- Completeness heuristics detect known fragments, not every semantic or grammatical
  defect. A fluent sentence may still be unsupported.
- Raw **application** SSE lines, outputs and errors are preserved. If production
  validation discards provider tokens before SSE, those hidden tokens are unavailable
  to this runner. Capturing them requires an approved backend trace contract.
- The final-turn answer is checked automatically. Prior turns and their scope must
  be reviewed manually; incomplete review keeps the score pending.
- A reviewer attestation is a human workflow, not cryptographic proof of independence.
- Performance includes HTTP delivery; first useful text is operationally the first
  nonempty answer delta/report, not provider TTFT or a human-rated usefulness guarantee.

## Case readiness

| Category | Development definitions | Holdout definition | Current missing work |
|---|---|---|---|
| A dialogue | A1 greetings; A2 identity/general explanation | A3 unseen follow-up | Independent capability/input review; real audio/failed-history variants |
| B vision | B1 bearing; B2 schematic | B3 indistinct gauge | Approved images and independent visual annotations |
| C exact numbers | C1 conflicting PDFs; C2 point/window/units | C3 XLSX | Teammate files and separately extracted row/page/cell keys |
| D asset/multimodal | D1 three assets + image; D2 revisions/cutoff | D3 ambiguous scope | Linked/unlinked fixture provenance, genuine isolated case history |
| E hypotheses | E1 known fragments; E2 contradictions/unknowns | E3 >8 candidates | Real evidence-backed hypotheses; reviewed predicate/candidate keys |
| F case/simulation | F1 hour-48 scope; F2 unsupported scope | F3 actual case comparison | Supported/unsupported scenarios and genuine saved cases |
| G references/injection | G1 aliases; G2 injection document | G3 copied origins | Adversarial document/history plus independent origin mapping |
| H prediction | H1 four regimes × three pathways; H2 invalid/OOD | H3 partial comparison | Existing approved inputs, actual model runs and saved results |
| I communication | I1 audiences; I2 spoken wording | I3 ambiguous ASR | Independently reviewed finding/audio and blinded style review |

E1/G1 evaluator regressions run now; this does not mean their live SIRE behavior
passes. C2's 30-row pattern is a proposed fixture specification, not a delivered
dataset. All nine holdout instances/answer keys still need external custody and
sealing. No missing engineering evidence has been invented.

## Baseline model and prompt inventory to capture locally

At the approved source baseline, configured defaults are:

| Item | Source default; not a claim about the laptop runtime |
|---|---|
| Text / vision tags | `qwen3:4b-instruct` / `qwen3-vl:2b-instruct` |
| Temperature / seed | `0` / `42` |
| Text / vision context | 4096 / 4096 |
| Plain / conversation / evidence / voice tokens | 160 / 384 / 650 / 180 |
| Detailed / vision / investigation output tokens | 1200 / 1600 / 650 |
| Investigation rounds / new candidates | 2 / 2 |
| Think / keep-alive | `false` / 120 seconds |
| top_p, top_k, repeat penalty, stop, GPU offload | Not explicitly set in application payload; capture actual model defaults/runtime |

`capture` reads `/api/version`, `/api/tags`, `/api/ps`, and `/api/show` for installed
tags. It records actual digests, quantization/model details, templates/parameters,
GPU inventory when available, Python/platform/git identity, config contents and
hashes of the following generation-related files:

`config/app.yaml`, `config/conversation.yaml`, `config/hypotheses.yaml`,
`config/capabilities.yaml`, `config/retrieval.yaml`, `config/media.yaml`,
`app/chat/service.py`, `app/providers/adapter.py`, `app/providers/ollama.py`,
`app/investigation/engine.py`, `app/evidence/context.py`, `app/orchestration/tools.py`.

This captures whole source files rather than pretending to capture a final dynamic
assembled prompt. Per-turn `done.metadata`, provider metrics and model activity
retain the fields actually exposed by the application. Context/eval token counts,
done reasons and CPU/GPU details must be reported as unavailable when absent.
Installed/resident is different from actually executed; check model activity.
The runner rejects missing/unverified models and cloud/remote model entries.

Historical expected Q4_K_M digests from the repository audit (verify, never assume):

- Text: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`
- Vision: `afc393e3572c07db0bc84aa460d928a16c75f3fbb9ca9e0dccc4fbd2dafb573e`

Stop a paired baseline comparison if installed identities differ unexpectedly.
Do not pull replacement models or change decoding to make the run proceed.

## Windows 11 / RTX 4050 procedure

Use the existing approved SIRE checkout with its protected weights and working
environment. Preserve its `.venv` and external package linkage. Obtain the feature
branch from **saivats/SIRE**, after checking the local working tree and remote:

```powershell
git status --short
git remote -v
# Only when origin is https://github.com/saivats/SIRE (or its SSH equivalent):
git fetch origin feature/final-cybers-llm-quality
# If the local feature branch does not exist:
git switch --track origin/feature/final-cybers-llm-quality
# If it already exists, inspect it and switch normally; never reset/force it.
git rev-parse HEAD
git diff 34d41bc46923e1a7d9e089148c3574225aba81fc --stat
```

Do not switch with uncommitted unrelated work. The feature diff should contain
evaluation-only files. No upstream write or PR is needed. A separate worktree is
possible, but ignored weights/environments are not automatically present; coordinate
read-only local asset access without copying or modifying protected model files.

1. **Deterministic preflight and isolated locations.**

```powershell
$QualityPython = (Resolve-Path .venv\Scripts\python.exe).Path
$QualityRoot = Join-Path $env:LOCALAPPDATA 'SIRE-Quality'
$FixtureRoot = Join-Path $QualityRoot 'inputs'
$KeyRoot = Join-Path $QualityRoot 'reviewer-keys'
New-Item -ItemType Directory -Force $FixtureRoot, $KeyRoot | Out-Null
& $QualityPython -B -m unittest discover -s tests/quality -t tests -v
& $QualityPython -B scripts/eval_quality.py inventory
& $QualityPython -c "import fastapi, uvicorn, pydantic, yaml; print('Existing application dependencies import')"
```

The final import check is not the full dependency check. Use the team's existing
locked application environment; if dependencies are missing, report the problem
rather than replacing the environment or installing new model packages implicitly.

2. **Verify existing local Ollama and models.** In a separate terminal, only if
the approved local daemon is not already running:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
ollama serve
```

Use the actual installed executable path if `ollama` is not on PATH. No `ollama
pull` is part of this procedure. With the existing daemon running:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:11434/api/ps | ConvertTo-Json -Depth 8
ollama show qwen3:4b-instruct --parameters
ollama show qwen3-vl:2b-instruct --parameters
nvidia-smi
& $QualityPython -B scripts/eval_quality.py capture --out "$QualityRoot\runtime-before.json"
```

Inspect the saved full digests, quantization and parameters. `capture` performs no
generation. Files are create-once: use a new name for subsequent snapshots.

3. **Prepare and independently review a development instance.**

```powershell
& $QualityPython -B scripts/eval_quality.py prepare A1 --out "$QualityRoot\A1-plan.json"
# A real reviewer now checks the inputs, then records their name and review status.
# For asset cases, add role/path and exact SHA-256 only after reviewing those bytes:
Get-FileHash "$FixtureRoot\actual-approved-fixture.csv" -Algorithm SHA256
```

The hash command is illustrative: replace the filename with an existing approved
asset. Do not manufacture a file to satisfy a missing fixture. Independent keys
live under `$KeyRoot`, never `$FixtureRoot`. See `tests/quality/README.md` for fields.

4. **Run the original pipeline and record raw application outputs.**

```powershell
& $QualityPython -B scripts/eval_quality.py run `
  --plan "$QualityRoot\A1-plan.json" --fixtures "$FixtureRoot" `
  --out "$QualityRoot\before-A1-r1"
```

This starts `python -m uvicorn app.api.main:app` on an owned ephemeral loopback
port, with `SIRE_STATE_DIR=<new-run>/state`, then calls the existing
`POST /api/v1/conversations`, optional `POST /api/v1/attachments`, and
`POST /api/v1/chat/message`. It stops only its child afterwards. Never point a
generic benchmark client at the normal production server. The application startup
may perform its existing specialist readiness probe; that is recorded startup work,
not an evaluated prediction case. It does not replace missing specialist artifacts.

Each run saves plan, runtime snapshot, attachment receipts, raw timestamped SSE,
parsed turns, persisted conversation/metadata and final record. Missing fixtures
or review return exit code 2 with a pending record and **no server launch**. Other
failures keep error details and partial output. `complete` means request completion,
not a factual-quality pass. No fixture/key or raw result is committed by the runner.

Fresh application state avoids old conversation/index/vision-cache reuse. The runner
does not unload resident Ollama models or pretend to force cold GPU inference.
Record `/api/ps`, actual model activity and cache metadata; label warm/cold explicitly.
For repeated trials use new output directories and matching `repetition` numbers.
Compare cold with cold and warm with warm; do not cherry-pick the fastest trial.

5. **Score independently and compare after a separately approved production change.**

```powershell
& $QualityPython -B scripts/eval_quality.py digest "$QualityRoot\before-A1-r1\record.json"
# Reviewer binds their external key to input_digest and annotation to record digest.
& $QualityPython -B scripts/eval_quality.py score `
  --record "$QualityRoot\before-A1-r1\record.json" `
  --key "$KeyRoot\A1-before-key.json" --annotation "$KeyRoot\A1-before-review.json" `
  --out "$QualityRoot\A1-before-score.json"
# AFTER Phase 2B approval/change, run the identical reviewed input plan into a new directory.
& $QualityPython -B scripts/eval_quality.py compare `
  --before "$QualityRoot\before-A1-r1\record.json" --after "$QualityRoot\after-A1-r1\record.json" `
  --before-score "$QualityRoot\A1-before-score.json" --after-score "$QualityRoot\A1-after-score.json" `
  --out "$QualityRoot\A1-comparison.json"
```

The after files do not exist yet. These commands describe the later comparison,
not a completed experiment. Input/case/variant/repetition mismatch is rejected.
Record model/prompt/config changes, per-dimension deltas, critical-error counts and
actual first-text/full latency. Agree a material latency regression budget with
the team **before** tuning. Do not estimate a GPU target from this environment.

6. **Manual/API cases and media.** For F/H/D2 and custodied holdouts, use a separately
owned local server with a fresh external `SIRE_STATE_DIR`, original APIs and approved
setup fixtures. Existing contracts are in `app/api/main.py` and
`app/api/intelligence.py`; inspect the local `/docs` for that exact checkout before
execution. Record actual requests/responses, case/prediction IDs and errors. Do not
invent setup IDs, copy production rows, seed a hidden ground-truth answer into the
application or silently fix an unsupported route. Adapt raw output to the documented
record interface for offline scoring. Full automation of these setup flows is pending
Abhigyan's integration review.

The production media worker uses `ROOT/.runtime/media_jobs`, outside `SIRE_STATE_DIR`.
The Phase 2A runner therefore rejects audio/video uploads. ASR/TTS and XLSX cases
need a separately isolated checkout/runtime procedure before execution; do not claim
that voice-ready text testing verifies microphone, audio latency or interruption.

## Ownership and Phase 2B review queue

| Owner | Proposed integration requiring approval; not implemented here |
|---|---|
| Abhigyan | Unify source validation across chat and `llm.chat`; strict malformed/pseudo-reference policy; entailment remains separate |
| Abhigyan | Typed numeric/asset/time/availability claims and complete source mapping; extend checks beyond current units/mechanism-only prose |
| Abhigyan | Hypothesis completeness/status and layered explanation contracts; bounded retries with preserved failed originals |
| Abhigyan | Selected-asset what-if propagation; prior-case paired comparison/cutoff; history/context and ASR provenance handling |
| Abhigyan | Evaluation-only setup adapters for cases/scenarios/predictions, actual provider-output trace, per-call effective settings/cache telemetry |
| Kunal (with backend owner) | Plain answer/details/trace presentation, uncertainty labels, failed-tool cards, source-unavailable display, accessible progressive disclosure |
| Kunal (with backend owner) | Voice length/chunking, first-audio and interruption semantics, keeping written citations accessible without speaking hashes |
| Fourth teammate | Approved synthetic photos/documents/CSV/XLSX/audio, independent context/limits and sealed unseen holdout instances |

Proposed wording for later UI/voice review (policy proposals, not production edits):

- Unknown evidence: "I do not have evidence for that claim."
- Insufficient measurements: "These measurements are not enough to identify the cause."
- Contradictory data: "The sources disagree; both readings are shown below."
- Failed tool: "This check did not complete, so I cannot report a result from it."
- Estimated versus observed: "This is a model estimate, not a measured value."
- Synthetic simulation: "This is a simulated scenario, not a prediction of this machine."
- Source unavailable: "I cannot resolve that source in the current case."

Before changing prompts: obtain reviewed fixture/answer-key instances, verify actual
local models, run a fresh baseline including ordinary chat, multimodal, contradiction,
multi-asset and prediction explanation, retain failures, complete blinded scoring,
agree latency budgets and receive file-specific backend/UI approvals. No colleague's
approval is inferred from the user's authorization to build this harness.

Proposed Phase 2B sequence, **awaiting separate approval**:

1. Finish fixture custody and real baseline; freeze input hashes and holdouts.
2. Version current prompts; change one prompt-policy variable in reviewed integration
   points, beginning with zero-source chat, provenance and complete mechanisms.
3. Coordinate deterministic citation/numeric/scope fixes with Abhigyan; separately
   coordinate plain-language layers and voice labels with Kunal.
4. Run paired development trials with actual raw traces and reviewer scores; retain
   all failures and reject material factual or latency regressions.
5. Freeze candidate configuration, execute custodied holdouts once, document exposed
   failures and decide whether the candidate is ready for a separately authorized PR.

## Protection and rollback

The commit adds only evaluation source, unit-control payloads and internal technical
documentation. No application prompt/config, shared backend, UI, voice code, model,
frozen result or database file is changed. The protected 813/7,956/15 counts are
assignment constraints, not freshly re-hashed inventories from this environment.
No private photo, dataset, answer key or live trace is included in the feature commit.
No model download, hosted inference, upstream write or pull request is part of Phase 2A.

To remove the evaluation addition later, revert its feature commit after reviewing
the branch history; do not reset or force-push. External local result directories are
separate and should be retained as evidence rather than deleted by a rollback.
