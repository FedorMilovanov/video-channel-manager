# Playlist workflow evolution — verified result and next design

This document records the first remotely verified eight-track VK Audio playlist result and converts it into design constraints for a future supported workflow.

It is **not** a supported runbook, final implementation, or authorization to execute the archived packages.

## Verified remote result

The supplied transcript supports the following remote state:

- playlist title: `Анатомия церкви — Джон МакАртур`;
- playlist ID: `85093900`;
- owner/community: `-60805374`;
- exact track count: `8`;
- each expected track appears exactly once;
- no extra tracks were reported;
- order is exact: `01` through `08`;
- the verification result classified the playlist as safe to publish.

The verification run reported:

```text
PLAYLIST ALREADY COMPLETE — NO WRITE
status: playlist_already_complete_verified
playlist_create_final_save: 0
```

This proves that the verifier found the exact desired remote object and did not create a duplicate during that run.

## What remains causally uncertain

The transcript suggests that the previous Workhorse v1.0 may have completed enough of the nested-save flow for VK to persist the playlist, even though the local workflow later raised:

```text
Audio selector did not close back to playlist form
```

However, the transcript does not contain a captured final write response that proves exactly which click/request created playlist `85093900`.

Therefore the historical conclusion is:

- **remote playlist existence and exact content:** verified;
- **v1.1 duplicate avoidance and read-only verification:** verified;
- **exact originating write and causal attribution:** unknown;
- **claim that v1.0 definitely created the playlist:** not allowed without stronger evidence.

This distinction is intentional. Provider state outranks local control-flow assumptions, but postflight state alone cannot always attribute the exact writer.

## The key failure pattern

The creation form contained nested UI states:

1. main playlist form;
2. audio selector modal;
3. eight track selections;
4. inner `Сохранить`;
5. return to main playlist form;
6. final `Сохранить`;
7. remote readback.

Workhorse v1.0 used a weak transition test: it treated any visible `Быстрый поиск` field as evidence that the audio selector remained open. A background search field on the music page could satisfy that test even after the active modal had changed.

The resulting local exception was therefore not reliable evidence that the provider write failed.

## What not to do

### Do not infer provider failure from a DOM transition exception

A UI waiter can be wrong while the provider has already accepted a mutation. After any ambiguous save, run read-only reconciliation before retrying.

### Do not retry the whole creation sequence

Once the eight selected tracks or the exact playlist may have been persisted, restarting from the beginning risks duplicate playlists or repeated writes.

### Do not use page-global selectors for nested modal state

Selectors such as `input[placeholder*="Быстрый поиск"]` must be scoped to the active topmost modal and checked for hit visibility.

### Do not use disappearance as the only transition proof

A nested modal may remain in the DOM, become covered, or leave a visually similar background element. Verify the positive state expected next: active title field, preserved title value, topmost modal identity, and clickability.

### Do not trust a successful click dispatch

A coordinate click, DOM `.click()`, or CDP mouse event proves only dispatch. It does not prove that VK accepted the state change.

### Do not send the final create action more than once

The final playlist save is a non-idempotent boundary unless the exact remote playlist identity has already been reconciled.

### Do not report `created` when the run only found an existing object

Use `playlist_already_complete_verified`, not `playlist_created`, when no final save was dispatched.

### Do not collapse creation and verification into one Boolean

Track separately:

- selections verified;
- inner save dispatched;
- transition observed;
- final save dispatched;
- remote playlist found;
- exact membership verified;
- exact order verified;
- duplicate absence verified.

## What to keep

### Exact remote-first idempotency

Before any playlist write:

1. search for the exact title in the exact community;
2. inspect candidate playlist IDs;
3. read membership and order;
4. return `already_complete_verified` with zero writes when exact.

### Scoped active-modal detection

A control is eligible only when it belongs to the active topmost modal, is visible, is hit-testable at its click point, and is anchored to the expected form field.

### Positive transition contracts

After the inner save, require:

- playlist title input is active/hit-visible;
- audio-selector search is not the active topmost form;
- title value is preserved exactly;
- the final save belongs to the same active playlist form.

### One bounded fallback

If the trusted mouse click does not produce the expected transition, allow at most one fallback on the same exact marked control. Do not rediscover a broad `Сохранить` button and do not restart selection.

