# SIRE evidence showcase

The evidence-review entry point is `/showcase`. It accepts the four approved development scenarios through SIRE's local application. It works with the GPU and Ollama offline. To run a model-backed investigation, the review page checks the installed text tag against the reference digest. Image cases also require the matching vision tag. The full React workspace remains available at `/chat` after a frontend build.

## Windows 11 setup and launch

Use a clone of the personal fork. Commit or move any ongoing local work before switching branches. These commands fast-forward the existing local branch.

```powershell
git remote get-url origin
git fetch origin
git switch feature/final-cybers-llm-quality
git merge --ff-only origin/feature/final-cybers-llm-quality
git rev-parse HEAD
py -3.11 --version
.\scripts\start_sire.ps1 -Setup -BuildWeb -Port 8765
```

Check that `origin` names `saivats/SIRE`. The first launch installs the Windows application lock into a dedicated environment under `%LOCALAPPDATA%\SIRE-Showcase\venv`. The optional build uses the project's npm lockfile. Use Node 22.12+ or a supported newer LTS. If Node is unavailable, omit `-BuildWeb` and open the evidence-review URL printed by the launcher. Subsequent launches need only `.\scripts\start_sire.ps1`. Every launch gets a fresh state directory and logs. Press Ctrl+C in the launch terminal to stop the owned server.

The launcher reports NVIDIA driver/free VRAM when available, queries loopback Ollama, compares both model digests with `docs/OLLAMA_MODELS.json`, and polls SIRE health. It performs no model download. For a stopped Ollama service, start the existing Ollama application, check `ollama list`, then reload the review page. Missing or mismatched tags need operator review before a benchmark. Treat `ml_ready`, installed Ollama tags and optional voice readiness as separate checks. Native C-MAPSS prediction needs the verified private research runtime, preserved weights and compatible histories. A Git clone alone supplies the evidence showcase.

## Demonstration at the table

1. Open **http://127.0.0.1:8765/showcase**. Read the actual backend and model status aloud. Select only the source files in one prepared `inputs/D01` directory. Click **Inspect sources**.
2. In the pump table, choose a channel and compare its first and last good readings with the full mean. The two window columns average the first 24 and last six samples, filtered for good quality. Short series have overlapping windows. Open **Source rows** to inspect the exact field, data-row ordinal, UTC timestamp and evidence ID. The execution trace records the deterministic tool run.
3. Start a fresh upload with D03. Show the pump and valve in separate rows. A blank channel stays absent for that asset. D02 is a visual-association example. A photograph alone cannot establish which machine it depicts. The displayed image is the server's normalized copy. The original file hash remains on its receipt.
4. With D04, expand both PDFs' extracted passages and their locators. Point out the disagreement and the missing vibration channel. These are source excerpts and counts. A document's assertion still needs independent confirmation.
5. With verified local models, ask **Which possible explanations fit this asset, which records disagree, and what would distinguish them?** Start the investigation. Follow real job status, candidate mechanisms, support, conflicts, excluded evidence, limitations and next checks. Cancellation and partial/error states preserve previously extracted facts. With unavailable models, present the deterministic evidence review and the original sources. Leave the hypothesis outcome open.
6. In a provisioned installation, open **Predictions**, choose compatible NASA C-MAPSS history and compare saved models on the same engine and dataset. Values are remaining operating cycles. For voice, use the React chat workspace and verify permissions, transcript review, playback, stop and text fallback on the laptop.

A short contribution explanation for Saivats: “I worked on whether an engineer can check SIRE's answers. Here is a number the system calculated. I can open the original measurement behind it, show which asset it belongs to, and show where the evidence runs out.”

## How the application connects

The SIRE Brain is the project's orchestration layer. The request, attachment identities and conversation scope determine which registered tools can run. The measurement tool calculates statistics. The evidence ledger stores a resolvable record and its provenance. Local Qwen can propose a mechanism or explain supplied evidence. Verification, hypothesis ranking and saved job status have separate responsibilities. A completed job can still produce a tentative or unresolved finding.

