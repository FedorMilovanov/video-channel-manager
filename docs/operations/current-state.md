# Current operational state
Updated: 2026-09-07

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical issues, comments, pull requests, CI runs, credentials, releases and receipts are evidence only; they are never standing execution authority.

For every new task, resolve fresh current `main` and the relevant durable state before acting. Do not treat an older SHA, issue body, checkpoint comment or workflow run as the live baseline when newer terminal evidence exists.

## Completion and authority model

Repository implementation, artifact production and provider rollout are separate completion states.

- Implementation completion does not itself authorize execution.
- A completed artifact/provider outcome is not retroactively reopened only because stricter policy is introduced later.
- An old successful rollout does not authorize a new mutation.
- An ambiguous provider effect remains blocking unless exact read-only reconciliation or a narrowly bound no-replay disposition resolves it.
- Credentials authenticate; exact project identity, target binding, immutable operation/release identity, durable state and fresh explicit execution authority select the operation.
- No blind provider retry is authorized by this document.

## Repository source of truth

Only `main` is a supported repository code/runtime execution baseline.

`state/lordchrist-telegram`, `state/svodka-telegram`, and `state/milovi-cake-telegram` are durable state-only refs. None is a code baseline. Ephemeral `work/`, `agent/`, `feature/` and `research/` refs become non-authoritative when their owning scope closes; preserve unique evidence before cleanup and never rewrite a durable state ref as branch hygiene.

### Current checkpoint

The exact repository checkpoint used for this documentation sync is `main` `796c955de8fef3cdeab7ad8341a365b0e3245e85`. Resolve fresh `main` again before any later operation; this SHA is evidence, not standing authority.

Material late-2026-09-06 / early-2026-09-07 hardening now present on `main`:

- PR #532: Milovi archive-before-terminal-state provider outcome capture plus exact provider-free recovery under the permanent writer concurrency contract.
- PRs #536, #538 and #540: retirement of consumed/ambiguous Svodka executable one-offs while preserving immutable no-replay evidence.
- PR #544: Milovi live release/execution gates bind exact publication identity through structured `reviewed_publication_id` / `authorized_publication_id`; free-text provenance cannot satisfy a fresh live authorization gate.
- PR #533: `milovi-feed-20260906-001` was merged provider-inert and expired without release/execution authorization or durable feed registration. It is stale evidence and must not be initialized, published, retimed or caught up.
- PR #548: LordChrist verified-quote production moved from a global one-publication-per-day guard to explicit durable `morning` / `evening` slots.
- PR #550: branch-hygiene final ledger merged; the audited 146-ref baseline was completely classified as 8 KEEP / 138 DELETE candidates.
- PR #551: scheduled LordChrist provider dispatch now rejects a slot-less scheduled envelope before any Telegram HTTP call.
- PR #555: provider-critical CODEOWNERS coverage was expanded; this is review routing and does not replace server-side branch protection.
- PR #557: the reviewed 60-card LordChrist successor quote corpus, translation ledger, exact source/translation bindings and provider-inert staged release were merged.
- Issue #531 is completed after the exact 138-ref frozen deletion manifest was physically deleted through genuine GitHub delete-ref operations and independently verified with a complete post-delete branch listing.
- `main` now has real server-side branch protection with eight GitHub Actions required checks bound to GitHub Actions App `15368`, strict up-to-date enforcement and administrator enforcement.

## Telegram / LordChrist verified quotes

Issues #541 and #543 are closed as **completed** after the slot-aware runtime, transport hardening and reviewed successor-corpus work merged through PRs #548, #551 and #557. Issue #168 is closed as repository implementation complete; implementation completion does not itself authorize execution.

The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced the exact `retired_no_replay` disposition. For unrelated ambiguity, every other `dispatching` or `may_exist` effect remains fail-closed, and the retired August research release itself cannot resume, retry, or authorize a successor.

The authoritative production schedule is schema v3:

- `morning`: 09:17 `Europe/Moscow`, every day;
- `evening`: 21:17 `Europe/Moscow`, Tuesday / Friday / Sunday;
- one verified publication maximum per slot and two maximum per eligible day;
- each slot has a two-hour freshness window;
- `backfill_policy=none`: a missed slot does not become a later catch-up publication;
- scheduled workflow reruns are forbidden;
- a same-day manual publication closes scheduled slots for that Moscow date;
- a legacy verified scheduled row without slot metadata conservatively closes its transition date rather than guessing a historical slot.