### Final save once, then reconcile

After one final save attempt:

1. stop all write behavior;
2. perform read-only playlist search;
3. resolve exact playlist ID;
4. verify exact title, membership, uniqueness, and order;
5. classify the outcome from remote state.

### Per-stage evidence

A future result should include fields such as:

```json
{
  "playlist_preflight": "absent|partial|exact",
  "tracks_selected_count": 8,
  "inner_save_dispatched": true,
  "inner_transition_observed": false,
  "final_save_dispatched": false,
  "remote_playlist_found": true,
  "remote_playlist_id": "85093900",
  "membership_exact": true,
  "order_exact": true,
  "duplicates_absent": true,
  "causal_write_attribution": "unknown",
  "status": "playlist_already_complete_verified"
}
```

## How to improve the next implementation

### 1. Replace UI-centric success with a state machine

Use explicit states:

```text
PREFLIGHT
EXACT_ALREADY_EXISTS
FORM_OPEN
TRACKS_SELECTED
INNER_SAVE_DISPATCHED
INNER_TRANSITION_CONFIRMED
FINAL_SAVE_DISPATCHED
RECONCILING
EXACT_VERIFIED
AMBIGUOUS_REQUIRES_RECONCILIATION
FAILED_BEFORE_WRITE
```

Each state must persist enough evidence to resume without replaying previous writes.

### 2. Capture write-boundary evidence

For development canaries, capture a redacted network event around inner and final saves:

- endpoint/path classification;
- request timestamp;
- target community/playlist identity when safe;
- HTTP status;
- response classification;
- secrets and action hashes removed.

This should be optional diagnostic instrumentation, not a dependency for normal operation.

### 3. Use stable semantic anchors

Prefer:

- exact input purpose/label;
- active modal ancestry;
- role and enabled state;
- hit testing;
- before/after form-state fingerprint.

Avoid long CSS class names, page-global text scans, and static coordinates.

### 4. Build a modal-state fingerprint

Record a small redacted fingerprint before and after each save:

- active element purpose;
- visible/hit-visible title/search fields;
- modal count and geometry;
- exact title value;
- selected track count;
- eligible save-button count;
- topmost element at intended click point.

Use it to diagnose false transition detection without preserving private page content.

### 5. Add an operation lock

Only one playlist workflow may run for the same community/title pair. The lock key should include:

```text
project_key + owner_id + normalized_playlist_title
```

### 6. Separate create from repair

Future supported commands should distinguish:

- `playlist plan`;
- `playlist create`;
- `playlist verify`;
- `playlist repair-membership`;
- `playlist reorder`.

A failed create must not silently become a repair or reorder operation.

### 7. Keep the one-command user experience

Internally the workflow may have multiple stages, but the operator should invoke one repository-owned command. The command should print:

- current transport;
- exact target;
- whether a write is still possible;
- current stage;
- declared wait/deadline;
- final remote result.

### 8. Add deterministic regression fixtures

Required tests:

1. background quick-search remains visible after selector closes;
2. selector remains in DOM but is not topmost/hit-visible;
3. title form becomes active while a background search is visible;
4. inner click dispatched but no transition;
5. first click fails and one exact-control fallback succeeds;
6. remote playlist exists despite local transition exception;
7. rerun detects exact playlist and performs zero writes;
8. same title with wrong membership is not `already_complete`;
9. exact membership with wrong order is not `already_complete`;
10. duplicate track is detected;
11. final save cannot be dispatched twice;
12. causal attribution remains `unknown` when write evidence is absent.

## Promotion criteria for a supported implementation

Do not promote a future playlist tool from history into the supported operator surface until it has:

- repository-owned source and tests;
- zero/one/many PowerShell tests where applicable;
- canary verification on one disposable playlist;
- exact no-write rerun verification;
- ambiguous-save reconciliation;
- duplicate and order checks;
- documented rollback/repair behavior;
- secret-safe diagnostics;
- bounded timeouts and heartbeats;
- a stable single command.

## Current status

The historical operation achieved the desired remote playlist state. The archived Workhorse packages remain experimental evidence. Their useful ideas should be reimplemented in the supported architecture rather than copied wholesale.
