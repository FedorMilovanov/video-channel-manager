# Milovi Issue #323 interim rollout postmortem

Date: 2026-08-14
Project: `milovi-cake`
YouTube channel: `UCMDnxfGZiBqcDzgUV1zjFpw`
VK community: `68859909`
VK owner: `-68859909`
Issue: #323
Status: **interim** — recovery/finalizer architecture is merged; live 12/12 completion and final provider postflight are still pending.

This document is operational memory, not provider-write authority. The current Issue #323 scope and durable journal remain the live operation authority/state. Do not infer current provider state from this document without fresh read-only verification.

## Executive finding

The repeated Issue #323 stops were not one VK error repeated many times. They exposed one architectural class of error: **the implementation repeatedly promoted mutable, incomplete, or incarnation-local provider projections into durable identity, negative existence proof, or phase authority — and then propagated corrected identity semantics through the pipeline only partially**.

Fail-closed behavior was correct and prevented blind replay or broad deletion. The defect was that several guards were attached to facts that were not stable or complete enough to define the same logical remote operation across time. As VK legitimately changed processing/readback/presentation state, omitted an already-known due wall object from an aggregate projection, or retired one postponed wall ID while exposing the published incarnation under another ID, later phases interpreted normal provider lifecycle as identity loss or object disappearance. Even after recovery learned the correct successor-aware identity model, the finalizer initially retained the old permanent-`post_id` model, leaving the same defect waiting later in the pipeline.

The corrected model is monotonic and phase-consistent:

- durable success is never reclassified as failure only because a later provider projection changes;
- each destructive mutation has exactly one owning phase;
- recovery has narrower capabilities than a fresh write path;
- stable logical identity and authorized semantic invariants are separated from transient provider presentation/readiness fields and incarnation-local IDs;
- omission from an aggregate projection is not automatically proof of absence when a stronger exact/readback contract exists;
- scheduled wall state is time-aware, and a postponed timer ID is not assumed to remain the published incarnation's ID;
- recovery, metadata maintenance, ambiguous-write reconciliation and final postflight must use the **same logical mapping/current-incarnation contract**;
- ambiguous provider effects are reconciled from durable bindings and exact evidence, never replayed blindly.

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

The first verified rollout post (`468`) had a frozen slot of 2026-08-14 19:00 Europe/Moscow. After that time, scheduled publication is the intended provider transition. Historical wall recovery and final audit originally treated any `postponed -> published` surface change as drift.

PR #342 made recovery time-aware without ignoring wall content: only exact prior `wall_verified` mappings whose durable slot is due may participate in historical normalization, and a candidate is accepted only when it reconstructs the exact historical pre-upload SHA. Early publication remains blocking.

PR #346 later showed that surface evolution was only half the lifecycle: the provider may also retire the postponed timer object's ID and expose the published incarnation under a new wall ID. Section 12 records that deeper correction.

Permanent rule: **a durable state machine must model legitimate time-driven transitions explicitly, including provider identity/incarnation changes proven to be part of that transition.**

### 7. Historical preflight and lifecycle postflight used different interpretations

Normalizing only the historical pre-upload snapshot would still fail later if generic lifecycle postflight compared against a different current wall view.

The recovery writer supplies the same uniquely solved historical view to the shared lifecycle postflight and separately records the actual/effective provider snapshots and normalization evidence.

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

- stable logical identity;
- provider object/incarnation identity;
- phase ownership;
- durable state transitions;
- provider-effect/replay state;
- time-driven transitions;
- projection completeness assumptions;
- preflight/postflight interpretation;
- capability boundaries.

The corrective PR #342 was effective because it addressed most of that full contract rather than the latest exception message. PRs #344 and #346 then exposed two remaining assumptions about provider projection completeness and provider ID stability. PR #348 exposed the final propagation problem: even a correct new identity model is not complete until every downstream consumer uses it.

### 11. Aggregate projection omission was treated as proof of exact-object absence

After PRs #342 and #343, live FINAL-v2 passed the exact wall-475 tombstone reconciliation and then stopped read-only while recovering the eighth Clip because earlier durable wall mapping `-68859909_468` was absent from the aggregate published/postponed `wall.get` snapshot.

That STOP was safe, but the inference was too strong. The journal already contained wall ID `-68859909_468`, exact Clip `-68859909_456239225`, and frozen publish date `1786723200`; by then the slot was due. Absence from one aggregate projection did not by itself prove that the scheduled publication had disappeared.

PR #344 added a deliberately narrow exact-read fallback for the old journaled ID. That was a correct improvement to negative proof, but the first version still assumed the old postponed ID itself had to remain the published object's ID. The next live run disproved that assumption and led to PR #346.

Permanent rule: **an aggregate collection read can be a useful snapshot without being sufficient negative proof for a durable logical mapping. When the operation already owns stronger binding evidence, use the strongest applicable exact/readback reconciliation before declaring the mapping lost.**

