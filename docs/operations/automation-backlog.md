# Operational automation backlog

Updated: 2026-08-05  
Program state: `WAVES_0_16_COMPLETED_CI_RUNTIME_SQLITE_MP3_IDENTITY_HARDENED_OPERATIONAL_GRAPH_CLOSED_NO_PROVIDER_WRITES`

This backlog is subordinate to [`current-state.md`](current-state.md), current v9, and immutable v8/v7/v6/v5/v4/v3/v2 predecessors.

## Completed program foundation

- Waves 0–12C — identity, guarded execution, deterministic handoffs, project ownership, shared-token semantics, and issue-contract convergence completed.
- Wave 13 — final evidence-backed operational closure completed.
- Wave 14 — repository-wide documentation/integrity polish completed.
- Wave 15 / #133 — adaptive-agent reasoning and local-only MP3 foundation completed through PR #134, exact head `48baa13b0d08e27e5a1dfc8b30901524d3207148`, merge `eb58c1ad238fde01d66c6630b16e244b1c6c2992`, CI `31006136529`, `833 passed, 1 xfailed`, coverage `79%`, provider queries/writes/plans/executor runs `0/0/0/0`.
- Wave 16 / #137 — CI runtime, SQLite lifetime, and MP3 identity hardening completed through PR #138, exact head `c495308430bce6e1b86343b6cd4e6ae3a302734b`, merge `22ed56256df3388c23c9f785f1e02cca71fd8524`, CI `31022560789`, `845 passed, 1 xfailed`, coverage `79%`, provider queries/writes/plans/executor runs `0/0/0/0`.

## Active backlog

None.

There is no active provider reconciliation, transfer queue, catalog/article-wall/playlist continuation, browser writer, MP3 upload, metadata edit, cleanup/reset/recovery, or provider-mode research after the Wave 16 state-sync merge.

## Local MP3 status

Implemented and supported:

- read-only ffprobe intake;
- exact audio identity and embedded-tag evidence;
- explicit/policy-declared metadata decisions;
- metadata-ranked canonical selection for exact-byte duplicates;
- fail-closed `source_id_sha256_conflict` and `sha256_multiple_source_ids` states;
- unique deterministic local operation IDs and schema 1.1 manifest;
- one-at-a-time ready chunks by default;
- deterministic 1,000-track local planning regression.

Not implemented or authorized:

- ID3 rewrite;
- rename/transcode;
- browser automation;
- VK Audio upload or metadata edit;
- playlist creation/membership mutation;
- wall publication.

Historical BrowserCanary, PlaylistOnly, Metadata Manager, reliable batch, calibrator, and Playlist Workhorse packages remain retired evidence.

## Final issue dispositions

- #31, #119, #38, #130, #133, #137 — completed.
- #32, #33, #99, #123 — retired/not planned.
- #135 — completed Wave 15 state sync; owns no provider operation.
- #139 — Wave 16 state-sync issue; it closes with the v9 merge and owns no provider operation.

Do not group #32/#38 as Legendary Poet. Historically #32 belonged to Lord God, #38 was shared, and #119 belonged to Legendary Poet.

## Future work rule

This backlog is closed, not waiting. Future work starts from a new explicit user request and a new exact scope. Provider writes remain unauthorized. Historical packages, transcripts, counts, and README commands are never resume or authorization tokens.
