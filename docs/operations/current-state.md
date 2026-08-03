# Current operational state

Updated: 2026-08-04  
Repository baseline: `main@43070fb4eb04bd2c1055bcc45e3881996f39aad7`  
Canonical audit: [`master-audit-2026-08-04.md`](master-audit-2026-08-04.md)  
Machine register: [`audit-register-2026-08-04.json`](audit-register-2026-08-04.json)

This is the first file to read before any YouTube/VK work. Chat history, screenshots, remembered counts, and retired package instructions do not override this state.

## Current engineering mode

`WAVE_0_CANONICAL_STATE_COMPLETE / WAVE_1_UPLOAD_STATE_MACHINE_NEXT`

No VK or YouTube provider write is authorized by Wave 0. Live queue completion and retransmission remain blocked until the upload reservation/recovery state machine in issue #65 is merged and the relevant local ledgers are reconciled.

## Project boundary

The repository manages two separate projects. Their exact IDs and links are in [`project-identity-registry.md`](project-identity-registry.md).

### `lord-god-strength`

- YouTube channel: `UCeSJsC6go2c9pdJCuUI1BYA`
- YouTube OAuth alias: `fedor-milovanov`
- current documented YouTube access: read-only
- VK community: `60805374`
- VK owner: `-60805374`
- shared VK credential alias: `legendary-poet` — credential label only

### `legendary-poet`

- YouTube channel: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- YouTube OAuth alias: `legendary-poet`
- VK community: `235216998`
- VK owner: `-235216998`

Never infer project identity from the shared VK alias. Every operation must bind `project_key`, exact provider IDs, and the matching registered link profile.

## Verified repository baseline

### Closed reliability work

PR #61, merge `51cc2144508c33adf78380ab35e32ee88c10f90f`:

- exact project identity and cross-project fail-closed guards;
- project-bound publication rendering and guarded legacy plan upgrade;
- SQLite WAL, `busy_timeout=5000`, and `foreign_keys=ON`.

PR #62, merge `55477df06ae0ae5238634aad829ba2fe8fe70fd7`:

- persistent owned/borrowed HTTP clients for VK and YouTube inventory reads.

PR #63, merge `b19d4faa7e58ff4c0ae7f974092e9fd2441c571d`:

- persistent clients for VK video/thumbnail writers, YouTube description writer, OAuth exchange/refresh, and VK processing polling;
- ambiguous mutations remain non-retryable by default.

### Current code blockers

The following are confirmed on the 2026-08-04 baseline and block broad upload continuation:

1. base sync journals the upload only after reservation, transfer, and processing verification;
2. a visible journal `remote_id` can be reused without verified stage/readiness/content reconciliation;
3. upload readiness is weaker than the required exact duration/type/playability/source postcondition;
4. content preview/plan loading does not run full per-record validation;
5. the supported textsafe wrapper still monkeypatches a directly executable Poet-hardcoded base sync;
6. YouTube read requests have no bounded transient retry;
7. provider transport, limiter, PowerShell runner, wave-generation, coverage, album identity, and media-cache work remain in later waves.

Issue #65 owns the immediate upload state-machine P0. Issue #64 owns the remaining reliability roadmap.

## `lord-god-strength` operational state

### Closed — do not rerun

- reviewed VK duplicate cleanup: `403 confirmed_deleted`, `0 planned`, `0 unresolved`;
- exact transfer boundary YouTube `KobOzfBqzic` is already present and must never be uploaded again;
- YouTube `s512Opa8Eu4` is already mapped to VK `-60805374_456241938`;
- 34 reviewed low-view Shorts were replaced by ordinary videos; their generated wall posts were removed; protected post `12400` remained present;
- theological article photo wave: `10/10` verified postponed posts, IDs `12471–12480`, scheduled 2026-08-04 through 2026-08-13; Apply must not be repeated.

### Requires local/live reconciliation

Long-form queue:

- reviewed queue size: `26`;
- queue SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- local evidence directory: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26`;
- tracked by issue #31;
- no accepted, processing, or unknown row may be retransmitted before exact live reconciliation.

Shorts/Clips:

- canonical source inventory recorded as `108` Shorts;
- final accepted/processing objects and final `short_video` types still require exact reconciliation;
- tracked by issues #32 and #38;
- keep Shorts and long-form in separate manifests and ledgers.

Wall:

- upload and wall publication remain separate operations;
- immediate publication is blocked by default;
- issue #36 owns the universal upload/wall contract and fresh published+postponed audit;
- issue #37 is limited to its exact approved post-boundary cleanup scope;
- `guid` is only an additional short-window guard, not complete idempotency.

Catalog/publishing:

- issue #33 remains blocked until upload, Shorts, and wall unknown outcomes are resolved;
- do not begin combined catalog/description/wall/audio mutation work.

## `legendary-poet` operational state

Latest supplied reviewed Shorts matrix:

- 56 exact YouTube Shorts;
- 41 exact YouTube→VK pairs;
- 15 confirmed missing;
- 0 ambiguous;
- 0 extra vertical VK objects;
- `BXZeRiEOHmQ` maps to VK `-235216998_456239039`;
- the old `59/40/19/1` matrix is retired;
- two protective stops performed no new VK writes;
- a V3 canary package was prepared, but completed V3 Apply/postflight is not proven in the retained evidence.

Current status: `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

Do not run the old package or upload the 15 candidates until the exact V3 canary/apply state is recovered and the Wave 1 lifecycle is available.

## Separate VK Audio browser workflow

The browser-based VK Audio automation belongs to the adjacent `mp3telegrambot` workflow. It uses a browser profile and undocumented web contracts. Treat it as a separate state machine and do not import it into the VK Video API core without a formal manifest/result/unknown-outcome interface.

## Active issue graph

- #31 — reconcile the 26-item long-form result and ledger;
- #32 — exact VK Clips inventory and Shorts queue;
- #33 — catalog and publishing after dependencies;
- #36 — upload-triggered wall safety and postponed publishing;
- #37 — exact approved Shorts wall cleanup scope;
- #38 — VK Shorts upload modes and final player/type behavior;
- #64 — master reliability roadmap after PR #61–63;
- #65 — Wave 1 journaled upload state machine and recovery.

## Next allowed work

1. Implement issue #65 on one isolated branch/PR.
2. Run offline state-transition and crash fault-injection tests.
3. Preserve all project identity, media QC, lock, and no-blind-retry guarantees.
4. Merge only after exact-head CI on Python 3.11/3.12/3.13.
5. Perform no live queue retransmission as part of the code PR.
6. After Wave 1 merge, reconcile local ledgers before any canary or resume.

## Update protocol

After every wave or operational run, update this file with:

- exact repository HEAD;
- selected `project_key` and exact provider IDs;
- manifest/plan digest;
- attempted, reserved, accepted, processing, verified, rejected, and unknown counts;
- result and ledger paths;
- whether retry is safe;
- exact remaining work;
- linked issue/PR;
- any new provider-contract, identity, media, wall, wrapper, or packaging failure.
