# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read these files in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v2-2026-08-04.json`
4. `docs/operations/current-state.md`
5. `docs/operations/automation-backlog.md`
6. GitHub issue #64 and the issue that owns the exact current wave/finding
7. `docs/operations/local-credential-sources.md`
8. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
9. `docs/operations/operational-artifact-standard.md`

`docs/operations/master-audit-2026-08-04.md` and `audit-register-2026-08-04.json` are historical pre-Wave-1 baselines. They remain evidence, but the v2 audit/register and current repository state override them.

These operational documents and current repository evidence take priority over chat memory, screenshots, remembered counts, retired ZIP instructions, and older agent audits.

A finding marked `fixed`, `retracted`, `disputed-provider-contract`, or `historical` in the current machine register must not be silently converted back into an active implementation task.

## Two-project identity boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

They are not aliases. Never mix their YouTube channels, VK communities, sites, Telegram channels, Rutube channels, playlist links, descriptions, comments, manifests, journals, reports, or public footers.

The canonical identity and link allowlists are in `docs/operations/project-identity-registry.md`.

## Credential model

### YouTube

YouTube uses separate local OAuth aliases per selected channel:

- `fedor-milovanov` — `lord-god-strength`; currently documented as read-only;
- `legendary-poet` — The Legendary Poet; currently documented as write-capable.

Reauthorizing one alias with `--force` replaces only that alias. Never use the poet YouTube token for the theological project.

### VK

VK intentionally uses one user access token for both communities. The stored alias `legendary-poet` is a credential label, not a project selector.

The configured token source is outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, log, package, or place the token value in a command line. Do not request manual token entry while the configured external source exists.

Every VK operation must bind:

- `project_key`;
- exact `community_id`;
- exact `owner_id`;
- the matching project link profile.

Selecting a target only by token alias, display order, vanity route, or remembered context is forbidden.

## Canonical project IDs

### `lord-god-strength`

- YouTube channel ID: `UCeSJsC6go2c9pdJCuUI1BYA`
- YouTube OAuth alias: `fedor-milovanov`
- VK community ID: `60805374`
- VK owner ID: `-60805374`
- shared VK token alias: `legendary-poet`

### `legendary-poet`

- YouTube channel ID: `UC-78ys2S3cQ3lpqgXfo-SvQ`
- YouTube OAuth alias: `legendary-poet`
- VK community ID: `235216998`
- VK owner ID: `-235216998`
- shared VK token alias: `legendary-poet`

Every provider plan must bind the exact expected IDs and project-specific link profile. Alias names and display titles are never sufficient guards.

## Current engineering sequence

Verified baseline:

- actual `main`: `963955230e6fac269635337e8a2366fbfe54652d`;
- Waves 0–7: completed;
- Audit Wave A0: issue #88, documentation/state synchronization only;
- active core engineering wave: Wave 8 / issue #86;
- implementation/CI provider writes through Waves 0–7 and Audit A0: `0`.

The only allowed core implementation after Audit A0 is issue #86: exact-first matching, canonical identity, exact catalog/album mapping, authoritative media/cache evidence, structured media validation, and exact thumbnail postconditions.

Until Wave 8 is merged and synchronized:

- do not resume broad upload queues;
- do not retransmit accepted, processing, or unknown items;
- do not run old Legendary Poet V1/V2/V3/V4 or “48 clips” packages;
- do not use old browser/VK Audio packages as supported entrypoints;
- do not begin combined catalog/description/wall/audio operations;
- do not infer live completion from green CI.

Issue #64 is the canonical master roadmap. Wave 9 owns separate live reconciliation under issues #31/#32/#33/#38. Wave 10 owns retirement, release, runbook, rollback, archive, and governance work.

## Separate VK Audio boundary

The VK Audio browser/internal-web experiments are a separate system, not a supported part of the core YouTube→VK Video engine.

Do not import them into core until a reviewed adapter defines:

- versioned source/plan/result schemas;
- exact per-item stages and durable ledger;
- browser-session acquisition boundary;
- allowlisted upload-ticket host/path contract;
- exact artist/title/playlist identity;
- bounded deadlines and heartbeat;
- partial/unknown reconciliation;
- canary and exact postflight.

Historical audio scripts and ZIP versions remain evidence only.

## Branch discipline

- Documentation, links, configuration, and narrowly scoped low-risk maintenance may go directly to `main` only when the current task explicitly requires it.
- Substantial or risky changes use one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Do not create status-only, duplicate, or artificial follow-up branches.
- Merge only after exact-head green CI and synchronize operational memory in the same wave.
- Do not mix live provider reconciliation into a reliability-refactor PR.
- One issue owns each active wave; superseded duplicate issues and PRs must be closed, not kept as parallel authorities.

## Verified closed state

