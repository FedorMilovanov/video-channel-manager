# Current operational state

Updated: 2026-08-10

This file is the concise current operational interpretation. It does **not** authorize provider mutation. Historical audits/PRs/issues are evidence only.

For every new task, resolve the exact current `main` commit and relevant durable state at task start; do not treat a SHA written in an old document as the live baseline.

Latest repository/local control continuation: [`control-audit-continuation-2026-08-09.md`](control-audit-continuation-2026-08-09.md).

## Current closure model

Repository implementation, final artifact production, and live provider rollout are separate completion states.

- Repository code may be complete while live rollout remains intentionally unauthorized.
- A media/artifact issue is not complete until the exact current-policy bytes are regenerated and verified.
- Future provider execution requires a new explicit exact operation/review; an old issue, release, credential, CI run, or artifact is never standing authorization.

## YouTube / Legendary Poet / «Чёрный человек»

Repository/local implementation is hardened and current:

- final album timing/render/package paths require exact accepted quality-master provenance;
- stale/tampered quality masters fail closed;
- canonical YouTube project identity is `project_key + OAuth alias + channel_id` and must be proved before credentials are relied on;
- description authoring is source-first and unresolved media-derived chapters fail closed;
- exact chapters can be rendered only from a digest-valid album package and produce immutable evidence bound to body/package/media/timing/quality-master hashes;
- same-media upload planning uses stable project/channel/media identity; timestamps or metadata changes cannot create a new journal namespace;
- current `main` includes the guarded YouTube release executor completed by Issue #232 / PR #271: read-only existing-target adoption, immutable provider-inert release planning, separate exact execution approval, durable child-operation state, resumable upload/status reconciliation, metadata/status, thumbnail, fully paginated playlist membership, visibility, top-level comment, and manual-only pin evidence; mutation transport uses zero blind retries. Canonical plans remain provider-inert and implementation completion does not itself authorize execution.

A separately authorized one-off provider rollout of the **historical pre-#213 media bytes** was completed on 2026-08-09 and is now durable remote-state evidence, not standing authorization:

- video ID `x-puy27S2qs`;
- uploaded media SHA-256 `sha256:e5450342249e95882136af35976ee3ab08bc85bba626a061be9944b28d8310a0`;
- final visibility `public`, processing succeeded;
- custom thumbnail verified present; exact input SHA-256 `sha256:1d10f48a6a3eb38e9e155e4771b4d58f504c41d8e3d5edad6283af44202ccdf8`;
- `selfDeclaredMadeForKids=false`;
- YouTube Studio AI-use setting observed `Yes`; `videos.list` omitted `status.containsSyntheticMedia` in the release readback and therefore that API omission is recorded as unobserved rather than false;
- playlist `Сергей Есенин` (`PLy9lLJfoq3uapKkid7HzfXHmSi3FR2y3Q`) membership verified present;
- playlist `Поющие Поэты` (`PLy9lLJfoq3uaxXMvilfZIYVXsf4fY18T8`) membership inserted and verified;
- top-level comment thread `UgwqMEOx27WrGwhO7Bt4AaABAg` created; pin state remains unverified/manual-only.

Exact retrospective/live-state evidence is recorded in [`black-man-youtube-release-retrospective-2026-08-09.md`](black-man-youtube-release-retrospective-2026-08-09.md) and [`black-man-youtube-live-state-2026-08-09.json`](black-man-youtube-live-state-2026-08-09.json).

Issue #154 remains **artifact-level open** for one reason: the uploaded/rendered album MP4 predates the quality-master binding fix. Completion requires regeneration from the seven accepted exact masters under the current pipeline, then fresh timing/render/verify/package/description evidence (SHA-256 + required ffprobe/QC). Do not reuse the historical MP4 as current-policy proof and do **not** reupload the album to solve this provenance gap.

The known public target `x-puy27S2qs` remains an external collision guard for the stable project/channel/media identity. Issue #232 is now repository-implementation complete and current `main` provides the read-only adoption/reconciliation path, but absence of a local journal still must never be interpreted as permission to create another `videos.insert` for the same media. Any future mutation requires a separately reviewed exact execution approval bound to the intended release operation.

No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state. The successful historical rollout does not authorize replay.

## Telegram / Lordchrist legacy quote publisher

The legacy `@lordchrist` quote publisher remains a live Telegram publishing track.

Durable reviewed state includes verified publications `1470`, `1472`, `1473`, and `1474`; later reviewed queue items remain governed by the strict durable ledger. Cross-author rotation is implemented without changing the immutable legacy queue/digest, so repeated-author history no longer forces exhaustion of one author before alternatives when a safe alternative exists.

Safety properties include lossless single-writer serialization, exact-current-main/CI gates around provider access, durable intent-before-send, zero blind mutation retry, archived exact provider outcome before final state persistence, evidence-bound recovery, publication-time-correct reconciliation, and cross-track blocking when either Lordchrist ledger contains an unresolved provider effect.

Do not modify the legacy live path merely to activate another content class.

## Telegram / Lordchrist research-v2

