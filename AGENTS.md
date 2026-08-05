# Repository agent instructions

Read these sources before work on Fedor Milovanov's YouTube/VK workflow:

1. `docs/operations/project-identity-registry.md`
2. `docs/operations/current-state.md`
3. `docs/operations/audit-register-v9-2026-08-05.json`
4. `docs/operations/audit-register-v8-2026-08-05.json`
5. `docs/operations/master-audit-marathon-v2-2026-08-04.md`
6. `docs/operations/agent-reasoning-playbook.md`
7. `docs/operations/mp3-batch-processing-contract.md`
8. `docs/operations/wave16-ci-sqlite-mp3-hardening-2026-08-05.md`
9. `docs/operations/vk-audio-browser-experiment-retrospective.md`
10. `docs/operations/wave15-transcript-and-agent-audit-2026-08-05.md`
11. `docs/operations/audit-register-v7-2026-08-05.json`
12. `docs/operations/audit-register-v6-2026-08-05.json`
13. `docs/operations/audit-register-v5-2026-08-05.json`
14. `docs/operations/audit-register-v4-2026-08-05.json`
15. `docs/operations/audit-register-v3-2026-08-05.json`
16. `docs/operations/audit-register-v2-2026-08-04.json`
17. `docs/operations/automation-backlog.md`
18. `docs/operations/repository-integrity-audit-2026-08-05.md`
19. `.github/copilot-instructions.md`
20. `docs/operations/local-credential-sources.md`
21. `docs/operations/operational-artifact-standard.md`
22. `docs/operations/operational-package-acceptance.md`
23. `docs/operations/retirement-registry-v1.json`

Current machine state and `current-state.md` override old chats, screenshots, ZIP names, remembered counts, stale issue wording, historical packages, and superseded audits. Historical material teaches; it never authorizes execution.

## Current verified baseline

Current code baseline: `main@22ed56256df3388c23c9f785f1e02cca71fd8524`.

Current program state: `WAVES_0_16_COMPLETED_CI_RUNTIME_SQLITE_MP3_IDENTITY_HARDENED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`.

Wave 16 proof:

- issue #137 and PR #138;
- exact head `c495308430bce6e1b86343b6cd4e6ae3a302734b`;
- merge `22ed56256df3388c23c9f785f1e02cca71fd8524`;
- CI `31022560789`;
- Python 3.11/3.12/3.13: `845 passed, 1 xfailed`;
- coverage `79%` across `14,675` statements;
- Ruff `464 files already formatted`;
- strict mypy `147 source files`;
- dependency audit clean;
- all three PowerShell environments green;
- no Node 20 action warning;
- no unclosed SQLite database warning;
- provider queries/writes/write plans/historical executor runs `0/0/0/0`.

No operational continuation is pending. Provider writes remain unauthorized. Issue #139 is state synchronization only and owns no provider operation.

## Exact project and credential boundary

This repository manages two separate projects:

- `lord-god-strength` — Господь Бог — Сила Моя;
- `legendary-poet` — The Legendary Poet — Легендарный Поэт.

Canonical identities:

- Lord God: YouTube `UCeSJsC6go2c9pdJCuUI1BYA`, OAuth alias `fedor-milovanov`, VK community `60805374`, VK owner `-60805374`;
- Legendary Poet: YouTube `UC-78ys2S3cQ3lpqgXfo-SvQ`, OAuth alias `legendary-poet`, VK community `235216998`, VK owner `-235216998`.

VK uses one shared user access token from external `VK_API_TOKEN`. The local VK alias `legendary-poet` names the stored credential; it is not a project selector. Exact project key, community/owner IDs, manifests, journals, results, and links select the target.

YouTube aliases are channel-specific. They do not imply separate VK tokens.

Never print, copy, package, commit, log, request manual entry of, or put the configured VK token on a command line.

## Adaptive reasoning contract

Agents reason from invariants and observable state transitions rather than copying one exact historical script.

Before implementation or handoff, state:

- requested outcome independently of mechanism;
- exact project, surface, and object type;
- one transport per phase: local only, official API read/write, internal web read, or browser UI read/write;
- allowed and forbidden side effects;
- operation phase;
- provider-effect state: impossible, not dispatched, confirmed absent, may exist, or verified;
- exact completion postcondition;
- one falsifiable hypothesis, one minimal bounded probe, and one stop condition.

A timeout, exit code, selector match, click, HTTP success, modal closure, visible title, screenshot, playback state, or stdout line is not a provider postcondition.

Preserve partial success. Upload, processing visibility, metadata edit, playlist creation, membership change, final save, and wall publication are separate child operations. Resume from the first unverified child phase. Never rerun a verified parent phase.

Unknown or possibly completed remote effects require read-only reconciliation. Never repeat an intent-persisted, accepted, processing, verified, or unknown mutation.

After the first diagnostic selector revision, patch repository-owned code and fixtures. Stop the ZIP/version treadmill. A second failure requires a fresh DOM/state observation and revised hypothesis.

## Browser UI state contract

Before every browser action:

1. bind the topmost active page or modal root;
2. prove visibility and hit-testability;
3. prove the control belongs to that root;
4. record expected state transition;
5. capture before-state evidence;
6. perform one action;
7. verify exact content/state and remote postcondition.

A background search input is not an audio selector. Playback is not selection. Artist text inside a title is not proof of an exact separate artist field. `already_correct` requires exact per-field readback.

