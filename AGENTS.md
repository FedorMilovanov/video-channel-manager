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

The v2 audit/register and current-state file override old chats, screenshots, packages, counts, and pre-Wave-1 audit files. A finding marked `fixed`, `retracted`, `disputed-provider-contract`, or `historical` must not be silently reactivated.

## Project identity boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

They are not aliases. Never mix channels, communities, owners, sites, links, descriptions, comments, manifests, journals, reports, credentials, or footers.

Canonical IDs:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

Every provider plan or readback snapshot must bind the exact project key and registered channel/community/owner IDs. Alias names, token labels, vanity routes, display order, remembered context, titles, or screenshots are never sufficient guards.

## Credential model

YouTube uses separate local OAuth aliases per channel. Never use the Legendary Poet write token for the theological project.

VK intentionally uses one user token for both communities. The stored alias `legendary-poet` is a credential label, not a project selector. The configured source is outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, log, package, or place the token value on a command line. Do not request manual token entry while the configured external source exists.

## Current sequence

Verified code baseline: `main@604b962a9936ab173e41602bd9ab10b2dfaa9e59`.

- Waves 0–7: completed;
- Audit A0: completed;
- Waves 8A–8F: completed at evidence level `self_tested`;
- Wave 9 read-only reconciliation contract: completed at evidence level `read_only_contract_self_tested`;
- active operational work: fresh bounded read-only reconciliation under #31 and #32/#38;
- provider queries during Wave 9 contract implementation/CI: `0`;
- provider writes during Waves 8A–8F, Wave 9 contract implementation/CI, and their state syncs: `0`;
- write plans created during Wave 9 contract implementation/CI: `0`.

Wave 9 contract PR #107 merged as `604b962a9936ab173e41602bd9ab10b2dfaa9e59`. Exact-head CI `30954499845` passed on Python 3.11/3.12/3.13 with `761 passed, 1 xfailed`; Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux were green.

This proves the reconciliation model and regression matrix. It does **not** prove current live provider state, complete local ledger availability, canary verification, batch verification, or permission to mutate providers.

Issue #64 is the canonical roadmap. Wave 10 owns retirement, release, runbook, rollback, archive, and governance work.

## Completed Wave 8 contracts

### Wave 8A — exact-first matching

Order: reviewed source ID → target ID, unique exact canonical title, bounded token/trigram fallback. Duplicate exact titles, duration conflicts, and non-unique fallback candidates are explicit conflicts and create no mapping or upload candidate.

### Wave 8B — canonical identity

Ruleset `wave-8b-v1`. Purpose-specific canonicalizers cover identity/display titles, descriptions, collections, variation/version text, public URLs, and project URLs. `already_correct` requires exact per-field readback. Cross-project, author/admin, unknown, substring, prefix, and combined-row evidence fail closed.

### Wave 8C — exact catalog identity

Schema `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`. A reviewed source collection ID → exact target album ID is the only existing-album authority. Duplicate canonical titles and unreviewed candidates are conflicts; membership compares exact target video ID sets.

### Wave 8D — media authority

Schema `video-manager.media-artifact-evidence`, version `1.0`, ruleset `wave-8d-v1`. One exact structured-result field is final-path authority. Cache reuse requires project/source/path/size/SHA-256/manifest/fresh-ffprobe agreement. Globs, extension guessing, first-match selection, MP4 container names, and remux status are not compatibility evidence.

### Wave 8E — thumbnail authority

Schema `video-manager.vk-thumbnail-evidence`, version `1.0`, ruleset `wave-8e-v1`. Intent is persisted before dispatch. Save acceptance is not success. Verified requires exact `video.get` readback and a non-empty exact descriptor-set match. Unknown outcomes reconcile by readback and are never blindly replayed.

### Wave 8F — integration proof

Schema `video-manager.operation-integration-evidence`, version `1`, ruleset `wave-8f-v1`. One immutable object binds project, comparison/catalog/plan/result digests, bounded source set, media manifests, upload and thumbnail journals, expected remote delta, and operation-scoped totals. A verified early mutation followed by later failure remains uploaded and becomes `requires_attention`; it is not failed or replayable.

## Completed Wave 9 read-only contract

Schema `video-manager.read-only-reconciliation-evidence`, version `1`, ruleset `wave-9-v1`.

Supported public boundary:

- `build_read_only_reconciliation_evidence`;
- `ReadOnlyReconciliationEvidence`;
- `BoundedSourceSnapshot`;
- `BoundedTargetSnapshot`;
- `LocalReconciliationRecord`;
- `RemoteReconciliationObservation`.

The contract:

- binds exact registered project identity and one sorted bounded source set;
- requires fresh, complete, deterministic source and target snapshots with SHA-256 identities;
- accepts only exact source-ID, reviewed exact mapping, or exact reserved-remote-ID associations;
- classifies every bounded item as `present`, `duplicate`, `missing`, `unknown`, or `requires_attention`;
- prohibits classifying upload intent, accepted, processing, verified, or unresolved mutation evidence as safely missing;
- marks duplicates, processing objects, local/remote binding mismatches, and missing claimed-present objects as replay-prohibited;
- rejects stale snapshots, cross-project IDs, incomplete local coverage, and reserved-ID-only absence claims without a known exact remote ID;
- contains no `WavePlan`, mutation operations, writer, provider adapter, or write-plan creator;
- fixes `provider_writes` to `0`, `write_plan_created` to `false`, and every item field `future_write_authorized` to `false`.

