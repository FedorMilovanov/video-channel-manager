# Timeline — Lord God Strength VK Audio

## 001. Initial browser canary closed during transfer

**Goal:** upload one long MP3 to the community and then create a test playlist.

**Observed:** the upload indicator had progressed only partway when the script checked too early, failed to find the record, and closed the browser. Closing the browser interrupted the transfer.

**Outcome:** failed upload; later manual inspection found no remote record, so one retry was considered safe.

**Permanent rule:** browser transfer completion, remote visibility, and workflow completion are separate states. Never close the browser or authorize replay from a short timeout alone.

## 002. Browser canary v1.3 — upload success, playlist partial failure

**Changes:** wait up to 30 minutes, keep browser open, capture progress, refresh the audio surface, search by title, and request explicit confirmation before playlist work.

**Observed:** the MP3 became visible and was marked `upload_verified`. The later playlist stage ended with `uploaded_playlist_created_add_action_not_found` and code 45.

**Outcome:** mixed. The upload itself succeeded; adding the uploaded track to the playlist did not.

**Permanent rule:** report upload, playlist creation, and playlist membership as independent outcomes. A final nonzero exit does not erase a previously proven remote upload and must not authorize retransmission.

## 003. Browser process cleanup produced noisy false errors

**Observed:** terminating a parent browser process also terminated its child processes. The loop then attempted to terminate the already removed child PIDs and printed repeated `process not found` errors.

**Outcome:** cleanup was functionally successful but diagnostically noisy.

**Permanent rule:** take a process snapshot, terminate roots once, and treat already-exited children as expected. Cleanup noise must not be confused with provider failure.

## 004. PlaylistOnly v1.4 selected the wrong UI target

**Goal:** create a playlist and add the already uploaded track without uploading again.

**Observed:** the automation clicked the track row and started playback instead of clicking the selection control. The empty circle remained unselected.

**Outcome:** failed playlist membership automation.

**Permanent rule:** a visually nearby row is not an action control. Require semantic target evidence, control role/state verification, and post-click state change before continuing.

## 005. PlaylistOnly v1.7 hung after confirmation

**Observed:** after `СОЗДАТЬ`, the workflow remained stuck with no useful progress signal.

**Outcome:** failed or unknown playlist operation.

**Permanent rule:** every UI mutation requires bounded stages, heartbeats, explicit timeout classification, and read-only reconciliation. Silence is not success and must not trigger blind retry.

## 006. Metadata Manager v1.0 failed before mutation

**Goal:** correct local ID3 tags and rename the already uploaded VK audio.

**Observed:** PowerShell parameter-set resolution failed and the VK form controls were not recognized. The local MP3 and VK record were not changed.

**Outcome:** safe failure before mutation.

**Permanent rule:** local metadata preparation and remote metadata mutation must be separate operations. A failed control-discovery phase must prove that no save action was dispatched.

## 007. Metadata Manager v1.1 broadened control discovery

**Changes:** fixed PowerShell parameter handling; cleared stale uploader/channel metadata; preserved the MP3 bitstream; added backups and `ffprobe` verification; recognized `input`, `textarea`, `contenteditable`, and `role=textbox`; reread fields before save; refused uncertain saves.

**Outcome:** useful design improvement, but the supplied transcript does not prove a final successful VK rename.

**Permanent rule:** distinguish a proposed fix from a verified provider outcome. Archive both, but never label an unobserved result successful.

## 008. Rename AUTO v2.0 produced a false `already_correct`

**Observed:** the script saw the desired artist name inside the old title and the desired title as a prefix of a longer incorrect title. It then concluded both fields were already correct. It also filled the global VK search instead of the music-section search.

**Outcome:** critical false positive; no metadata was changed.

**Permanent rule:** title and artist are separate exact fields. `already_correct` requires exact normalized equality of each field after reopening the exact target form. Substring presence, combined row text, and prefix matching are forbidden as success evidence.

## 009. Rename AUTO v2.1 corrected the matching design

**Changes:** scoped search to the music section, excluded global search, parsed title and artist separately, prioritized the exact menu/control, selected the exact edit action, and reopened the form after save for verification.

**Outcome:** the transcript contains the design and expected statuses, but not a demonstrated final success.

**Permanent rule:** expected status names are not evidence. Only a readback of exact fields on the exact remote identity may close the operation.

## 010. VK Audio Web Read Probe v1.1 succeeded

**Goal:** prove reliable read-only access without performing upload, edit, or playlist writes.

