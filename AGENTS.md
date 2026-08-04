# Repository agent instructions

Before work on Fedor Milovanov's YouTube/VK workflow, read in order:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
3. `docs/operations/audit-register-v2-2026-08-04.json`
4. `docs/operations/current-state.md`
5. `docs/operations/automation-backlog.md`
6. GitHub issue #64 and the issue owning the exact current wave
7. `docs/operations/local-credential-sources.md`
8. `docs/operations/2026-07-31-youtube-vk-transfer-postmortem.md`
9. `docs/operations/operational-artifact-standard.md`

The v2 audit/register and current-state file override old chats, screenshots, packages, counts, and pre-Wave-1 audit files. A finding marked `fixed`, `retracted`, `disputed-provider-contract`, or `historical` must not be silently reactivated.

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

## Current engineering sequence

Verified code baseline: `main@a0230ea156eeb1717e15c6523d0b6b28e90f6d8e`.

- Waves 0–7: completed;
- Audit A0: completed;
- Wave 8A exact-first matching: completed;
- Wave 8B canonical text/URL identity: completed;
- Wave 8C exact catalog/album identity: completed;
- Wave 8D authoritative media/cache evidence: completed;
- Wave 8E exact thumbnail postflight evidence: completed;
- active core engineering owner: Wave 8F under issue #86;
- provider writes during Waves 8A–8E, their CI, and state syncs: `0`.

Wave 8F owns cross-wave integration proof only. Do not mix Wave 9 live reconciliation, catalog/wall publication, broad upload queues, VK Audio experiments, or provider writes into Wave 8F.

Until Wave 8 is fully closed and synchronized:

- do not resume broad upload queues;
- do not retransmit accepted, processing, verified, or unknown items;
- do not run old Legendary Poet V1/V2/V3/V4 or “48 clips” packages;
- do not use browser/VK Audio packages as supported entrypoints;
- do not begin combined catalog/description/wall/audio operations;
- do not infer live completion from green CI.

Issue #64 is the canonical roadmap. Wave 9 owns separate live reconciliation under #31/#32/#33/#38. Wave 10 owns retirement, release, runbook, rollback, archive, and governance.

## Completed Wave 8 contracts

### Wave 8A — exact-first matching

Order: reviewed source ID → target ID, unique exact canonical title, bounded token/trigram fuzzy fallback. `duplicate_exact_title`, `exact_title_duration_mismatch`, and `non_unique_fallback` are conflicts. Conflicts create no mapping, upload candidate, missing item, or collection placement.

### Wave 8B — canonical identity

Ruleset `wave-8b-v1`. Purpose-specific canonicalizers exist for identity title, display title, description, collection title, version/variation, public URL, and project URL. `already_correct` requires exact per-field readback. Substring, prefix, combined-row text, author/admin routes, foreign-project URLs, and unknown URL profiles fail closed.

### Wave 8C — exact catalog identity

Schema `video-manager.catalog-identity-evidence`, ruleset `wave-8c-v1`, comparison schema `3.0`, VK catalog plan version 3. A reviewed source collection ID → exact target album ID is the only existing-album authority. Duplicate canonical titles and unreviewed existing candidates are conflicts. Conflict decisions create no album or placement operation. Membership compares exact target video ID sets.

### Wave 8D — media authority

Schema `video-manager.media-artifact-evidence`, version `1.0`, ruleset `wave-8d-v1`.

- One exact structured-result field path is final-path authority.
- Directory globbing, wildcard paths, extension guessing, and first-match selection are not authority.
- Cache reuse requires exact project/source/path/file-size/SHA-256/manifest/fresh-ffprobe agreement.
- MP4 or remux status does not prove codec compatibility.
- The public VK upload entrypoint is the authority facade, not the legacy path/size/SHA-only executor.
- The manifest digest is persisted before reservation and freshly revalidated before transfer.
- Changed bytes after reservation preserve the exact remote ID and stage `RESERVED`; recovery resumes the same reservation after restoring the authoritative file.

### Wave 8E — thumbnail authority

Schema `video-manager.vk-thumbnail-evidence`, version `1.0`, ruleset `wave-8e-v1`.

- Evidence binds exact project, VK owner/video, and local image path/size/SHA-256/format/dimensions.
- Stages are `prepared`, `upload_intent_recorded`, `save_intent_recorded`, `saved`, `verified`, and `unknown_requires_reconciliation`.
- Upload/save intent is persisted before dispatch. Restart from an intent stage never replays the mutation.
- Save receipt records exact photo owner/id/hash, canonical image descriptors, and response digest.
- `video.saveUploadedThumb` acceptance is not selected-thumbnail success.
- Verified requires retry-safe exact `video.get` readback and a non-empty exact descriptor-set match.
- CDN query/fragment values are volatile; exact scheme/host/path/dimensions remain identity.
- Mismatch, incomplete evidence, ambiguous mutation, interrupted dispatch, or insufficient readback becomes `unknown_requires_reconciliation`.
- Saved/unknown operations with an exact receipt reconcile through readback only.
- The atomic journal is digest protected and project/video/image bound.
- Public exports use `VerifiedVkThumbnailWriter` and `execute_thumbnail_operation`; direct production imports of the low-level save-only writer are guarded.

## Active Wave 8F contract

Wave 8F must prove the completed contracts compose without weakening one another.

