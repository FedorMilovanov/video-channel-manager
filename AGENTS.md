# Repository agent instructions

Before any work involving Fedor Milovanov's YouTube/VK media workflow, read these files in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-2026-08-04.md`
3. `docs/operations/audit-register-2026-08-04.json`
4. `docs/operations/current-state.md`
5. the GitHub issue that owns the finding/wave
6. `docs/operations/local-credential-sources.md`
7. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
8. `docs/operations/operational-artifact-standard.md`

These operational documents and current repository evidence take priority over chat memory, screenshots, remembered counts, retired ZIP instructions, and older agent audits.

A finding marked `fixed`, `retracted`, or `disputed-provider-contract` in the machine register must not be silently converted back into an active implementation task.

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

Wave 0 established the canonical audit, machine register, current state, and issue graph. No provider write was authorized by Wave 0.

The next code task is issue #65: journaled VK upload state machine and recovery. Until it is merged and the relevant local ledgers are reconciled:

- do not resume broad upload queues;
- do not retransmit accepted, processing, or unknown items;
- do not run old Legendary Poet V3 packages without recovering their exact canary/apply state;
- do not begin combined catalog/description/wall/audio operations.

Issue #64 is the master roadmap for Waves 2–10.

## Branch discipline

- Documentation, links, configuration, and narrowly scoped low-risk maintenance may go directly to `main` when the current task explicitly requires it.
- Substantial or risky code changes use one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Do not create status-only, duplicate, or artificial follow-up branches.
- Merge promptly after exact-head green CI and update operational memory in the same wave.
- Do not mix live provider reconciliation into a reliability-refactor PR.

## Verified closed state

- PR #61 closed the main project-identity/branding defects in supported paths and hardened SQLite.
- PR #62/#63 migrated the main inventory, writer, upload, description, and OAuth paths to persistent client ownership without blind mutation retry.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- YouTube `KobOzfBqzic` is the already-present long-form boundary and must not be uploaded again.
- YouTube `s512Opa8Eu4` is already mapped to VK `-60805374_456241938`.
- The 34-item Shorts reset completed and protected wall post `12400` remained present.
- Theological article photo wave completed: postponed post IDs `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed without merge. Never rerun its historical deletion executors.

## Current blockers

The current audit confirms:

- upload reservation/ticket is journaled too late in base sync;
- visible incomplete remote objects can be treated as reusable;
- upload readiness lacks a complete exact postcondition;
- content preview/plan loading does not perform full per-record validation;
- supported sync still monkeypatches an executable Poet-hardcoded base sync;
- YouTube safe reads lack bounded retry;
- transport/limiter, Windows wrappers, wave generations, risk coverage, matching, album identity, and media cache require later waves.

Do not "fix" retracted claims such as the system YouTube `Uploads` playlist creating a VK album. Do not invent a VK chunk/resume protocol. Do not treat `guid` as complete wall idempotency. Do not mandate disputed provider parameters without current evidence.

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

## Execution and handoff rules

- Read-only inventory first; writes only from a reviewed exact-ID scope.
- Store exact project key, source ID, target ID, title, duration, state, attempt timestamps, provider evidence, artwork identity, and postflight result in a durable ledger.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve intermediate successful audits and resume from durable state; do not repeat expensive scans unnecessarily.
- Every handoff states the selected project, exact entrypoint, exact command, expected outputs, ledger path, result path, and recovery behavior.
- Operational ZIPs are flat unless the launch command explicitly includes the nested directory.
- Launchers verify their own location and required sibling files before network writes.
- After every wave or run, update `current-state.md`, the audit register, the changelog, the owning issue, and regression coverage.