**Observed:** the probe used browser-session cookies in memory with Node HTTP requests to VK web audio endpoints. Self-tests passed, writes attempted were zero, one exact candidate was found, and the old metadata was correctly distinguished from the expected metadata.

**Outcome:** successful read-only discovery and exact remote identification.

**Permanent rule:** prefer structured network reads over DOM scraping when the provider surface lacks a supported public API, but treat undocumented web endpoints as unstable adapters with explicit limitations and secret redaction.

## 011. Manual edit network observer did not capture the save

**Goal:** observe one operator-performed metadata save and learn the exact network contract without automating the write.

**Observed:** the operator changed the title, but the observer did not detect the request and remained waiting. A later calibrator also required another manual save.

**Outcome:** failed observation/calibration.

**Permanent rule:** an observer must prove attachment to the correct browser target, request domain, frame, and event source before asking the operator to mutate anything. A self-test of parsers does not prove live interception coverage.

## 012. Series importer v1.2 prepared canonical media correctly

**Goal:** import a YouTube playlist as a VK Audio series.

**Observed:** ten playlist positions were reduced to eight unique tracks; two duplicate entries were explicitly identified; existing downloads were reused; titles and ID3 tags were normalized; a deterministic plan and prepared media directory were produced.

**Outcome:** successful preparation and deduplication. The subsequent remote batch upload had not yet been proven at this stage.

**Permanent rule:** preparation success and provider upload success are separate. Preserve exact source positions, canonical unique identities, duplicate evidence, and prepared-media hashes.

## 013. Batch architecture was opaque to the operator

**Observed:** the console requested browser authorization while describing direct upload behavior, leading to uncertainty about whether the workflow used API calls, browser DOM automation, or a hybrid transport.

**Outcome:** operational confusion even before the technical failure was known.

**Permanent rule:** every run must state the transport for each stage: browser authorization, cookie bridge, internal web request, upload-server POST, DOM action, or public API call. Hidden hybrid architecture is a usability defect.

## 014. Reliable Batch v3.0 failed on an empty PowerShell collection

**Goal:** process tracks sequentially with fresh browser processes, fresh upload slots, curl streaming, reconciliation, retries, FFmpeg fallback, checkpoints, and final verification.

**Observed:** after correctly recognizing an existing track, the worker returned `execution.entries: []`. Under `Set-StrictMode`, the supervisor read `.Count` from an empty/scalar value and crashed before any new upload. Provider-write counts remained zero.

**Outcome:** failed coordinator, not a VK or curl failure.

**Permanent rule:** normalize all PowerShell command output with array wrapping before `.Count` or indexing. Add regression cases for zero, one, and many results under `Set-StrictMode` before provider dispatch.

## 015. Reliable Batch v3.1 fixed the collection bug and made partial progress

**Changes:** normalized empty/single collections, added a pre-write regression self-test, built one initial read-only plan, marked existing tracks as `ALREADY_REMOTE`, scoped reconciliation to the current track, and retained fresh-slot/curl/retry logic.

**Observed:** tracks 01 and 02 were already remote; tracks 04 and 05 uploaded and verified; track 03 exhausted attempts and was deferred; track 06 remained in progress.

**Outcome:** partial operational success with safe continuation and no duplicate replay of existing tracks.

**Permanent rule:** partial success must be preserved per track. Continue independent items, defer unresolved ones, and never collapse a batch into a single Boolean status.

## 016. Wrong upload host caused HTTP 413

**Observed:** failed attempts received an extracted upload URL on host `vk.ru` and stopped after roughly 7–8 MB with HTTP 413. Successful tracks received host `pu.vk.ru` and completed to `VERIFIED`.

**Outcome:** provider-contract discovery; the URL extractor accepted a plausible but incorrect HTTPS address.

**Permanent rule:** do not accept the first URL-shaped value from a provider response. Parse the exact response field and validate an allowlisted upload-host/path contract before transmitting media. Reject unexpected hosts before dispatch and archive the response shape in redacted fixtures.

## 017. Waiting was repeatedly confused with hanging

**Observed:** intentional waits, circuit-breaker delays, heartbeats, retries, and actual silent hangs were difficult to distinguish for the operator.

**Outcome:** unnecessary uncertainty and pressure to interrupt a live operation.

**Permanent rule:** emit one structured state line with current track, state, attempt, elapsed, next action, and deadline. A declared wait must show countdown progress; an undeclared silence beyond a bounded threshold is a failure.