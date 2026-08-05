# Adaptive agent reasoning playbook

This playbook governs unfamiliar, partially documented, or changing YouTube/VK workflows. It supplements exact project identities, provider safety rules, and operation-specific contracts. It does not authorize provider access or writes.

The objective is not to memorize one historical selector, script version, or ZIP. The objective is to preserve invariants while adapting the mechanism to new evidence.

## 1. Start with the outcome, not the historical mechanism

Before reading old scripts, write one sentence for each field:

- requested outcome;
- exact project and target identity;
- object type or surface;
- allowed side effects;
- forbidden side effects;
- completion postcondition;
- evidence needed to prove completion.

Example: “Prepare a local-only manifest for these MP3 files” is not the same operation as “upload MP3”, “edit VK audio metadata”, “create a playlist”, or “publish a wall post”. Treat each as a separate operation even when a previous ZIP coupled them.

Never inherit a mechanism merely because it once produced the desired outcome. A browser path, internal endpoint, API adapter, or manual action is a proposed transport, not part of the user’s goal.

## 2. Declare the transport before acting

Every operation declares exactly one transport for each phase:

| Transport | Permitted interpretation |
|---|---|
| `local_only` | Filesystem, ffprobe, manifests, tests; provider effect is impossible. |
| `official_api_read` | Supported provider read; endpoint coverage must be explicit. |
| `official_api_write` | Supported provider mutation through a reviewed adapter. |
| `internal_web_read` | Experimental read through undocumented web interfaces; never promoted to a stable adapter from one success. |
| `browser_ui_read` | Observation in an authenticated browser session. |
| `browser_ui_write` | UI mutation; requires exact active-surface binding, persisted intent, and postflight. |

A workflow may change transport between phases only when that boundary is explicit. “API or browser, whichever works” is not a transport declaration.

Do not call an internal-web request “API” without qualification. Do not describe a DOM click as an API result. Do not infer that a browser-visible object is covered by an official API endpoint.

## 3. Use the invariant ladder when the exact pattern is missing

Use the strongest available layer and fall back only one level at a time:

1. repository-owned adapter with current regression tests;
2. exact operation contract and state machine;
3. provider/transport invariants;
4. one bounded read-only probe;
5. manual observation with retained evidence.

Never jump from “old selector failed” directly to “generate another full executor”. First ask which invariant is still true:

- exact project/community/channel identity;
- exact source file or source ID;
- one active modal or page root;
- a visible and hit-testable control inside that root;
- a before/after state change;
- a returned remote ID;
- an exact postcondition.

Selectors, labels, coordinates, title prefixes, modal closure, HTTP success, playback state, and stdout are observations. None is an identity or postcondition by itself.

## 4. Build an evidence table before a hypothesis

For every uncertain step, record:

| Field | Meaning |
|---|---|
| Known | Directly observed facts. |
| Unknown | Missing evidence that matters to the next decision. |
| Contradiction | Two sources that cannot both describe the same current state. |
| Hypothesis | One falsifiable explanation. |
| Minimal probe | Smallest non-mutating action that distinguishes the hypothesis. |
| Stop condition | Result that forbids further automatic action. |

Use one hypothesis at a time. A probe must answer a specific question. “Try several selectors and see” is not a bounded probe.

When evidence contradicts, do not average it or choose the newest-looking output. Reconcile source identity, timestamp, transport coverage, and exact object IDs.

## 5. Bind browser state before every action

Browser UI automation must prove the active surface rather than search the entire document for convenient text.

Before clicking or filling:

1. identify the topmost active dialog/page root;
2. prove it is visible and hit-testable;
3. prove the target control belongs to that root;
4. record the expected transition;
5. capture before-state evidence;
6. perform one action;
7. observe the transition by content/state, not only by window closure.

A background quick-search input is not the playlist selector. A row click that starts playback is not track selection. A title containing an artist name is not proof that the separate artist field is correct.

For browser uploads, the browser profile is a single-writer resource. Own one exact profile directory, detect existing profile processes, and terminate only the root process tree once. “Process not found” after killing child processes is diagnostic noise and must not be treated as an operation failure.

## 6. Separate phases and their success semantics

Use independent phases with independent results:

