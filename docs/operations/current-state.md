# Current operational state
Updated: 2026-09-10

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

The exact repository checkpoint used for this documentation sync is `main` `46cc305f7b25e2f340fb945f01ee51b01cb711e3`. Resolve fresh `main` again before any later operation; this SHA is evidence, not standing authority.

Material 2026-09-06 through 2026-09-10 hardening now present on `main` includes:

- PRs #532, #536, #538, #540 and #544: provider-outcome/recovery hardening and retirement of consumed or ambiguous executable one-offs without weakening no-replay semantics.
- PRs #548 and #551: LordChrist verified-quote production moved to durable `morning` / `evening` slots, and scheduled dispatch rejects slot-less envelopes before Telegram HTTP.
- PR #550 plus completed issue #531: the frozen 138-ref DELETE manifest was physically deleted with exact-SHA checks; force-moving refs was not used as a substitute for deletion.
- PR #555: provider-critical CODEOWNERS coverage expanded; this remains review routing, not server-side protection.
- PR #557: reviewed 60-card LordChrist successor quote corpus and provider-inert staged release.
- PR #559: sealed successor source-integrity amendment v2, preserving historical v1 reproducibility while moving current source authority to an explicit amendment-bound release.
- PR #556: evidence-backed historical/biographical LordChrist editorial lane with 69 reviewed URLs, 52 accepted A/B+ sources and a sealed nine-post provider-inert cycle.
- PR #583 / issue #582: LordChrist verified-quote production replaced the fragile two-hour scheduler freshness gate with bounded same-Moscow-day leases and added a release-bound automatic predecessor-to-successor handoff that remains fail-closed on incomplete, mismatched or ambiguous durable state.
- PR #590 / issue #589: successor-ledger durable initialization moved behind publication eligibility, exact-current-main quality proof and provider-target preflight; preview, preflight and stale/inactive scheduled invocations remain durable-state read-only.
- PR #591 / issue #561: LordChrist historical rich production gained the separate archival-v3 recurring release, exact scheduled bridge, 16 bound media exhibits for eight recurring posts, reader-safe rendering, durable canary/editorial approval and a pre-exhaustion successor guard.
- PR #585 / issue #584: Instagram local MP4 resumable upload was integrated into the existing guarded publication state machine with canonical Reel compatibility proof, a hard 1 GB service/manifest boundary, durable child-ledger recovery and no blind replay.
- PR #588 / issue #572: provider-critical Instagram runtime, CLI, persistence, migration and runbook paths were added to CODEOWNERS review routing without weakening existing Telegram/VK ownership rules.
- PR #592: the exact non-secret Legendary Poet Instagram/Facebook production target binding was added to the canonical project identity registry.
- PR #593: Meta OAuth error code `190` is classified as an invalid/expired credential during read-only Instagram preflight, with secret-safe operator diagnostics and a dedicated credential-lifecycle runbook.
- PR #595: scheduled exact-main quality proof now waits up to 420 seconds for a successful run on the exact current `main` SHA, re-proves `main` on every poll, and fails closed on timeout or branch movement.

## Telegram / LordChrist verified quotes

Issues #541, #543, #582 and #589 are closed as **completed** after the slot-aware runtime, transport hardening, reviewed successor-corpus work, production handoff and state-initialization ordering fixes merged through PRs #548, #551, #557, #559, #583 and #590. Issue #168 is closed as repository implementation complete; implementation completion does not itself authorize execution.

The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced the exact `retired_no_replay` disposition. For unrelated ambiguity, every other `dispatching` or `may_exist` effect remains fail-closed, and the retired August research release itself cannot resume, retry, or authorize a successor.

The authoritative production schedule remains schema v3:

