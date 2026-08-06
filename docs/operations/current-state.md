# Current operational state

Updated: 2026-08-06  
Current code baseline: `main@c04f0a4f948174ced6287e4bae87e4bf1be2be52`  
Program state: `WAVES_0_16_COMPLETED_VK_POSTPONED_TEXT_EDIT_SUPPORTED_OPERATIONAL_GRAPH_CLOSED_NO_ACTIVE_PROVIDER_MUTATION`  
Current machine state: [`audit-register-v10-2026-08-06.json`](audit-register-v10-2026-08-06.json)  
Immutable predecessor: [`audit-register-v9-2026-08-05.json`](audit-register-v9-2026-08-05.json)

This file and the v10 overlay override stale baseline text elsewhere in the repository, including the older Wave 16 baseline paragraph in `AGENTS.md`, old chats, screenshots, ZIP names, remembered counts, superseded audits, and earlier local executors. Historical material teaches; it never authorizes execution.

## Current status

The repository now contains a supported, repository-owned capability for exact text editing of existing postponed VK wall posts. Issue #147 was completed by PR #150 and merge `c04f0a4f948174ced6287e4bae87e4bf1be2be52`.

There is no active provider mutation, no queued cleanup continuation, and no authorized replay. The 2026-08-06 Lord God cleanup is complete. Future provider work requires a new explicit user request, a new exact project-bound issue, a reviewed immutable request and plan, durable journals, and exact postflight.

## Supported VK postponed-text capability

Canonical CLI:

```powershell
video-manager-vk-postponed-text plan REQUEST.json --output PLAN.json --account legendary-poet
video-manager-vk-postponed-text reconcile PLAN.json --output RECONCILE.json --account legendary-poet
video-manager-vk-postponed-text apply PLAN.json `
  --output-dir data/operator/EXACT-RUN `
  --account legendary-poet `
  --confirm-plan-sha256 sha256:... `
  --enable-provider-writes
```

The supported implementation is `video_channel_manager.platforms.vk.postponed_text_edit`. PowerShell may invoke the package-owned CLI but must not become a second provider client.

The capability is limited to existing postponed VK wall posts and requires:

- exact project key, community ID, owner ID, and sorted unique post IDs;
- expected full postponed-row count;
- exact line-removal rules and exact expected match counts;
- immutable request and plan digests;
- complete published and postponed wall snapshots;
- exact preservation of `publish_date` and canonical attachment identities;
- an intent journal before every `wall.edit` dispatch;
- exact live readback after every dispatch;
- final proof that every target is exact after-state and every non-target wall object is unchanged.

It does not select targets from text similarity, edit published posts, create posts, move posts between surfaces, reconstruct missing posts, automate CAPTCHA solving, or authorize broad wall cleanup.

Full operating contract and incident history: [`vk-postponed-text-edit-runbook-2026-08-06.md`](vk-postponed-text-edit-runbook-2026-08-06.md).

## Retry and stop contract

There is no blind mutation retry.

A transient error such as HTTP 429 may be retried only after exact postflight proves the previous mutation had no effect and the post still matches the immutable before-state. The supported default cadence is 25 seconds between mutation attempts.

Stop without another mutation when:

- the complete wall snapshot cannot be read;
- postponed count differs from the plan;
- a target is absent from postponed;
- owner, ID, date, attachments, or text differs from exact before/after state;
- provider effect is unknown;
- CAPTCHA is required;
- a non-target wall object changes;
- a post is too close to scheduled publication;
- the confirmed plan digest differs.

`confirmed_absent`, `captcha_required_confirmed_absent`, and `unknown_requires_reconciliation` are separate states and must never be merged into one counter.

## Completed Lord God cleanup: 2026-08-06

Exact identity:

- project: `lord-god-strength`;
- community: `60805374`;
- owner: `-60805374`;
- local VK credential alias: `legendary-poet`;
- target postponed posts: `12513` through `12541`;
- target count: `29`;
- full postponed count: `66`;
- non-target postponed count: `37`;
- approved plan SHA-256: `sha256:8dcbe984cb24e003770fa3897ff3b7da351a34d92d4931ac3cb9a5707d2c1cbb`.

Requested change:

- remove the standalone translation/editorial line;
- remove the standalone visible `Источник: https://...` line;
- preserve the quotation, attribution, sermon metadata, Scripture reference, post identity, and scheduled publication date.