Required outcomes:

- bind one bounded source set through matching, canonical identity, reviewed catalog identity, media authority, upload lifecycle, and thumbnail result evidence;
- create one integration evidence object binding project key, exact source/target IDs, source snapshot, expected remote delta, plan digest, media manifest digest, upload journal identity, and thumbnail operation ID;
- prove conflict or `unknown_requires_reconciliation` at any boundary creates no unauthorized later operation;
- prove a verified or accepted early mutation is never replayed because a later catalog, metadata, thumbnail-readback, wall, or reporting stage fails;
- preserve the distinction between designed/self-tested evidence and canary/batch provider evidence;
- guard supported public entrypoints against legacy bypasses;
- prove operation-scoped totals: planned, uploaded, verified, duplicate, failed, and requires-attention;
- keep implementation and tests local/mocked; provider writes remain 0;
- do not perform Wave 9 live reconciliation or any publication in Wave 8F.

## Separate VK Audio boundary

VK Audio browser/internal-web experiments are a separate system, not supported core YouTube→VK Video functionality. Historical scripts and ZIPs remain evidence only.

Do not import them into core without a reviewed adapter defining versioned source/plan/result schemas, per-item stages, durable ledger, browser-session boundary, allowlisted upload-ticket host/path, exact field identity, bounded deadlines, partial/unknown reconciliation, canary, and exact postflight.

## Branch discipline

- Substantial changes use one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Do not create status-only, duplicate, or artificial implementation branches.
- Merge only after exact-head green CI.
- Synchronize operational memory in a separate narrow state PR after a code-wave merge.
- Do not mix live provider reconciliation into reliability refactors.
- One issue owns each active wave; close superseded duplicates.

## Verified closed state

- Waves 0–7 are completed and must not be repeated.
- PR #66 closed Wave 1.
- PR #68 closed Wave 2.
- PR #70 closed Wave 3.
- PR #71/#73 closed Wave 4.
- PR #75/#77 closed Wave 5.
- PR #78/#81 closed Wave 6.
- PR #84/#87 closed Wave 7.
- PR #91/#92 closed Wave 8A.
- PR #93/#94 closed Wave 8B.
- PR #95/#97 closed Wave 8C.
- PR #98/#101 closed Wave 8D and state sync.
- PR #102 closed Wave 8E.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- YouTube `KobOzfBqzic` is already present and must not be uploaded again.
- YouTube `s512Opa8Eu4` maps to VK `-60805374_456241938`.
- The 34-item Shorts reset completed and wall post `12400` remained present.
- Theological article photo wave completed: postponed posts `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed.
- Duplicate Wave 7 issue #79 and PR #83 are closed.

## Unresolved operational state

- Legendary Poet retained matrix: `56 Shorts / 41 exact pairs / 15 missing / 0 ambiguous`; completed V3 Apply is not proven.
- Lord God local ledger/result reconciliation is required.
- VK Audio has partial experimental evidence only.
- PR #85 remains valuable draft history but needs an archive-specific CI boundary before merge.

Do not reactivate retracted claims, invent provider protocols, treat `guid` as complete idempotency, mandate disputed parameters without current evidence, or treat historical number `48` as a current queue contract.

## Non-negotiable safety rules

1. Never use the `legendary-poet` YouTube write token for `lord-god-strength`.
2. Never select a VK target only from the shared token alias.
3. Never expose or request manual entry of the configured VK token.
4. Never rerun closed deletion, reset, article-wave, or superseded executors.
5. Never infer absence from an endpoint that does not cover the relevant surface.
6. Use exact IDs and inventories, not screenshots or relative dates, for transfer boundaries.
7. Never upload an ambiguous match.
8. Never repeat an upload with an unknown outcome; reconcile first.
9. Keep long-form and Shorts/Clips in separate manifests and ledgers.
10. Preserve controlled local masters; screen capture is not source media.
11. Preserve exact source artwork identity unless an exception is explicit.
12. Video upload and wall publication are separate operations.
13. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
14. Every operational ZIP must pass `scripts/verify_operational_bundle.py`.
15. Public text may use only the selected project's registered links.
16. Unknown or unregistered links fail closed.
17. Transport reuse must not broaden mutation retry semantics.
18. A successful HTTP response is not a postcondition; verify the exact remote effect.
19. Machine state belongs in journals/results, not only stdout.
20. Live queue retransmission is never a side effect of code refactoring.
21. Counts, ZIP names, screenshots, file extensions, containers, save responses, and CDN URLs are not immutable identity.
22. Historical evidence code is never a supported entrypoint.
23. Later failure must not replay an earlier verified or accepted mutation.
24. `already_correct` requires exact per-field readback.
25. Vertical format and duration do not prove VK Clip type.
26. Cache reuse requires exact manifest/file/source/probe agreement.
27. Glob-selected files are never authoritative acquisition evidence.
28. Remux or MP4 alone never proves codec compatibility.
29. Thumbnail success requires exact selected-thumbnail postflight.
30. Unknown thumbnail outcome is reconciled, not blindly replayed.

## Execution and handoff rules

- Read-only inventory first; writes only from reviewed exact-ID scope.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states project, exact entrypoint/command, outputs, ledger/result paths, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network writes.
- After every wave, update `current-state.md`, the machine register, issue #64, the owning issue, and regression coverage.