- `morning`: 09:17 `Europe/Moscow`, every day;
- `evening`: 21:17 `Europe/Moscow`, Tuesday / Friday / Sunday;
- one verified publication maximum per slot and two maximum per eligible day;
- the morning event has a bounded 720-minute same-day lease and expires at the 21:17 editorial boundary;
- the evening event has a bounded 160-minute lease and cannot cross the Moscow calendar-day boundary;
- `backfill_policy=none`;
- scheduled workflow reruns are forbidden;
- a same-day manual publication closes scheduled slots for that Moscow date.

Production binds `scheduled_slot` into durable ledger state and the dispatch envelope, persists intent before `sendMessage`, uses one provider attempt and zero blind mutation retries, and fails closed on ambiguous outcomes. Scheduler delay inside the reviewed lease is not treated as catch-up or backfill; next-day execution remains impossible.

Scheduled exact-main quality proof is also bounded rather than instant-only: PR #595 allows a scheduled invocation to wait up to 420 seconds for a successful quality run proving the exact current `main` SHA. Every poll re-proves the `main` ref; timeout or any branch movement fails closed. Manual/non-scheduled invocations retain the zero-wait behavior unless an explicit reviewed wait is supplied.

The runtime keeps the immutable verified 30-post predecessor queue authoritative until exact terminal completion and cross-track provider-effect safety are proven. Incomplete predecessor state, digest mismatch, partial successor state or ambiguous provider effects block handoff. Closing implementation issues does not authorize an ad-hoc send, replay, edit/delete/pin or MTProto action.

When the predecessor becomes terminal, preview/preflight may materialize any missing successor ledger only in the local checkout for validation. Durable successor-ledger initialization is allowed only after publication eligibility, exact-current-main quality proof and provider-target preflight and only on a publishing invocation; this prevents preview or stale/inactive scheduled execution from mutating durable state.

The successor corpus remains a separate reviewed contract with exactly 60 cards across 12 authors and 12 reviewed theological themes: 42 public-domain primary-source excerpts and 18 modern short quotations. Modern exact fragments and visible translated quotations remain capped at 25 words.

Current sealed successor release identities after PR #559:

- base candidate Git blob SHA-1: `da9d9c812772510ddcfe14cc5f69a6771e2dbc4c`;
- translation ledger SHA-256: `61eec8558cc62ea709c4c2aa835528fa7d5fa519ec624568e2327762434f5e59`;
- integrity amendment SHA-256: `b4d0346a2353c6e309c5003eb5a0c13b8dc60094e8f865e6d25da364e5783549`;
- normalized effective corpus SHA-256: `6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873`;
- release id: `lordchrist-successor-quotes-v1-integrity-v2`.

The immutable sealed successor release itself remains `activation_policy=after_predecessor_queue_complete`, `release_state=staged_provider_inert`, `provider_writes_authorized=false`. PR #583 adds the separate reviewed `successor-activation-v1.json` envelope for owning issue #582 with `release_state=armed_after_predecessor_terminal` and `provider_writes_authorized=true`, bound to the exact predecessor/successor digests, Telegram target identity and presentation policy. The runtime may select that envelope only after predecessor terminality and cross-track provider-effect safety are proven, and then uses the successor's separate durable ledger. This envelope is not permission for a premature or manual provider send and does not weaken the repository-wide requirement for fresh durable-state and execution-gate verification.

## Telegram / LordChrist historical rich editorial

Issue #552 remains closed as **completed** for the evidence-backed editorial foundation merged through PR #556: 52 accepted A/B+ sources from 69 reviewed URLs, exact evidence/theology bindings, deterministic source/post/cycle digests and fail-closed prose-to-claim, quote-fragment, registry-identity, URL and repository-path validation.

Issue #561 is now closed as **completed** through PR #591. The canonical v2 release is preserved for reproducibility. On actual GitHub Actions `schedule` execution, the production facade bridges the exact legacy v2 release identity to the separate archival-v3 release only under `GITHUB_ACTIONS=true` and `GITHUB_EVENT_NAME=schedule`; manual, PR and local paths do not silently activate archival-v3.