| Action | Actual contract and presentation |
| --- | --- |
| Start a case and attach files | `POST /api/v1/conversations`, then multipart `POST /api/v1/attachments` with the conversation ID. Review shows receipts, original hashes and individual processing errors. |
| Inspect measurements and records | `POST /api/v1/intelligence/execute` with `measurements.profile`, `GET /api/v1/evidence/{id}`, `GET /api/v1/knowledge/sources` and `GET /api/v1/runs/{id}/trace`. Documents retain page or worksheet locators. |
| Investigate and cancel | `POST /api/v1/investigation-jobs`, conversation-scoped job polling and the job's `/cancel` route. The renderer reads the persisted assistant message and case. Proposed support links must occur in the case's source inventory. |
| Continue a conversation | The React client uses `/api/v1/chat/message` and its SSE or background-job response. Saved case history uses `/api/v1/investigations`. |
| Estimate or compare RUL | The original React prediction interface uses SIRE's model inventory and `/api/v1/predictions/run` or `/compare`. A dataset mismatch is rejected before looking up input history. |
| Speak and listen | Existing `/api/v1/voice/session` WebSocket, transcription and speech endpoints. Narration omits pipe-formatted engineering tables. Exact cached audio is identified as a cache hit. |

The frontend ZIPs informed the treatment of source links, hypothesis cards, capability gates and partial results. The shipped app retains the existing React client for chat streaming, history, predictions and voice. The additive review page works without Node after checkout and uses the deployed backend contracts. The ZIP's full visual shell was not ported.

## Engineering and quality changes

Five explicit wide-header mappings cover vibration RMS, surface temperature, pressure drop, discharge temperature and discharge pressure. Tall inputs retain computed source locators even if an uploader supplies conflicting locator fields. Ambiguous duplicate typed columns and duplicate asset/channel/timestamp samples fail validation. Generic unknown-column files retain generic ingestion. Original CSV bytes are read through the integrity checker. Source data rows are one-based after the header.

Each measurement group exposes chronological good endpoints, the full good-sample mean, signed endpoint change and percent change. A zero first reading gives an undefined relative change. Existing first-24/recent-six calculations and immutable previous records remain usable. Structured verification accepts the new statistic kinds, enforces percent units and recomputes values from snapshots. Prose checks recognize explicit endpoint/full-series wording and conventional asset labels such as PUMP-011. Free-form paraphrases, unconventional units and asset names still require review.

The versioned `engineering-grounding/1` policy covers grounded chat, investigations, visual analysis and nested text-tool calls. Ordinary chat has its own conversation policy. Prediction caveats remain downstream of actual native output. Short aliases and bracketed canonical references are checked before display. Unlinked photographs, historical comparisons, missing channels and conflicting records have explicit handling instructions. The vision cache fingerprint includes the revised instructions. Evaluation captures the policy source. Temperature, seed, token budgets, context lengths and residency were held constant. The quality and latency effect on Qwen requires a paired live run.

## Fresh verification

| Development instance | Uploaded files | Asset/channel groups | Populated sensor cells verified | Isolated intake time |
| --- | ---: | ---: | ---: | ---: |
| D01 | 4 | 3 | 36 | 0.310 s |
| D02 | 4 | 2 | 16 | 0.221 s |
| D03 | 4 | 5 | 40 | 0.240 s |
| D04 | 5 | 2 | 20 | 0.250 s |

Times are one Linux in-process pass per scenario, including isolated application setup, uploads, profiling, source reads and checks. Each case checked every populated sensor cell, its locator/asset/time, numerical endpoints, mean and both windows. The supplied numerical-gold procedure separately passed all four cases. The actual JavaScript upload handler, run with a test DOM against Uvicorn over HTTP, processed all 17 files and opened all 12 measurement sources. Browser layout and physical-device behavior remain laptop acceptance items.

| Gate | Outcome |
| --- | --- |
| Original quality framework | 67 passed via unittest. All 27 definitions remain in place. |
| Focused pytest gate | 137 passed, 2 skipped for missing Silero. Covers the quality suite, new contracts, citations, claim verification, hypotheses, case comparisons, conversation, tabular integrity, jobs, voice, prediction domain and cached-audio handling. Counts overlap the quality suite. |
| Broad pytest run with collection errors retained | 328 passed, 11 failed, 34 errors, 9 skipped. The 22 legacy collection errors and 12 history-fixture setup errors involve missing preserved C-MAPSS code, histories or Torch. The failures cover four native inference cases, two ensemble cases, native export/integrity/registry, CSV history and native cancellation. Optional speech, VAD, semantic and video dependencies account for skips. |
| Frontend | 21 Node tests passed, including seven response-rendering scenarios. Standalone TypeScript checking and the Vite production build passed. Vite reported a main-chunk size warning. |
| Startup and static checks | Loopback Uvicorn served the review and real APIs. Python compileall and JavaScript syntax checks passed. Chromium startup failed at its local process socket. Black and Ruff were unavailable in this host's Python package environment. |
| Model questions | All 12 reached preflight. Both configured local model identities remained unavailable here. Zero Qwen answers, diagnostic accuracy scores or inference latencies. |
| Physical acceptance | Windows PowerShell execution, GPU residency, physical microphone/speaker, real investigation completion and native prediction require the provisioned laptop. |