Production prepares bind `scheduled_slot` into both the durable ledger entry and dispatch envelope. A replay of the same `(Moscow date, slot)` is blocked. The workflow maps the exact GitHub schedule event to one logical slot, re-proves freshness/release binding immediately before mutation, requires exact current-main CI and exact target preflight, persists intent before `sendMessage`, uses one mutation attempt and zero blind retries. PR #551 additionally enforces the slot at the transport boundary before HTTP.

The immutable verified 30-post queue/digest remains unchanged. Historical ledger rows remain readable; no migration/rewrite of `state/lordchrist-telegram` was required by #548/#551. Closing #541/#543 records implementation completion and does not authorize an ad-hoc send, replay, edit/delete/pin or MTProto action.

The successor corpus is a separate reviewed contract and does not weaken the legacy verified-30 schema. It contains exactly 60 cards across 12 authors and all 12 reviewed theological themes: 42 public-domain primary-source excerpts and 18 modern short quotations. Modern exact source fragments and visible translated quotations are capped at 25 words, require reviewed official author/ministry/publisher evidence, and retain substantial Russian editorial context. Visible Russian quotation text is cryptographically bound to the exact continuous source fragment; source/translation tampering fails closed. The reviewed release is also bound to the exact candidate Git blob, translation-ledger bytes and normalized corpus digest.

Exact reviewed successor identities:

- candidate Git blob SHA-1: `da9d9c812772510ddcfe14cc5f69a6771e2dbc4c`;
- translation ledger SHA-256: `61eec8558cc62ea709c4c2aa835528fa7d5fa519ec624568e2327762434f5e59`;
- normalized corpus SHA-256: `2cda3946e4cf0e34ac476b668271e90d66cb1adb6528db6adc8c0cc6f86bf677`.

The successor release remains `activation_policy=after_predecessor_queue_complete`, `release_state=staged_provider_inert`, `provider_writes_authorized=false`. Corpus readiness is not permission to bypass the remaining legacy queue or to perform a manual provider send.

## Telegram / LordChrist historical rich editorial

Issue #552 is the active provider-inert historical/biographical editorial lane. Its repository scope requires a broad discovery pass, A/B+ production evidence, exact quote locators, certainty/proximity classification, image-rights provenance, explicit separation of historical description from theological evaluation, and approximately three staged historical rich posts per week.

Issue #552 authorizes repository code/content/tests/docs only. It authorizes **0 provider writes** and does not create live scheduling/execution authority. The first research wave includes Spurgeon/Down-Grade, Bunyan imprisonment/preaching and Judson/Burmese Bible with correction of simplistic narratives. Do not interfere with active #552 refs during branch hygiene; the completed #557 successor quote corpus is immutable release evidence, not an active competing research lane.

The earlier LordChrist rich successor canary remains historical completion evidence: `lordchrist-rich-sermons-survive-century` published as Telegram message `1484` with verified durable state and one `sendRichMessage`; its one-shot workflows are retired and do not authorize another rich publication.

## LordChrist YouTube Shorts -> Telegram native video

Repository implementation is complete and hardened through PRs #502, #504, #505, #515 and #516. The canonical provider-inert operator path is `lordchrist_shorts_artifacts build-wave`, using stable `lordchrist-short-<youtube_video_id>` identities, exact owner snapshot/media bindings and atomic artifact derivation.

Issue #503 remains an **artifact-level** scope until a fresh owner `video-manager youtube scan` AuditPackage is classified and every selected backlog item is exact-owner-media accepted or explicitly media-missing/candidate-unconfirmed. Historical duration-only snapshots are reconciliation evidence only. No Telegram publication, Story, MTProto action, YouTube mutation, release authorization or execution authority is created by this lane.

Canonical runbook: [`lordchrist-shorts-feed.md`](lordchrist-shorts-feed.md).

## Telegram / Svodka

Issue #170 is closed as repository pipeline implementation complete. The historical approval bound release `svodka-pilot-2026-08`; its profile used `provider_writes_authorized=true` only for the reviewed rollout gates, and the durable ledger now exists on `state/svodka-telegram`. Those facts are historical evidence, not standing authority.

