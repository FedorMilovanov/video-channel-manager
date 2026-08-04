# Lessons — VK Audio false patterns and countermeasures

## FP-A01 — Treating a nonzero final exit as total failure

**Seen in:** canary v1.3.

The MP3 upload was verified, but the later playlist-add stage failed. Repeating the whole workflow would risk a duplicate upload.

**Rule:** every operation has independent stage outcomes. Persist remote identity immediately after verification and resume only the unfinished stage.

## FP-A02 — DOM proximity treated as semantic identity

**Seen in:** PlaylistOnly v1.4 and metadata/rename attempts.

A click on a visually nearby row started playback instead of selecting the track; broad control discovery also risked choosing unrelated fields.

**Rule:** identify controls by scoped container, role, label, state, and exact post-action transition. Coordinates and nearest-text heuristics are insufficient.

## FP-A03 — Silence interpreted inconsistently

**Seen in:** PlaylistOnly v1.7, network observer, calibrator, batch waits.

Some silence was a true hang, some was an intentional wait, and some meant the observer was attached to the wrong network surface.

**Rule:** all long operations expose a machine-readable state, heartbeat, deadline, and reason. The operator should never infer state from silence.

## FP-A04 — Substring matching used as exact metadata verification

**Seen in:** Rename AUTO v2.0.

The desired artist occurred inside the old title, and the desired title was only a prefix of a longer incorrect title. The script returned `already_correct` without exact field equality.

**Rule:** verify artist and title independently with exact normalized equality on the exact remote record. Reopen and reread after save.

## FP-A05 — Global search confused with surface-specific search

**Seen in:** Rename AUTO v2.0.

The automation filled VK's global search rather than the audio-section search.

**Rule:** every selector is scoped to the intended application surface. Global fallbacks are prohibited for write workflows.

## FP-A06 — Parser self-tests mistaken for live observer coverage

**Seen in:** manual edit network observer.

The observer's local tests passed, but it did not capture the real save request.

**Rule:** before asking for a manual mutation, prove live attachment using a harmless known request from the exact page/frame/session.

## FP-A07 — Browser/API hybrid transport hidden from the operator

**Seen in:** series and batch upload attempts.

The workflow used browser authorization, session cookies, internal web endpoints, and direct binary POSTs, but the console did not clearly explain the boundaries.

**Rule:** print a transport map before execution and include it in the result: authentication, read inventory, slot reservation, binary upload, commit/finalization, and verification.

## FP-A08 — PowerShell scalar/array ambiguity under `Set-StrictMode`

**Seen in:** Reliable Batch v3.0.

An empty result lost array shape, and `.Count` caused the supervisor to crash before provider writes.

**Rule:** normalize external and pipeline output using explicit arrays and test zero/one/many cases under the exact supported PowerShell versions.

## FP-A09 — First URL-shaped value accepted as upload authority

**Seen in:** Reliable Batch v3.1 partial run.

A URL on `vk.ru` looked plausible but returned HTTP 413 after a partial transfer. Valid uploads used `pu.vk.ru`.

**Rule:** parse the exact provider field and enforce an allowlisted upload-host/path contract before dispatch. Unexpected URLs are evidence for review, not retry targets.

## FP-A10 — Retry used without validating whether the ticket is valid

**Seen in:** repeated slot attempts.

Fresh retries could still receive a structurally wrong upload URL, wasting time and bandwidth.

**Rule:** validate reservation evidence before the binary transfer. Retry only the reservation stage when the slot contract is invalid.

## FP-A11 — Batch represented as one Boolean outcome

**Seen across:** canary/playlist and reliable batch flows.

Some tracks were already remote, some verified, some deferred, and some untouched.

**Rule:** maintain a per-item ledger with exact states such as `already_remote`, `prepared`, `slot_rejected`, `upload_dispatched`, `verified`, `deferred`, and `unknown_requires_reconciliation`.

## FP-A12 — Proposed fixes described as completed outcomes

**Seen in:** Metadata Manager v1.1, Rename AUTO v2.1, Reliable Batch v3.0 design descriptions.