Backend validation used Python 3.12 and pytest 8.4.2 from its tagged source with plugin autoload disabled. The target Windows application lock uses Python 3.11. Node installed the frontend lockfile. No private sources, evaluator keys, blind fixtures, logs, weights or generated web build are part of the Git delivery.

## Reproduce and compare

From the fork in another PowerShell terminal, with the QA server running:

```powershell
$py = Join-Path $env:LOCALAPPDATA 'SIRE-Showcase\venv\Scripts\python.exe'
$qa = Join-Path $env:LOCALAPPDATA ('SIRE-Eval-' + [guid]::NewGuid())
$zip = Read-Host 'Path to approved development ZIP'
& $py scripts/eval_quality.py prepare-development --archive $zip --out "$qa/bundle" --reviewer $env:USERNAME
& $py "$qa/bundle/original/verify_numeric_gold.py" development
& $py scripts/check_development_intake.py --bundle "$qa/bundle" --out "$qa/intake"
node scripts/smoke_showcase.mjs http://127.0.0.1:8765 "$qa/bundle"
& $py -m unittest discover -s tests/quality -t tests -v
& $py -m pytest tests --continue-on-collection-errors -q
Push-Location web
npm test
npm run build
Pop-Location
```

Use only `inputs/D01` through `inputs/D04` for interactive uploads. Never select the archive root, scenario instructions, expected findings or evaluator folder. The intake checker saves each unmodified receipt, calculated profile, extracted chunks, local ledger and timings outside the repository. Its counts describe software behavior. Development answers use the separate four-dimensional 0–3 pack rubric. The main rubric has eight 0–4 dimensions.

Before a model comparison, match both installed digests to the manifest, verify the Ollama endpoint is local, and capture the configuration on the same laptop. Use an additional checkout for the original baseline and the same reviewed bundle in both runs. The evaluator starts a fresh application and uses a dedicated loopback port. The comparison measures the whole candidate, including ingestion changes.

```powershell
$baseline = Join-Path $qa 'baseline-source'
git worktree add --detach $baseline 20496baf61383527c42f93da08887b706a3a79cc
Push-Location $baseline
& $py scripts/eval_quality.py capture --out "$qa/before-runtime.json"
& $py scripts/eval_quality.py run-development --bundle "$qa/bundle" --out "$qa/before"
Pop-Location
& $py scripts/eval_quality.py capture --out "$qa/after-runtime.json"
& $py scripts/eval_quality.py run-development --bundle "$qa/bundle" --out "$qa/after"
& $py scripts/eval_quality.py compare --before "$qa/before/D01.q1/record.json" --after "$qa/after/D01.q1/record.json" --out "$qa/D01-q1-comparison.json"
```

Inspect every record's execution status, model digest, trace and raw response. Apply independently reviewed annotations using the scoring commands in FINAL_LLM_QUALITY.md. A record pair alone supplies no accuracy score. Keep blind cases sealed pending a frozen candidate and separate authorization.

## Troubleshooting and recovery

- **Port occupied.** Choose another QA port and use the same port in the browser and Node smoke command.
- **Static review works, chat workspace unavailable.** Run the launcher with `-BuildWeb`. Review the TypeScript/npm error if the build fails.
- **Provider missing or slow.** Present the deterministic source review. For live acceptance, check both local model digests, available VRAM, the saved job, its trace and backend logs. A partial result retains its actual status.
- **Unsupported CSV.** Inspect the header, units, asset identity and timezone. Generic CSV intake cannot establish typed measurements by guessing column meanings.
- **Empty native predictions or 503.** Verify the approved research bundle, dataset history and matching model files on the laptop. Keep industrial uploads in the engineering workflow.
- **Recover an earlier release.** Stop the QA launcher, then use `git worktree add --detach ../SIRE-before-showcase 20496baf61383527c42f93da08887b706a3a79cc`. Use a separate QA state directory there. Keep the current branch and both result sets for comparison.

The next acceptance gate is one complete paired development run on the RTX 4050. Prioritize wrong-asset claims, incomplete mechanisms and explanations when documents disagree. Record peak VRAM, first useful response and final answer time under the same cache/residency conditions. Verify microphone denial and recovery, transcript review and speaker cancellation in the real browser. Only then select further prompt or decoding changes from the measured failures.