- Waves 0–7 are completed and must not be repeated.
- PR #66 closed Wave 1 upload lifecycle/recovery.
- PR #68 closed Wave 2 project/content identity and supported sync entrypoint.
- PR #70 closed Wave 3 HTTP ownership/retry/redaction/limiter work.
- PR #71 and state sync #73 closed Wave 4 upload/wall separation.
- PR #75 and state sync #77 closed Wave 5 supported PowerShell operator work.
- PR #78 and state sync #81 closed Wave 6 versioned engine/retirement work.
- PR #84 and state sync #87 closed Wave 7 mutation-boundary/fault/corruption/operator proofs.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- YouTube `KobOzfBqzic` is the already-present long-form boundary and must not be uploaded again.
- YouTube `s512Opa8Eu4` is already mapped to VK `-60805374_456241938`.
- The 34-item Shorts reset completed and protected wall post `12400` remained present.
- Theological article photo wave completed: postponed post IDs `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed without merge. Never rerun its historical deletion executors.
- Duplicate Wave 7 issue #79 and PR #83 are closed; issue #80 / PR #84 are authoritative.

## Current blockers

The current audit confirms only these active core gaps:

- exact-first matching is not implemented;
- ambiguous selected pairs can still create mappings;
- current fuzzy matching remains O(N×M);
- field-specific canonical text/URL identity is not centralized;
- normalized-title album maps can silently overwrite duplicate albums;
- catalog placement still relies on title keys instead of reviewed exact IDs;
- media cache reuse lacks authoritative final path, SHA-256 and structured probe evidence;
- yt-dlp fallback can select a glob result instead of the authoritative final path;
- MP4 remux does not prove the required codec/profile;
- thumbnail save does not prove the selected video thumbnail postcondition.

Separate unresolved operational state:

- Legendary Poet: latest recorded matrix is `56 Shorts / 41 exact pairs / 15 missing / 0 ambiguous`; completed V3 Apply is not proven;
- Lord God: local ledger/result reconciliation is still required;
- VK Audio: partial experimental evidence only, not production completion;
- PR #85: valuable draft history archive, but its archive/CI boundary must be fixed before merge.

Do not "fix" retracted claims such as the system YouTube `Uploads` playlist creating a VK album. Do not invent a VK chunk/resume protocol. Do not treat `guid` as complete wall idempotency. Do not mandate disputed provider parameters without current evidence. Do not treat the historical number `48` as a current queue contract.

## Non-negotiable safety rules

1. Never use the `legendary-poet` YouTube write token for `lord-god-strength`.
2. Never select a VK target only from the shared token alias; confirm exact project/community/owner identity.
3. Never expose or request manual entry of the configured VK token.
4. Never rerun a closed deletion, reset, article-wave, or superseded executor.
5. Never infer absence from an endpoint that does not cover the relevant surface.
6. Never infer a transfer boundary from screenshots or relative dates; use exact IDs and inventories.
7. Never upload an ambiguous match.
8. Never repeat an upload with an unknown outcome. Reconcile journal and live state first.
9. Keep long-form and Shorts/Clips in separate manifests and ledgers.
10. Preserve controlled local masters when available; do not use screen capture as source media.
11. Preserve exact source artwork identity and result; a generated frame requires an explicit exception.
12. Video upload and wall publication are separate operations. Upload must disable wall publication.
13. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
14. Every operational ZIP must pass `scripts/verify_operational_bundle.py` before handoff.
15. Public text may use only the selected project's registered links unless the exact cross-project exception is reviewed.
16. Unknown or unregistered links fail closed.
17. Transport reuse must not broaden mutation retry semantics.
18. A successful HTTP response is not a postcondition; verify the exact remote effect.
19. Machine state belongs in journals/results, not only human console output.
20. Live queue retransmission is never a side effect of code refactoring.
21. A count, ZIP name, browser screen, or visible object is not immutable operation identity.
22. Historical code stored for evidence is never a supported entrypoint.
23. A late-stage failure must not cause retransmission of an earlier verified mutation.
24. `already_correct` requires exact per-field readback, never substring/prefix matching.
25. Vertical format and duration are supporting evidence, not proof of VK Clip surface/type.

## Execution and handoff rules

- Read-only inventory first; writes only from a reviewed exact-ID scope.
- Store exact project key, source ID, target ID, title, duration, state, attempt timestamps, provider evidence, artwork identity, and postflight result in a durable ledger.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve intermediate successful audits and resume from durable state; do not repeat expensive scans unnecessarily.
- Every handoff states the selected project, exact entrypoint, exact command, expected outputs, ledger path, result path, and recovery behavior.
- Operational ZIPs are flat unless the launch command explicitly includes the nested directory.
- Launchers verify their own location and required sibling files before network writes.
- After every wave or run, update `current-state.md`, the current audit register, the changelog, issue #64, the owning issue, and regression coverage.
