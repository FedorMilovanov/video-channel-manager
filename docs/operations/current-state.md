# Current operational state
Updated: 2026-09-11

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
The exact repository checkpoint used for this documentation sync is `main` `880845214e0323dc883ff1d498d856eaa762293e`. Resolve fresh `main` again before any later operation; this SHA is evidence, not standing authority.
Recent hardening now present on `main` includes:
- LordChrist quote production: durable morning/evening slots, bounded same-Moscow-day leases, predecessor-to-successor handoff, reviewed 60-card successor corpus, source-integrity amendment, and successor-ledger initialization moved behind publication eligibility/current-main/target gates (#548, #551, #557, #559, #583, #590).
- LordChrist historical production: evidence-backed editorial foundation plus the separate archival-v3 recurring release, 16 media exhibits for eight recurring posts, reader-safe rendering, durable canary/editorial approval and pre-exhaustion successor guard (#556, #591).
- Instagram: guarded production publisher, exact target binding, local resumable MP4 upload with durable no-replay state, phase-aware failure reconciliation, immediate terminalization of explicit non-retriable 4xx rejects, ruleset-v3 progressive/4:2:0/closed-GOP proof, secret-safe wire/correlation diagnostics, reviewed public-HTTPS `video_url` fallback, and a credential-free `validate-local` command that reuses the production media boundary (#569, #573, #585, #592, #599, #601, #606, #611, #617, #623, #627).
- Repository/runtime hardening: provider-outcome/recovery cleanup, completed branch-hygiene deletion manifest, scheduled exact-main quality proof that waits up to 420 seconds while re-proving `main`, stale/divergent branch salvage classification, and non-executable preservation of the retired LordChrist v3 phase-1 acquisition provenance (#532, #536, #538, #540, #544, #550, #555, #595, #608, #616).
- Legendary Poet VK long-form: #622 removed the accidental `wall.get` hard gate. The active follow-up hardening moves native upload to stable `vk-native-video-wave-v2` identity: one YouTube source per run, canonical provider state, community mutex, fresh video-only duplicate check, explicit zero wall-publication flags, exact-ID readiness verification, and no blind mutation retry. Live provider transfer is still pending.

## Telegram / LordChrist verified quotes
Issues #541, #543, #582 and #589 are closed as **completed** after the slot-aware runtime, transport hardening, reviewed successor-corpus work, production handoff and state-initialization ordering fixes. Issue #168 is closed as repository implementation complete; implementation completion does not itself authorize execution.
The historical research-v2 canary ambiguity is no longer a legacy blocker. Issue #286 / PR #287 introduced the exact `retired_no_replay` disposition. For unrelated ambiguity, every other `dispatching` or `may_exist` effect remains fail-closed, and the retired August research release itself cannot resume, retry, or authorize a successor.
The authoritative production schedule remains schema v3:
- `morning`: 09:17 `Europe/Moscow`, every day;
- `evening`: 21:17 `Europe/Moscow`, Tuesday / Friday / Sunday;
- one verified publication maximum per slot and two maximum per eligible day;
- morning has a 720-minute same-day lease ending at the 21:17 editorial boundary;
- evening has a 160-minute lease that cannot cross the Moscow calendar-day boundary;
- `backfill_policy=none`;
- scheduled workflow reruns are forbidden;
- a same-day manual publication closes scheduled slots for that Moscow date.
Production binds `scheduled_slot` into durable ledger state and the dispatch envelope, persists intent before `sendMessage`, uses one provider attempt and zero blind mutation retries, and fails closed on ambiguous outcomes. Scheduler delay inside the reviewed lease is not catch-up/backfill; next-day execution remains impossible.
Scheduled exact-main quality proof may wait up to 420 seconds for a successful run proving the exact current `main` SHA. Every poll re-proves `main`; timeout or branch movement fails closed. Manual/non-scheduled invocations retain zero-wait behavior unless an explicit reviewed wait is supplied.
The immutable verified 30-post predecessor remains authoritative until exact terminal completion and cross-track provider-effect safety are proven. Incomplete predecessor state, digest mismatch, partial successor state or ambiguous provider effects block handoff.
When the predecessor becomes terminal, preview/preflight may materialize a missing successor ledger only in the local checkout. Durable successor-ledger initialization is allowed only after publication eligibility, exact-current-main quality proof and provider-target preflight and only on a publishing invocation.
The successor corpus remains a reviewed 60-card contract across 12 authors and 12 theological themes: 42 public-domain primary-source excerpts and 18 modern short quotations. Modern exact fragments and visible translated quotations remain capped at 25 words.
Current sealed successor identities:
- base candidate Git blob SHA-1: `da9d9c812772510ddcfe14cc5f69a6771e2dbc4c`;
- translation ledger SHA-256: `61eec8558cc62ea709c4c2aa835528fa7d5fa519ec624568e2327762434f5e59`;
- integrity amendment SHA-256: `b4d0346a2353c6e309c5003eb5a0c13b8dc60094e8f865e6d25da364e5783549`;
- normalized effective corpus SHA-256: `6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873`;
- release id: `lordchrist-successor-quotes-v1-integrity-v2`.
The sealed successor release itself remains `activation_policy=after_predecessor_queue_complete`, `release_state=staged_provider_inert`, `provider_writes_authorized=false`. The separate reviewed activation envelope is bound to exact predecessor/successor digests, Telegram target and presentation policy and may be selected only after predecessor terminality and provider-effect safety. It is not permission for a premature/manual send, replay, edit/delete/pin or MTProto action.

## Telegram / LordChrist historical rich editorial
Issue #552 is completed for the evidence-backed foundation: 52 accepted A/B+ sources from 69 reviewed URLs with exact evidence/theology and deterministic source/post/cycle bindings.
Issue #561 is closed as **completed** through PR #591. Canonical v2 remains preserved. Only actual GitHub Actions `schedule` execution bridges the exact legacy v2 release identity to archival-v3 under `GITHUB_ACTIONS=true` and `GITHUB_EVENT_NAME=schedule`; manual, PR and local paths do not silently activate it.
Archival-v3 contains eight remaining publications bound to 16 exact Git/media exhibits. Reader-facing rendering suppresses internal acquisition/evidence captions and claim-boundary prose; exact media bytes are re-proved before the one-shot rich send path; `replenishment_guard_remaining=1` prevents dispatch of the final pending post without an exact durable successor-cycle binding.
Canary Telegram message `1516` is durable `published` / `provider_effect=verified`. Editorial approval was recorded provider-free on `state/lordchrist-telegram` commit `1e0ce0e47bbb66f80cb6406a45937b52bcffe5a2`, with verified/approved timestamps `2026-09-10T11:42:41+00:00`.
The reviewed Monday/Wednesday/Saturday 19:17 `Europe/Moscow` archival-v3 cadence is armed only through normal exact-release/media/target/slot/quality/state/cross-track/replenishment gates. `backfill_policy=none` and one-shot/no-blind-replay semantics remain in force.
Issue closure and canary approval are not general Telegram authority. They do not authorize an ad-hoc historical send, alternate trigger, backfill, replay, edit/delete/pin or bypass of scheduled release/state gates. Earlier rich canary message `1484` remains historical completion evidence only.

## LordChrist YouTube Shorts -> Telegram native video
Repository implementation is complete and hardened through PRs #502, #504, #505, #515 and #516. The canonical provider-inert path remains `lordchrist_shorts_artifacts build-wave`, using stable `lordchrist-short-<youtube_video_id>` identities and exact owner snapshot/media bindings.
Issue #503 is closed as **not planned / externally blocked**, not artifact-complete. The last admissible materialized inventory reached 279 duration-eligible records; that owner snapshot later expired under the 48-hour freshness contract and no newer owner AuditPackage/local masters were available.
Do not substitute public/third-party downloads, stale-snapshot reinterpretation or replacement OAuth credentials. Reopen only when a new <=48h owner AuditPackage and/or exact owner media exists. No Telegram/Story/MTProto/YouTube mutation authority is created by the closed tracker.
Canonical runbook: [`lordchrist-shorts-feed.md`](lordchrist-shorts-feed.md).

## Telegram / Svodka
Issue #170 is closed as repository pipeline implementation complete. The historical approval bound release `svodka-pilot-2026-08`; its profile used `provider_writes_authorized=true` only for the reviewed rollout gates, and the durable ledger now exists on `state/svodka-telegram`. Those facts are historical evidence, not standing authority.
Issue #235 is completed with verified successor publications including Telegram messages `28` and `29`; the intervening v3 failed-no-effect identity is immutable and was not retried.
The original 14-entry ledger is terminal no-replay evidence. Consumed one-shot executors were retired. No new Svodka Telegram mutation is authorized by this state.

## VK / Legendary Poet long-form transfer
The historical #594 canary never reached `video.save`; binary upload did not begin and no VK wall/content mutation occurred. That old operator run is evidence only and must not be replayed.
The current native-video direction is deliberately smaller: prepare and execute one YouTube source at a time. `vk-native-video-wave-v2` separates durable source identity from snapshot/attempt evidence, stores provider state at a canonical source-keyed path, takes the one community mutex, rechecks the current VK Video surface immediately before a new reservation, and verifies the exact resulting VK video including title, duration, description digest, public state, type and playability. A historical VK target AuditPackage is optional advisory evidence; it is not the final absence authority.
The upload path does not call `wall.get` and does not build a multi-video batch ahead of the first result. Continue only from current `main` and the durable per-source state.

## VK / Milovi Cake / Issue #323
Issue #323 is closed. All 12 allowlisted Milovi Cake sources completed native VK Clip uploads with durable logical wall mappings. Older `OPEN`, `8/12`, `upload_in_progress` or `pending` checkpoints are historical only.
Do not duplicate a verified Clip because of transient projection; aggregate omission is not exact disappearance proof; ambiguous provider responses require exact reconciliation; retired finalizers must not return as second writers.
Canonical analysis: [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md). Architecture target: [`vk-native-clip-golden-path.md`](vk-native-clip-golden-path.md).

## Telegram / Milovi Cake / Issue #353
`.github/workflows/milovi-telegram-feed-publisher.yml` remains the only supported Milovi Telegram writer and owns `state/milovi-cake-telegram` through the reviewed generic prepare/send/apply contract.
`milovi-feed-20260819-001`, `milovi-feed-20260820-001`, `milovi-feed-20260820-002`, `milovi-feed-20260821-001` and `milovi-feed-20260906-001` are all historical identities now. Their release/execution windows are expired evidence, not current authority. Issue #353 has no standing Telegram provider authority. Any future publication requires a fresh identity plus current review, provider-free state initialization and separate fresh execution authority.
The native-video artifact lane remains complete at `16 / 16` accepted Telegram-ready MP4/H.264 outputs on evidence ref `agent/milovi-video-accepted-73c578eff825`, digest `sha256:73c578eff82563300c463361bd3998caeba8a083ce0de4ed29cc271617dfd6ae`.
Issue #353 is closed as **not planned for further work under the historical tracker**. Future growth/Dzen/paid placement/invite-link/admin/publication work requires a new exact scope and explicit authorization.
Canonical runbook: [`milovi-telegram-feed-control-plane.md`](milovi-telegram-feed-control-plane.md).

## Instagram / Legendary Poet and Lord God
Issue #492 is closed as repository implementation complete for the earlier provider-inert launch/content/factory scope. PR #569 provides the production publisher: explicit login/Graph configuration, exact identity preflight, default-off double write gate, durable SQL ledger, idempotent publication-key/content binding, CAS claims, fail-closed reconciliation and public-media integrity verification before provider POST.

Issue #571 / PR #573 introduced canonical Reel media compatibility. PR #585 added direct local-MP4 resumable upload with a hard 1 GB boundary, exact-byte re-proof, durable child state and zero blind replay. PR #599 aligned binary framing with Meta's reviewed complete-byte upload shape. PR #601 added phase-aware `video_status` handling, dedicated upload timeout, bounded provider diagnostics, the <=48 kHz AAC rule and MP4 edit-list/`moov` validation. PR #606 routes CLI reconciliation through that resumable state model. PR #611 preserves Meta's explicit retryability decision and immediately terminalizes definite HTTP 4xx upload rejects that report `retriable=false`; transport and 5xx ambiguity remain fail-closed/no-replay.

PR #617 / issue #614 moves local resumable media proof to ruleset v3: progressive scan, 4:2:0 chroma and a deterministic closed-GOP proof are required before provider intent. The proof inspects the local MP4 AVC/HEVC sample entry and verifies that every intra access unit is IDR rather than trusting container key-frame flags alone. PR #623 / issue #613 preserves a secret-safe outbound resumable request fingerprint and provider correlation evidence without changing the reviewed upload semantics; request `Content-Type` remains absent pending documented evidence. It also records the already-supported public-HTTPS `video_url` path as the preferred transport fallback if an immutable direct object URL can be provisioned and byte-verified without redirects. PR #627 / issue #624 adds provider-inert `video-manager instagram production validate-local`, which is credential-free/DB-free and shares the exact production local verification boundary, including MP4 structure, media ruleset-v3 and closed-GOP checks.

The canonical non-secret Legendary Poet target remains project `legendary-poet`, Instagram account `17841435926122104`, username `the.legendary.poet`, Facebook Page `1299632476567433`, login mode `facebook`, Graph host `https://graph.facebook.com`. Credentials authenticate this target; they do not redefine it and are not repository state. A fresh local read-only production preflight previously succeeded against that exact account/username and returned publishing quota `0/100` at that checkpoint; credential validity and quota must still be re-proved before any later provider work.

Provider publications remain 0. Neither `-03` nor `-04` reached `media_publish`. The reviewed CLEAN local MP4 is `sha256:93246e03a794e51d8b18b59f3a23cf9617c68e30bc1e723ca3265b914938667e`, size `81833620` bytes. It was produced by stream-copy remux with `-use_editlist 0 -movflags +faststart`; its MP4 structure was verified as `ftyp -> moov -> mdat` with no `edts/elst` edit list.

The single authorized CLEAN resumable canary `legendary-poet-yesenin-chto-eto-takoe-20260910-04` passed exact-target preflight, created container `18095416130197538`, then the binary upload returned HTTP 400 `ProcessingFailedError` with `retriable=false`. Read-only reconciliation proved the same terminal OIL ingest signature previously seen on `-03`: parent `terminal_failure`, child `provider_failed`, provider code `1363008`, `bytes_transferred=0`, `source_file_size=0`, and `OIL Error[FILE_NOT_FOUND: 6]`. This reproduced the failure after removal of edit lists and after the uploader moved to reviewed complete-byte framing, so neither of those earlier implementation details explains the observed `-04` failure.

Existing `-01` through `-04` publication keys/containers are immutable no-replay evidence. They must not be republished, re-uploaded or converted into permission for another attempt. There is no standing authorization for `-05` or any other Instagram provider mutation.

Issue #581 remains open for the first **successful** Legendary Poet canary. Before any later provider write, start from fresh current `main`, run the provider-inert `validate-local` command on the exact candidate bytes, re-prove exact target/quota read-only, freeze one new immutable publication identity/caption/feed choice, and obtain fresh operation-specific execution authority. If a stable direct public HTTPS object can be provisioned and byte-verified without redirects, the reviewed `video_url` transport is the preferred fallback because it bypasses the failing `rupload.facebook.com` ingest boundary.

The handoff remains one-way: exact local bytes -> provider-inert v3 validation -> immutable manifest/state binding -> read-only target/quota preflight -> separately authorized single provider write -> provider-visible reconciliation. No blind retry is allowed from ambiguous or terminal provider state.
Canonical runbooks: [`instagram-production-publishing.md`](instagram-production-publishing.md), [`instagram-local-resumable-upload.md`](instagram-local-resumable-upload.md) and [`instagram-facebook-token-lifecycle.md`](instagram-facebook-token-lifecycle.md).

## YouTube / Legendary Poet / «Чёрный человек»
The historical authorized rollout is complete. Public video `x-puy27S2qs` remains the collision guard. Processing, public visibility, thumbnail, playlist membership and top-level comment were verified. The current `main` includes the guarded YouTube release executor; implementation completion does not itself authorize execution. Issue #154 is closed as **completed**. The historical provenance gap predates the later quality-master binding rule and is not required rework. Do not regenerate or reupload the album solely to satisfy policy introduced after the published bytes were produced.
No future YouTube upload, metadata/thumbnail/playlist/visibility/comment mutation, deletion or replacement is authorized by this state.

## Telegram runtime / supply chain
The minimal Telegram runtime remains exact-version and SHA-256 hash locked with pip `--require-hashes`. Production/minimal installs keep this transaction isolated from test-only dependencies. Any lock refresh must pass isolated install, `pip check`, provider-free guarded CLI smoke and dependency audit.
One durable state/concurrency namespace has one write owner at a time. Parallel agents must not create competing provider writers against the same state namespace.

## Local MP3 and Resi DASH
Local MP3 remains `local_only_read_only_intake_and_manifest`: inspect/probe/hash/tag inventory and deterministic manifests only; no rewrite, rename/transcode, remote upload or provider mutation.
Resi remains `watch -> sample -> explicit handoff`. The watcher never auto-dispatches a multi-gigabyte FULL download; the retained `<TITLE> - FULL.mp4` master goes to canonical Windows Downloads (`C:\Users\Fedor\Downloads`); generated handoff/watcher control files and exact-trim outputs remain under repository `operator-output` unless explicitly redirected. Provider effect remains `impossible`.
Canonical runbooks: [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md) and [`resi-grace-russian-live.md`](resi-grace-russian-live.md).

## Repository branch hygiene / Issue #531
Issue #531 is closed as **completed**. PR #550's frozen baseline produced 138 DELETE candidates, physically removed with exact-SHA rereads and zero open-PR collisions.
PR #608 later classified newly accumulated stale/divergent refs without disturbing active lanes. PR #616 preserved the final unique LordChrist archival-v3 phase-1 acquisition JSONs byte-for-byte as documentation-only history before that obsolete execution branch was retired.
A previously recorded post-cleanup ref count is not a durable invariant. Any later hygiene pass must resolve fresh complete refs and classify them by durable-state role, open ownership and unique evidence. Never delete/rewrite a ref merely by prefix/age or treat a durable state ref as disposable debt.

## GitHub governance / Issue #443
Issue #443 is closed as **completed**. Fresh administration-capable evidence at closure proved `protected=true`, required-status enforcement level `everyone`, the exact eight required GitHub Actions checks bound to GitHub Actions App ID `15368`, strict checks, PR-before-merge, administrator enforcement, conversation resolution, force-push/deletion disabled and no ordinary bypass. The three durable state refs use the intended protected state-safe profile.
The repository ruleset count `0` remains unchanged, Dependency Graph itself is policy-enabled for this public repository, and SBOM REST export is verified unavailable through both documented generation surfaces; that scoped result must not be collapsed into a blanket `UNVERIFIED` item.
This closure is evidence, not standing authority. Future protection changes require fresh administration-capable audit; repository YAML/CODEOWNERS/CI self-checks are not substitutes for server-side policy.

## Next safe work
1. Reopen #503 only with a fresh <=48h owner AuditPackage and/or exact owner media.
2. Future Milovi/Dzen/provider/admin experiments require new exact scope and real attribution/outcome data.
3. LordChrist historical #561 is complete through #591; archival-v3 may progress only through exact scheduled release/state gates, and later cycles require exact successor binding before the final pending post.
4. Instagram #577 is complete. #581 remains open for the first successful canary: run the credential-free `validate-local` boundary on the exact candidate, re-prove target/quota read-only, prefer a verified immutable public-HTTPS `video_url` fallback if available, and require fresh operation-specific authority before one new provider write. Never replay `-01`..`-04`; no `-05` is currently authorized.
5. Legendary Poet YouTube -> VK live transfer is still pending. Use the current one-source `vk-native-video-wave-v2` path; do not replay the historical canary, manufacture a multi-video batch, require `wall.get`, or use an old aggregate missing count as the final duplicate check.
6. For provider-visible work, start from fresh current `main`, fresh durable state, exact target identity, immutable operation identity and a new explicit owning authorization scope.

Nothing in this document is authorization for a provider mutation.