The archival-v3 recurring set contains eight remaining publications bound to 16 exact Git/media exhibits. Reader-facing rendering suppresses internal archival acquisition/evidence captions and claim-boundary prose, exact media bytes are re-proved before the existing one-shot rich send path, and `replenishment_guard_remaining=1` prevents the final pending post from dispatching without an exact durable successor-cycle binding.

Canary Telegram message `1516` is durable `published` with `provider_effect=verified`. Its editorial approval was recorded provider-free on `state/lordchrist-telegram` commit `1e0ce0e47bbb66f80cb6406a45937b52bcffe5a2`, with `canary_verified_at_utc` and `canary_editorial_approved_at_utc` both `2026-09-10T11:42:41+00:00`. This arms the reviewed Monday/Wednesday/Saturday 19:17 `Europe/Moscow` archival-v3 cadence through the normal exact-release, exact-media, target, slot, quality, durable-state, cross-track and replenishment gates. `backfill_policy=none` and one-shot/no-blind-replay semantics remain in force.

Issue closure and durable canary approval are not general Telegram mutation authority. They do not authorize an ad-hoc historical send, an alternate trigger, backfill, replay, edit/delete/pin or bypass of the scheduled release/state gates.

The earlier rich successor canary `lordchrist-rich-sermons-survive-century` remains historical completion evidence as Telegram message `1484`; its one-shot workflows are retired and do not authorize another rich publication.

## LordChrist YouTube Shorts -> Telegram native video

Repository implementation is complete and hardened through PRs #502, #504, #505, #515 and #516. The canonical provider-inert operator path remains `lordchrist_shorts_artifacts build-wave`, using stable `lordchrist-short-<youtube_video_id>` identities, exact owner snapshot/media bindings and atomic artifact derivation.

Issue #503 is closed as **not planned / externally blocked**, not as artifact-complete. The last admissible materialized inventory reached 279 duration-eligible records: 2 exact Shorts plus 277 explicit candidates, with `unresolved_non_candidate=0`; that owner snapshot later expired under the 48-hour freshness contract. Fresh connected-Drive review on 2026-09-07 found no newer owner AuditPackage, and this environment has no local OAuth token runtime or owner Takeout/local masters.

Do not substitute public/third-party downloads, stale-snapshot reinterpretation or replacement OAuth credentials. Reopen this scope or create a fresh successor only when a new <=48h owner AuditPackage and/or exact owner media exists. No Telegram publication, Story, MTProto action, YouTube mutation, release authorization or execution authority is created by the closed tracker.

Canonical runbook: [`lordchrist-shorts-feed.md`](lordchrist-shorts-feed.md).

## Telegram / Svodka

Issue #170 is closed as repository pipeline implementation complete. The historical approval bound release `svodka-pilot-2026-08`; its profile used `provider_writes_authorized=true` only for the reviewed rollout gates, and the durable ledger now exists on `state/svodka-telegram`. Those facts are historical evidence, not standing authority.

Issue #235 is completed with verified successor publications including Telegram messages `28` and `29`; the intervening v3 failed-no-effect identity is immutable and was not retried under the same release identity.

The original 14-entry `svodka-pilot-2026-08` ledger is terminal historical no-replay evidence. Consumed reconciliation/bootstrap/canary executors were retired where appropriate. No new Svodka Telegram mutation is authorized by this state.

## VK / Milovi Cake / Issue #323

Issue #323 is closed. The marathon accepted all 12 allowlisted Milovi Cake sources as completed native VK Clip uploads with durable logical wall mappings. Older checkpoints saying `OPEN`, `8/12`, `upload_in_progress` or `pending` are historical evidence only.

Durable invariants remain: do not duplicate a verified Clip because of transient projection; aggregate omission is not exact disappearance proof; ambiguous provider responses require exact reconciliation; retired legacy finalizers must not return as second mutation authorities.

Canonical historical analysis: [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md). Reusable architecture target: [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md).

## Telegram / Milovi Cake / Issue #353

