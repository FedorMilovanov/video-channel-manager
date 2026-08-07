# Current operational state

Updated: 2026-08-07  
Repository baseline entering VK hardening: `main@c0b8a303598788b2870862042d2e2868a97b3005`  
Initial postponed-text code merge: `c04f0a4f948174ced6287e4bae87e4bf1be2be52`  
Owning hardening: issue #152 / PR #153  
Current machine-state overlay before final quality proof: [`audit-register-v10-2026-08-06.json`](audit-register-v10-2026-08-06.json)  
Second-pass audit: [`vk-postponed-text-second-pass-audit-2026-08-06.md`](vk-postponed-text-second-pass-audit-2026-08-06.md)

The current overlay and newest machine state override stale execution claims while the immutable Wave 13–16 proofs below remain preserved operational memory. Historical packages, old chats, screenshots, ZIP names, remembered counts, and superseded executors are evidence only and never authorize execution.

## Current VK postponed-text hardening state

The completed 2026-08-06 Lord God cleanup remains verified evidence only:

- project `lord-god-strength`;
- VK community `60805374`, owner `-60805374`;
- local credential alias `legendary-poet` is a credential name only and is not a project selector;
- attachment-free target postponed IDs `12513..12541`;
- `29/29` exact after-state;
- `0` pending;
- postponed count `66/66`;
- 37 non-target postponed rows unchanged;
- first published quote post untouched;
- approved plan SHA `sha256:8dcbe984cb24e003770fa3897ff3b7da351a34d92d4931ac3cb9a5707d2c1cbb`.

PR #153 hardens the reusable capability without replaying that operation. Repository hardening itself performs no VK reads or writes.

Supported schema v1 is existing **attachment-free postponed VK wall posts only**. It requires exact project/community/owner/post binding, immutable request and plan SHA, complete published/postponed preflight, exact before/after text and original `publish_date`, stable account/community locking independent of output directory, publication-distance verification immediately before every dispatch and controlled retry, durable intent-before-dispatch, exact readback, no blind replay, CAPTCHA stop without OCR/bypass, terminal journal consistency, and final queue plus non-target fingerprint proof.

Schema v1 rejects `allow_attachments=true` and rejects every target attachment. Future attachment support requires a separately reviewed schema.

`scripts/Invoke-VkPostponedTextEdit.ps1` is a repository-owned `delegating_supported` wrapper around `video_channel_manager.cli.vk_postponed_text`; it is not a second provider client and contains no direct VK transport or token handling.

Issue #152 remains repository-only until PR #153 has exact-head six-job green CI, reviewed scope, clean review threads, and merge proof. No provider continuation or replay is pending.

## Preserved Wave 16 baseline