Issue #235 is completed with verified successor publications including Telegram messages `28` and `29`; the intervening v3 failed-no-effect identity is immutable and was not retried under the same release identity.

The original 14-entry `svodka-pilot-2026-08` ledger is fully terminalized as historical no-replay evidence. Completed reconciliation/successor workflows and later consumed one-offs have been retired from executable `main` where appropriate. PR #536 preserves the custom-emoji canary as `unknown / may_exist / message_id=null`; PR #538 retired the consumed native-rich canary; PR #540 retired the consumed ledger bootstrap. None created new provider authority or changed `state/svodka-telegram`.

No new Svodka Telegram mutation is authorized by this state.

## VK / Milovi Cake / Issue #323

Issue #323 is closed. The marathon accepted all 12 allowlisted Milovi Cake sources as completed native VK Clip uploads with durable logical wall mappings. Older checkpoints saying `OPEN`, `8/12`, `upload_in_progress` or `pending` are historical evidence only.

Durable invariants remain: do not duplicate a verified Clip because of transient projection; aggregate omission is not exact disappearance proof; ambiguous provider responses require exact reconciliation; the retired legacy finalizer must not return as a second mutation authority; destructive cleanup authority is consumed unless a new exact scope explicitly grants another operation.

Canonical historical analysis: [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md). Reusable architecture target: [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md).

## Telegram / Milovi Cake / Issue #353

The permanent Milovi architecture is a single feed control plane. `.github/workflows/milovi-telegram-feed-publisher.yml` is the only supported Milovi Telegram provider writer. It owns `state/milovi-cake-telegram`, shares the generic Telegram prepare/send/apply runtime and keeps source/release authorization separate from provider execution authorization.

Each new feed operation requires a fresh immutable `milovi-feed-YYYYMMDD-NNN` identity, exact review, provider-free state initialization after release authorization, channel-wide duplicate agreement, strict freshness, exact target preflight, current-main quality, durable intent before mutation, exactly one provider attempt and fresh exact human execution authority. Structured publication identity is the live authorization gate; credentials, old receipts, old issue text, accepted media and generic continuation are not.

`milovi-feed-20260819-001`, `milovi-feed-20260820-001`, `milovi-feed-20260820-002`, `milovi-feed-20260821-001` and `milovi-feed-20260906-001` are all historical identities now. Their old release/execution windows are expired evidence, not current authority. Issue #353 has no standing Telegram provider authority. Any future publication requires a fresh identity plus current review, provider-free state initialization and separate fresh execution authority.

The native-video artifact lane remains complete at `16 / 16` accepted Telegram-ready MP4/H.264 outputs on content-addressed evidence ref `agent/milovi-video-accepted-73c578eff825`, digest `sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`. Artifact readiness is not provider authority.

Issue #353 remains open for growth/acquisition/Dzen and deliberately authorized future publication operations, not architecture reimplementation.

Canonical runbook: [`milovi-telegram-feed-control-plane.md`](milovi-telegram-feed-control-plane.md).

## Instagram / Legendary Poet and Lord God

Issue #492 is closed as repository implementation complete. Launch packs, Reel factory, caption rendering and a read-only Graph identity client exist; exact Professional account IDs, hashed vertical masters and a live Meta publisher do not. Provider publications remain 0. Live rollout requires a new exact owning scope.

## YouTube / Legendary Poet / «Чёрный человек»

The historical authorized rollout is complete. Public video `x-puy27S2qs` remains the collision guard for that exact project/channel/media identity. Processing, public visibility, custom thumbnail, playlist membership and top-level comment were verified. The current `main` includes the guarded YouTube release executor; implementation completion does not itself authorize execution. Issue #154 is closed as **completed**. The historical provenance gap predates the later quality-master binding rule and is not required rework. Do not regenerate or reupload the album solely to satisfy policy introduced after the published bytes were produced.

No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state.

## Telegram runtime / supply chain

The minimal Telegram runtime remains exact-version and SHA-256 hash locked with pip `--require-hashes`. Production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. Any lock refresh is one coherent supply-chain change and must pass isolated install, `pip check`, guarded provider-free CLI smoke and dependency audit before acceptance.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not create competing provider writers against the same state namespace.