The permanent Milovi architecture is a single feed control plane. `.github/workflows/milovi-telegram-feed-publisher.yml` remains the only supported Milovi Telegram provider writer and owns `state/milovi-cake-telegram` through the reviewed generic prepare/send/apply contract.

`milovi-feed-20260819-001`, `milovi-feed-20260820-001`, `milovi-feed-20260820-002`, `milovi-feed-20260821-001` and `milovi-feed-20260906-001` are all historical identities now. Their release/execution windows are expired evidence, not current authority. Issue #353 has no standing Telegram provider authority. Any future publication requires a fresh identity plus current review, provider-free state initialization and separate fresh execution authority.

The native-video artifact lane remains complete at `16 / 16` accepted Telegram-ready MP4/H.264 outputs on content-addressed evidence ref `agent/milovi-video-accepted-73c578eff825`, digest `sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`.

Issue #353 is closed as **not planned for further work under the historical tracker**. Engineering/control-plane work is complete; no Dzen/acquisition experiment is being falsely claimed as executed. Future growth, Dzen, paid placement, invite-link/admin work or publication operations require a new exact scope with real attribution/outcome data and explicit operation-specific provider/admin authorization.

Canonical runbook: [`milovi-telegram-feed-control-plane.md`](milovi-telegram-feed-control-plane.md).

## Instagram / Legendary Poet and Lord God

Issue #492 is closed as repository implementation complete for the earlier provider-inert launch/content/factory scope. PR #569 under issue #568 provides the production-publishing authority: explicit Instagram/Facebook login mode and Graph version, exact account preflight, default-off double write gate, durable SQL publication ledger, idempotent publication-key/content binding, compare-and-set mutation claims, fail-closed ambiguous-result reconciliation, and exact public-media trust/integrity verification before the first provider POST.

Issue #571 / PR #573 adds the provider-inert Reel media-compatibility boundary on top of that publisher. Canonical `MediaArtifactEvidence` carries FPS plus video/audio bitrate telemetry, and `InstagramReelArtifactBinding` binds exact reviewed local bytes to the current Reel profile before hosting/provider mutation. Hard container/codec/sample-rate/FPS/dimension/video-bitrate/duration/file-size constraints fail closed; recommended 9:16 and the documented 128 kbps audio target remain advisories rather than invented hard maxima. The versioned binding is exported through the canonical `video-manager schema export` path.

PR #585 under issue #584 adds direct local-MP4 resumable upload without creating a second publication authority. The local service proves the canonical Reel compatibility contract before durable planning/provider mutation, enforces the 1 GB maximum at the service/manifest boundary, records resumable child-state durably and fails closed on ambiguous upload/provider effects instead of blindly replaying. Before the binary upload it re-proves the exact local bytes and compatibility binding, then returns to the existing publication state machine for processing/publish semantics.

The canonical non-secret Legendary Poet production target is now recorded in the project identity registry through PR #592: project `legendary-poet`, Instagram Professional account ID `17841435926122104`, username `the.legendary.poet`, linked Facebook Page ID `1299632476567433`, login mode `facebook`, Graph host `https://graph.facebook.com`. Credentials authenticate this target; they do not redefine it.

PR #593 hardens the remaining credential-lifecycle boundary. Read-only preflight classifies Meta OAuth error code `190` as an invalid/expired credential condition, suppresses the raw provider message for that class, keeps provider writes disabled and directs the operator to replace the credential outside Git and rerun exact identity/quota preflight. Other provider errors retain their ordinary diagnostics.

The repository now contains the exact non-secret production target binding and guarded publishing transports, but it does **not** contain a valid current access-token value and there is no accepted fresh post-rotation preflight or live Instagram canary evidence. Issues #577 and #581 remain open on that external acceptance boundary. A green repository state, successful credential rotation or successful read-only preflight is not standing live execution authority; the first canary still requires one immutable reviewed Reel/manifest, current durable state and separate operation-specific authorization.

