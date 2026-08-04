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

## Current sequence

Verified code baseline: `main@dc3b25fdbbdb7d87e34f0f52e29fc9e3856190ae`.

- Waves 0–7: completed;
- Audit A0: completed;
- Waves 8A–8F: completed;
- Wave 8 evidence level: `self_tested`;
- active work: Wave 9 read-only reconciliation under #31 and #32/#38;
- provider writes during Waves 8A–8F, their CI, and state syncs: `0`.

Wave 8 is complete. It proves local contracts and mocked composition, not current live-provider completion, canary verification, or batch verification.

Wave 9 is read-only until separate reviewed evidence authorizes a later exact-ID canary. Do not upload, delete, edit metadata, create/place catalog items, save thumbnails, publish wall posts, or run any other provider mutation during Wave 9A/9B reconciliation.

Issue #64 is the canonical roadmap. Wave 10 owns retirement, release, runbook, rollback, archive, and governance work.

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
- Public upload entrypoints use the Wave 8D authority facade.
- Manifest digest is persisted before reservation and freshly revalidated before transfer.
- Changed bytes after reservation preserve the exact remote ID and `RESERVED` stage; recovery resumes the same reservation.

### Wave 8E — thumbnail authority

Schema `video-manager.vk-thumbnail-evidence`, version `1.0`, ruleset `wave-8e-v1`.

- Evidence binds exact project, owner/video, and local image identity.
- Upload/save intent is persisted before dispatch; restart never blindly replays mutation.
- `video.saveUploadedThumb` acceptance is not selected-thumbnail success.
- Verified requires retry-safe exact `video.get` readback and a non-empty exact descriptor-set match.
- Saved/unknown operations with an exact receipt reconcile through readback only.
- Public exports use `VerifiedVkThumbnailWriter` and `execute_thumbnail_operation`.

### Wave 8F — integration proof

Schema `video-manager.operation-integration-evidence`, version `1`, ruleset `wave-8f-v1`.

- One immutable evidence object binds exact project, comparison snapshots/digest, catalog digest, WavePlan/Result digests, bounded source set, media manifests, upload journals, thumbnail journals, expected remote delta, and exact totals.
- Every operation carries exact normalized `source_video_id` and explicit integration stage.
- Operations/evidence outside bounded scope fail closed.
- Matched, missing, and conflict items form a non-overlapping partition.
- Conflict items create zero later operations/evidence; matched items create no upload/thumbnail evidence.
- Missing items require exactly one upload operation and authoritative media evidence.
- Succeeded/unknown plan results must agree with durable upload/thumbnail stages.
- A verified upload followed by a later failure or unknown remains uploaded and becomes `requires_attention`; it is never failed/replayable.
- Totals partition items into planned, uploaded, verified, duplicate, failed, and requires-attention.
- Public boundary is `build_operation_integration_evidence` / `OperationIntegrationEvidence`.
- Evidence level is `self_tested`; `provider_writes` is structurally 0.

## Active Wave 9 read-only contract

### Wave 9A — Lord God, issue #31

- inventory local plans/results, upload journals, media manifests, and retained reconciliation files;
- take fresh bounded read-only YouTube/VK snapshots for the exact supplied source set;
- reconcile source IDs, target IDs, accepted/processing/verified/unknown stages, and expected remote delta;
- produce duplicate, present, missing, unknown, and requires-attention totals;
- do not create or execute a write plan.

Retained facts:

- `KobOzfBqzic` is already present and must not be uploaded again;
- `s512Opa8Eu4` → `-60805374_456241938`;
- 27 reviewed, 1 present, previously verified missing: `26`;
- local evidence `data\vk-upload\verified-longform-26`;
- SHA `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`;
- status `BLOCKED_PENDING_FRESH_READ_ONLY_WALL_AUDIT_AND_LOCAL_LEDGER_RECONCILIATION`.

### Wave 9B — Legendary Poet, issues #32/#38

- keep Shorts/Clips separate from long-form;
- do not use retired V1/V2/V3/V4 or historical “48 clips” packages;
- reconcile exact source/target IDs and local results against fresh bounded read-only provider snapshots;
- do not retransmit accepted, processing, verified, or unknown items.

Retained matrix:

- 56 exact YouTube Shorts;
- 41 exact pairs;
- 15 confirmed missing;
- 0 ambiguous;
- `BXZeRiEOHmQ` → `-235216998_456239039`;
- completed V3 Apply/postflight is not proven;
- status `REVIEWED_MANIFEST_PREPARED / UPLOAD_COMPLETION_NOT_PROVEN`.

### Wave 9C — later reviewed next-action gate

Issue #33 owns later catalog/publication work. A canary or batch mutation requires a separate reviewed exact-ID plan after Wave 9A/9B. Green CI, old counts, visible objects, screenshots, or historical packages never authorize writes.

## Separate VK Audio boundary

VK Audio browser/internal-web experiments remain `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. They are not part of Wave 9 video reconciliation.

## Branch discipline

- Substantial changes use one `agent/{description}` branch and one focused PR.
- Keep at most one active working branch for the current wave.
- Merge only after exact-head green CI.
- Synchronize operational memory in a separate narrow PR after a code-wave merge.
- Do not mix live provider reconciliation into reliability refactors.
- One issue owns each active wave; close superseded duplicates.

## Verified closed state

- Waves 0–8 are completed and must not be repeated.
- PR #66 closed Wave 1; #68 Wave 2; #70 Wave 3; #71/#73 Wave 4; #75/#77 Wave 5; #78/#81 Wave 6; #84/#87 Wave 7.
- PR #91/#92 closed Wave 8A; #93/#94 Wave 8B; #95/#97 Wave 8C; #98/#101 Wave 8D; #102/#103 Wave 8E; #104 Wave 8F.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- The 34-item Shorts reset completed and protected wall post `12400` remained present.
- Theological article photo wave completed: postponed posts `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed.
- Duplicate Wave 7 issue #79 and PR #83 are closed.

## Remaining non-live work

- Wave 9A/9B read-only reconciliation;
- PR #85 archive-specific CI boundary before any merge;
- Wave 10 governance/release/runbook work;
- separate VK Audio adapter contract, if ever approved.

Do not reactivate retracted claims, invent provider protocols, treat `guid` as complete idempotency, mandate disputed parameters without current evidence, or treat historical number `48` as a current queue contract.

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
27. Wave 9A/9B are read-only: provider writes remain 0.

## Execution and handoff rules

- Read-only inventory first; writes only from a separately reviewed exact-ID scope.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve successful intermediate stages and resume from durable state.
- Every handoff states project, exact entrypoint/command, outputs, ledger/result paths, and recovery behavior.
- Operational ZIPs are flat unless launch instructions explicitly say otherwise.
- Launchers verify their own location and required siblings before network writes.
- After every wave, update `current-state.md`, the machine register, issue #64, the owning issue, and regression coverage.
