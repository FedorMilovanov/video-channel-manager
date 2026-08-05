# Current operational state

Updated: 2026-08-05  
Verified Wave 14 repository-polish code baseline: `main@626f83c6e5c068d7faa8b6d14163b42916faa769`  
Program state: `WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`  
Current machine state: [`audit-register-v7-2026-08-05.json`](audit-register-v7-2026-08-05.json)  
Immutable predecessor: [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json)  
Earlier immutable predecessors: [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json), [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json), [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json), [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file and the v7 machine-state overlay override old chats, screenshots, ZIP names, remembered counts, stale issue wording, superseded audits, and old README/roadmap status blocks.

## Final status

Waves 0–14 are complete. There is no active operational reconciliation, transfer queue, catalog wave, article-wall continuation, playlist mutation, cleanup/reset executor, approved replay, provider mutation plan, or repository backlog after the Wave 14 state-sync merge.

Wave 13 disposition proof:

- PR #128;
- exact head `731cc247a0c757c7103cd1ce5336adaf125d04d0`;
- merge/code baseline `8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba`;
- CI `30992600857`;
- Python 3.11/3.12/3.13: `792 passed, 1 xfailed`;
- coverage: `78%` across `14,306` statements;
- Ruff correctness and formatting: green;
- strict mypy: `145 source files`;
- dependency audit: no known vulnerabilities;
- Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux: green;
- provider queries/writes/write plans during Wave 13: `0/0/0`.

Wave 13 completed-state sync proof:

- PR #129;
- exact head `44a1590fac0e8fe8b563d35cfd68f2bed4727743`;
- merge `07388521e8d3a2c5d501382227c35bdce6e6470e`;
- CI `30994245235`;
- Python 3.11/3.12/3.13: `796 passed, 1 xfailed`;
- coverage: `78%` across `14,306` statements;
- Ruff formatting: `449 files already formatted`;
- strict mypy: `145 source files`;
- dependency audit: no known vulnerabilities;
- all three PowerShell environments: green;
- provider queries/writes/write plans: `0/0/0`.

Wave 14 repository polish proof:

- issue #130;
- PR #131;
- exact head `80f701b6926a5a9c788b99c69634b54d63ed1862`;
- merge/code baseline `626f83c6e5c068d7faa8b6d14163b42916faa769`;
- CI `31000834701`;
- Python 3.11/3.12/3.13: `801 passed, 1 xfailed`;
- coverage: `78%` across `14,306` statements;
- Ruff correctness: green;
- Ruff formatting: `451 files already formatted`;
- strict mypy: `145 source files`;
- dependency audit: no known vulnerabilities;
- Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux: green;
- changed files: `7`; runtime/provider code files: `0`;
- provider queries/writes/write plans/historical executor runs: `0/0/0/0`.

Wave 14 removed stale initial-roadmap wording, stale CI/test counts, and playlist-as-next-stage claims; made the no-write boundary prominent; added repository-wide JSON/Markdown integrity regressions; and made a scheduled photo-rehost test deterministic by freezing only its test clock. Production provider behavior did not change.

Green CI proves repository contracts and fixtures. It does not authorize a future provider mutation.

## Credential model

VK uses one shared **user access token** from external `VK_API_TOKEN`. The local VK alias `legendary-poet` names the stored credential and is not a project selector.

Project isolation still requires exact `project_key`, community/owner IDs, manifests, plans, journals, results, and link profiles.

YouTube OAuth aliases remain channel-specific:

- OAuth alias `fedor-milovanov` → Lord God channel `UCeSJsC6go2c9pdJCuUI1BYA`;
- OAuth alias `legendary-poet` → Legendary Poet channel `UC-78ys2S3cQ3lpqgXfo-SvQ`.

## Closed operational graph

### Completed

- #31 — Lord God long-form reconciliation: exact queue `26/26`, missing `0`, thumbnail repairs `26/26`, album postflight complete.
- #119 — Legendary Poet Shorts/Clips reconciliation: bounded source `56`; 41 reviewed prior pairs; 8 verified new `short_video` outcomes; one accepted long ordinary-video/draft canary remains non-replayable; six long items were never dispatched. This does not claim all 56 are native Clips.
- #38 — shared VK native Clip/ordinary-video provider-mode and final-type contract: native Clip success requires final `type=short_video`, processing complete, non-draft state, and exact public visibility.

### Retired / not planned

- #32 — non-authoritative Lord God 108-item Shorts auto-upload scope retired; old provisional 65/108 and 108/108 outputs remain `DO_NOT_UPLOAD`; completed #37 reset evidence and protected post `12400` are preserved.
- #33 — broad Lord God catalog/editorial/postponed-wall continuation retired without new writes.
- #99 — unproved Legendary Poet article-wall launcher continuation cancelled; existing remote objects remain untouched.
- #123 — deferred YouTube playlist mutation scope retired; no playlist write is authorized.

Closed historical issues #2–#5, #37, #64, #118, #122, #126, #127, and #130 remain closed and provide no execution authority.

Do not group #32/#38 as Legendary Poet. Historical ownership was: #32 Lord God, #38 shared, #119 Legendary Poet. All three are now closed with the exact dispositions above.

## Permanent unknown and replay boundary

`M5hNecL_MsQ → -235216998_456239160` was observed as ordinary `video` with `is_draft=1`. It is not native Clip success and must not be retransmitted.

The six undispatched Legendary Poet long items, Lord God provisional Shorts queues, article-wall launcher generations, retired cleanup/reset packages, and deferred playlist mutation design are not active work and must not be executed.

## Repository integrity boundary

- Every tracked JSON file must parse.
- Local Markdown links must resolve after code examples, anchors, external URLs, and explicit placeholders are excluded.
- README and security documents must say that provider writes, replay, deletion, and mutation plans are unauthorized.
- Historical commands document capability and safety protocol; they do not grant execution authority.
- Wall-clock-sensitive tests must freeze their own clock.

## Permanent safety rules

- Provider writes remain unauthorized.
- Never rerun retired V1/V2/V3/V4, reset, recovery, article-wave, transfer, cleanup, or playlist executors.
- Never blind-retry intent-persisted, accepted, processing, verified, or unknown operations.
- Existing VK and YouTube objects remain untouched by Waves 13–14 closure and polish.
- Package A, green CI, dashboards, previews, issue bodies, counts, ZIP names, save responses, visible objects, README commands, or roadmap text never authorize writes.
- Every future provider write requires a new user request, a new exact project-bound owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
- VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

## Next allowed action

No operational continuation is pending. Future work begins only from a new explicit user request and a new exact issue; closed issues and historical packages must not be reopened as execution authority.
