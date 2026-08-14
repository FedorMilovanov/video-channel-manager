# Milovi Issue #323 interim rollout postmortem

Date: 2026-08-14
Project: `milovi-cake`
YouTube channel: `UCMDnxfGZiBqcDzgUV1zjFpw`
VK community: `68859909`
VK owner: `-68859909`
Issue: #323
Status: **interim** — recovery architecture is merged; live 12/12 completion and final provider postflight are still pending.

This document is operational memory, not provider-write authority. The current Issue #323 scope and durable journal remain the live operation authority/state. Do not infer current provider state from this document without fresh read-only verification.

## Executive finding

The repeated Issue #323 stops were not one VK error repeated many times. They exposed one architectural class of error: **the implementation repeatedly promoted mutable provider projections into durable identity or phase authority**.

Fail-closed behavior was correct and prevented blind replay or broad deletion. The defect was that several guards were attached to facts that were not stable enough to define the same remote object across time. As VK legitimately changed processing/readback/presentation state, later phases interpreted the evolution as identity loss or wall drift.

The corrected model is monotonic:

- durable success is never reclassified as failure only because a later provider projection changes;
- each destructive mutation has exactly one owning phase;
- recovery has narrower capabilities than a fresh write path;
- stable identity and authorized semantic invariants are separated from transient provider presentation/readiness fields;
- scheduled wall state is time-aware (`postponed -> published` after the frozen slot is normal, not drift);
- ambiguous provider effects are reconciled from exact identity and durable evidence, never replayed blindly.

## What actually went wrong

### 1. Two phases partially owned one destructive effect

The exact wall-475 cleanup was originally reachable from both the anomaly reconciler and the finalizer. That meant phase 2 could try to validate/delete an object that phase 1 had already reconciled.

This was a state-machine error, not insufficient checking. More checks in both phases made the conflict worse.

PR #342 established one destructive owner: `milovi_issue323_anomaly_reconcile.py` phase 1. The finalizer is read-only for wall 475 and consumes only durable `verified_absent` plus exact absence/tombstone readback.

Permanent rule: **one provider mutation has one owner. Later phases consume durable outcome evidence; they do not reacquire mutation authority.**

### 2. Fresh-upload readiness was reused as durable identity

Temporary fields such as player availability, blank/nonblank title, `processing`, and conversion state are meaningful while proving a newly uploaded Clip is ready. They are not reliable identity requirements for a Clip that is already durably verified and is being preserved or metadata-edited.

This caused already-established objects to become blockers when VK temporarily returned a weaker projection.

The corrected split is:

- new/resumed upload lifecycle: strict readiness remains required;
- phase-1 preservation: exact owner/id existence only;
- already durable Clip in metadata/final audit: exact owner/id, native `short_video`, and source/promotion binding, without re-running transient player/title readiness.

Permanent rule: **readiness is phase-specific evidence, not permanent object identity.**

### 3. Provider presentation fields were promoted into anomaly identity

During wall-475 reconciliation, fields such as current text and `post_source` changed while stronger bindings still identified the same already-proven remote object. A temporary implementation also treated those presentation fields as deletion identity and produced safe but false STOPs.

The final stable contract preserves stronger server/object bindings and records mutable provider projection as evidence instead of using it as identity.

Permanent rule: **do not add an observed provider field to identity merely because it was stable in one read. New identity predicates require authority/evidence that they are semantically stable.**

### 4. “Exactly one attachment” was stricter than the intended semantic invariant

VK can project additional non-video attachments around a wall post. The intended safety invariant was one exact video attachment, not one total attachment object.

PR #343 applies the semantic rule to normal rollout posts too:

- exactly one video attachment is required;
- extra non-video provider projections may coexist;
- zero videos, multiple videos, malformed attachment objects, wrong owner/video/date still fail closed.

Permanent rule: **validate the semantic object being authorized, not incidental container shape.**

### 5. Deleted tombstone was confused with live presence

`wall.getById` may represent an already-deleted exact post as an `is_deleted=true` tombstone rather than `None`. A generic non-null test therefore classified terminal absence as live presence.

The corrected path accepts only exact owner/id tombstone evidence as absence; an unrelated or identity-different object is still blocking.

Permanent rule: **provider terminal states may have a representation; absence is a semantic state, not necessarily a null response.**

### 6. Scheduled publication was treated as immutable wall surface

The first verified rollout post (`468`) had a frozen slot of 2026-08-14 19:00 Europe/Moscow. After that time, `postponed -> published` is the intended provider transition. Historical wall recovery and final audit originally treated any surface change as drift.

PR #342 made recovery time-aware without ignoring wall content: only exact prior `wall_verified` IDs whose durable slot is due may be considered for surface reversal during historical comparison, and a candidate is accepted only when it reconstructs the exact historical pre-upload SHA. Early publication remains blocking.

Permanent rule: **a durable state machine must model legitimate time-driven transitions explicitly.**

### 7. Historical preflight and lifecycle postflight used different interpretations

Normalizing only the historical pre-upload snapshot would still fail later if generic lifecycle postflight compared against a different current wall view.