### 12. The postponed timer ID was promoted into durable publication identity

The live run after PR #344 exact-read old wall ID `-68859909_468` and received absence/deleted-object semantics after its frozen slot. Recovery still stopped because it treated the journaled postponed `post_id` as an identifier that had to survive publication forever.

PR #346 established the missing lifecycle model: VK scheduled publication may retire the postponed timer object's ID and expose the published incarnation under a different wall ID. The durable object for Issue #323 is therefore the **logical scheduled mapping**, not an assumption that one provider `post_id` is immutable across the postponed→published transition.

The successor-aware recovery contract is intentionally narrow:

- only earlier Issue #323 items already durably `wall_verified` and already due are eligible;
- first exact-read the old journaled ID;
- if the old object is still live, exact owner/id/date/Clip checks still apply;
- if it is `None` or an exact deleted tombstone, require the complete current published surface to contain exactly one successor with the same owner, frozen timestamp and exact journaled Clip attachment;
- reject zero successors, multiple successors, wrong tombstone identity/date, wrong Clip binding, or successor collision with another journaled scheduled ID;
- rewrite only the successor `post_id` in the **in-memory historical recovery view** back to the old journaled ID;
- then require the existing historical pre-upload snapshot SHA solver to match exactly, so changed text, attachments, page counts or unrelated wall state still block;
- add no wall write, delete, upload reservation or binary retransmission capability.

Permanent rule: **do not assume a provider-assigned remote ID is durable across a lifecycle transition merely because it identified the object in the previous phase. Separate logical operation identity from provider incarnation identity, and require exact evidence before relating two incarnations.**

### 13. The identity-model migration stopped at the recovery boundary

After PR #346, recovery finally understood the logical scheduled mapping/current provider incarnation split. A deeper code audit found that the finalizer still used the historical journaled `wall_remote_id` as permanent identity in two downstream places:

- `_edit_wall_message()` looked up and edited only the old journaled `post_id`;
- `_final_postflight()` required current wall state and exact readback to use that same old ID.

That meant a successful successor-aware recovery could simply move the next STOP into promotion or final postflight. This was not a new VK behavior; it was an **incomplete architectural migration inside our own pipeline**.

PR #348 propagates one successor-aware contract through those later phases:

- capture a complete wall snapshot before metadata mutation;
- resolve the current provider incarnation of the durable source/Clip/frozen-slot mapping;
- before due, the journaled postponed ID remains exact;
- after due, exact-read the old ID first; if absent/exact tombstone, require one unique published successor with exact owner/frozen timestamp/Clip binding;
- reject ambiguous successors, journal-ID collisions, wrong identity/date/Clip and reuse of anomaly wall 475;
- exact-read the resolved current incarnation before `wall.edit`;
- edit a published successor by its current ID **without** re-sending `publish_date`; preserve the frozen date only for still-postponed incarnations;
- reconcile ambiguous edit responses through the same logical mapping resolver;
- use that same resolver in final postflight;
- retain both historical `wall_remote_id` and `current_wall_remote_id`/resolution mode in final evidence instead of silently rewriting journal history.

The existing transition tests were also updated to pass the durable journal binding; focused tests prove successor edit targeting, no-reschedule behavior, future-ID strictness, ambiguity blocking and final evidence preservation.

Permanent rule: **when an identity/state model changes, enumerate every reader, writer, reconciler, maintenance step and final auditor that consumes that object. A migration is incomplete until all of them share the same contract or an explicit adapter. Fixing only the phase that produced the latest STOP merely relocates the defect downstream.**

## What was not wrong

Fail-closed behavior itself was not the defect. The stops prevented a second upload, broad wall deletion, or silent acceptance of an unknown wall effect. The repair is not to weaken safety globally; it is to attach safety checks to stable, authorized invariants and propagate those invariants consistently.

The generic `upload_lifecycle.py` was deliberately not weakened by PR #342, #344, #346, or #348. Issue-specific recovery/finalization adapts the historical provider state around it.

The existence of a shared VK credential alias was also not target authority. Project/community/owner binding remains mandatory before writes. A faster historical browser flow is not evidence that it had a stronger target-binding model.

## Timeline of the failure class

The operational history across Issue #323 and PRs #328–#348 shows the progression:

- source/media preparation and codec compatibility were hardened without re-downloading intact reviewed bytes;
- canary and later child processing exposed transient `processing`, blank-title and playability projections;
- seven children became durably `wall_verified`;
- eighth Clip `-68859909_456239232` produced unexpected immediate wall post `-68859909_475`, correctly moving the upload lifecycle to reconciliation;
- exact cleanup authority was added for post 475 only;
- repeated false STOPs exposed mutable wall text/provider-source/container-shape assumptions;
- phase-1 cleanup ultimately reconciled wall 475 absent while preserving the eighth Clip;
- PR #342 replaced layered recovery with the single-owner monotonic model;
- PR #343 removed the remaining one-total-attachment assumption from finalizer wall identity;
- the next live run passed tombstone cleanup but exposed aggregate omission of due wall `468` during recovery;
- PR #344 added exact read-only recovery for missing due, previously `wall_verified` IDs while retaining exact historical SHA proof;
- the next live run showed the old postponed ID itself could be absent/tombstoned after publication even though the logical scheduled publication still existed;
- PR #346 added successor-aware read-only reconciliation for that exact postponed-ID→published-ID transition and retained exact historical SHA proof;
- post-#346 audit found finalizer promotion/final audit still depended on the stale historical ID;
- PR #348 propagated the same successor-aware logical mapping/current-incarnation contract through wall metadata maintenance, ambiguous edit reconciliation and final postflight.

Do not use this timeline as live provider state. Read the durable Issue #323 journal and current provider surfaces before any continuation.

## Current repository checkpoint

At the time of this interim postmortem update:

- PR #342 merged as `cb192f3bce0e7adbc4b37ecea26bdba8c7a02a34`; exact head `0dca308c85b5e1a8d3803d74906ea05a27237a7e`; CI #4313 succeeded across Python 3.11/3.12/3.13 and PowerShell Windows 5.1 / Windows 7 / Linux 7;
- PR #343 merged as `c828a76cfbe19afe8adbaf671bc7687c2dd4818e`; exact head `9962ab9671561e67b86ebe6e45ef1a53f085c34c`; CI #4315 succeeded across the same matrix;
- PR #344 merged as `cac9d91bab509d2a512aef1df39e84daa783aa46`; exact head `834b44c190071a782de0c3ca231ac5ec6b6933a1`; CI #4319 succeeded 6/6 across Python 3.11/3.12/3.13 and PowerShell Windows 5.1 / Windows 7 / Linux 7;
- PR #345 merged as `488fad76d8674af666288062b651ad09e751ab5a` and synchronized operational memory through the PR #344 state;
- PR #346 merged as `2adad1275c4882da5dca1491bd75a0020fee4522`; exact head `a0bdeebbc52e559451f008e65d87fc550c32cf4a`; it implements postponed-ID→published-successor reconciliation without adding provider-write capability;
- PR #347 merged as `14be5224e1d4757b868a0d36b5fe9dc897e3d5a5` and synchronized the existing current-state/postmortem through the PR #346 identity model;
- PR #348 merged as `eaa85bfefa008f3f240299966fffc14d01cd8881`; exact head `c44c2ca44fc84a7e478382d6576626c5b4f347b7`; CI #4334 completed successfully across Python 3.11/3.12/3.13 and PowerShell Windows 5.1 / Windows 7 / Linux 7; it propagates successor-aware wall identity into metadata maintenance and final postflight;
- Issue #323 remains open because repository correctness is not the same as live 12/12 completion.

Latest recorded live evidence remains the pre-#346 provider checkpoint: phase 1 verified wall `-68859909_475` absent via exact deleted tombstone and preserved Clip `-68859909_456239232`; the following phase-2 run proved that due old wall `-68859909_468` could disappear/tombstone across publication while requiring successor-aware reconciliation. PRs #346 and #348 harden the repository against that class across recovery and finalization, but the provider must be read again at operation start; merged code does not prove the next live run or 12/12 completion.

## Do not reintroduce

- a wall-475 delete path in phase 2/finalizer;
- fresh-upload player/title readiness as preservation or durable metadata identity;
- mutable provider text or `post_source` as exact object identity without explicit stable-authority evidence;
- “one total attachment” where the semantic invariant is one exact video;
- `None` as the only possible representation of deletion/absence;
- an assumption that a scheduled mapping remains `postponed` forever;
- an assumption that a postponed timer `post_id` is necessarily the published incarnation's `post_id`;
- treating aggregate omission, old-ID absence, or old-ID tombstone alone as proof that a due logical scheduled publication disappeared;
- successor inference without unique owner/frozen-date/exact-Clip proof and historical SHA reconstruction;
- one identity contract in recovery and a different permanent-ID contract in metadata maintenance/final audit;
- metadata mutation against a stale historical wall ID without resolving/proving the current incarnation first;
- historical preflight normalization that is not used consistently by postflight;
- recovery writers with fresh reservation/binary-upload capability;
- blind replay after a provider effect may exist;
- tests that prove an obsolete phase ownership or provider-ID permanence contract.

## Required closure before a final postmortem

This document is intentionally not final. Issue #323 can move to final disposition only after a live read proves the exact intended 12 Clip mappings and their 12 logical scheduled wall mappings with each mapping's legitimate current provider incarnation, verifies the authorized Milovi internal public copy on those proved current objects, and completes the final provider postflight with no unresolved provider effect.

At that point, append a final outcome section or create a short final disposition document. Do not rewrite this incident history to make the path appear cleaner than it was.
