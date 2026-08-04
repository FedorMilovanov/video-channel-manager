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

Current operational documents and repository evidence take priority over chat memory, screenshots, remembered counts, retired ZIP instructions, and older audits. A finding marked `fixed`, `retracted`, `disputed-provider-contract`, or `historical` must not be silently reactivated.

## Two-project identity boundary

This repository manages two separate projects:

- `lord-god-strength` — **Господь Бог — Сила Моя**;
- `legendary-poet` — **The Legendary Poet — Легендарный Поэт**.

They are not aliases. Never mix their channels, communities, owners, sites, links, descriptions, comments, manifests, journals, reports, credentials, or public footers.

Canonical IDs:

- `lord-god-strength`: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- `legendary-poet`: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

Every provider plan must bind the exact project key, channel/community/owner IDs, and project-specific link profile. Alias names, tokens, vanity routes, display order, and remembered context are never sufficient guards.

## Credential model

YouTube uses separate local OAuth aliases per channel. Reauthorizing one alias with `--force` replaces only that alias. Never use the Legendary Poet YouTube write token for the theological project.

VK intentionally uses one user access token for both communities. The stored alias `legendary-poet` is a credential label, not a project selector. The configured source is outside this repository:

- file: `C:\Users\Fedor\Projects\mp3telegrambot\.env`;
- key: `VK_API_TOKEN`.

Never copy, print, commit, log, package, or place the token value in a command line. Do not request manual token entry while the configured external source exists.

## Current engineering sequence

Verified current code baseline: `main@b3b121f1c40b397d29c213d69a623b55641d020e`.

- Waves 0–7: completed;
- Audit A0: completed;
- Wave 8A exact-first matching: completed;
- Wave 8B canonical text/URL identity: completed;
- Wave 8C exact catalog/album identity: completed;
- Wave 8D authoritative media/cache evidence: completed;
- active core engineering owner: Wave 8E under issue #86;
- provider writes during Wave 8A–8D, their CI, and state syncs: `0`.

Wave 8E owns exact thumbnail identity and selected-thumbnail delayed postflight. Do not mix Wave 8F integration proof, Wave 9 live reconciliation, VK Audio experiments, catalog publication, wall publication, or live provider writes into Wave 8E.

Until Wave 8 is fully merged and synchronized:

- do not resume broad upload queues;
- do not retransmit accepted, processing, verified, or unknown items;
- do not run old Legendary Poet V1/V2/V3/V4 or “48 clips” packages;
- do not use old browser/VK Audio packages as supported entrypoints;
- do not begin combined catalog/description/wall/audio operations;
- do not infer live completion from green CI.

Issue #64 is the canonical master roadmap. Wave 9 owns separate live reconciliation under issues #31/#32/#33/#38. Wave 10 owns retirement, release, runbook, rollback, archive, and governance work.

## Completed Wave 8 contracts

### Wave 8A — exact-first matching

Supported order:

1. reviewed one-to-one source ID → target ID;
2. unique exact canonical-title pair;
3. bounded token/trigram-indexed fuzzy fallback.

`duplicate_exact_title`, `exact_title_duration_mismatch`, and `non_unique_fallback` are conflicts. Conflicts never create mapping, missing/upload candidates, or collection placement.

### Wave 8B — canonical identity

Purpose-specific canonicalizers exist for identity title, display title, description, collection title, version/variation, public URL, and project URL. Canonical evidence preserves original value, canonical value, ruleset, transformations, and digest.

`already_correct` requires exact per-field readback. Substring, prefix, combined-row text, author/admin routes, foreign-project URLs, and unknown URL profiles fail closed.

### Wave 8C — exact catalog identity

Existing collection authority is a reviewed exact source collection ID → target album ID mapping. A title candidate is evidence only.