The regression matrix preserves the retained Lord God processing/API-22/untouched boundaries and the Legendary Poet `56 / 41 / 15 / 0` matrix, but those fixtures are not fresh live snapshots.

## Active Wave 9 live read-only reconciliation

No upload, deletion, metadata change, catalog placement, thumbnail save, wall publication, or other provider mutation is authorized. Do not create a write plan during this phase.

### Wave 9A — Lord God, issue #31

Required inputs:

1. exact local plans/results, upload journals, media manifests, and retained reconciliation files;
2. a fresh bounded read-only YouTube snapshot for the supplied source set;
3. a fresh bounded read-only VK snapshot covering the relevant exact target surface;
4. one immutable reconciliation evidence object and human-readable report.

Retained facts, not fresh conclusions:

- `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → `-60805374_456241938`;
- 27 reviewed, 1 present, previously verified missing: `26`;
- local evidence `data\vk-upload\verified-longform-26`;
- SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- retained operational outcome: 23 confirmed, 2 processing (`4wmCcHMcP90`, `Vs__dbIlVqU`), 1 explicit API 22 failure (`84puu6MnLZs`);
- status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

Never rerun the old 26-item launcher or infer absence from a partial endpoint.

### Wave 9B — Legendary Poet, issues #32/#38

Keep Shorts/Clips separate from long-form. Do not use retired V1/V2/V3/V4 or historical “48 clips” packages.

Retained matrix, not fresh conclusions:

- 56 exact YouTube Shorts;
- 41 exact pairs;
- 15 confirmed missing;
- 0 ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- completed V3 Apply/postflight is not proven;
- status `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

### Wave 9C — later reviewed next-action gate

Issue #33 owns later catalog/publication work. A canary or batch mutation requires a separate reviewed exact-ID plan after fresh Wave 9A/9B evidence. Green CI, old counts, visible objects, screenshots, fixtures, or historical packages never authorize writes.

## Separate VK Audio boundary

VK Audio browser/internal-web experiments remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. They are not part of Wave 9 video reconciliation.

## Branch discipline

- Substantial changes use one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Merge only after exact-head green CI.
- Synchronize operational memory in a separate narrow PR after a code-wave merge.
- Do not mix live provider reconciliation into reliability refactors.
- One issue owns each active operation; close superseded duplicates.

## Verified closed state

- Waves 0–8 and the Wave 9 contract are completed and must not be repeated.
- PR #66 closed Wave 1; #68 Wave 2; #70 Wave 3; #71/#73 Wave 4; #75/#77 Wave 5; #78/#81 Wave 6; #84/#87 Wave 7.
- PR #91/#92 closed Wave 8A; #93/#94 Wave 8B; #95/#97 Wave 8C; #98/#101 Wave 8D; #102/#103 Wave 8E; #104/#106 Wave 8F and final Wave 8 state; #107 completed the Wave 9 read-only contract.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- The 34-item Shorts reset completed and protected wall post `12400` remained present.
- Theological article photo wave completed: postponed posts `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed.
- Duplicate Wave 7 issue #79 and PR #83 are closed.

## Remaining work

- actual Wave 9A/9B fresh bounded read-only provider reconciliation;
- PR #85 archive-specific CI boundary before any merge;
- Wave 10 governance/release/runbook work;
- separate VK Audio adapter contract, only if explicitly approved.

## Non-negotiable safety rules

1. Never mix project identities, credentials, IDs, journals, links, or manifests.
2. Never expose or request manual entry of the configured VK token.
3. Never rerun closed deletion, reset, article-wave, transfer, or superseded executors.
4. Never infer absence from an endpoint that does not cover the relevant surface.
5. Use exact IDs and bounded inventories, not screenshots, titles, or relative dates.
6. Never upload an ambiguous match.
7. Never repeat an accepted, processing, verified, intent-persisted, or unknown mutation; reconcile first.
8. Keep long-form and Shorts/Clips in separate manifests and ledgers.
9. Preserve controlled local masters; screen capture is not source media.
10. Video upload and wall publication are separate operations.
11. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
12. Public text may use only the selected project's registered links; unknown links fail closed.
13. Transport reuse must not broaden mutation retry semantics.
14. A successful HTTP response is not a postcondition; verify the exact remote effect.
15. Machine state belongs in journals/results, not only stdout.
16. Live queue retransmission is never a side effect of code refactoring or reconciliation.
17. Historical counts, packages, extensions, containers, save responses, and CDN URLs are not immutable identity.
18. Later failure must not replay an earlier verified or accepted mutation.
19. `already_correct` requires exact per-field readback.
20. Cache reuse requires exact manifest/file/source/probe agreement.
21. Thumbnail success requires exact selected-thumbnail postflight.
22. Wave 9 provider writes remain 0 until a separate reviewed exact-ID decision.
23. The Wave 9 contract does not create, imply, or authorize a write plan.

## Execution and handoff rules

- Read-only inventory first; writes only from a separately reviewed exact-ID scope.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states project, exact entrypoint/command, inputs, outputs, ledger/result paths, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network writes.
- After every wave or operational reconciliation, update `current-state.md`, the machine register, issue #64, the owning issue, and regression coverage.