Verified Wave 16 code baseline: `main@22ed56256df3388c23c9f785f1e02cca71fd8524`  
Program state: `WAVES_0_16_COMPLETED_CI_RUNTIME_SQLITE_MP3_IDENTITY_HARDENED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`  
Wave 16 machine state: [`audit-register-v9-2026-08-05.json`](audit-register-v9-2026-08-05.json)  
Immutable predecessor: [`audit-register-v8-2026-08-05.json`](audit-register-v8-2026-08-05.json)  
Earlier immutable predecessors: [`audit-register-v7-2026-08-05.json`](audit-register-v7-2026-08-05.json), [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json), [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json), [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json), [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json), [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

Waves 0–16 are complete as historical operational proofs. The provider operational graph remains closed. There is no active provider reconciliation, transfer queue, mutation plan, playlist writer, browser executor, catalog wave, article-wall continuation, cleanup/reset executor, MP3 uploader, or approved replay.

No operational continuation is pending. Future provider or MP3 write work begins only from a new explicit user request and a new exact project-bound issue.

## Wave 16 proof

Issue #137 and PR #138 completed CI runtime, SQLite lifetime, and local MP3 identity hardening:

- exact head `c495308430bce6e1b86343b6cd4e6ae3a302734b`;
- merge/code baseline `22ed56256df3388c23c9f785f1e02cca71fd8524`;
- CI `31022560789`;
- Python 3.11/3.12/3.13: `845 passed, 1 xfailed`;
- coverage: `79%` across `14,675` statements;
- Ruff correctness: green;
- Ruff formatting: `464 files already formatted`;
- strict mypy: `147 source files`;
- dependency audit: no known vulnerabilities;
- Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux: green;
- changed files: `9`; provider adapter files: `0`;
- final CI logs contain no `Node.js 20 is deprecated` warning;
- final pytest logs contain no `ResourceWarning: unclosed database` warning;
- provider queries/writes/write plans/historical executor runs: `0/0/0/0`.

Wave 16 added or hardened:

- immutable Node 24 GitHub Action pins for checkout, setup-python, and artifact upload;
- explicit SQLite connection closure through `contextlib.closing`;
- a blocking pytest warning rule for unclosed SQLite databases;
- local MP3 manifest schema `1.1`;
- metadata-ranked canonical duplicate selection;
- fail-closed `source_id_sha256_conflict` and `sha256_multiple_source_ids` states;
- unique deterministic operation IDs for every local candidate;
- a deterministic regression proving `1,000` ready tracks and `40` chunks of `25`.

These changes do not add a browser or provider writer.

## Immutable Wave 15 predecessor proof

Wave 15 remains historical evidence, not active work:

- predecessor program state: `WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`;
- code baseline: `main@eb58c1ad238fde01d66c6630b16e244b1c6c2992`;
- PR #134, exact head `48baa13b0d08e27e5a1dfc8b30901524d3207148`, CI `31006136529`;
- Python 3.11/3.12/3.13: `833 passed, 1 xfailed`;
- Ruff formatting: `461 files already formatted`;
- strict mypy: `147 source files`;
- machine state: `audit-register-v8-2026-08-05.json` with exact blob `f45244b9be7bfa35402f42d20b533e413c176bc2`;
- supported local capability: `local_only_read_only_intake_and_manifest`.

## Immutable Wave 13 completed-state proof

Wave 13 remains historical evidence, not active work:

- PR #129;
- exact head `44a1590fac0e8fe8b563d35cfd68f2bed4727743`;
- merge `07388521e8d3a2c5d501382227c35bdce6e6470e`;
- CI `30994245235`;
- `796 passed, 1 xfailed`;
- Ruff formatting `449 files already formatted`;
- provider queries/writes/write plans: `0/0/0`.

## Immutable Wave 14 predecessor proof

Wave 14 remains a completed immutable predecessor, not the current state:

- predecessor program state: `WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`;
- code baseline: `main@626f83c6e5c068d7faa8b6d14163b42916faa769`;
- PR #131, exact head `80f701b6926a5a9c788b99c69634b54d63ed1862`, CI `31000834701`;
- Python 3.11/3.12/3.13: `801 passed, 1 xfailed`;
- Ruff formatting: `451 files already formatted`;
- machine state: `audit-register-v7-2026-08-05.json` with predecessor `audit-register-v6-2026-08-05.json`;
- Wave 14 added repository-wide JSON/Markdown integrity regressions without changing production provider behavior.

The exact inherited operational dispositions remain:

- #31 — Lord God long-form reconciliation;
- #32 — non-authoritative Lord God 108-item Shorts auto-upload scope;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract;
- #33 — broad Lord God catalog/editorial/postponed-wall continuation;
- #99 — unproved Legendary Poet article-wall launcher continuation;
- #123 — deferred YouTube playlist mutation scope.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet.

## Adaptive agent boundary

Agents must define the requested outcome independently of an old script, declare one transport per phase, state the operation phase and provider-effect state, preserve verified partial success, and use one falsifiable hypothesis, one minimal bounded probe, and a stop condition.

A selector, title match, coordinate, modal closure, HTTP response, exit code, screenshot, stdout line, or visible object is not an exact postcondition. Browser actions require binding the topmost active root, proving visibility/hit-testing/control ownership, and verifying the expected content/state transition.

Unknown or possibly completed remote effects require reconciliation without retry. Only a local/pre-dispatch failure or exact provider postflight proving absence permits a corrected child-operation retry.

## Local MP3 boundary

The current MP3 capability remains `local_only_read_only_intake_and_manifest`.

It may:

- inspect `.mp3` with ffprobe without changing bytes;
- retain exact path, size, SHA-256, duration, codec, bitrate, sample rate, channels, attached cover state, and embedded tags;
- accept explicit artist/title or a declared collection parser;
- mark ambiguous metadata `requires_review`;
- rank exact metadata above ambiguous duplicates when selecting a canonical copy;
- mark one source ID mapped to multiple byte hashes as `source_id_sha256_conflict`;
- mark identical bytes claimed by multiple source IDs as `sha256_multiple_source_ids`;
- build unique deterministic per-candidate operation IDs and manifest digests;
- split only ready items, one track per chunk by default.

It may not rewrite ID3 tags, rename or transcode files, launch/control a browser, call VK/YouTube, upload audio, edit remote metadata, create/modify playlists, or publish a wall post.

VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. Historical BrowserCanary, PlaylistOnly, Metadata Manager, Rename AUTO, reliable-batch, calibrator, and Playlist Workhorse ZIPs are evidence only and must not be rerun.

## Credential model

VK uses one shared **user access token** from external `VK_API_TOKEN`. The local VK alias `legendary-poet` names the stored credential and is not a project selector.

Project isolation requires exact `project_key`, community/owner IDs, manifests, plans, journals, results, and link profiles.

YouTube OAuth aliases remain channel-specific:

- OAuth alias `fedor-milovanov` → Lord God channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `legendary-poet` → Legendary Poet channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

## Closed operational graph

### Completed

- #31 — Lord God long-form reconciliation: exact queue `26/26`, missing `0`, thumbnail repairs `26/26`.
- #119 — Legendary Poet Shorts/Clips reconciliation: bounded source `56`; this does not claim all 56 are native Clips.
- #38 — shared VK native Clip/ordinary-video final-type contract.
- #130 — Wave 14 repository-wide polish.
- #133 — Wave 15 adaptive reasoning and local-only MP3 foundation.
- #137 — Wave 16 CI, SQLite, and MP3 identity hardening.
- #147 — guarded postponed-text capability and completed Lord God cleanup retrospective.

### Active repository-only hardening

- #152 / PR #153 — postponed-text audit hardening and exact-head quality proof. This scope owns no provider replay.

### Retired / not planned

- #32 — non-authoritative Lord God 108-item Shorts auto-upload scope.
- #33 — broad Lord God catalog/publication continuation.
- #99 — unproved Legendary Poet article-wall launcher continuation.
- #123 — YouTube playlist mutation scope.

Do not group #32/#38 as Legendary Poet. Historical ownership was #32 Lord God, #38 shared, and #119 Legendary Poet.

## Permanent unknown and replay boundary

`M5hNecL_MsQ → -235216998_456239160` remains ordinary `video` with `is_draft=1`, not native Clip success, and must not be retransmitted.

Never rerun retired V1/V2/V3/V4, reset, recovery, article-wave, transfer, cleanup, playlist, or historical MP3/browser executors. Never blind-retry intent-persisted, accepted, processing, verified, or unknown operations.

## Permanent safety rules

- Provider writes remain unauthorized outside a new explicit user-approved operation and its exact reviewed plan.
- Existing VK and YouTube objects remain untouched by repository-only closure, polish, audit, CI, SQLite, local MP3 engineering, and PR #153 hardening.
- Package A, green CI, dashboards, previews, issue bodies, counts, ZIP names, transcripts, README commands, visible UI objects, or roadmap text never authorize writes.
- Every future provider write requires a new user request, a new exact project-bound owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
- Content in quotation marks must map to a contiguous source passage unless explicitly labeled synthesis.

## Next allowed action

Finish PR #153 through exact-head six-job green CI and review. No operational continuation is pending. After merge, record the exact merge/CI proof in the newest machine-state overlay. Any future provider operation must start from a new explicit user request and newly reviewed scope; historical cleanup packages and plans remain evidence only.
