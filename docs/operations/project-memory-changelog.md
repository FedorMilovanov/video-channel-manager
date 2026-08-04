# Project memory changelog

This file records durable changes to operational memory. Add an entry whenever project identity, exact provider IDs, selected project state, OAuth aliases, link profiles, completed/blocked operations, resume safety, provider contracts, or active artifact paths change.

## 2026-08-04

### Wave 6 completed — stable versioned wave engine

- Merged PR #78 as `c4c4d3233ec20b8f939343c5d667d8687d7ff040`.
- Exact-head CI run `30908185487` passed dependency audit, compileall, Ruff, formatting, strict mypy, and full pytest on Python 3.11, 3.12, and 3.13: `611 passed, 1 xfailed`.
- Pester passed `20/20` on Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux.
- Added strict immutable v1 source/plan/apply/result/reconciliation schemas with exact project, snapshot, policy, file, operation-set, and self-digest binding.
- Classified all 91 Python scripts; retired 26 direct provider-write executors before functions, credentials, paths, or provider dispatch.
- Confined historical private cross-script imports to compatibility adapters; the supported engine imports no historical `scripts.*` modules.
- Added atomic per-operation journals, automatic replay prohibition, one-attempt ambiguous mutation semantics, and exact unknown-operation reconciliation.
- Restricted PowerShell provider mutations to the complete Wave 6 `wave apply` contract; no implicit production provider adapter is registered by the CLI.
- No VK or YouTube provider write occurred during implementation or CI.
- Wave 6 issue #76 closed; Wave 7 fault-injection work is owned by issue #80.

### Wave 5 completed — reliable Windows/PowerShell operator layer

- Merged PR #75 as `1a62779293a404e4654b6230644dfc78e9b20dc1`.
- Exact-head CI run `30900532613` passed dependency audit, compileall, Ruff, formatting, strict mypy, and full pytest on Python 3.11, 3.12, and 3.13: `591 passed, 1 xfailed`.
- Pester passed `17/17` on Windows PowerShell 5.1, PowerShell 7 on Windows, and PowerShell 7 on Linux.
- Classified 23 production `.ps1` files as 1 supported, 3 compatibility-only, and 19 retired; the Pester test file is separately bound as test-only.
- Added canonical UTF-8/LF wrapper digests stable across Windows CRLF and Linux LF checkouts.
- Historical provider-write wrappers now stop before credentials, hard-coded paths, nested shells, or child execution.
- Added one supported manifest-driven operator with exact request/manifest SHA-256, exact project/community/owner/snapshot/count confirmations, strict JSON types, output-collision rejection, and safe-read CLI allowlisting.
- Added one Python 3.11/3.12/3.13 resolver, native exit-code evidence, UTF-8 without BOM, and atomic JSON replacement.
- Apply remains impossible in CI and requires `ambiguous_mutation`, a positive operation count, and `-EnableProviderWrites` outside CI.
- Nonzero ambiguous mutations remain `unknown_requires_reconciliation`, non-retry-safe, and never auto-replayed.
- No VK or YouTube provider write occurred during implementation or CI.
- Wave 5 issue #72 closed; Wave 6 stable engine work is owned by issue #76.

### Wave 3 completed — central HTTP ownership and safe-read reliability

