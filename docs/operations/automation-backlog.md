# Operational automation backlog

Updated: 2026-08-04  
Program state: `WAVE_8B_COMPLETED_WAVE_8C_ACTIVE`

This backlog is subordinate to [`current-state.md`](current-state.md), [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md), and [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json).

## Completed foundation

- Waves 0–7: project boundaries, durable upload lifecycle, fail-closed identity, shared HTTP/retry/redaction, upload/wall separation, one supported PowerShell operator, versioned Wave Engine, and 15 mutation-boundary proof ownership.
- Audit A0: PR #89, merge `a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5`, CI `30925523584`, provider writes 0.
- Wave 8A: PR #91, merge `09babd9176049d8271c50b6f5e44b7b0fd10d39f`, CI `30933582322`, `664 passed, 1 xfailed`, exact-first conflict-explicit matching, provider writes 0.
- Wave 8A state sync: PR #92, merge `160382e4dea51d2691081e42c86c878a58ccdd97`, CI `30934601690`, `665 passed, 1 xfailed`.
- Wave 8B: PR #93, merge `c28aee4177d6f99e8f52fd82b60f4c1d93d50c29`, CI `30936757433`, `680 passed, 1 xfailed` on Python 3.11/3.12/3.13, all three PowerShell environments green, provider writes 0.

## Closed Wave 8A findings

- reviewed one-to-one video mapping runs first;
- unique exact canonical-title pairs run second;
- bounded indexed fuzzy fallback runs only afterward;
- duplicate exact titles, excessive exact-title duration differences, and non-unique fallback components are conflicts;
- conflicts produce no selected mapping or operation candidate;
- input order cannot change results.

## Closed Wave 8B findings

The `wave-8b-v1` contract provides separate canonical evidence for identity title, display title, description, collection title, variation, HTTP URL, public URL, and exact project URL.

Each result preserves original, canonical, ruleset, ordered transformations, and SHA-256 digest.

Exact readback now rejects:

- substring matches;
- title-prefix matches;
- artist text embedded in a title;
- combined visible rows instead of separate fields;
- missing expected fields.

URL identity now rejects:

- author/admin routes in public fields;
- cross-project profiles;
- unknown project profiles;
- malformed HTTP(S) identities and embedded credentials.

Comparison evidence schema is `2.1` and retains canonical title/description evidence.

## Active Wave 8C — catalog and album identity

Owner: issue #86. Provider writes: 0.

### Required contract

1. One versioned collection-mapping evidence schema.
2. Reviewed source collection ID → exact target collection ID is the only authority for an existing album.
3. Validate exact source and target IDs against bound source/target snapshots.
4. Mapping is one-to-one; reused target IDs fail closed.
5. Duplicate canonical target titles are conflicts and never overwrite each other in a dict.
6. Renamed existing albums are not silently selected or recreated.
7. An unmapped source collection may produce a create proposal only when creation is explicitly approved and no conflicting target candidate exists.
8. Unresolved conflicts produce no album or placement operations.
9. Semantic membership uses exact sets of mapped target video IDs; provider position changes are ignored.
10. Evidence records project key, source/target snapshot IDs, title identities, exact IDs, decision, transformations, and digest.
11. Issue #33 may later consume immutable evidence but Wave 8C performs no provider mutation.

### Required tests

- valid reviewed mapping;
- unknown source collection ID;
- unknown target album ID;
- duplicate target reuse;
- duplicate canonical target titles;
- renamed reviewed target;
- unreviewed existing title candidate;
- explicitly approved create proposal;
- create proposal blocked by candidate conflict;
- semantic membership equality under reordered positions;
- missing and extra membership sets;
- stale project/snapshot/digest evidence;
- conflict cannot create placement operation;
- deterministic result under input permutation.

### Exit criteria

- no title-key authority remains in cross-platform collection gaps or VK catalog planning;
- album create/placement planning consumes exact collection evidence;
- catalog plan validates mapping/policy/snapshot digests;
- exact-head CI is green on all Python and PowerShell environments;
- living state and issues #64/#86 are synchronized;
- provider writes 0.

## Remaining Wave 8

### Wave 8D — media/cache authority

- authoritative downloader final path only;
- source ID, exact path, size, SHA-256, policy digest, structured ffprobe evidence;
- reject missing, partial, stale, corrupt, audio-only, wrong-container/codec/stream, and unexpected multi-file candidates;
- no successful glob fallback when the reported final path is absent;
- remux does not count as codec proof.

### Wave 8E — thumbnail identity

- local image SHA/dimensions/quality;
- returned remote photo identity;
- delayed selected-thumbnail exact readback;
- unknown consistency result enters reconciliation, not retry.

### Wave 8F — integration

- integrate 8A–8E into supported operation planning;
- reject stale/pre-versioned evidence;
- exact-head CI and living-state sync;
- provider writes 0.

## Operation-scoped policy

A normal operation validates only supplied source files, takes a short exact target snapshot, creates one immutable plan, executes per-item stages, verifies only expected delta, and reports planned/uploaded/verified/duplicate/failed/requires-attention totals.

Do not maintain a permanent whole-account mirror or require a global audit for every bounded task.

## Permanent operational regressions

- file selected ≠ upload complete ≠ remote visible ≠ workflow verified;
- later stage failure does not authorize replay of a verified earlier mutation;
- batch state is per item/per stage;
- exact per-field readback replaces substring/prefix/combined-row matching;
- UI clicks require observed state changes;
- observer self-test does not prove correct target/frame/network attachment;
- PowerShell boundaries test 0/1/N outputs;
- upload ticket requires exact field plus allowlisted scheme/host/path;
- designed, self-tested, canary-verified, and batch-verified remain distinct.

## Later work

- Wave 9: fresh operation-scoped reconciliation for issues #31, #32, #38, then issue #33 catalog/publication.
- VK Audio: separate incubation only after versioned schemas, exact per-item ledger, upload-ticket contract, canary, postflight, and reconciliation.
- Wave 10: resolve PR #85 archive CI boundary, retirement registry, release/runbook/rollback/governance.
- Issue #37 alone owns exact reviewed cleanup; no bulk deletion is authorized here.

## Definition of done

A wave closes only after exact scope, fail-closed evidence, full exact-head CI, synchronized state/register/issues, and exactly authorized provider writes—otherwise 0.