Final verified result:

- total verified targets: `29`;
- pending targets: `0`;
- postponed before/after: `66/66`;
- non-target postponed objects unchanged: `37`;
- published posts touched: `0`;
- Telegram objects touched: `0`;
- final status: `succeeded`.

The first published quote post was outside the target set and was not edited.

## Incident lessons now encoded in code and tests

1. Raw wall-surface row count is authoritative; content-audit summary categories are not substitutes.
2. Full exact before/after preview is mandatory before apply.
3. PowerShell orchestration must use strict mode, fail-fast behavior, exact paths, and native exit-code checks.
4. HTTP 429 requires exact readback before any controlled retry.
5. Confirmed absence is not an unknown provider effect.
6. Verified partial success is preserved; resume begins at the first exact before-state operation.
7. CAPTCHA stops the core workflow. OCR, challenge reconstruction, and bypass are unsupported.
8. External ZIP/version executors are retired as an implementation strategy.
9. Repository-owned code, tests, schemas, and journals are authoritative.
10. Conservative pacing is an operational safety control, not merely a performance setting.

## PR #150 and CI infrastructure exception

PR #150 exact head: `0bfb1260c37411e8df686f26120ceea85e2f8116`.  
Merge: `c04f0a4f948174ced6287e4bae87e4bf1be2be52`.

GitHub Actions runs `#3208` (`31125025717`) and `#3209` (`31125540845`) remained queued without starting. Both normal cancellation and `force-cancel` repeatedly returned HTTP 502. This was an infrastructure failure, not a failing test result.

Before merge, all seven changed files were manually reviewed against the exact safety contract: identity binding, plan digest, schedule and attachment preservation, intent-before-dispatch, exact reconciliation, 429 handling, CAPTCHA stop, unknown-outcome stop, conservative pacing, CLI registration, regression tests, and final full-wall non-target postconditions.

Repository implementation work for PR #150 performed `0` VK provider calls and `0` VK writes. The historical user-approved cleanup occurred before the repository integration and is recorded as evidence, not replay authority.

## Project and credential boundary

This repository manages two distinct projects:

- `lord-god-strength` — VK community `60805374`, owner `-60805374`;
- `legendary-poet` — VK community `235216998`, owner `-235216998`.

The local VK alias `legendary-poet` names the shared stored user credential. It is not a project selector. Project identity is selected by exact project key, community/owner IDs, plan, journal, and result.

Never print, package, commit, log, request manual entry of, or place the VK token on a command line.

## Inherited Wave 16 baseline

The immutable predecessor remains v9 and `main@22ed56256df3388c23c9f785f1e02cca71fd8524`. It records the completed CI runtime, SQLite lifetime, and local MP3 identity hardening baseline:

- Node 24-generation immutable action pins;
- explicit SQLite connection closure;
- local MP3 manifest schema `1.1`;
- metadata-ranked duplicate selection;
- fail-closed source-ID/hash conflicts;
- deterministic 1,000-track planning regression;
- local MP3 support remains read-only intake and manifest generation.

The v10 overlay changes the current baseline only by adding the supported VK postponed-text editor and its completed incident record. It does not authorize VK Audio upload, browser automation, playlist mutation, article-wall replay, broad catalog continuation, ID3 rewriting, rename, transcode, or any other provider operation.

## Closed operational graph

Completed repository work now includes:

- #31 — Lord God long-form reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared VK final-type contract;
- #130 — repository documentation and integrity polish;
- #133 — adaptive reasoning and local-only MP3 foundation;
- #137 — CI, SQLite, and MP3 identity hardening;
- #147 / PR #150 — guarded VK postponed-text editing capability and 2026-08-06 retrospective.

Retired or not planned remains unchanged:

- #32 — non-authoritative Lord God Shorts auto-upload scope;
- #33 — broad Lord God catalog/publication continuation;
- #99 — unproved Legendary Poet article-wall launcher continuation;
- #123 — deferred YouTube playlist mutation scope.

Historical local cleanup packages, browser packages, article executors, transfer executors, reset/recovery executors, and old ZIP versions are evidence only and must not be rerun.

## Next allowed action

No operational continuation is pending. Future VK postponed-text editing starts from a new reviewed request JSON and a newly generated immutable plan. Future provider work of any other kind starts from a new explicit user request and a new exact owning issue.