- Merged PR #70 as `995167bdadc90d8d53414570cc3e5010bc4a93f2`.
- Exact-head CI run `30871435907` passed dependency audit, compileall, Ruff, formatting, strict mypy, and full pytest on Python 3.11, 3.12, and 3.13.
- `platforms/http.py` is now the only reusable `src/` factory for direct `httpx.Client()` construction.
- `YouTubeCommentWriter` moved from per-request construction to one owned/borrowed persistent client.
- Ten remaining bounded one-shot script constructors are documented and protected by an AST inventory gate.
- Added explicit `SAFE_READ` versus `AMBIGUOUS_MUTATION` retry authority.
- Added bounded backoff, bounded valid `Retry-After`, injectable jitter, deterministic limiter timing, structured failure kinds, and attempt evidence.
- Ambiguous YouTube, VK, OAuth, upload-server, and thumbnail mutations execute once and surface externally non-retryable outcomes.
- Added redaction boundaries for tokens, OAuth secrets, authorization values, token endpoints, opaque upload URLs, and sensitive payload details.
- Cached the YouTube uploads playlist ID for the client lifecycle.
- Added an injectable thread-safe request limiter with zero default; no unverified VK request rate was embedded.
- Added ownership, retry, limiter, redaction, OAuth, thumbnail, and externally non-retryable mutation regression coverage.
- No VK or YouTube provider write occurred.
- Wave 3 issue #69 closed; Wave 4 remains owned by issue #36.

### Wave 2 completed — fail-closed project/content pipeline

- Merged PR #68 as `19c2671bf91c8376def527a592e0bb7674841d03`.
- Exact-head CI run `30867659234` passed all gates on Python 3.11, 3.12, and 3.13.
- Removed implicit project fallback from reusable canonical and legacy content parsing.
- Added expected project/channel context before preview and plan rendering and rejected mixed-project batches.
- Bound content plan schema v2, operation IDs, operation-set digest, and plan digest to `project_key`.
- Required exact bidirectional loaded-record↔operation coverage.
- Made `scripts/sync_youtube_to_vk.py` internal-only with immutable `SyncRuntime`.
- Replaced production monkeypatching with one supported dependency-injected sync entrypoint.
- Preserved Wave 1 upload lifecycle, media QC, writer lock, `wallpost=0`, and no blind mutation retry.
- No VK or YouTube provider write occurred.

### Wave 1 completed — journaled VK upload lifecycle

- Merged PR #66 as `56da03247f60ec9d25f1646fb9ccdfbb651aff9c`.
- Added versioned upload stages from `planned` through `verified`, plus `rejected` and `unknown_requires_reconciliation`.
- Persisted reservation intent before `video.save`, a separate dispatch marker before request dispatch, and exact ticket evidence before media transfer.
- Distinguished safe pre-dispatch restart from ambiguous post-dispatch provider outcome.
- Required exact identity/title/duration/type/processing/playability evidence before `verified`.
- Added atomic JSON journal durability and crash/replay fault coverage.
- Preserved no-blind-retry behavior and separated live historical reconciliation from architecture work.
- No VK or YouTube provider write occurred.

### Wave 4 completed — fail-closed upload/wall separation

- Merged PR #71 as `d85f7cf94b8ba0b30947291b3a08491239438843`.
- Merged living-state synchronization PR #73 as `3bf01aec2f0d17133f0ec5821f88d63ec92373bb`.
- Exact-head CI run `30895905586` passed dependency audit, compileall, Ruff, formatting, strict mypy, and full pytest on Python 3.11, 3.12, and 3.13: `586 passed, 1 xfailed`.
- Added immutable self-digested `wall_mutation_authorized=false` upload policy.
- Every supported `video.save` now sends `wallpost=0`, `auto_publish=0`, and `repeat=0` explicitly.
- Missing-policy journal migration is allowed only before provider dispatch and recomputes operation identity and initial evidence.
- Provider-dispatched historical journals without the policy fail closed and require reconciliation.
- Upload batches bind complete published+postponed wall baseline evidence and require a clean postflight delta before `verified`.
- Postponed publication is the only supported default wall-write path, with exact future `publish_date`, deterministic `guid`, duplicate/schedule collision checks, and one-attempt ambiguous-response reconciliation.
- Unexpected wall objects are classified but never automatically deleted; issue #37 remains the only owner of its exact cleanup scope.
- No VK or YouTube provider write occurred during implementation or CI.
- Wave 4 issue #36 closed; Wave 5 operator-layer work is owned by issue #72.