## Local MP3 and Resi DASH

Local MP3 support remains `local_only_read_only_intake_and_manifest`: inspect, probe, hash, tag inventory and deterministic manifests. It does not authorize ID3 rewrite, rename/transcode, remote upload, metadata mutation, playlist changes or wall publication.

Resi remains the repository-owned `watch -> sample -> explicit handoff` flow. The watcher never auto-dispatches a multi-gigabyte FULL download; language-sensitive work samples sermon speech before full handoff. The retained `<TITLE> - FULL.mp4` master goes to canonical Windows Downloads (`C:\Users\Fedor\Downloads`); generated handoff/watcher control files and exact-trim outputs remain under repository `operator-output` unless explicitly redirected. This capability has provider effect `impossible` and does not bypass DRM/access controls or infer rights.

Canonical runbooks: [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md) and [`resi-grace-russian-live.md`](resi-grace-russian-live.md).

## Repository branch hygiene / Issue #531

PR #550 merged the final role ledger: [`branch-hygiene-final-ledger-2026-09-06.md`](branch-hygiene-final-ledger-2026-09-06.md). Its frozen baseline completely partitions 146 refs into **8 KEEP / 138 DELETE candidates** with exact tip/evidence dispositions. Force-moving obsolete refs is explicitly not deletion and remains prohibited.

Issue #531 is closed as **completed**. The exact 138-ref frozen DELETE manifest passed a provider-inert PLAN-ONLY preflight proving 127 absorbed tips and 11 explicitly dispositioned divergent histories, with zero moved refs and zero open-PR collisions. A repository-admin `gh api DELETE repos/.../git/refs/heads/...` pass then deleted exactly 138/138 refs with exact-SHA rereads before each deletion.

Fresh GitHub post-delete inventory is complete: page 1 contains **11 refs** and page 2 is empty. `main`, all three durable `state/*` refs and content-addressed Milovi evidence `agent/milovi-video-accepted-73c578eff825` remain intact. Active/new LordChrist and documentation refs created outside the frozen manifest remain separate work and must not be swept by prefix or inverse keep-list.

## GitHub governance

`main` now has real classic GitHub branch protection enabled. Fresh GitHub branch readback reports `protected=true`, required-status enforcement level `everyone`, and exactly eight required GitHub Actions checks, each bound to GitHub Actions App ID `15368`:

- `quality (3.11)`;
- `quality (3.12)`;
- `quality (3.13)`;
- `PowerShell Windows 5.1`;
- `PowerShell Windows 7`;
- `PowerShell Linux 7`;
- `milovi-gap-read`;
- `permanent-feed-contract`.

The repository-admin apply/readback also verifies strict up-to-date required checks, PR-before-merge with `required_approving_review_count=0`, administrator enforcement, required conversation resolution, force-push disabled, protected-branch deletion disabled, linear-history enforcement disabled and branch locking disabled. The zero-approval setting deliberately avoids a single-owner self-review deadlock while still requiring the PR and all protected checks. The repository ruleset count `0` remains unchanged; classic branch protection is the active server-side enforcement surface.

Dependency Graph itself is policy-enabled for this public repository. SBOM REST export is verified unavailable through both documented generation surfaces at the recorded probe points; that scoped result must not be collapsed into a blanket `UNVERIFIED` item.

The connected GitHub App still cannot read the full Administration-only `/branches/main/protection` object, but its independent branch endpoint confirms `protected=true`, enforcement=`everyone` and the exact eight `(context, app_id=15368)` bindings. Do not confuse that connector permission boundary with absence of protection.

## Next safe work

1. Continue #552 historical-editorial work in its active lane; review its eventual PR independently rather than creating competing provider-authority paths.
2. Continue #503 only when a fresh owner AuditPackage/media source exists; do not write speculative replacement code for an external-data blocker.
3. Treat #353 as measured growth/future-publication operations with no standing provider authority.
4. Reclassify only the small retained/active branch set when its owning scopes close; do not reopen the completed frozen #531 cleanup or bulk-delete by prefix.
5. For any provider-visible work, start from fresh current `main`, fresh durable state, exact target identity, immutable operation identity and a new explicit owning authorization scope.

Nothing in this document is authorization for a provider mutation.