- duplicate canonical target album names are conflicts;
- one unreviewed existing candidate is a conflict;
- creation requires explicit approval and no candidate conflict;
- target IDs cannot be reused;
- renamed reviewed albums remain bound to exact ID and record title drift;
- conflicts create no album or placement operations;
- membership compares exact target video ID sets and ignores provider position churn;
- catalog evidence is project/snapshot/channel bound and digest protected;
- extra membership is evidence only, not deletion authority.

### Wave 8D — authoritative media and cache evidence

The immutable media schema is `video-manager.media-artifact-evidence`, version `1.0`, ruleset `wave-8d-v1`.

It binds:

- exact project key, source platform/channel/video ID, source URL/revision when available, and expected duration;
- acquisition method and path authority;
- requested output path and authoritative final path;
- file size and SHA-256;
- structured ffprobe evidence;
- compatibility profile, including container, stream counts, video/audio codecs, dimensions, sample rate, channels, and duration tolerance;
- deterministic manifest digest.

Permanent media rules:

- cache reuse requires exact manifest/source/project/path/file-size/SHA-256/fresh-ffprobe agreement;
- missing, renamed, stale, wrong-source, wrong-project, tampered, or substituted files fail closed;
- `yt-dlp` and transformed outputs use one exact structured-result field path as final-path authority;
- directory globbing, extension guessing, wildcard paths, and first-match file selection are never authority;
- MP4 or remux status does not prove H.264/AAC compatibility;
- the public VK upload entrypoint is the Wave 8D authority facade, not the legacy path/size/SHA-only executor;
- the manifest is journaled before reservation, bound into reservation intent, and freshly revalidated before file transfer;
- a legacy size/SHA-only media journal is not cache authority;
- the media manifest cannot change after `MEDIA_VERIFIED`;
- if bytes change after an exact VK reservation, file transfer is blocked, stage remains `RESERVED`, the exact remote ID is preserved, and recovery restores the authoritative file and resumes the same reservation instead of creating another one.

## Active Wave 8E contract

Wave 8E must make thumbnail success an exact postcondition, not an upload/save-response assumption.

Required outcomes:

- bind the exact project, target owner/video ID, and source image identity;
- source image identity includes absolute path, size, SHA-256, format, dimensions, mode, and quality findings from the existing local image inspector;
- persist a versioned thumbnail plan, mutation intent, upload response, save response, readback attempts, and final result digest;
- distinguish `planned`, `source_verified`, `upload_url_acquired`, `image_uploaded`, `save_started`, `save_accepted`, `postflight_verified`, and `unknown_requires_reconciliation` stages;
- `video.saveUploadedThumb` success is not the selected-thumbnail postcondition;
- a CDN URL alone is not thumbnail identity and volatile query strings must never be treated as stable evidence;
- when the provider supplies stable photo identity, compare exact owner/photo ID/hash and normalized image descriptors against the saved identity;
- perform bounded delayed readback against the exact owner/video ID;
- if provider readback cannot prove the exact selected thumbnail, return `unknown_requires_reconciliation`, preserve the accepted mutation evidence, and prohibit blind replay;
- a later readback failure must not repeat the already accepted thumbnail mutation;
- tests and implementation work remain local/mocked; provider writes remain 0;
- do not invent undocumented provider fields as guaranteed contracts: unsupported or absent proof fails closed.

## Separate VK Audio boundary

VK Audio browser/internal-web experiments are a separate system, not supported core YouTube→VK Video functionality. Historical scripts and ZIP versions remain evidence only.

