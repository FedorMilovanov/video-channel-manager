# Current operational state

Updated: 2026-08-09

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
- upload planning remains provider-inert (`plan/status/abandon` only);
- current-main read-only release adoption can bind immutable live-state evidence plus exact provider readback into the same stable journal, with canonical identity checked before OAuth material is loaded;
- the durable release child-state model preserves immutable payload digests, blocks on `may_exist`, preserves verified parents and marks an adopted existing target as already-uploaded rather than replaying upload;
- there is still **no provider upload/release execute command** in the supported baseline. Issue #232 remains open for the concrete mutation/resume transport layer.

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

The known public target `x-puy27S2qs` remains a collision guard even before local adoption. The current-main read-only command `python -m video_channel_manager.youtube_release_cli adopt-existing ...` can now represent such evidence as a `verified` stable journal entry with provider writes fixed at zero. Absence of a local adoption journal is never permission to create another `videos.insert` for the same media.

No future YouTube upload, metadata edit, thumbnail change, playlist mutation, visibility change, comment mutation, deletion or replacement is authorized by this state. The successful historical rollout does not authorize replay.

## Telegram / Lordchrist legacy quote publisher

The legacy `@lordchrist` quote publisher is the only live Telegram publishing track represented here.

Durable reviewed state currently includes verified publications `1470`, `1472`, and `1473`; later reviewed queue items were pending with `provider_effect=impossible` at the latest control audit, with no reviewed unresolved `may_exist` entry.

Safety properties include lossless single-writer serialization, exact-current-main/CI gates around provider access, durable intent-before-send, zero blind mutation retry, archived exact provider outcome before final state persistence, evidence-bound recovery, and publication-time-correct reconciliation.

Do not modify the legacy live path merely to activate another content class.

## Telegram / Lordchrist research-v2

Research-v2 repository implementation is complete as a **provider-inert content/release track**:

- claim/source/evidence validation is separate from provider execution;
- immutable evidence identity is separate from mutable activation state;
- exact target-bound release review/approval is provider-inert;
- generic Lordchrist profile remains `provider_writes_authorized=false`;
- no research sender/scheduler is activated by this state.

Issue #168 is closed as repository implementation complete. The closure is not standing authorization for a live research canary. Any future live research publication is a new explicit rollout scope and must re-establish its current execution gates.

## Telegram / Svodka

`@deep_info_life` has a separate generic multi-channel implementation, target binding, reviewed-content tooling, durable state model, provider-outcome recovery and deployment/catch-up safety regressions.

Current activation state remains fail-closed:

- `content/telegram/channels/svodka.json` has `provider_writes_authorized=false`;
- pinned target is chat `-1003527567039` with bot `8716602202 / @preaching_mp3_bot`;
- no approved live August release is present at the latest control point;
- no live Svodka publication ledger is present at the latest control point;
- no Svodka provider mutation or scheduled production is authorized by this state.

Issue #170 is closed as repository pipeline implementation complete. A future canary or scheduled pilot is a separate live rollout decision and requires a new explicit exact provider scope rather than reopening generic implementation work.

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
2. Complete Issue #232 with the concrete current-main provider mutation/resume layer on top of the read-only adoption and durable release child-state model; the issue still authorizes no live canary or provider write.
3. Keep Lordchrist research-v2 and Svodka provider-inert unless a new explicit live execution request is created and reviewed.
4. Treat production Telegram lock refreshes as explicit coherent supply-chain changes; routine bot maintenance must not edit that closure piecemeal.
5. Treat the 2026-08-09 GitHub governance evidence as observed state, not permanent truth: future changes require fresh read-only verification rather than assumptions.

Nothing in this document is authorization for a provider mutation.
