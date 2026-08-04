# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@df956bbbf19af6652f8711f95fb4fecf272e9951`  
Program state: `WAVE_7_COMPLETED_WAVE_8_NEXT`  
Canonical audit: [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md)  
Machine register: [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json)

This is the first state board to read before YouTube/VK work. Chat history, screenshots, remembered counts, retired packages, and older agent audits do not override it.

## Completed reliability waves

- Wave 0: canonical state and issue ownership;
- Wave 1: durable journaled VK upload lifecycle and exact-ID recovery — PR #66;
- Wave 2: fail-closed project/content identity and supported sync entrypoint — PR #68;
- Wave 3: shared HTTP ownership, safe-read retry taxonomy, redaction, and limiter infrastructure — PR #70;
- Wave 4: fail-closed separation of VK video upload and VK wall publication — PR #71, merge `d85f7cf94b8ba0b30947291b3a08491239438843`;
- Wave 5: one tested fail-closed Windows/PowerShell operator layer — PR #75, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`;
- Wave 6: one stable versioned source/plan/apply/result/reconciliation engine — PR #78, merge `c4c4d3233ec20b8f939343c5d667d8687d7ff040`;
- Wave 7: exact risk-based mutation-boundary and fault/replay coverage — PR #84, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`.

Wave 7 exact-head CI run `30918639372` passed dependency audit, compileall, Ruff, Ruff format, strict mypy, and the full suite on Python 3.11, 3.12, and 3.13: `657 passed, 1 xfailed`. Pester passed `25/25` on Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux. Development and CI performed zero VK or YouTube writes.

## Wave 7 guarantees now in `main`

The supported reliability surface is explicitly inventoried and proof-bound:

- 15 supported mutation boundaries are recorded in `mutation-boundary-register.json` with exact callable, risk, intent/dispatch/response/postflight evidence, reconciliation identity, attempt limit, replay policy, required fault stages, and owning tests;
- an AST gate scans all `src/` provider calls and rejects unregistered or stale mutation markers;
- `mutation-fault-proof-register.json` binds every required stage to an exact pytest node ID or exact Pester `It` title;
- CI requires exact equality between the mutation-boundary set and proof set and rejects missing, unexpected, stale, or duplicate proof claims;
- aggregate coverage is informational only; the safety gate is boundary- and scenario-specific;
- deterministic dependency-injected WaveEngine faults cover intent, dispatch, response persistence, operation-result, final-result, and reconciliation boundaries without environment-controlled activation;
- apply and reconciliation journals form durable replay barriers before ambiguous provider calls;
- interrupted or lost ambiguous outcomes remain one-attempt, non-retry-safe, stop later operations, and require exact reconciliation;
- malformed, truncated, reordered, stale, wrong-digest, cross-project, wrong-owner, wrong-snapshot, wrong-policy, duplicate, and incomplete evidence fails closed;
- interrupted atomic replacement preserves prior evidence and removes orphan temporary files;
- historical pre-dispatch journal migration remains narrowly allowed, while provider-dispatched incomplete historical evidence remains blocked;
- the PowerShell operator has bounded child execution, timeout exit `124`, process termination compatible with Windows PowerShell 5.1 and PowerShell 7, concurrent stdout/stderr draining, and structured-result validation independent of stdout wording;
- missing, malformed, or internally inconsistent operator results fail closed;
- the permanent PowerShell fault suite is canonical-SHA-bound in the wrapper registry;
- no VK or YouTube provider write occurred during Wave 7 development or CI.

## Live-operation gate

Waves 1–7 close architecture, operator, orchestration, and tested mutation-boundary gaps; they do not prove the current remote wall, video inventory, or historical local queue state. Broad live upload/publication remains blocked until the exact project has:

1. a fresh read-only VK video inventory;
2. a fresh complete published+postponed wall snapshot;
3. reconciliation of local result/ledger files not stored in GitHub;
4. immutable Wave 6 source evidence, plan, and apply-intent files with exact digests;
5. one project-bound canary plan;
6. exact postflight evidence proving only the expected remote delta.

No accepted, processing, unknown, or previously verified upload may be replayed from an old package, retired executor, remembered count, or pre-Wave-6 journal.

## Project boundaries

### `lord-god-strength`

- YouTube channel: `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias: `fedor-milovanov`;
- VK community: `60805374`;
- VK owner: `-60805374`;
- shared VK credential alias: `legendary-poet` — credential label only, never project selection.

Closed facts that must not be rerun:

- reviewed duplicate cleanup: `confirmed_deleted=403`, `run=completed`;
- YouTube boundary `KobOzfBqzic`;
- YouTube `s512Opa8Eu4` maps to VK `-60805374_456241938`;
- theological article photo wave: 10/10 postponed posts, IDs 12471–12480;
- draft PR #29 is superseded and prohibited.

Long-form local evidence requiring exact reconciliation:

- reviewed newer-than-boundary items: `27`;
- already present: `1`;
- verified missing: `26`;
- SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- local evidence: `data\vk-upload\verified-longform-26`;
- owner issue: #31.

Wall/live status: `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### `legendary-poet`

- YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`;
- OAuth alias: `legendary-poet`;
- VK community: `235216998`;
- VK owner: `-235216998`.

Latest retained reviewed Shorts matrix:

- 56 exact YouTube Shorts;
- 41 exact YouTube→VK pairs;
- 15 confirmed missing;
- 0 ambiguous;
- 0 extra vertical VK objects;
- `BXZeRiEOHmQ` maps to VK `-235216998_456239039`;
- old `59/40/19/1` matrix is retired;
- V3 canary preparation exists, but completed V3 Apply/postflight is not proven.

Status: `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Do not run the old package or upload the 15 candidates until the exact V3 canary/apply state and journal are recovered, converted into Wave 6 evidence, and reconciled through the supported operator and merged lifecycle/wall contracts.

## Next engineering wave

Wave 8 / issue #86 owns exact matching, catalog identity, and media correctness without live provider mutation:

- deterministic exact-first matching with explicit ambiguity/conflict states;
- field-specific Unicode/text/URL normalization that preserves original evidence;
- exact album/catalog identity rather than normalized-title-only selection;
- semantic membership comparison independent of provider position churn;
- authoritative downloader final path and cache identity;
- ffprobe-equivalent structured duration/stream/container/playability validation;
- exact thumbnail identity and caller-owned selected-thumbnail postflight;
- provider writes in development and CI: 0.

Issue #33 remains the later catalog/publication workflow and stays blocked by exact queue reconciliation under issues #31 and #32.

## Active issue graph

- #31 — long-form result and ledger reconciliation;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #37 — exact approved wall-cleanup scope;
- #38 — Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #86 — active Wave 8 exact matching/catalog/media correctness;
- #36/#65/#67/#69/#72/#76/#80 — completed wave issues.

## Global prohibitions

- Do not mix `lord-god-strength` and `legendary-poet` IDs, credentials, links, journals, or manifests.
- Do not repeat completed Waves 0–7.
- Do not blind-retry `video.save`, upload-server POST, `wall.post`, `wall.edit`, `wall.delete`, or any ambiguous mutation.
- Do not execute a retired Python or PowerShell provider-write wrapper.
- Do not infer live success from green CI, an old package, a duration/format heuristic, a visible object, stdout wording, or a stale count.
- Do not perform bulk deletion outside issue #37’s exact immutable scope.