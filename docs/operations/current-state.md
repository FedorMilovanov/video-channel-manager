# Current operational state

Updated: 2026-08-05  
Verified Wave 13 closure code baseline: `main@8d6a5ba243788e7b95b0e8a57eb02fb10eaf12ba`  
Program state: `WAVES_0_13_COMPLETED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`  
Current machine state: [`audit-register-v6-2026-08-05.json`](audit-register-v6-2026-08-05.json)  
Final disposition predecessor: [`audit-register-v5-2026-08-05.json`](audit-register-v5-2026-08-05.json)  
Immutable predecessors: [`audit-register-v4-2026-08-05.json`](audit-register-v4-2026-08-05.json), [`audit-register-v3-2026-08-05.json`](audit-register-v3-2026-08-05.json), [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json)

This file and the v6 machine-state overlay override old chats, screenshots, ZIP names, remembered counts, stale issue wording, and superseded audits.

## Final status

Waves 0–13 are complete. There is no active operational issue, provider mutation plan, approved replay, or pending repository PR after this completed-state merge.

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

Closed historical issues #2–#5, #37, #118, #122, and #126 remain closed and provide no parallel execution authority.

Do not group #32/#38 as Legendary Poet. Historical ownership was: #32 Lord God, #38 shared, #119 Legendary Poet. All three are now closed with the exact dispositions above.

## Permanent unknown and replay boundary

`M5hNecL_MsQ → -235216998_456239160` was observed as ordinary `video` with `is_draft=1`. It is not native Clip success and must not be retransmitted.

The six undispatched Legendary Poet long items, Lord God provisional Shorts queues, article-wall launcher generations, retired cleanup/reset packages, and deferred playlist mutation design are not active work and must not be executed.

## Permanent safety rules

- Provider writes remain unauthorized.
- Never rerun retired V1/V2/V3/V4, reset, recovery, article-wave, transfer, cleanup, or playlist executors.
- Never blind-retry intent-persisted, accepted, processing, verified, or unknown operations.
- Existing VK and YouTube objects remain untouched by Wave 13 closure.
- Package A, green CI, dashboards, previews, issue bodies, counts, ZIP names, save responses, or visible objects never authorize writes.
- Every future provider write requires a new user request, a new exact project-bound owning issue, a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
- VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`.

## Next allowed action

No operational continuation is pending. Future work begins only from a new explicit user request and a new exact issue; closed issues and historical packages must not be reopened as execution authority.
