# Operational documentation

Operational documents are living sources of truth. They override chat history, screenshots, remembered counts, retired ZIP packages, stale issue wording, old README/roadmap status blocks, and older audits.

## Start here

- [`project-identity-registry.md`](project-identity-registry.md) — exact projects, one shared VK credential, channel-specific YouTube aliases, IDs, routes, and no-mixing rules.
- [`current-state.md`](current-state.md) — concise current operational interpretation and permanent safety boundaries. Wave-16 and older audit registers below are historical evidence, not live backlog.
- [`../audits/2026-08-21-full-operational-reconnaissance.md`](../audits/2026-08-21-full-operational-reconnaissance.md) — 2026-08-21 reconnaissance of leftover branches vs live/unfinished lanes. Evidence only; it does not replace `current-state.md`.
- [`2026-08-14-milovi-issue-323-interim-postmortem.md`](2026-08-14-milovi-issue-323-interim-postmortem.md) — interim Milovi #323 failure analysis: monotonic recovery, identity vs provider projection, single mutation ownership, and live-closure boundary.
- [`audit-register-v9-2026-08-05.json`](audit-register-v9-2026-08-05.json) — current CI/SQLite/MP3-identity machine state.
- [`audit-register-v8-2026-08-05.json`](audit-register-v8-2026-08-05.json) — immutable Wave 15 predecessor.
- [`audit-register-v7-2026-08-05.json`](audit-register-v7-2026-08-05.json) — immutable Wave 14 predecessor.
- [`agent-reasoning-playbook.md`](agent-reasoning-playbook.md) — general method for unfamiliar API/browser/local states without brittle pattern copying.
- [`wave15-transcript-and-agent-audit-2026-08-05.md`](wave15-transcript-and-agent-audit-2026-08-05.md) — transcript/script/agent failure taxonomy and retained invariants.
- [`wave16-ci-sqlite-mp3-hardening-2026-08-05.md`](wave16-ci-sqlite-mp3-hardening-2026-08-05.md) — Node 24, SQLite lifetime, and MP3 identity findings.
- [`vk-audio-browser-experiment-retrospective.md`](vk-audio-browser-experiment-retrospective.md) — BrowserCanary/PlaylistOnly/Metadata Manager/Workhorse evidence and retirement boundary.
- [`mp3-batch-processing-contract.md`](mp3-batch-processing-contract.md) — supported local-only MP3 intake and future provider phase contract.
- [`automation-backlog.md`](automation-backlog.md) — closed backlog and future-work rule.
- [`repository-integrity-audit-2026-08-05.md`](repository-integrity-audit-2026-08-05.md) — Wave 14 integrity findings.
- [`final-operational-disposition-2026-08-05.md`](final-operational-disposition-2026-08-05.md) — human-readable operational dispositions.
- [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md) — canonical audit baseline.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md) — deterministic Windows and adaptive diagnosis contract.
- [`operational-artifact-standard.md`](operational-artifact-standard.md) — package/manifest/launcher/ledger requirements.
- [`operational-package-acceptance.md`](operational-package-acceptance.md) — truth levels and fail-closed acceptance.
- [`retirement-registry-v1.json`](retirement-registry-v1.json) — supported/compatibility/retired/historical execution boundaries.

## Engineering sequence

1. Waves 0–12C — completed foundations and governance.
2. Wave 13 — completed evidence-backed operational closure.
3. Wave 14 — completed repository-wide documentation/integrity polish.
4. Wave 15 — completed adaptive-agent reasoning and local-only MP3 foundation.
5. Wave 16 — completed CI runtime, SQLite lifetime, and MP3 identity hardening.

Wave 16 proof:

- issue #137;
- PR #138;
- exact head `c495308430bce6e1b86343b6cd4e6ae3a302734b`;
- merge `22ed56256df3388c23c9f785f1e02cca71fd8524`;
- CI `31022560789`;
- `845 passed, 1 xfailed` on Python 3.11/3.12/3.13;
- coverage `79%` across `14,675` statements;
- Ruff correctness green and `464 files already formatted`;
- strict mypy `147 source files`;
- dependency audit clean;
- all three PowerShell environments green;
- Node 20 action warning absent;
- unclosed SQLite database warning absent;
- provider queries/writes/write plans/historical executor runs `0/0/0/0`.

