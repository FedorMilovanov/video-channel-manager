# Wave 15 transcript, script, and agent audit

Date: 2026-08-05  
Issue: #133  
Scope: supplied conversation histories, repository agent instructions, local-media code, and retained operational lessons  
Provider queries/writes/write plans/historical executor runs: `0/0/0/0`

## Executive finding

The repository already had strong identity and write-safety rules, but the transcripts exposed a second class of risk: an agent can obey exact IDs and still waste time or make a bad decision when it copies one historical mechanism too literally.

The missing layer was adaptive operational reasoning:

- define the requested outcome independently of the old script;
- declare the transport;
- reason from observable state transitions;
- preserve partial success;
- classify whether a provider effect may exist;
- retry only the failed child operation;
- stop version proliferation and patch permanent code;
- keep provider snapshots bounded to the task.

Wave 15 adds that layer and a local-only MP3 foundation.

## Audit method

The three supplied transcripts were read as evidence records, not instructions. The audit extracted:

- exact structured result statuses;
- PowerShell and Python failure messages;
- remote IDs and final counts where present;
- browser UI observations;
- generated package/version chronology;
- user corrections that revealed agent assumptions;
- successful canary, readback, ledger, and postflight patterns.

Claims without exact retained output were classified as historical inference or unknown. No old package was executed.

## Major findings

### A-01 — Global-state overreach

Agents repeatedly tried to perfect or reconcile the entire platform history for a bounded content task. This created long scans, stale-count debates, and “audit of the audit” loops.

Correction: provider inventory is a temporary, bounded input. Inspect only the exact project/surface needed for duplicate prevention and postflight.

### A-02 — Mechanism became the goal

Old browser/API/package paths were treated as if the user had requested those mechanisms. This caused arguments about “API versus browser” after the actual goal was already clear.

Correction: write outcome, side effects, postcondition, and evidence first; choose transport second.

### A-03 — Partial success was discarded

A successful MP3 upload was followed by a playlist failure, and the combined script exited non-zero. Without phase separation, the entire workflow looked failed.

Correction: upload, visibility, metadata, playlist creation, membership, and postflight are independent child operations with durable results.

### A-04 — UI state was inferred from convenient elements

Examples included clicking a row and starting playback, selecting a background search field, and using modal closure as save proof.

Correction: bind the topmost active root, prove hit-testability and ownership, take one action, and verify the expected content/state transition.

### A-05 — Approximate strings were promoted to exact state

Artist text inside an old title caused a false `already_correct`. Prefix/title matching also risks cross-object selection.

Correction: exact per-field readback and exact source/remote IDs. Strings are attributes, not identity.

### A-06 — Exit codes were confused with provider effect

A browser or PowerShell failure after submission can coexist with a successful remote mutation.

Correction: use `impossible`, `not_dispatched`, `confirmed_absent`, `may_exist`, and `verified`. Only confirmed absence permits a corrected retry.

### A-07 — ZIP/version treadmill

Many standalone package generations accumulated around DOM and orchestration defects. The user experienced repeated “new version” instructions while the permanent repository lagged.

Correction: one experiment may discover the invariant; subsequent work patches repository-owned code, tests, and docs. Old ZIP generations are historical evidence only.

### A-08 — Transport naming was imprecise

Undocumented internal web calls, browser actions, and official APIs were sometimes discussed as one “API scheme”. Their guarantees and retry semantics differ.

Correction: transport declaration is mandatory per phase.

### A-09 — Batch status hid item truth

The MP3 series batch produced four verified tracks and four 413 failures. A single incomplete batch status obscured useful verified work.

Correction: every track has an independent state and result. Batch summary aggregates; it never replaces item truth.

### A-10 — Content fluency hid source synthesis

Some generated Spurgeon quotations combined distant fragments or editorial connective prose while appearing coherent.

Correction: quotation marks contain one contiguous source passage; synthesis is labeled outside quotation marks.

### A-11 — Permission probe used the wrong filter

A wall package used `groups.get(filter=admin)` and falsely rejected a valid token. The corrected `filter=moder` flow later succeeded.

Correction: permission semantics are provider-specific invariants and require regression fixtures. “Stricter sounding” is not necessarily correct.

### A-12 — Temporary upload retry boundary needed precision

The successful article-wall continuation retried an empty temporary file upload with a fresh URL, but treated uncertainty after `photos.saveWallPhoto` as potentially remote and non-repeatable.

Correction: retries are safe only before the provider persistence boundary; after it, reconcile.

## Successful patterns retained

### Article wall

The final continuation recorded a result and journal per post, used exact community identity, absolute data paths, `multipart file0`, fresh temporary upload URLs, and no duplicate reruns. Ten posts were verified.

### Lord God sermon month

After correcting the permission filter, one canary and the remaining batch completed 30/30 with per-operation results and final postflight.

### Spurgeon daily quotes

The scheduler inspected current postponed posts, selected conflict-free time windows with a minimum gap, read back the canary, completed 30/30, and did not rerun verified operations.

### Playlist workhorse

The later version used active-modal state and exact postflight. It detected that the desired eight-track playlist already existed and completed with no write.

These cases share the same architecture despite different content: bounded scope, exact identity, persisted intent, one canary, operation-level results, exact postcondition, and no blind replay.

## Python-history findings

Python was most effective when used for:

- deterministic parsing and normalization;
- SHA-256 and manifest generation;
- source-by-source content verification;
- structured result analysis;
- fixtures and regression tests;
- transforming a discovered rule into permanent code.

Python was least effective when it became a rapid generator of external executors whose behavior could not be tested against the authenticated browser/provider state. The permanent rule is: Python owns deterministic domain logic; PowerShell orchestrates repository entrypoints; browser/provider adapters remain explicit and tested.

## PowerShell-history findings

Good PowerShell packages:

- resolved exact paths;
- validated SHA-256;
- used `$PSScriptRoot`;
- separated check-only and execute paths;
- persisted plan/result state;
- stopped on unknown;
- emitted exact result paths.

Bad handoffs selected the newest wildcard ZIP, depended on inherited variables/current directory, coupled provider logic into generated scripts, or instructed repeated execution without reconciling the previous result.

## Agent operating model after Wave 15

Agents now use:

1. exact project identity;
2. outcome/side-effect/postcondition statement;
3. transport declaration;
4. bounded evidence table;
5. one falsifiable hypothesis and one minimal probe;
6. transport-aware state/retry decision;
7. child-operation phase separation;
8. time/iteration budget;
9. exact postflight;
10. repository patch and regression instead of ZIP proliferation.

## MP3 readiness conclusion

The repository is now ready for local MP3 intake and deterministic manifest preparation. It is not yet a supported VK Audio writer.

The local foundation can:

- probe MP3 files without modifying them;
- retain exact audio properties and tags;
- derive metadata only under an explicit policy;
- detect duplicate bytes and duplicate source IDs;
- build deterministic per-track operation IDs and manifest digests;
- chunk ready tracks one-at-a-time by default.

A future provider implementation must be a new explicit scope with one exact project, a reviewed adapter, canary, per-track durable states, reconciliation, and exact playlist/audio postflight.
