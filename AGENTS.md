# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v2-2026-08-04.json`
4. `docs/operations/current-state.md`
5. `docs/operations/automation-backlog.md`
6. GitHub issue #64 and the issue owning the exact current operation
7. `docs/operations/local-credential-sources.md`
8. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
9. `docs/operations/operational-artifact-standard.md`

The audit register and `current-state.md` override old chats, screenshots, packages, counts, and superseded audits. A finding marked `fixed`, `retracted`, `disputed-provider-contract`, or `historical` must not be silently reactivated.

## Project identity boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

They are not aliases. Never mix their channels, communities, owners, sites, links, descriptions, comments, manifests, journals, reports, credentials, or footers.

Canonical IDs:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

Every provider plan must bind the exact project key, channel/community/owner IDs, and project-specific link profile. Alias names, token labels, vanity routes, display order, or remembered context are never sufficient guards.

## Credential model

YouTube uses separate local OAuth aliases per channel. Never use the Legendary Poet write token for the theological project.

VK intentionally uses one user token for both communities. The stored alias `legendary-poet` is a credential label, not a project selector. The configured source is outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, log, package, or place the token value on a command line. Do not request manual token entry while the configured external source exists.

## Current sequence

Verified code baseline: `main@8f8b224f0386cf9f1ed89e0983e8af440e96cdd4`.

- Waves 0–8F: completed;
- Wave 9 read-only evidence contract: completed;
- Package A (Wave 9A + Wave 9B + Wave 10 tooling/governance): completed at evidence level `read_only_package_self_tested`;
- Package A PR #109 exact-head CI `30958445398`: `773 passed, 1 xfailed` on Python 3.11/3.12/3.13; all three PowerShell environments green;
- provider queries during Package A implementation/CI: `0`;
- provider writes during Package A implementation/CI: `0`;
- write plans created during Package A implementation/CI: `0`;
- actual fresh Wave 9A/9B live reconciliation remains pending local ledgers and fresh bounded provider snapshots.

Green CI proves contracts, not current provider state. Retained queue counts are historical inputs until fresh read-only evidence validates them.

## Package A supported boundaries

### Wave 9A — bounded read-only reconciliation

Supported boundary: `video-manager-package-a reconcile --manifest <package-a-manifest.json>`.

It binds exact project identity, sorted supplied source IDs, immutable source/target snapshot digests, local journal/result stages, exact remote observations, and totals for `present`, `duplicate`, `missing`, `unknown`, and `requires_attention`.

A source with local `intent`, `accepted`, `processing`, `verified`, or unresolved mutation evidence is never classified as safely missing. Stale or incomplete snapshots, cross-project IDs, duplicate observations, and digest tampering fail closed.

### Wave 9B — recovery decision ledger

Schema `video-manager.recovery-decision-ledger`, ruleset `wave-9b-v1`.

Recovery decisions are exact-source scoped and derived from reconciliation evidence. Accepted, processing, verified, unknown, duplicate, and requires-attention states never authorize blind retransmission. Any later mutation requires a separate reviewed exact-ID plan; Package A itself creates none.

### Wave 10 — operator board and governance

Schema `video-manager.operator-board`, ruleset `wave-10-v1`.

The board is read-only and exposes status, evidence level, blockers, exact safe next action, and zero-write counters. It cannot dispatch provider calls or construct mutation plans.

Supported verification boundary: `video-manager-package-a verify-output --output <package-a-output-directory>`.

Wave 10 also separates supported runtime, historical archive, operational evidence, runbooks, rollback, and release governance. Historical literal code and PR #85 are not supported entrypoints.

## Live reconciliation owners

- #31 — Lord God long-form queue reconciliation;
- #32/#38 — Legendary Poet Shorts/Clips reconciliation;
- #33 — later reviewed catalog/publication gate only after reconciliation;
- #64 — canonical roadmap.

Retained Lord God facts:

- `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → `-60805374_456241938`;
- local evidence directory `data\vk-upload\verified-longform-26`;
- reviewed manifest SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.

Retained Legendary Poet facts:

- 56 exact YouTube Shorts;
- 41 retained exact pairs;
- 15 retained missing candidates;
- 0 retained ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`.

These retained facts are not fresh provider conclusions. Do not use retired V1/V2/V3/V4 packages or the historical “48 clips” queue.

## Separate VK Audio boundary

VK Audio browser/internal-web experiments remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. They are not part of Package A video reconciliation.

## Branch and merge discipline

- Substantial work uses one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Merge only after exact-head green CI.
- Synchronize operational memory in a separate narrow PR after a code-wave merge.
- Guard squash merges by unchanged expected head, reviewed scope, and clean review threads.
- Never mix live provider reconciliation into reliability or governance refactors.

## Non-negotiable safety rules

1. Never mix project identities, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun closed deletion, reset, article-wave, or superseded executors.
4. Never infer absence from an endpoint that does not cover the relevant surface.
5. Use exact IDs and inventories, not screenshots or relative dates, for transfer boundaries.
6. Never upload an ambiguous match.
7. Never repeat an accepted, processing, verified, or unknown mutation; reconcile first.
8. Keep long-form and Shorts/Clips in separate manifests and ledgers.
9. Preserve controlled local masters; screen capture is not source media.
10. Video upload and wall publication are separate operations.
11. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
12. Public text may use only the selected project's registered links.
13. Unknown or unregistered links fail closed.
14. Transport reuse must not broaden mutation retry semantics.
15. A successful HTTP response is not a postcondition; verify the exact remote effect.
16. Machine state belongs in journals/results, not only stdout.
17. Live queue retransmission is never a side effect of code refactoring.
18. Counts, ZIP names, screenshots, extensions, containers, save responses, and CDN URLs are not immutable identity.
19. Historical evidence code is never a supported entrypoint.
20. Later failure must not replay an earlier verified or accepted mutation.
21. `already_correct` requires exact per-field readback.
22. Cache reuse requires exact manifest/file/source/probe agreement.
23. Glob-selected files are never authoritative acquisition evidence.
24. Remux or MP4 alone never proves codec compatibility.
25. Thumbnail success requires exact selected-thumbnail postflight.
26. Unknown thumbnail outcome is reconciled, not blindly replayed.
27. Package A and Wave 9A/9B are read-only: provider writes remain 0.
28. Package A output never authorizes a provider mutation by itself.
29. Live reconciliation requires the exact local ledgers/results and fresh bounded provider snapshots.
30. A dashboard or green status display is not mutation authorization.

## Execution and handoff rules

- Read-only inventory first; writes only from a separately reviewed exact-ID scope.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states project, exact entrypoint/command, inputs, outputs, ledger/result paths, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network writes.
- After every package, update `current-state.md`, the machine register, issue #64, owning issues, and regression coverage.
