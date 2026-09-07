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

The exact repository checkpoint used for this documentation sync is `main` `900c0ac0d3cd946ca7dad9f63f49aa5f83f5b690`, the merge of PR #560. Resolve fresh `main` again before any later operation; this SHA is evidence, not standing authority.

Material 2026-09-06 / 2026-09-07 hardening now present on `main` includes:

- PRs #532, #536, #538, #540 and #544: provider-outcome/recovery hardening and retirement of consumed or ambiguous executable one-offs without weakening no-replay semantics.
- PRs #548 and #551: LordChrist verified-quote production moved to durable `morning` / `evening` slots, and scheduled dispatch rejects slot-less envelopes before Telegram HTTP.
- PR #550 plus completed issue #531: the frozen 138-ref DELETE manifest was physically deleted with exact-SHA checks; force-moving refs was not used as a substitute for deletion.
- PR #555: provider-critical CODEOWNERS coverage expanded; this remains review routing, not server-side protection.
- PR #557: reviewed 60-card LordChrist successor quote corpus and provider-inert staged release.
- PR #559: sealed successor source-integrity amendment v2, preserving historical v1 reproducibility while moving current source authority to an explicit amendment-bound release.
- PR #556: evidence-backed historical/biographical LordChrist editorial lane with 69 reviewed URLs, 52 accepted A/B+ sources and a sealed nine-post provider-inert cycle.

## Telegram / LordChrist verified quotes

Issues #541 and #543 are closed as **completed** after the slot-aware runtime, transport hardening and reviewed successor-corpus work merged through PRs #548, #551, #557 and #559. Issue #168 is closed as repository implementation complete; implementation completion does not itself authorize execution.

The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced the exact `retired_no_replay` disposition. For unrelated ambiguity, every other `dispatching` or `may_exist` effect remains fail-closed, and the retired August research release itself cannot resume, retry, or authorize a successor.

The authoritative production schedule remains schema v3:

- `morning`: 09:17 `Europe/Moscow`, every day;
- `evening`: 21:17 `Europe/Moscow`, Tuesday / Friday / Sunday;
- one verified publication maximum per slot and two maximum per eligible day;
- each slot has a two-hour freshness window;
- `backfill_policy=none`;
- scheduled workflow reruns are forbidden;
- a same-day manual publication closes scheduled slots for that Moscow date.

Production binds `scheduled_slot` into durable ledger state and the dispatch envelope, persists intent before `sendMessage`, uses one provider attempt and zero blind mutation retries, and fails closed on ambiguous outcomes.

The immutable verified 30-post predecessor queue remains historical/current release context. Closing implementation issues does not authorize an ad-hoc send, replay, edit/delete/pin or MTProto action.

The successor corpus remains a separate reviewed contract with exactly 60 cards across 12 authors and 12 reviewed theological themes: 42 public-domain primary-source excerpts and 18 modern short quotations. Modern exact fragments and visible translated quotations remain capped at 25 words.

Current sealed successor release identities after PR #559:

- base candidate Git blob SHA-1: `da9d9c812772510ddcfe14cc5f69a6771e2dbc4c`;
- translation ledger SHA-256: `61eec8558cc62ea709c4c2aa835528fa7d5fa519ec624568e2327762434f5e59`;
- integrity amendment SHA-256: `b4d0346a2353c6e309c5003eb5a0c13b8dc60094e8f865e6d25da364e5783549`;
- normalized effective corpus SHA-256: `6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873`;
- release id: `lordchrist-successor-quotes-v1-integrity-v2`.

The successor release remains `activation_policy=after_predecessor_queue_complete`, `release_state=staged_provider_inert`, `provider_writes_authorized=false`. Corpus readiness is not permission to bypass the predecessor queue or perform a manual provider send.

## Telegram / LordChrist historical rich editorial

Issue #552 is closed as **completed** through PR #556. The merged provider-inert lane contains a broad discovery record, 52 accepted A/B+ sources from 69 reviewed URLs, exact evidence/theology bindings, nine independently sealed posts over three Monday/Wednesday/Saturday weeks, deterministic source/post/cycle digests, and fail-closed prose-to-claim, direct-quote-fragment, registry-identity, URL and repository-path validation.

The historical editorial release remains non-live: `provider_writes_authorized=false`, `live_eligible=false`, `backfill_policy=none`. Its image plans remain transport-inert until exact direct media bytes/MIME/SHA-256 and rights evidence are separately pinned and reviewed. PR #556 and issue #552 authorize **0 provider writes** and do not create live scheduling/execution authority.

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

Issue #531 is closed as **completed**. PR #550's frozen role ledger partitioned the audited 146-ref baseline into 8 KEEP / 138 DELETE candidates, and the exact 138-ref DELETE manifest was physically removed through genuine delete-ref operations with exact-SHA rereads and zero open-PR collisions.

The stable post-merge inventory, excluding the transient branch used for this documentation update, contains **9 refs total**: `main`, the three durable state refs, the content-addressed Milovi accepted-video evidence ref, and four retained historical/research/agent refs. This newer count does not reopen the completed frozen #531 cleanup and is not permission for prefix-based deletion.

## GitHub governance / Issue #443

Issue #443 is closed as **completed**. Administration-capable owner-token readback on current `main` proves the source policy in full: required status checks use `strict=true`; the exact eight required GitHub Actions contexts remain present; pull requests are required before merge; administrator enforcement is enabled; conversation resolution is required; force pushes and branch deletion are disabled; branch lock is disabled; and no ordinary bypass allowance is configured. Connected branch-summary readback independently reports `protected=true` for `main`, required-status enforcement level `everyone`, and the same eight required GitHub Actions checks bound to GitHub Actions App ID `15368`.

All three exact durable state refs are also protected at their unchanged SHAs. Administration-capable readback proves the intended state-safe profile on each: no PR/check gate, no actor restriction, administrator enforcement enabled, force pushes and deletion disabled, lock disabled, and intended ordinary fast-forward publisher/recovery writes preserved. The repository ruleset count `0` remains unchanged, so classic branch protection is the active server-side enforcement surface. Dependency Graph itself is policy-enabled for this public repository. SBOM REST export is verified unavailable through both documented generation surfaces at the recorded probe points; that scoped result must not be collapsed into a blanket `UNVERIFIED` item.

This governance closure is evidence, not standing authority. Future protection changes require a fresh administration-capable audit; repository YAML, CODEOWNERS or CI self-checks are not substitutes for server-side policy.

## Next safe work

1. Repository governance tracker #443 is complete; no current GitHub-governance remediation remains. Re-audit only after a future policy change or contradictory fresh evidence.
2. Reopen #503 or create a successor only when a fresh <=48h owner YouTube AuditPackage and/or exact owner media is available; do not substitute public downloads or stale evidence.
3. Any future Milovi growth/Dzen/provider/admin experiment needs a new exact scope and real attribution/outcome data; closed #353 is not standing authority.
4. Any live rollout of the completed #552 historical editorial lane needs a fresh release identity, media proof where applicable, exact review/canary and separate explicit execution authorization.
5. For any provider-visible work, start from fresh current `main`, fresh durable state, exact target identity, immutable operation identity and a new explicit owning authorization scope.

Nothing in this document is authorization for a provider mutation.