## Immutable Wave 15 compatibility ledger

Wave 15 remains completed predecessor evidence:

- program state `WAVES_0_15_COMPLETED_ADAPTIVE_AGENT_REASONING_LOCAL_MP3_FOUNDATION_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`;
- `main@eb58c1ad238fde01d66c6630b16e244b1c6c2992`;
- PR #134, CI `31006136529`, `833 passed, 1 xfailed`;
- Ruff `461 files already formatted`;
- machine state `audit-register-v8-2026-08-05.json`.

## Immutable Waves 0–14 compatibility ledger

This ledger preserves exact historical regression anchors. It is not an active backlog and does not authorize execution.

- Waves 0–7 — completed.
- Waves 8A–8F — completed.
- Wave 9 read-only contract — completed.
- Package A / Waves 9A–10 — completed.
- Wave 11 — completed.
- Wave 12 — completed.
- Wave 12A / #118 — completed.
- Wave 12B / #122 — completed.
- Wave 12C / #126 — completed.
- Wave 13 / #127 — completed.
- Wave 14 / #130 — completed.
- Wave 14 proof: PR #131, CI `31000834701`, `801 passed, 1 xfailed`, Ruff `451 files already formatted`.

The credential invariant is one shared user access token. Its alias never selects a project. YouTube remains channel-specific through OAuth alias `fedor-milovanov` and OAuth alias `legendary-poet`.

Historical issue ownership remains:

- #31 — long-form reconciliation;
- #32 — Shorts/Clips reconciliation;
- #119 — Shorts/Clips reconciliation;
- #38 — shared VK native Clip/ordinary-video provider-mode;
- #123 — YouTube playlist mutation design.

Do not group #32/#38 as Legendary Poet.

Wave 14 integrity anchors remain: Every tracked JSON file must parse. Local Markdown links must resolve. Provider writes remain unauthorized. Closed issues and historical packages must not be reopened as execution authority.

## Agent reasoning boundary

Agents define outcome before mechanism, declare transport per phase, separate current phase from provider-effect state, preserve partial success, and use one falsifiable hypothesis plus one bounded probe. Browser UI work binds the active root and verifies a state/content transition. Unknown remote effects are reconciled, never blindly retried.

Provider snapshots are task-scoped temporary inputs. One failed selector does not justify a new package generation; permanent repository code and fixtures must be patched.

## MP3 boundary

Supported now: local read-only MP3 probe, exact properties/tags/SHA, explicit metadata policy, metadata-ranked duplicate selection, fail-closed source-ID/SHA conflicts, deterministic schema 1.1 manifest, and ready-item chunking.

One source ID mapped to multiple hashes is `source_id_sha256_conflict`. Identical bytes claimed by multiple source IDs is `sha256_multiple_source_ids`. Both require review and never become provider-ready automatically.

Not supported or authorized: ID3 writes, rename/transcode, browser control, VK Audio upload, remote metadata edit, playlist mutation, or wall publication.

VK Audio remains `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`. Historical browser ZIP generations are evidence only.

## Credential and final operational boundary

VK uses one shared user access token. Exact project/community/owner IDs select and isolate the target. YouTube OAuth aliases remain channel-specific.

Completed: #31, #119, #38, #130, #133, #137. Retired/not planned: #32, #33, #99, #123. Do not group #32/#38 as Legendary Poet.

Native Clip success still requires exact final `type=short_video`, processing complete, non-draft state, and exact public visibility. `M5hNecL_MsQ → -235216998_456239160` remains ordinary-video/draft evidence and is non-replayable.

Provider writes remain unauthorized. Green CI, Package A, issue bodies, transcripts, previews, ZIP names, README commands, browser-visible objects, or roadmap entries never authorize a mutation. Future provider work requires a new explicit user request, a new exact project-bound issue, reviewed immutable exact-ID plan, expected remote delta, durable per-operation results, and exact postflight.
