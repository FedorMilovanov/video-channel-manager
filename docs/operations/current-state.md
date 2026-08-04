# Current operational state

Updated: 2026-08-04  
Verified code baseline: `main@d85f7cf94b8ba0b30947291b3a08491239438843`  
Program state: `WAVE_4_COMPLETED_WAVE_5_NEXT`  
Canonical audit: [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md)  
Machine register: [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json)

This is the first state board to read before YouTube/VK work. Chat history, screenshots, remembered counts, retired packages, and older agent audits do not override it.

## Completed reliability waves

- Wave 0: canonical state and issue ownership;
- Wave 1: durable journaled VK upload lifecycle and exact-ID recovery — PR #66;
- Wave 2: fail-closed project/content identity and supported sync entrypoint — PR #68;
- Wave 3: shared HTTP ownership, safe-read retry taxonomy, redaction, and limiter infrastructure — PR #70;
- Wave 4: fail-closed separation of VK video upload and VK wall publication — PR #71, merge `d85f7cf94b8ba0b30947291b3a08491239438843`.

Wave 4 exact-head CI run `30895905586` passed dependency audit, compileall, Ruff, Ruff format, strict mypy, and the full suite on Python 3.11, 3.12, and 3.13: `586 passed, 1 xfailed`. Development and CI performed zero VK or YouTube writes.

## Wave 4 guarantees now in `main`

The supported VK upload path:

- binds an immutable self-digested `wall_mutation_authorized=false` policy;
- sends `wallpost=0`, `auto_publish=0`, and `repeat=0` explicitly on `video.save`;
- captures complete published+postponed wall evidence before the first batch mutation;
- binds every upload operation to that baseline;
- requires a clean postflight wall delta before `verified`;
- permits missing-policy migration only before provider dispatch and recomputes operation identity/evidence;
- blocks provider-dispatched historical journals from receiving missing authority retroactively;
- never auto-deletes an unexpected wall object.

The supported VK wall path:

- defaults to postponed publication only;
- requires exact project/community/owner/video/text/time binding;
- requires a timezone-aware future `publish_date` and deterministic `guid`;
- scans published and postponed surfaces for duplicate attachments and schedule collisions;
- performs one ambiguous `wall.post` attempt;
- reconciles a lost response only when exactly one expected postponed post is the sole approved wall delta.

Issue #36 is completed. Issue #37 remains the only owner of its exact reviewed cleanup scope.

## Live-operation gate

Wave 4 closes the architecture gap; it does not prove the current remote wall or historical local queue state. Broad live upload/publication remains blocked until the exact project has:

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

Do not run the old package or upload the 15 candidates until the exact V3 canary/apply state and journal are recovered and reconciled under the merged lifecycle and wall firewall.

## Next engineering wave

Wave 5 / issue #72 owns the reliable Windows/PowerShell operator layer:

- one repository/Python/venv bootstrap;
- checked native exit codes, never stdout wording;
- deterministic UTF-8 structured results;
- exact artifact paths and SHA-256, never newest-file selection;
- supported/compatibility/retired wrapper registry;
- provider writes in development and CI: 0.

## Active issue graph

- #31 — long-form result and ledger reconciliation;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #37 — exact approved wall-cleanup scope;
- #38 — Shorts upload modes and final type/player behavior;
- #64 — master reliability roadmap;
- #72 — active Wave 5 operator layer;
- #36/#65/#67/#69 — completed wave issues.

## Global prohibitions

- Do not mix `lord-god-strength` and `legendary-poet` IDs, credentials, links, journals, or manifests.
- Do not repeat completed Waves 0–4.
- Do not blind-retry `video.save`, upload-server POST, `wall.post`, `wall.edit`, `wall.delete`, or any ambiguous mutation.
- Do not infer live success from green CI, an old package, a duration/format heuristic, or a stale count.
- Do not perform bulk deletion outside issue #37’s exact immutable scope.
