# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@1a62779293a404e4654b6230644dfc78e9b20dc1`  
Program state: `WAVE_5_COMPLETED_WAVE_6_NEXT`  
Canonical audit: [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md)  
Machine register: [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json)

This is the first state board to read before YouTube/VK work. Chat history, screenshots, remembered counts, retired packages, and older agent audits do not override it.

## Completed reliability waves

- Wave 0: canonical state and issue ownership;
- Wave 1: durable journaled VK upload lifecycle and exact-ID recovery — PR #66;
- Wave 2: fail-closed project/content identity and supported sync entrypoint — PR #68;
- Wave 3: shared HTTP ownership, safe-read retry taxonomy, redaction, and limiter infrastructure — PR #70;
- Wave 4: fail-closed separation of VK video upload and VK wall publication — PR #71, merge `d85f7cf94b8ba0b30947291b3a08491239438843`;
- Wave 5: one tested fail-closed Windows/PowerShell operator layer — PR #75, merge `1a62779293a404e4654b6230644dfc78e9b20dc1`.

Wave 5 exact-head CI run `30900532613` passed dependency audit, compileall, Ruff, Ruff format, strict mypy, and the full suite on Python 3.11, 3.12, and 3.13: `591 passed, 1 xfailed`. Pester passed `17/17` on Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux. Development and CI performed zero VK or YouTube writes.

Living-state synchronization after the Wave 5 merge is tracked by PR #77 and contains documentation/register/test changes only; it does not authorize or perform provider operations.

## Wave 5 guarantees now in `main`

The PowerShell/operator surface is now explicit:

- 23 production `.ps1` files are classified as 1 `supported`, 3 `compatibility_only`, and 19 `retired`;
- the Pester test `.ps1` is separately registered as test-only;
- every wrapper is bound by a canonical UTF-8/LF SHA-256 stable across CRLF/LF checkouts;
- all 19 historical provider-write wrappers stop before credentials, hard-coded paths, nested shells, or child execution;
- the only supported production entrypoint is `scripts/operator/Invoke-VideoManager.ps1`.

The supported operator requires:

- exact request and manifest paths plus SHA-256 confirmations;
- exact registered project/community/owner/snapshot/count binding;
- exact JSON field types and non-empty strings/arrays;
- output paths that cannot overwrite request or manifest evidence;
- one supported Python 3.11/3.12/3.13 resolver, with strict explicit-path behavior;
- native exit codes and structured sanitized evidence, never human stdout parsing;
- UTF-8 without BOM and atomic JSON replacement;
- an explicit safe-read CLI allowlist;
- non-CI environment, positive operation count, `ambiguous_mutation` classification, and `-EnableProviderWrites` for apply mode.

A nonzero ambiguous mutation is classified `unknown_requires_reconciliation`, is never retry-safe, and is never replayed automatically.

## Live-operation gate

Waves 1–5 close architecture and operator gaps; they do not prove the current remote wall, video inventory, or historical local queue state. Broad live upload/publication remains blocked until the exact project has:

1. a fresh read-only VK video inventory;
2. a fresh complete published+postponed wall snapshot;
3. reconciliation of local result/ledger files not stored in GitHub;
4. an immutable source manifest and digest;
5. one project-bound canary plan;
6. exact postflight evidence proving only the expected remote delta.

No accepted, processing, unknown, or previously verified upload may be replayed from an old package or remembered count.

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

Do not run the old package or upload the 15 candidates until the exact V3 canary/apply state and journal are recovered and reconciled through the supported operator and merged lifecycle/wall contracts.

## Next engineering wave

Wave 6 / issue #76 owns the stable versioned wave engine:

- exact inventory and classification of Python wave generations;
- one versioned plan/apply/reconcile/result contract;
- no private cross-script imports in supported paths;
- read-only legacy adapters and fail-closed retired executors;
- Wave 5 operator calls only the supported engine for apply-capable work;
- provider writes in development and CI: 0.

## Active issue graph

- #31 — long-form result and ledger reconciliation;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #37 — exact approved wall-cleanup scope;
- #38 — Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #76 — active Wave 6 stable wave engine;
- #36/#65/#67/#69/#72 — completed wave issues.

## Global prohibitions

- Do not mix `lord-god-strength` and `legendary-poet` IDs, credentials, links, journals, or manifests.
- Do not repeat completed Waves 0–5.
- Do not blind-retry `video.save`, upload-server POST, `wall.post`, `wall.edit`, `wall.delete`, or any ambiguous mutation.
- Do not infer live success from green CI, an old package, a duration/format heuristic, or a stale count.
- Do not perform bulk deletion outside issue #37’s exact immutable scope.