1. local intake/probe;
2. metadata decision;
3. upload;
4. upload visibility/readback;
5. metadata edit;
6. playlist creation or selection;
7. track membership update;
8. final postflight;
9. optional wall publication.

Success in one phase never promotes later phases. “MP3 uploaded and visible” remains success even when playlist creation fails. Resume from the failed child operation; do not rerun the upload.

Every phase result records:

- transport;
- phase state;
- exact input identity;
- exact remote identity when available;
- before/after evidence;
- whether a provider effect is impossible, confirmed absent, may exist, or verified;
- safe next action.

The repository model in `application/operation_reasoning.py` encodes the core retry decision. It is deliberately transport-aware and pattern-independent.

## 7. Retry by provider-effect evidence, not by exit code

| Provider-effect state | Automatic retry rule |
|---|---|
| `impossible` | Local-only step may be corrected and retried. |
| `not_dispatched` | Correct the cause and retry the exact child operation. |
| `confirmed_absent` | One corrected retry is allowed with retained proof. |
| `may_exist` | No blind retry; reconcile provider state first. |
| `verified` | Complete; rerun is forbidden. |

An exit code cannot prove `confirmed_absent`. A timeout after bytes were submitted is `may_exist` until reconciled. Accepted, processing, unknown, and verified states are never blindly repeated.

## 8. Make progress without turning the task into a global audit

Provider snapshots are temporary operation inputs, not permanent truth. Scan only the surfaces needed to prevent duplicates or prove the requested postcondition.

Default scope:

- exact input folder/manifest;
- exact target project/community/channel;
- bounded current inventory relevant to those inputs;
- exact outputs from this operation.

Do not block a 12-item upload because a historical channel-wide count is stale. Do not rescan thousands of unrelated objects to perform a metadata-only local task. Do not commit live provider snapshots after every mutation.

A useful final summary is operation-scoped:

```text
Planned:
Ready:
Executed:
Verified:
Skipped exact duplicates:
Requires review:
Unknown:
```

## 9. Use time and iteration budgets

Before implementation, set:

- maximum hypotheses for one failure class: normally 3;
- maximum retries of the same provider child operation: 1 after confirmed absence;
- maximum browser selector revisions without a new DOM/state observation: 1;
- maximum full-package generations: 1; subsequent fixes patch repository code and tests;
- maximum read-only inventory scope and page count;
- explicit timeout per long upload, processing wait, or postflight.

Stop and redesign when:

- the same failure returns after two mechanism-only changes;
- a new ZIP version changes no underlying invariant;
- the agent cannot state which provider effect may already exist;
- the active browser surface is not bound;
- a result depends on title prefix, arbitrary coordinate, or global text search;
- the requested postcondition is not observable;
- user action is being blamed without a clean reproducible run.

## 10. Avoid the ZIP/version treadmill

A ZIP is a handoff format, not the implementation source of truth.

After a successful experiment:

1. extract the invariant and failure mode;
2. implement or patch repository-owned code;
3. add a regression fixture;
4. retire the experimental generation;
5. preserve only minimal evidence and final disposition.

Do not create v1.4, v1.7, v2.0, and v3.x families when the permanent adapter remains unchanged. Do not import an old executor wholesale. Reuse proven logic only after reviewing transport, identity, retry, and postflight boundaries.

## 11. Content verification uses the same method

For quotations, captions, descriptions, and translations:

- source identity precedes prose quality;
- quoted text must map to one contiguous source passage unless explicitly marked as synthesis;
- beautiful connective prose generated by a model is not evidence that the author said it;
- preserve a short source anchor and verification note;
- distinguish exact quotation, translation, paraphrase, and editorial synthesis.

This prevents a fluent composite passage from being promoted to a quotation merely because every sentence is thematically plausible.

## 12. Decision record template

```text
Outcome:
Project/target:
Operation surface:
Transport:
Allowed side effects:
Forbidden side effects:
Current phase:
Provider-effect state:
Known:
Unknown:
Contradictions:
Single hypothesis:
Minimal probe:
Expected transition:
Exact postcondition:
Retry rule:
Stop condition:
Durable evidence path:
```

An agent may adapt the implementation, but it may not weaken these fields.