One authenticated browser profile is a single-writer resource. Own one exact profile directory, refuse concurrent writers, and terminate its root process tree once.

## Local MP3 contract

Supported capability is exactly `local_only_read_only_intake_and_manifest`.

Current manifest schema is `1.1`. Local code may inspect MP3 bytes and ffprobe properties, retain exact tags/SHA/path/size/duration, apply explicit or declared metadata policy, detect exact-byte duplicates, and build deterministic manifests and chunks.

Canonical duplicate selection is evidence-ranked:

1. explicit exact artist/title;
2. declared-policy ready metadata;
3. unresolved metadata;
4. path only as a deterministic tie-breaker.

One source ID mapped to multiple hashes is `source_id_sha256_conflict`. Identical bytes claimed by multiple exact source IDs is `sha256_multiple_source_ids`. Every such item remains `requires_review`; no conflict becomes upload-ready automatically.

Wave 16 proves deterministic local planning for 1,000 ready tracks, 1,000 unique operation IDs, and 40 chunks of 25. This is not provider throughput evidence or permission.

The default metadata policy is `explicit_only`. Never infer a filename convention unless the manifest declares it.

Not implemented or authorized: ID3 rewrite, rename, transcode, browser launch/control, VK Audio upload, remote metadata edit, playlist creation/membership mutation, or wall publication.

VK Audio browser/internal-web work remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. BrowserCanary, PlaylistOnly, Metadata Manager, Rename AUTO, reliable-batch, calibrator, Playlist Workhorse, and related ZIPs are evidence only.

## SQLite and CI lifetime contract

`sqlite3.Connection.__exit__` does not close a connection. Repository code and fixtures use `contextlib.closing`; tests treat `ResourceWarning: unclosed database` as an error.

CI actions are pinned by immutable SHA to Node 24-generation releases. Do not downgrade them to old Node 20-generation pins. A version comment is descriptive; the immutable SHA is authoritative.

## Package and operational truth

Package A output never authorizes a provider mutation by itself. It creates read-only evidence and no-blind-replay decisions.

PowerShell orchestrates one repository-owned implementation. It does not become a second provider client. Generated external provider executors are unsupported.

Green CI, a filename, ZIP, preview, issue body, confirmation prompt, stdout line, dashboard, README command, visible UI object, or roadmap entry never authorizes execution.

## Historical compatibility ledger

Wave 15 predecessor:

- `WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`;
- `main@eb58c1ad238fde01d66c6630b16e244b1c6c2992`;
- PR #134, CI `31006136529`, `833 passed, 1 xfailed`, Ruff `461 files already formatted`;
- machine state `docs/operations/audit-register-v8-2026-08-05.json`.

Wave 14 predecessor compatibility anchors:

- `WAVES_0_14_COMPLETED_REPOSITORY_POLISHED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`;
- historical `main@626f83c6e5c068d7faa8b6d14163b42916faa769`;
- PR #131, CI `31000834701`, `801 passed, 1 xfailed`;
- repository-wide JSON/Markdown integrity regressions.

These are historical proofs, not current work.

## Final issue graph

Completed:

- #31 — exact Lord God 26-item long-form reconciliation;
- #119 — Legendary Poet Shorts/Clips reconciliation;
- #38 — shared VK native Clip/ordinary-video final-type contract;
- #130 — repository-wide documentation and integrity polish;
- #133 — adaptive reasoning and local-only MP3 foundation;
- #137 — CI runtime, SQLite lifetime, and MP3 identity hardening.

Retired/not planned:

- #32 — Lord God non-authoritative 108-item Shorts auto-upload scope;
- #33 — broad Lord God catalog/publication continuation;
- #99 — unproved Legendary Poet article-wall launcher continuation;
- #123 — deferred YouTube playlist mutation scope.

Do not group #32/#38 as Legendary Poet. Historically #32 belonged to Lord God, #38 was shared, and #119 belonged to Legendary Poet.

`M5hNecL_MsQ → -235216998_456239160` remains ordinary `video` with `is_draft=1`, is not native Clip success, and must not be retransmitted.

## Repository integrity and Windows handoff rules

- Every tracked JSON file must parse.
- Local Markdown links must resolve.
- Tests depending on time must freeze their test clock.
- Managed-community enumeration uses `filter=moder`; `filter=admin` is not equivalent.
- Copy-paste PowerShell defines every variable and uses exact paths, `-LiteralPath`, `Test-Path`, `$PSScriptRoot`, and explicit output/result locations.
- Never select packages by `LastWriteTime`, newest ZIP, broad wildcard, or undefined inherited variable.
- Never mix project identities, OAuth aliases, credentials, manifests, journals, snapshots, or results.
- Never infer absence from an endpoint that does not cover the relevant surface.
- Never upload an ambiguous match.
- Keep video, Clip, catalog, metadata, thumbnail, wall, audio, and playlist operations separate.
- Machine state belongs in durable journals/results, not only stdout.

## Branch and merge discipline

Substantial work uses one `agent/{description}` branch and one focused PR. Merge only after exact-head six-job green CI, unchanged expected head, reviewed scope, and clean review threads. Synchronize operational memory separately after a code/runtime baseline changes.

No operational continuation is pending. Future provider work begins only from a new explicit user request and a new exact issue with a reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