The operator handoff remains one-way and exact: reviewed local artifact -> compatibility binding -> either the same immutable bytes at a reviewed HTTPS URL or the guarded local resumable transport -> exact publication manifest/state binding -> read-only preflight -> separately authorized production publish. No blind retry is allowed from an ambiguous provider state.

Canonical runbooks: [`instagram-production-publishing.md`](instagram-production-publishing.md) and [`instagram-facebook-token-lifecycle.md`](instagram-facebook-token-lifecycle.md).

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

Issue #531 is closed as **completed**. PR #550's frozen role ledger partitioned the audited 146-ref baseline into 8 KEEP / 138 DELETE candidates, and the exact 138-ref DELETE manifest was physically removed through genuine delete-ref operations with exact-SHA rereads and zero open-PR collisions.

A previously recorded post-cleanup total ref count is not a durable invariant and must not be reused as current branch authority. For any later hygiene pass, resolve the fresh complete ref inventory and classify each ref by durable-state role, open PR/issue ownership and unique evidence before mutation. Never delete or rewrite a ref merely by prefix or age, and never treat a durable state ref as disposable branch debt.

## GitHub governance / Issue #443

Issue #443 is closed as **completed**. Administration-capable owner-token readback on current `main` proves the source policy in full: required status checks use `strict=true`; the exact eight required GitHub Actions contexts remain present; pull requests are required before merge; administrator enforcement is enabled; conversation resolution is required; force pushes and branch deletion are disabled; branch lock is disabled; and no ordinary bypass allowance is configured. Connected branch-summary readback independently reports `protected=true` for `main`, required-status enforcement level `everyone`, and the same eight required GitHub Actions checks bound to GitHub Actions App ID `15368`.

All three exact durable state refs are also protected at their unchanged SHAs. Administration-capable readback proves the intended state-safe profile on each: no PR/check gate, no actor restriction, administrator enforcement enabled, force pushes and deletion disabled, lock disabled, and intended ordinary fast-forward publisher/recovery writes preserved. The repository ruleset count `0` remains unchanged, so classic branch protection is the active server-side enforcement surface. Dependency Graph itself is policy-enabled for this public repository. SBOM REST export is verified unavailable through both documented generation surfaces at the recorded probe points; that scoped result must not be collapsed into a blanket `UNVERIFIED` item.

This governance closure is evidence, not standing authority. Future protection changes require a fresh administration-capable audit; repository YAML, CODEOWNERS or CI self-checks are not substitutes for server-side policy.

## Next safe work

1. Repository governance tracker #443 is complete; no current GitHub-governance remediation remains. Re-audit only after a future policy change or contradictory fresh evidence.
2. Reopen #503 or create a successor only when a fresh <=48h owner YouTube AuditPackage and/or exact owner media is available; do not substitute public downloads or stale evidence.
3. Any future Milovi growth/Dzen/provider/admin experiment needs a new exact scope and real attribution/outcome data; closed #353 is not standing authority.
4. LordChrist historical issue #561 is completed through #591. The reviewed archival-v3 recurring lane may progress only through its exact Mon/Wed/Sat scheduled release/state gates; any later cycle requires an exact successor binding before the final pending post and no ad-hoc replay/backfill authority is created by this document.
5. Instagram repository implementation now has canonical hosted-media and local-resumable paths plus an exact non-secret Legendary Poet target binding and credential-expiry diagnostics. Issues #577/#581 remain externally blocked until a fresh valid credential proves exact read-only identity/quota preflight; the first live canary still requires a separately frozen exact manifest/media/caption/feed choice and explicit operation-specific execution authority.
6. Issue #594 is a separate Legendary Poet YouTube -> VK transfer scope with its own fresh provider reconciliation and authorization requirements; do not merge it conceptually with Instagram or LordChrist lanes and do not reuse historical missing counts as authority.
7. For any provider-visible work, start from fresh current `main`, fresh durable state, exact target identity, immutable operation identity and a new explicit owning authorization scope.

Nothing in this document is authorization for a provider mutation.
