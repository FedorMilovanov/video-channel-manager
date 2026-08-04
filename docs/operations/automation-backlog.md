# Operational automation backlog

Updated: 2026-08-04  
Program state: `WAVE_8A_COMPLETED_WAVE_8B_ACTIVE`

This backlog is subordinate to [`current-state.md`](current-state.md), [`master-audit-marathon-v2-2026-08-04.md`](master-audit-marathon-v2-2026-08-04.md), and [`audit-register-v2-2026-08-04.json`](audit-register-v2-2026-08-04.json). It must not reactivate retracted findings, retired executors, historical ZIP packages, or completed destructive work.

## Completed work

### Waves 0–7

Completed reliability foundation:

- canonical project/state boundaries;
- durable journaled upload lifecycle and exact-ID recovery;
- fail-closed project/content identity;
- shared HTTP ownership, bounded safe-read retry, redaction, and limiter;
- upload/wall separation;
- one supported PowerShell operator;
- versioned source/plan/apply/result/reconciliation engine;
- 15 mutation boundaries with exact fault/replay/corruption/operator proofs.

Wave 7: PR #84, merge `df956bbbf19af6652f8711f95fb4fecf272e9951`, CI `30918639372`, Python `657 passed, 1 xfailed`, Pester `25/25`, provider writes 0.

### Audit A0

PR #89, merge `a06a93e1ec16b4ddb0f578a92e47ce76b4ee78a5`, CI `30925523584`, Python `657 passed, 1 xfailed`, all PowerShell environments green, provider writes 0.

Audit A0 repaired authoritative entry documents, added master audit/register v2, separated core Wave 8 from live Wave 9 and VK Audio incubation, and preserved PR #85 as historical evidence rather than supported code.

### Wave 8A — exact-first conflict-explicit matching

PR #91, merge `09babd9176049d8271c50b6f5e44b7b0fd10d39f`, exact-head CI `30933582322`:

- reviewed one-to-one mapping runs first;
- unique exact-normalized-title pairs run second;
- token/trigram-indexed fuzzy fallback runs only for unresolved objects;
- duplicate exact titles, exact-title duration mismatches, and non-unique fallback components become explicit conflicts;
- conflicts do not create mappings, missing/upload candidates, or collection placement;
- input order cannot change the selected result;
- result schema advanced to `2.0`;
- Python 3.11/3.12/3.13: `664 passed, 1 xfailed`;
- Windows PowerShell 5.1, PowerShell 7 Windows, and PowerShell 7 Linux green;
- provider writes: 0.

## Active work

### Wave 8B — field-specific canonical identity

Owner: issue #86.

Required outcomes:

- separate identity-title, display-title, description, public-URL, collection-title, and version/variation canonicalizers;
- retain original value, canonical value, ruleset version, ordered transformations, and digest;
- exact public/admin/author route classification;
- reject cross-project and unknown URL profiles;
- preserve semantically distinct versions and collections;
- exact field-by-field comparison; substring, prefix, or combined-row text cannot produce `already_correct` or identity success;
- zero provider writes.

Required tests:

1. Unicode normalization and whitespace/punctuation evidence;
2. `ё`/`е`, case, brand markers, and display preservation;
3. version/variation tokens remain identity-significant where policy requires;
4. public URL vs author/admin URL;
5. cross-project URL rejection;
6. unknown URL profile rejection;
7. transformation-order and digest determinism;
8. input-order independence;
9. exact per-field readback regression from VK Audio history.

Exit criteria:

- no single aggressive normalizer is reused as authority across unrelated fields;
- every canonical identity is versioned and evidence-backed;
- URL identities fail closed on unknown/cross-project/admin/public mismatches;
- exact-head Python and PowerShell CI green;
- state/register/#64/#86 synchronized;
- provider writes 0.

## Remaining Wave 8 sequence

### Wave 8C — catalog and album identity

- reviewed source collection ID → exact target album ID;
- duplicate or renamed albums become conflicts;
- no normalized-title dictionary overwrite;
- semantic membership comparison ignores provider position churn;
- immutable mapping evidence for issue #33.

### Wave 8D — media/cache authority

- authoritative downloader final path only;
- no successful glob fallback when the reported final path is absent;
- source ID, exact path, size, SHA-256, downloader policy, and structured ffprobe evidence;
- reject empty, partial, stale, corrupt, audio-only, unexpected multi-file, stream, codec, or container candidates;
- remux is not treated as codec/profile proof.

### Wave 8E — thumbnail identity and postcondition

- exact local image SHA/dimensions/quality policy;
- preserve remote photo identity;
- caller-owned delayed selected-thumbnail readback;
- unknown consistency result enters reconciliation, not blind retry.

### Wave 8F — integration and state sync

- integrate 8A–8E into the supported planning path;
- reject stale/pre-versioned evidence or migrate only through reviewed narrow paths;
- exact-head CI;
- synchronize living state and issue #64/#86;
- provider writes 0.

## Operation-scoped manager policy

A normal operation should:

1. validate only the supplied source files;
2. take a short read-only snapshot of the exact target surface;
3. produce one clear immutable plan;
4. execute with per-item stages and no implicit wall publication;
5. verify only the expected remote delta from that operation;
6. report planned/uploaded/verified/duplicate/failed/requires-attention totals.

Do not turn every bounded task into a global account audit, continuous provider mirror, whole-library visual fingerprint pass, or mandatory GitHub commit of mutable provider state.

## Permanent regression themes from operational history

- file selected ≠ upload completed ≠ remote visible ≠ complete workflow;
- a verified early stage is not repeated because a later playlist/metadata/catalog stage failed;
- batch results are per-item/per-stage, never one Boolean;
- exact field readback is required; substring/prefix/combined-row matching is prohibited;
- UI clicks require observed state transition;
- parser/observer self-test does not prove correct browser target/frame/network attachment;
- PowerShell must test 0/1/N outputs under strict mode;
- upload tickets require exact field and allowlisted scheme/host/path before media transfer;
- designed, self-tested, canary-verified, and batch-verified are separate evidence levels.

## Later waves

### Wave 9 — live project reconciliation

Only after Wave 8 and fresh operation-scoped read-only evidence:

- issue #31: Lord God long-form ledger/result reconciliation;
- issues #32/#38: Legendary Poet exact Clips/Shorts/type reconciliation;
- issue #33: catalog/publication planning after exact dependencies;
- separate immutable manifests and canaries per project;
- no automatic deletion of old VK Video copies.

### Separate VK Audio incubation

Not core Wave 8/9 Video work. Before another batch it requires its own versioned schemas, exact per-item ledger, adapter boundary, allowlisted upload-ticket contract, bounded deadline, canary, postflight, and reconciliation.

### Wave 10 — retirement and governance

- archive supported/compatibility/retired surfaces;
- resolve PR #85 archive-specific CI boundary without weakening production gates;
- formal release/runbook/rollback/reconciliation/provider-contract review rules;
- immutable history validation and retention policy.

## Independent cleanup

Issue #37 owns only its exact immutable reviewed cleanup scope. This backlog authorizes no bulk deletion.

## Definition of done

A wave is complete only when:

- issue scope and non-goals remain exact;
- no unrelated provider mutation is included;
- exact-head CI is green on all supported runtimes;
- conflicts and ambiguous outcomes remain fail closed and non-retryable;
- per-item evidence is complete and machine-readable;
- current state, register, roadmap, and issue state are synchronized;
- provider writes are exactly those separately authorized, otherwise 0.