The recovery writer now supplies the same uniquely solved historical view to the shared lifecycle postflight and separately records the actual provider snapshot and reversed surface IDs.

Permanent rule: **preflight and postflight must reason over the same identity/normalization contract.**

### 8. Recovery needed capability restrictions, not only conditional code

For the already-dispatched eighth upload, “do not re-upload” was initially a logical branch expectation. That is weaker than making replay impossible.

`_Issue323RecoveryWriter.begin_upload()` and `.upload_file()` now fail closed. Recovery can observe/complete the known effect but cannot reserve a second object or retransmit the binary.

Permanent rule: **give recovery only the capabilities required to reconcile the known effect.**

### 9. Tests encoded an obsolete architecture

`tests/test_milovi_promotion.py` historically treated finalizer-owned wall-475 deletion as expected behavior. That made the test suite reinforce the wrong ownership model.

PR #342 moved mutation fault proof to phase-1 anomaly-reconciler tests and changed promotion/finalizer tests to prove read-only phase-2 behavior.

Permanent rule: **green tests prove conformance to the tests, not conformance to authority. When authority changes, inspect what the tests are asserting, not only whether they pass.**

### 10. The process fixed individual STOP messages before reconstructing the whole temporal model

Several early fixes were locally correct but too narrow: one provider field drifted, one predicate was relaxed, then the next layer failed on another projection. The better approach is to reconstruct:

- stable identity;
- phase ownership;
- durable state transitions;
- provider-effect/replay state;
- time-driven transitions;
- preflight/postflight interpretation;
- capability boundaries.

The corrective PR #342 was effective because it addressed that full contract rather than the latest exception message.

## What was not wrong

Fail-closed behavior itself was not the defect. The stops prevented a second upload, broad wall deletion, or silent acceptance of an unknown wall effect. The repair is not to weaken safety globally; it is to attach safety checks to stable, authorized invariants.

The generic `upload_lifecycle.py` was deliberately not weakened by PR #342. Issue-specific recovery adapts the historical provider state around it.

The existence of a shared VK credential alias was also not target authority. Project/community/owner binding remains mandatory before writes. A faster historical browser flow is not evidence that it had a stronger target-binding model.

## Timeline of the failure class

The operational history across Issue #323 and PRs #328–#343 shows the progression:

- source/media preparation and codec compatibility were hardened without re-downloading intact reviewed bytes;
- canary and later child processing exposed transient `processing`, blank-title and playability projections;
- seven children became durably `wall_verified`;
- eighth Clip `-68859909_456239232` produced unexpected immediate wall post `-68859909_475`, correctly moving the upload lifecycle to reconciliation;
- exact cleanup authority was added for post 475 only;
- repeated false STOPs exposed mutable wall text/provider-source/container-shape assumptions;
- phase-1 cleanup ultimately reconciled wall 475 absent while preserving the eighth Clip;
- PR #342 replaced layered recovery with the single-owner monotonic model;
- PR #343 removed the remaining one-total-attachment assumption from finalizer wall identity.

Do not use this timeline as live provider state. Read the durable Issue #323 journal and current provider surfaces before any continuation.

## Current repository checkpoint

At the time of this interim postmortem:

- PR #342 merged as `cb192f3bce0e7adbc4b37ecea26bdba8c7a02a34`; exact head `0dca308c85b5e1a8d3803d74906ea05a27237a7e`; CI #4313 succeeded across Python 3.11/3.12/3.13 and PowerShell Windows 5.1 / Windows 7 / Linux 7;
- PR #343 merged as `c828a76cfbe19afe8adbaf671bc7687c2dd4818e`; exact head `9962ab9671561e67b86ebe6e45ef1a53f085c34c`; CI #4315 succeeded across the same matrix;
- Issue #323 remains open because repository recovery correctness is not the same as live 12/12 completion.

The latest Issue #323 durable checkpoint recorded before this document says wall 475 is reconciled absent, the first seven mappings are preserved, the exact eighth Clip must be adopted/resumed rather than re-uploaded, and sources 9–12 remain pending. That checkpoint must be re-read at operation start; it is not frozen by this document.

## Do not reintroduce

- a wall-475 delete path in phase 2/finalizer;
- fresh-upload player/title readiness as preservation or durable metadata identity;
- mutable provider text or `post_source` as exact object identity without explicit stable-authority evidence;
- “one total attachment” where the semantic invariant is one exact video;
- `None` as the only possible representation of deletion/absence;
- an assumption that a scheduled post remains `postponed` forever;
- historical preflight normalization that is not used consistently by postflight;
- recovery writers with fresh reservation/binary-upload capability;
- blind replay after a provider effect may exist;
- tests that prove an obsolete phase ownership contract.

## Required closure before a final postmortem

This document is intentionally not final. Issue #323 can move to final disposition only after a live read proves the exact intended 12 Clip mappings and their exact scheduled wall mappings, allowing legitimate due `published` surfaces, verifies the authorized Milovi internal public copy, and completes the final provider postflight with no unresolved provider effect.

At that point, append a final outcome section or create a short final disposition document. Do not rewrite this incident history to make the path appear cleaner than it was.