Do not import them into core until a reviewed adapter defines versioned source/plan/result schemas, exact per-item stages, durable ledger, browser-session boundary, allowlisted upload-ticket host/path, exact field identity, bounded deadlines, partial/unknown reconciliation, canary, and exact postflight.

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
- PR #66 closed Wave 1 upload lifecycle/recovery.
- PR #68 closed Wave 2 project/content identity and supported sync entrypoint.
- PR #70 closed Wave 3 HTTP ownership/retry/redaction/limiter work.
- PR #71/#73 closed Wave 4 upload/wall separation.
- PR #75/#77 closed Wave 5 supported PowerShell operator work.
- PR #78/#81 closed Wave 6 versioned engine/retirement work.
- PR #84/#87 closed Wave 7 mutation-boundary/fault/corruption/operator proofs.
- PR #91/#92 closed Wave 8A.
- PR #93/#94 closed Wave 8B.
- PR #95/#97 closed Wave 8C and its state sync.
- PR #98 closed Wave 8D.
- Reviewed VK duplicate cleanup is complete: `403 confirmed_deleted`, `0 planned`, `0 unresolved`.
- YouTube `KobOzfBqzic` is already present and must not be uploaded again.
- YouTube `s512Opa8Eu4` is mapped to VK `-60805374_456241938`.
- The 34-item Shorts reset completed and protected wall post `12400` remained present.
- Theological article photo wave completed: postponed post IDs `12471–12480`, `10/10` verified. Do not rerun Apply.
- Draft PR #29 is superseded and closed. Never rerun its historical deletion executors.
- Duplicate Wave 7 issue #79 and PR #83 are closed; issue #80 / PR #84 are authoritative.

## Current active gap

Core Wave 8E:

- thumbnail upload/save response does not prove which thumbnail is selected for the exact video;
- current code has no versioned source-image/remote-photo/readback evidence contract;
- a missing or insufficient provider readback must become `unknown_requires_reconciliation`, not success or automatic retry.

Separate unresolved operational state:

- Legendary Poet latest recorded matrix: `56 Shorts / 41 exact pairs / 15 missing / 0 ambiguous`; completed V3 Apply is not proven;
- Lord God local ledger/result reconciliation is required;
- VK Audio has partial experimental evidence only;
- PR #85 remains valuable draft history but needs an archive-specific CI boundary before merge.

Do not reactivate retracted claims, invent provider protocols, treat `guid` as complete idempotency, mandate disputed parameters without current evidence, or treat the historical number `48` as a current queue contract.

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
10. Preserve controlled local masters when available; do not use screen capture as source media.
11. Preserve exact source artwork identity unless an exception is explicit.
12. Video upload and wall publication are separate operations; upload disables wall publication.
13. Never commit tokens, media, local exports, ledgers, logs, backups, or generated upload packages.
14. Every operational ZIP must pass `scripts/verify_operational_bundle.py`.
15. Public text may use only the selected project's registered links unless an exact exception is reviewed.
16. Unknown or unregistered links fail closed.
17. Transport reuse must not broaden mutation retry semantics.
18. A successful HTTP response is not a postcondition; verify the exact remote effect.
19. Machine state belongs in journals/results, not only console output.
20. Live queue retransmission is never a side effect of code refactoring.
21. A count, ZIP name, browser screen, visible object, file extension, container name, save response, or CDN URL is not immutable operation identity.
22. Historical evidence code is never a supported entrypoint.
23. A late-stage failure must not cause retransmission of an earlier verified or accepted mutation.
24. `already_correct` requires exact per-field readback.
25. Vertical format and duration are supporting evidence, not proof of VK Clip type.
26. Cache reuse requires exact manifest/file/source/probe agreement.
27. A glob-selected file is never authoritative acquisition evidence.
28. Remux or MP4 container status alone never proves codec compatibility.
29. Thumbnail success requires exact selected-thumbnail postflight; save acceptance alone is not success.
30. An unknown thumbnail postcondition is reconciled, not blindly replayed.

## Execution and handoff rules

- Read-only inventory first; writes only from reviewed exact-ID scope.
- Persist mutation intent before dispatch and preserve unknown outcomes for reconciliation.
- Preserve successful intermediate stages and resume from durable state; do not repeat expensive scans unnecessarily.
- Every handoff states project, exact entrypoint, exact command, expected outputs, ledger/result paths, and recovery behavior.
- Operational ZIPs are flat unless the launch command explicitly includes a nested directory.
- Launchers verify their own location and required siblings before network writes.
- After every wave, update `current-state.md`, the machine register, issue #64, the owning issue, and regression coverage.
