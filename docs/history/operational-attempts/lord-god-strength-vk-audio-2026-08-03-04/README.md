# Lord God Strength VK Audio attempts — 2026-08-03/04

This archive records the progression from one-file browser canaries through playlist and metadata automation, network observation, series preparation, and reliable batch upload experiments for:

- project: `lord-god-strength`;
- VK community: `60805374`;
- VK owner: `-60805374`;
- surface: VK Audio / playlists / metadata;
- source period: 2026-08-03 through 2026-08-04.

This is historical evidence, not an active runbook or supported entrypoint.

## Contents

- [`TIMELINE.md`](TIMELINE.md) — chronological attempts and outcomes;
- [`LESSONS.md`](LESSONS.md) — recurring false patterns and permanent engineering rules;
- [`EVIDENCE.md`](EVIDENCE.md) — source transcript identity, coverage, and limitations.

## Important boundary

The VK Audio workflow is a separate provider surface from VK Video/Clips. Its browser session, undocumented web endpoints, upload slots, playlist actions, and metadata contracts must not be inferred from the VK Video API implementation.

## High-level outcome

The history contains both useful successes and repeated failures:

- successful single MP3 upload and remote visibility verification;
- successful read-only inventory using browser-session cookies without persisting cookie values;
- repeated fragile DOM automation failures around playlist and metadata controls;
- a false `already_correct` result caused by substring matching across title and artist;
- a batch supervisor crash caused by PowerShell scalar/empty collection semantics under `Set-StrictMode`;
- strong evidence that some extracted upload URLs used the wrong host (`vk.ru`) and failed with HTTP 413, while valid slots used `pu.vk.ru` and completed.

No historical package documented here is automatically approved for reuse.