The transcript often listed expected statuses before a live run had proved them.

**Rule:** documentation must label statements as `designed`, `self-tested`, `canary-verified`, or `batch-verified`. Never collapse these evidence levels.

## FP-A13 — Too many versioned ZIPs and newest-file selection

**Seen throughout:** v1.3, v1.4, v1.7, v2.0, v2.1, v3.0, v3.1 and multiple audit packages.

Each correction produced another standalone package selected from Downloads by `LastWriteTime`, making lineage and the active implementation unclear.

**Rule:** move stable logic into one repository-owned entrypoint. Use immutable manifests and explicit paths; do not select operational authority by newest downloaded filename.

## FP-A14 — Successful preparation confused with successful publication

**Seen in:** series importer v1.2.

The importer correctly produced eight canonical tracks from ten positions, but that did not prove remote upload.

**Rule:** represent preparation, provider dispatch, finalization, and remote verification as separate evidence documents.

## FP-A15 — Temporary provider instability overgeneralized as local network failure

**Seen in:** intermittent VK loading and mixed batch results.

Some tracks succeeded while others failed based on upload-host selection, showing that the issue was not simply the user's internet connection.

**Rule:** compare successful and failed transport evidence before assigning a cause. Host, path, HTTP status, bytes transferred, timing, and reservation response shape are required.

## FP-A16 — Background controls mistaken for the active nested modal

**Seen in:** Playlist Workhorse v1.0.

A page-global `Быстрый поиск` field remained visible outside the selector and was treated as proof that the nested selector had not closed.

**Rule:** transition predicates must be scoped to the active topmost modal and require hit visibility. Background elements do not define current workflow state.

## FP-A17 — Local transition failure treated as provider failure

**Seen in:** Playlist Workhorse v1.0 followed by the v1.1 exact verification.

The local workflow raised an exception after the inner save, while a later read-only run found the exact completed playlist.

**Rule:** after a write boundary with an ambiguous response or UI transition, freeze writes and reconcile. Never authorize a full retry from the local exception alone.

## FP-A18 — Exact remote completion confused with exact write attribution

**Seen in:** playlist `85093900`.

The final remote playlist state is verified, but the exact request/click that created it was not captured.

**Rule:** record `remote_state_verified` and `causal_write_attribution` separately. Use `unknown` when write evidence is absent.

## FP-A19 — Nested and final saves treated as one action

**Seen in:** playlist creation form.

The inner save commits track selection/returns to the parent form, while the final save creates or updates the playlist. Replaying both stages risks duplicate or unintended mutation.

**Rule:** model each write boundary separately, persist its evidence, allow at most one bounded retry for an unresolved inner transition, and dispatch the final save once.

## FP-A20 — Existing exact playlist not used as the primary idempotency key

**Seen in:** the successful v1.1 no-write rerun.

The safest successful result came from detecting exact remote title, membership, uniqueness, and order before attempting another write.

**Rule:** exact remote state is the primary idempotency mechanism. A rerun that finds the exact desired playlist must end with zero writes.

# Required regression themes

Future supported implementations should include tests for:

1. zero/one/many PowerShell outputs under `Set-StrictMode`;
2. exact title/artist equality versus substring and prefix matches;
3. global-search exclusion;
4. row click versus selection-control state;
5. verified upload followed by playlist failure without retransmission;
6. observer attached to wrong page/frame/domain;
7. allowlisted upload host/path validation;
8. HTTP 413 before retrying media transfer;
9. per-item partial batch outcomes and resume;
10. explicit declared-wait heartbeats and silent-hang timeout;
11. exact source-position deduplication;
12. clear evidence-level labels for designed, self-tested, canary-verified, and batch-verified states;
13. background search visible after the selector is no longer active;
14. selector still in the DOM but covered/not hit-visible;
15. exact playlist found after a local transition exception;
16. exact no-write rerun;
17. same title with partial or wrong membership;
18. exact members in the wrong order;
19. duplicate playlist member detection;
20. final create save cannot be dispatched twice;
21. remote completion with `causal_write_attribution: unknown`;
22. exact active-modal fingerprint before and after nested save.