### Wave 0 canonical-state consolidation

- Added `master-audit-2026-08-04.md` as the canonical audit synthesis and Waves 0–10 roadmap.
- Added `audit-register-2026-08-04.json` with 25 findings, explicit status/severity/wave/owner, and protection against reactivating fixed, retracted, or disputed claims.
- Updated `current-state.md` from the verified code baseline and retained exact project/live-queue boundaries without retransmitting anything.
- Updated `automation-backlog.md`, the operations index, and root `AGENTS.md` to require the canonical audit/register before work.
- Created issue #65 for the Wave 1 journaled upload state machine and fault-injection contract.
- Expanded issue #64 into the master Waves 0–10 tracker.
- Closed superseded draft PR #29 without merge; preserved its reusable ledger/reconciliation ideas while prohibiting the old destructive executors.
- No VK or YouTube provider writes were performed during Wave 0.

## 2026-08-02

### Universal operational publication/link contracts added

- Added `src/video_channel_manager/editorial/publication_links.py` as the central project-aware publication-link contract for web, Telegram, VK public, VK Clips, Rutube, VK author-cabinet, and VK admin/comment routes.
- Added explicit route-role separation: `audience`, `author`, and `operational`.
- Added project-specific public link surfaces for both `lord-god-strength` and `legendary-poet`.
- Added structured audit records for publication, persistence, transactional and provider-notes URLs.
- Added `scripts/audit_publication_links.py` with JSON output support and expected-project enforcement.
- Added tests that reject public/admin route swaps, invalid runtime publication URLs, cross-project publication records, and tampered catalog proofs.
- Updated the operations index and public docs to point to the corrected canonical profiles.

### Exact source-derived project link profiles added

- Added `lord-god-strength-description-profile.md` with exact footer links, related project links, prohibited substitutions, and article footer guidance.
- Added `legendary-poet-description-profile.md` with exact footer links, public VK Clips route, VK author-cabinet separation, prohibited substitutions, and article footer guidance.
- Recorded that Господь Бог — Сила Моя uses `https://lord-god-strength.ru/`, `https://t.me/lord_god_strength`, `https://vk.com/lordgodstrength`, and `https://rutube.ru/channel/75847456/`.
- Recorded that The Legendary Poet uses `https://thelegendarypoet.ru/`, `https://t.me/thelegendarypoet`, `https://vk.com/thelegendarypoet`, and `https://rutube.ru/channel/76394077/`.
- Recorded that The Legendary Poet public VK Clips are under `https://vk.com/clips/legendarypoet`, while `https://vk.com/clip/milovanov_fedor` is an author-cabinet route, not the public project route.
- Recorded that `https://admin.thelegendarypoet.ru/` is operational infrastructure, not a public project link.
- Corrected the operational index so The Legendary Poet no longer points to the Господь Бог description standard.
- Added a project-link audit record covering verified routes, compatibility routes, operational routes, and remaining synchronization work.

## 2026-08-01

### Project identity and credential boundary formalized

- Recorded exact `lord-god-strength` identities:
  - YouTube `UCeSJsC6go2c9pdJCuUI1BYA`;
  - YouTube OAuth alias `fedor-milovanov`;
  - VK community `60805374`;
  - VK owner `-60805374`;
  - verified public link `https://youtube.com/@ГосподьБогСилаМоя`.
