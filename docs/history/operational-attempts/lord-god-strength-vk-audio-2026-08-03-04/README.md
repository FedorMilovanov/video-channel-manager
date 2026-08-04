# Lord God Strength VK Audio attempts — 2026-08-03/04

This archive records the progression from one-file browser canaries through playlist and metadata automation, network observation, series preparation, reliable batch upload experiments, and the first exact eight-track playlist verification for:

- project: `lord-god-strength`;
- VK community: `60805374`;
- VK owner: `-60805374`;
- surface: VK Audio / playlists / metadata;
- source period: 2026-08-03 through 2026-08-04.

This is historical evidence, not an active runbook or supported entrypoint.

## Contents

- [`TIMELINE.md`](TIMELINE.md) — chronological attempts and outcomes;
- [`LESSONS.md`](LESSONS.md) — recurring false patterns and permanent engineering rules;
- [`PLAYLIST-WORKFLOW-EVOLUTION.md`](PLAYLIST-WORKFLOW-EVOLUTION.md) — verified playlist result, what not to repeat, what to preserve, and how the next implementation should evolve;
- [`EVIDENCE.md`](EVIDENCE.md) — source transcript identity, coverage, causal limits, and privacy boundary.

## Important boundary

The VK Audio workflow is a separate provider surface from VK Video/Clips. Its browser session, undocumented web endpoints, upload slots, playlist actions, and metadata contracts must not be inferred from the VK Video API implementation.

## Evidence levels used here

- `successful` — the transcript contains direct remote/readback evidence;
- `partial` — one stage succeeded while later stages failed or remained unknown;
- `safe failure` — failure occurred before any provider mutation;
- `false positive` — the tool reported success without exact evidence;
- `designed/self-tested only` — a fix was proposed or locally tested but no live provider result was shown;
- `provider-contract discovery` — successful and failed runs exposed a repeatable transport distinction;
- `remote exact state verified` — exact provider object, membership, uniqueness, and order were read back;
- `causal write attribution unknown` — the remote result is known, but the exact request that created it was not captured.

## High-level outcome

The history contains both useful successes and repeated failures:

- successful single MP3 upload and remote visibility verification;
- successful read-only inventory using browser-session cookies without persisting cookie values;
- successful canonical reduction of ten source positions to eight unique tracks;
- partial batch upload with per-track preservation and no blind replay of known remote tracks;
- repeated fragile DOM automation failures around playlist and metadata controls;
- a false `already_correct` result caused by substring matching across title and artist;
- a batch supervisor crash caused by PowerShell scalar/empty collection semantics under `Set-StrictMode`;
- strong evidence that some extracted upload URLs used the wrong host (`vk.ru`) and failed with HTTP 413, while valid slots used `pu.vk.ru` and completed;
- exact remote verification of playlist `85093900`, title `Анатомия церкви — Джон МакАртур`, containing exactly eight expected tracks once each in order `01` through `08`;
- an idempotent no-write rerun that detected the completed playlist and did not create a duplicate;
- unresolved causal attribution for the exact earlier write that originally created the playlist.

The successful remote result does not make the archived Workhorse packages final or supported. Their useful contracts should be reimplemented in the repository-owned operator architecture with regression tests and one-command execution.

No historical package documented here is automatically approved for reuse.