The canonical research-v2 evidence queue remains **staged/provider-inert**: claim/source/evidence validation is separate from provider execution, immutable evidence identity is separate from mutable activation state, and the generic Lordchrist profile remains `provider_writes_authorized=false`.

A separate exact live execution scope was explicitly reviewed in Issue #242 and is now installed on current `main` for the immutable release `lordchrist-research-live-2026-08` only:

- exact target: project `lord-god-strength`, channel `@lordchrist`, chat `-1001295216957`, bot `8716602202 / preaching_mp3_bot`;
- first strict canary: `lordchrist-research-three-preachers-numbers`;
- reviewed schedule: 2026-08-10, 12, 14, 16, and 18 at 15:00 `Europe/Moscow`, with a bounded same-day 15:47 catch-up opportunity;
- the first provider effect must be the exact canary in truthful manual mode; only a verified manual canary unlocks subsequent scheduled strict-next research items;
- execution authority is materialized only in an execution-only runtime profile; the canonical profile and canonical research schedule are not converted into standing broad write authority;
- durable research state lives separately under `state/lordchrist-telegram` at `content/telegram/lordchrist/research-v2/publication-ledger.json`; provider-visible outcome truth must be taken from the current durable state branch rather than this document;
- legacy and research share the `lordchrist-telegram-publisher` serialization namespace, explicit aggregate daily ceiling, and reciprocal unresolved-provider-effect blocking;
- exact current-main CI is required before provider access and again after durable intent; mutation transport retries remain zero;
- the 120-minute research freshness policy is checked both before preparation and again at the final generic send boundary, so a run that becomes stale while executing resolves provider absence without calling Telegram;
- ambiguous `may_exist` outcomes remain blocking until read-only reconciliation proves the next safe state.

Issue #168 is closed as repository implementation complete. Issue #242 authorizes only the exact reviewed August research release above; it is not standing authorization for another research release, new content, changed schedule, changed target, or broader generic Telegram writes.

## Telegram / Svodka

`@deep_info_life` has a separate generic multi-channel implementation, target binding, reviewed-content tooling, durable state model, provider-outcome recovery and deployment/catch-up safety regressions.

The exact August rollout is separately reviewed under Issue #235 and remains fail-closed at the manual-canary boundary:

- `content/telegram/channels/svodka.json` has `provider_writes_authorized=true` only for the reviewed rollout gates; this is not standing broad Telegram authority;
- immutable approval `content/telegram/svodka/release-approval-2026-08.json` binds release `svodka-pilot-2026-08` and approved digest `sha256:959a42e914acedc6969550ba842a12d1a2b174c940497d8a98f4ab8e2e63cdce`;
- pinned target is chat `-1003527567039` with bot `8716602202 / @preaching_mp3_bot`;
- the durable ledger now exists on `state/svodka-telegram`; at the latest verified checkpoint all 14 approved entries are still `pending` with `provider_effect=impossible`, with no verified manual canary or provider receipt;
- scheduled production remains blocked until the same-release manual canary is durably `published` with `provider_effect=verified`;
- mutable provider outcome truth must be read from the current durable state branch and Issue #235 at operation start; this document is not a substitute for either.

Issue #170 is closed as repository pipeline implementation complete. Issue #235 remains the live-rollout owner until its durable autonomous-publication closing criterion is met; no later or broader Svodka rollout is authorized by this August approval.

## Telegram runtime / supply chain

The minimal Telegram runtime is exact-version and SHA-256 hash locked with pip `--require-hashes`; production/minimal installs keep the hash-locked transaction isolated from test-only dependencies. CI validates the installed graph, guarded provider-free CLI surface, dependency audit, Python quality matrices and PowerShell operator environments.

`requirements/telegram-publisher.in` is the small root-constraint source for this production runtime; `requirements/telegram-publisher.txt` is one exact resolved/hash-bound closure. The production lock is excluded from routine Dependabot version edits because independent transitive changes can make the closure impossible. Any lock refresh is one explicit coherent supply-chain change that regenerates the whole exact closure and must pass isolated Python 3.11 install, `pip check`, guarded CLI smoke and dependency audit before acceptance.

One durable state/concurrency namespace has one write owner at a time. Parallel agents must not open competing hardening/mutation branches against shared Telegram runtime/state writers.

## VK

The completed Lord God postponed-text cleanup is historical verified evidence only. Supported reusable VK capability remains the guarded attachment-free postponed wall text-edit contract with exact project/community/owner/post binding, durable intent, no blind replay and exact postflight.

Historical browser/internal-web VK Audio executors and ZIP families remain retired/experimental evidence and are not current execution surfaces.

## Local MP3

Supported capability remains `local_only_read_only_intake_and_manifest`: inspect/probe/hash/tag inventory, deterministic manifests, explicit metadata policy and conflict classification.

It does not authorize ID3 rewrite, rename/transcode, browser automation, remote upload, metadata mutation, playlist changes, or wall publication.

## Local video / Resi DASH

Supported local-only capability is `video-manager resi handoff` (with `video-manager-resi` retained as a focused alias) for ordinary HTTP(S) DASH `Manifest.mpd` sources.

The workflow:

- accepts a manifest URL plus optional title and optional exact start/end;
- accepts operator-friendly `MM:SS[.mmm]` and `HH:MM:SS[.mmm]` timestamps and normalizes them deterministically;
- prints `yt-dlp -F` evidence and selects `bestvideo+bestaudio/best` without manual format-ID reconstruction;
- uses bounded download/fragment retries;
- preserves the full master and permits existing-master reuse only when a source receipt fingerprint and current master SHA-256 both match;
- fails closed unless master QC proves video, audio, and positive duration;
- optionally creates an exact trimmed second MP4 with NVENC runtime detection / CPU fallback and source-aware bitrate ceiling;
- stream-copies source audio during exact trim;
- writes source receipt + result JSON with exact master SHA-256 and, when trimming, exact clip SHA-256 plus normalized timing/duration evidence;
- writes user-facing outputs under canonical `operator-output`.

This capability has provider effect `impossible`. It does not bypass DRM/access controls, infer rights/permission, upload media, or authorize any provider mutation. The canonical runbook is [`resi-dash-local-handoff.md`](resi-dash-local-handoff.md).

## GitHub governance and external state

Read-only governance evidence is recorded in [`github-governance-readonly-probe-2026-08-09.md`](github-governance-readonly-probe-2026-08-09.md). Both one-shot probes used only `Contents: read` / `Metadata: read`, performed no checkout, and changed no repository setting or provider state.

At those probe points:

- `GET /branches/main` returned HTTP 200 with `protected=false`; the GitHub branch object did not mark `main` as protected;
- `GET /rulesets` returned HTTP 200 with repository ruleset count `0`;
- the detailed legacy branch-protection endpoint returned HTTP 403 to the integration, so nested legacy detail was not separately readable;
- this repository is public, and GitHub documents Dependency Graph as enabled/permanently enabled for public repositories;
- legacy `GET /dependency-graph/sbom` returned HTTP 404 `Not Found`;
- after GitHub's 2026 asynchronous SBOM API change was identified, current `GET /dependency-graph/sbom/generate-report` was independently probed with `Contents: read` and also returned HTTP 404 `Not Found`;
- GitHub's current SBOM REST documentation states that these export surfaces require only Contents(read), may be used without authentication for public resources, and document HTTP 404 as `Resource not found`.

The exact current conclusion is therefore: Dependency Graph itself is policy-enabled for this public repository, while GitHub **SBOM REST export is verified unavailable through both documented generation surfaces at the probe points**. This is no longer a blanket `UNVERIFIED` item. It is a scoped observed REST status and may change if GitHub changes repository/service state later.

`.github/CODEOWNERS` remains repository policy only; it must not be presented as branch protection. Green CI likewise does not create GitHub protection by itself.

Only `main` is a supported repository code/runtime execution baseline. `state/lordchrist-telegram` and `state/svodka-telegram` are durable state-only refs and must never be used as runtime/code sources. Any other branch is ephemeral and non-authoritative after its scope closes; delete it where supported or align the ref to exact current `main` after preserving any genuinely unique useful work through a focused PR.

Dependabot version-update work is a separate maintenance queue, not unresolved production state. Routine non-production-lock pip minor/patch updates may be grouped; all pip major upgrades are explicit compatibility work; GitHub Actions updates are grouped and exact-SHA pinned. The production Telegram hash lock is not a routine bot target. Every accepted maintenance change still requires exact-current-main CI.

## Provider/credential boundary

Credentials authenticate/select configuration; they do not choose the project target.

Canonical project identity, exact provider IDs, immutable release/plan, durable state and explicit execution authority select the operation. Never print, commit, package, log, or put provider credentials on a command line.

Unknown provider outcomes remain blocking until read-only reconciliation. A timeout, HTTP success, screenshot, stdout, filename, CI result, approval artifact, or visible UI state is not a provider postcondition.

## Next safe work

1. For #154, regenerate/verify the final seven-master Black Man artifact only when the exact accepted master bytes are available to the executing environment; do not reupload the known public target to resolve artifact provenance.
2. Treat Issue #232 / PR #271 as repository implementation complete only: use the guarded current-main YouTube executor only after a future exact execution approval is separately reviewed; no YouTube canary, upload, metadata/thumbnail/playlist/visibility/comment mutation, deletion, replacement, or replay is currently authorized by that completion.
3. Keep the Lordchrist research-v2 canonical evidence queue/provider profile inert and do not broaden execution beyond Issue #242's exact reviewed August release; read current provider outcome from the durable state branch, and require a new exact authorization for any later research release or changed schedule/target.
4. Keep Svodka inside Issue #235's exact approved August scope: read the current durable ledger first, resolve expired-slot recovery fail-closed, and never allow scheduled publishing before the same-release manual canary is durably verified.
5. Treat production Telegram lock refreshes as explicit coherent supply-chain changes; routine bot maintenance must not edit that closure piecemeal.
6. Treat the 2026-08-09 GitHub governance evidence as observed state, not permanent truth: future changes require fresh read-only verification rather than assumptions.

Nothing in this document is authorization for a provider mutation.
