# VK Audio and browser experiment retrospective

Date: 2026-08-05  
Status: historical evidence and design input  
Provider capability: not authorized  
Current support class: `SEPARATE_EXPERIMENTAL_SYSTEM / PARTIAL_OR_UNKNOWN_OUTCOMES / NOT_CORE_SUPPORTED`

This document reconstructs the useful engineering facts from the supplied conversation histories. It does not make the old ZIPs supported, and it does not authorize an MP3 upload, metadata edit, playlist change, or browser session.

## Source ledger

| Supplied transcript | Lines | SHA-256 |
|---|---:|---|
| `Вставленный текст(20260805-115343).txt` | 836 | `3077cff82659b2ca88efd181a4a4aa39e969304c17da7b9a8dd7beb6fff6e2bc` |
| `Вставленный текст (2)(20260805-115359).txt` | 2,156 | `d655f99617308d6cd364a74a5489fd17e849460e9001b388e6a6fe81131e80c9` |
| `Вставленный текст (3)(2).txt` | 406 | `a5414640a8898ddff47b6c35727f83365265723d11d88f3d5163c4c24151019b` |

The transcripts combine user observations, generated packages, PowerShell logs, browser result JSON, Python snippets, and retrospective conclusions. A statement is treated as verified only when supported by retained structured output or exact postflight in the transcript.

## Reconstructed chronology

### 1. Initial BrowserCanary closed the browser before upload completion

The first attempt observed an upload progress bar but began checking too early, found no track, and closed the automated browser profile. Closing the browser interrupted the transfer. The correction was to keep the profile alive, wait for a bounded long-upload interval, capture periodic evidence, refresh/search the audio surface, and ask before closing.

Lesson: “not visible yet” during transfer is not `confirmed_absent`. Upload progress and browser lifetime are part of the upload phase state.

### 2. BrowserCanary v1.3 proved upload success but not workflow success

The structured browser result recorded:

- file selection;
- completed upload dialog;
- exact title search;
- uploaded track visible;
- playlist creation attempted;
- final status `uploaded_playlist_created_add_action_not_found`.

The MP3 upload was therefore a verified parent-phase success while playlist membership was a failed child phase. The correct response was a playlist-only continuation. Repeating BrowserCanary would have risked a duplicate upload.

Lesson: preserve partial success and resume from the first unverified child phase.

### 3. PlaylistOnly clicked playback instead of selection

A later script reached the correct row but clicked the row body. The visible pause icon and playback position proved playback, while the selection circle remained empty.

Lesson: semantic labels and row identity do not prove control identity. Browser automation must bind the active modal and target the exact hit-testable selection control.

### 4. Metadata Manager v1.0 failed before mutation

The first metadata version encountered a PowerShell parameter-set error. The transcript states that the local MP3 was unchanged, the VK form was not saved, and no mutation occurred. The corrected version added:

- backup before local tag replacement;
- no audio re-encoding;
- ffprobe readback;
- support for `input`, `textarea`, `contenteditable`, and `role=textbox`;
- reread of exact fields before save.

Lesson: local tag preparation and remote metadata editing are separate operations. A pre-mutation failure is safe to correct; it is not evidence that the whole idea failed.

### 5. Rename automation produced a false `already_correct`

The old title contained the preacher’s name, so prefix/substring logic mistook it for a correct separate artist field. Another attempt filled a global VK search field rather than the music-specific search control.

Lesson: `already_correct` requires exact per-field readback. Search and form controls must be scoped to the active audio surface, not selected by globally convenient text.

### 6. Internal-web read probes were useful but not a supported adapter

An authenticated Yandex profile and browser cookies enabled read-only calls to undocumented VK web endpoints. Those probes helped inspect audio metadata, but endpoint stability and coverage were not established.

Lesson: classify this as `internal_web_read`. One successful response does not create an official API contract or mutation adapter.

### 7. Series import normalized ten source entries to eight unique tracks

A YouTube-derived series list contained duplicates and was normalized to eight unique source tracks. The reliable batch later reported four verified tracks and four `binary_http_413` failures after a long run.

Lesson:

- deduplicate before any upload;
- preserve exact source IDs and SHA-256;
- treat HTTP 413 as a transport/size-class failure, not a metadata or playlist failure;
- default to one-at-a-time execution until size limits, request framing, and browser behavior are proved;
- preserve each track’s state independently so four failures do not invalidate four verified outcomes.

No permanent size limit is asserted here because the transcripts do not establish a stable provider contract.

### 8. Playlist Workhorse v1.0 likely succeeded but misread the transition

The first workhorse selected eight tracks and clicked save, then expected the selection modal to disappear. A background quick-search input was mistaken for evidence that the selector remained active. A later version found the exact completed playlist and performed no duplicate write.

The corrected design used:

- topmost active modal selection;
- visibility plus hit-testing;
- content/state transition rather than modal closure alone;
- one bounded internal save fallback;
- exactly one final save;
- exact title and track-count postflight;
- `playlist_already_complete_verified` as a no-write completion state.

Lesson: postflight can prove that an earlier “failure” actually completed. Never rerun while the remote effect is uncertain.

## Cross-experiment error taxonomy

| Error class | Concrete symptom | Permanent correction |
|---|---|---|
| Premature observation | Browser closed while transfer still active. | Explicit upload/processing states and bounded waits. |
| Coupled phases | Playlist failure made upload appear failed. | Independent child operations and results. |
| Global selector | Background or unrelated field was filled. | Bind topmost active root and control ownership. |
| Action confusion | Row click started playback. | Prove exact control semantics and after-state. |
| False exactness | Artist substring inside title yielded `already_correct`. | Exact separate-field readback. |
| Transition confusion | Modal closure used as sole save proof. | Verify content and remote postcondition. |
| Transport ambiguity | UI/internal-web behavior described as API. | Declare transport per phase. |
| Retry ambiguity | Non-zero exit treated as permission to repeat. | Provider-effect state and no-blind-retry rule. |
| Version proliferation | Many generated ZIP generations around one defect. | Patch repository-owned implementation and fixtures. |
| Batch coupling | Four 413 failures obscured four verified tracks. | Per-track ledger and resumable chunks. |

## What is verified

- A BrowserCanary upload could complete and the uploaded track could become visible.
- A later playlist-only/workhorse sequence could detect an exact completed playlist and avoid a duplicate write.
- Exact artist/title fields matter; title substring matching is unsafe.
- Browser upload, metadata editing, playlist creation, membership update, and final verification need separate state.
- Single-profile browser ownership, retained JSON, screenshots, and exact postflight materially improved diagnosis.

## What is not verified as a permanent capability

- stable official VK Audio upload or playlist APIs;
- stable undocumented internal-web endpoint schemas;
- a universal file-size or duration limit;
- safe concurrent browser uploads;
- safe automatic metadata edits for arbitrary VK UI versions;
- a supported batch writer in this repository;
- permission to repeat any historical experiment.

## Retirement rule

BrowserCanary, PlaylistOnly, Metadata Manager, Rename AUTO, reliable-v3, calibrator, and Playlist Workhorse ZIP generations are historical experiments. Their names, SHA values, prompts, and local paths do not authorize execution.

Only reusable invariants are promoted:

- exact local intake;
- explicit metadata policy;
- transport declaration;
- phase separation;
- single-writer browser ownership;
- per-track durable state;
- exact no-write/verified postflight;
- reconciliation before retry.