- Recorded exact `legendary-poet` identities:
  - YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`;
  - YouTube OAuth alias `legendary-poet`;
  - VK community `235216998`;
  - VK owner `-235216998`.
- Recorded that the shared VK credential alias `legendary-poet` is a credential label only and never selects a project.
- Added a formal `ProjectIdentity` registry and strict runtime project-ID matching.
- Bound upload-plan validation, upload-plan preview, and guarded legacy-plan upgrade to exact `project_key` plus target community/owner.
- Recorded that `lord-god-strength` YouTube access is read-only and must never be used for mutations.

### Durable database setup added

- Recorded that every SQLite connection now enforces WAL, a 5000 ms busy timeout, and foreign keys.
- Added tests that verify foreign-key rejection and concurrent-writer waiting behavior.

## 2026-07-31

### Closed: VK duplicate cleanup

- Final `completed-run.json` recorded:
  - `confirmed_deleted: 403`;
  - `planned: 0`;
  - `unresolved: 0`;
  - `run: completed`.
- Confirmed that `KobOzfBqzic` is present in VK and is the transfer boundary.
- Confirmed that `s512Opa8Eu4` maps to VK `-60805374_456241938`.
- Permanent rule: never run bulk duplicate cleanup again without a fresh inventory and one explicit immutable plan.

### Closed: theological article photo wave

- Confirmed 10/10 postponed posts on VK.
- Exact post IDs: `12471`, `12472`, `12473`, `12474`, `12475`, `12476`, `12477`, `12478`, `12479`, `12480`.
- Exact schedule: 2026-08-04 through 2026-08-13.
- Permanent rule: never rerun the old article-photo Apply package.

### Blocked: long-form upload continuation

- Reviewed long-form queue newer than `KobOzfBqzic` contains 27 items.
- One is already present: `s512Opa8Eu4`.
- Verified missing count: 26.
- Manifest SHA-256: `b9c0268be62ea8fb9281cc9a551ebc5621dfdd4bfeb22a9d8f4b50707baa33ed`.
- Local package root: `C:\Users\Fedor\Projects\video-channel-manager\data\vk-upload\verified-longform-26`.
- Continuation is blocked until exact reconciliation of accepted, processing and unknown rows under issue #31.

### Blocked: Shorts/Clips continuation

- Canonical source inventory is recorded as 108 Shorts.
- Upload completion and final `short_video` classification are not proven.
- Issues #32 and #38 own the inventory and final type/player behavior.
- Permanent rule: long-form and Shorts remain separate manifests and ledgers.

### Wall safety incident recorded

- A previous transfer produced a large sequence of one-video wall posts.
- Upload and wall publication were formally separated in operational policy.
- Immediate publication was blocked by default.
- Issue #36 owns the universal upload/wall contract and future fresh read-only audit.
- Issue #37 owns only the exact approved cleanup scope.
- `guid` was recorded as an additional guard, not complete idempotency.

### Historical destructive PR retired

- Draft PR #29 was marked superseded and closed without merge.
- The old delete orchestrator and destructive state were retained only as historical evidence.
- Permanent rule: never rerun historical deletion executors.

## 2026-07-30

### Low-view Shorts replacement completed

- Replaced 34 reviewed low-view Shorts with ordinary videos.
- Removed the generated wall posts associated with those replacements.
- Protected post `12400` remained present.
- No broad wall-cleanup permission was implied.

## 2026-07-29

### The Legendary Poet V3 preparation recorded

- Latest reviewed matrix:
  - 56 exact YouTube Shorts;
  - 41 exact YouTube→VK pairs;
  - 15 confirmed missing;
  - 0 ambiguous;
  - 0 extra vertical VK objects.
- Exact pair retained: YouTube `BXZeRiEOHmQ` → VK `-235216998_456239039`.
- Old `59/40/19/1` matrix retired.
- Two protective stops performed no new VK writes.
- V3 canary preparation exists, but completed V3 Apply/postflight is not proven.
- Permanent rule: do not run the old package or upload the 15 candidates until the exact V3 journal is recovered and reconciled.

## 2026-07-28

### Separate VK Audio browser workflow identified

- Browser-based VK Audio automation belongs to the adjacent `mp3telegrambot` system.
- It uses undocumented web contracts and is not part of the supported API-based video/wall executor family.
- Permanent rule: keep it separate until a formal manifest/result/unknown-outcome interface exists.
