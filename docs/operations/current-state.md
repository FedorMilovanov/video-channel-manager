# Current operational state

Updated: 2026-08-07  
Repository baseline entering hardening: `main@c0b8a303598788b2870862042d2e2868a97b3005`  
Initial postponed-text capability merge: `c04f0a4f948174ced6287e4bae87e4bf1be2be52`  
Hardening implementation commit: `f7e0a7dc0a6ad965045783638c25384d69fe6b08`  
Owning hardening: issue #152 / PR #153  
Current machine state before final quality proof: [`audit-register-v10-2026-08-06.json`](audit-register-v10-2026-08-06.json)  
Second-pass audit: [`vk-postponed-text-second-pass-audit-2026-08-06.md`](vk-postponed-text-second-pass-audit-2026-08-06.md)

The newest audit-register overlay, this file, and the exact `main` Git ref override old chats, screenshots, ZIP names, remembered counts, stale issue wording, and superseded executors. Historical evidence never authorizes execution.

## Executive state

The 2026-08-06 Lord God cleanup is complete and verified. No continuation or replay is pending.

The reusable VK postponed-text capability has been hardened in PR #153. Its supported v1 boundary is existing **attachment-free postponed posts only**. PR #153 is repository-only and performs no VK reads or writes.

Issue #152 remains open until the exact final PR head receives all six green CI jobs, scope review is complete, and PR #153 is merged. Until then, no new provider execution is authorized from this hardening work.

## Historical operation proof

Exact operation identity:

- project `lord-god-strength`;
- VK community `60805374`, owner `-60805374`;
- local credential alias `legendary-poet` — credential name only, not project selector;
- attachment-free target postponed IDs `12513..12541`;
- target count `29`;
- postponed baseline `66`;
- non-target postponed rows `37`;
- approved plan SHA `sha256:8dcbe984cb24e003770fa3897ff3b7da351a34d92d4931ac3cb9a5707d2c1cbb`.

Final verified result:

- `29/29` exact after-state;
- `0` pending;
- postponed count `66/66`;
- 37 non-target postponed rows unchanged;
- published first quote post untouched;
- no Telegram objects touched;
- final status `succeeded`.

These facts prove the completed operation only. They do not authorize another request or prove unsupported attachment behavior.

## Supported postponed-text capability

Canonical Python CLI:

```powershell
video-manager-vk-postponed-text plan REQUEST.json --output PLAN.json --account legendary-poet
video-manager-vk-postponed-text reconcile PLAN.json --output RECONCILE.json --account legendary-poet
video-manager-vk-postponed-text apply PLAN.json `
  --output-dir data/operator/EXACT-RUN `
  --account legendary-poet `
  --confirm-plan-sha256 sha256:... `
  --enable-provider-writes
```

Canonical PowerShell wrapper:

```powershell
& .\scripts\Invoke-VkPostponedTextEdit.ps1 `
  -Command plan `
  -InputPath .\request.json `
  -OutputPath .\plan.json `
  -AccountAlias legendary-poet
```

PowerShell invokes only the package CLI. It has no token handling and no direct VK API transport.

Schema v1 requires:

- exact project/community/owner/post identity;
- sorted unique target IDs;
- complete published and postponed preflight;
- expected postponed count;
- exact line-removal match counts;
- immutable request and plan digests;
- exact before/after text and original `publish_date`;
- `allow_attachments: false` and no target attachments;
- one stable account/community lock independent of output directory;
- time-to-publication verification before every dispatch and retry;
- intent-before-dispatch and exact postflight;
- no blind retry;
- terminal child journals consistent with aggregate result;
- final target, count, and raw non-target fingerprint proof.

Full contract: [`vk-postponed-text-edit-runbook-2026-08-06.md`](vk-postponed-text-edit-runbook-2026-08-06.md).

## Hardening delivered by PR #153

The second-pass audit found and PR #153 corrects:

1. output-directory-scoped lock replaced by a stable data-directory account/community lock;
2. one-time publication-distance check supplemented by checks immediately before every dispatch and controlled retry;
3. delayed reconciliation journal rewritten to terminal verified state;
4. broad attachment claims narrowed to attachment-free schema v1;
5. non-target comparison hardened with ordered raw attachment-payload digests;
6. output directories protected from cross-plan reuse and journal overwrite;
7. repository-owned strict PowerShell wrapper added;
8. Pester coverage added for read-only/apply arguments, explicit authority, native exit propagation, and absence of token/provider code;
9. Python regressions added for ambiguous postflight, shared lock, threshold crossing, retry threshold, delayed journal consistency, attachment rejection, and non-target attachment-order mutation;
10. stale `AGENTS.md` and runbook claims corrected.

No provider call or write is part of this hardening.

## Retry and stop contract

A retry is allowed only after exact readback proves the previous dispatch had no effect. Before retry, the workflow waits, reads again, and rechecks publication distance.

Stop without another mutation when:

- any full read is incomplete;
- postponed count differs;
- target identity/date/text differs;
- a target has any attachment;
- publication is too close;
- provider effect is unknown;
- CAPTCHA is required;
- a non-target raw fingerprint changes;
- plan digest differs;
- output directory belongs to another plan;
- another local writer holds the account/community lock.

`confirmed_absent`, `captcha_required_confirmed_absent`, and `unknown_requires_reconciliation` remain distinct states.

## CI process record

PR #150 exact head `0bfb1260c37411e8df686f26120ceea85e2f8116` was merged as `c04f0a4f948174ced6287e4bae87e4bf1be2be52` after manual review because Actions runs #3208/#3209 remained queued and both cancellation endpoints returned HTTP 502.

That incident was honestly recorded but was not green CI. Issue #152 and PR #153 exist partly to obtain the missing real quality proof. An infrastructure exception must not be treated as successful tests.

## Project and credential boundary

Two projects remain distinct:

- `lord-god-strength` — VK community `60805374`, owner `-60805374`;
- `legendary-poet` — VK community `235216998`, owner `-235216998`.

The local VK alias `legendary-poet` names a stored shared user credential. Exact project key and community/owner IDs select the project.

Never print, package, commit, log, request manual entry of, or put the VK token on a command line.

## Inherited capabilities and exclusions

Wave 16 predecessor `main@22ed56256df3388c23c9f785f1e02cca71fd8524` remains immutable evidence for:

- Node 24-generation immutable Action pins;
- explicit SQLite closure;
- local MP3 manifest schema 1.1;
- fail-closed MP3 identity conflicts;
- deterministic 1,000-track local planning.

Local MP3 remains read-only intake/manifest work. VK Audio upload, browser automation, playlist mutation, article-wall replay, broad catalog continuation, ID3 rewrite, rename, and transcode are not authorized by postponed-text hardening.

Historical cleanup ZIPs, browser packages, transfer/reset/recovery executors, and article-wave scripts are evidence only and must not be rerun.

## Operational graph

Completed historical scopes:

- #31 — Lord God long-form reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared VK final-type contract;
- #130 — repository integrity polish;
- #133 — adaptive reasoning and local-only MP3 foundation;
- #137 — CI, SQLite, and MP3 identity hardening;
- #147 — initial postponed-text capability and retrospective.

Active repository-only scope:

- #152 / PR #153 — second-pass audit, hardening, tests, wrapper, state correction, and real quality proof.

Retired or not planned:

- #32 — non-authoritative Lord God Shorts auto-upload;
- #33 — broad Lord God catalog/publication continuation;
- #99 — unproved Legendary Poet article-wall continuation;
- #123 — deferred YouTube playlist mutation.

## Next allowed action

Finish exact-head six-job CI and review for PR #153. After green merge, close issue #152 and record the merge/CI proof in the newest machine-state overlay.

No VK operation is pending. Any future provider work starts from a new explicit user request, exact owning issue, newly generated reviewed plan, and exact postflight.
