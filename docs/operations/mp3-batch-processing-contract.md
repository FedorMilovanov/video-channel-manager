# Local MP3 batch-processing and future VK Audio contract

Status: local-only foundation  
Provider mutation support: none  
Default transport: `local_only`  
Current local manifest `schema_version`: `1.1`

This contract prepares the repository for future large MP3 collections without promoting the historical browser experiments to a supported writer.

## 1. Scope split

The system treats these as separate operations:

1. discover local MP3 files;
2. probe file integrity and audio properties;
3. derive or review exact artist/title metadata;
4. build a deterministic manifest, duplicate report, and identity-conflict report;
5. optionally prepare local metadata changes in a future reviewed module;
6. upload one track in a future provider adapter;
7. verify upload visibility;
8. edit remote metadata in a future child operation;
9. create/select a playlist in a future child operation;
10. add exact track membership;
11. verify exact playlist title and membership;
12. optionally publish elsewhere under a separate authorization.

Waves 15–16 implement only steps 1–4. They never write ID3 tags, rename files, transcode audio, open a browser, call VK, or create a provider plan.

Upload, upload visibility, metadata edit, playlist creation, track membership, final save, and wall publication remain independent future operations.

## 2. Local identity

Each candidate retains:

- absolute path;
- exact byte size;
- SHA-256;
- ffprobe duration;
- codec, sample rate, channels, and bitrate when available;
- embedded tags;
- optional exact source ID;
- metadata-decision status;
- deterministic per-candidate operation ID.

SHA-256 identifies exact bytes. Source ID identifies the intended source object. Filename and title are presentation fields, not identity.

The mappings are fail-closed:

- one source ID mapped to multiple SHA-256 values is `source_id_sha256_conflict`;
- one SHA-256 claimed by multiple exact source IDs is `sha256_multiple_source_ids`;
- every candidate in either conflict remains `requires_review`;
- a conflict never becomes `ready` or `duplicate_input` automatically;
- identical bytes with the same source ID may form one duplicate group;
- operation IDs include project, exact identity, SHA-256, and resolved path so every local candidate remains individually addressable.

## 3. Metadata derivation and canonical selection

The default policy is `explicit_only`. An agent must supply both artist and title, or the item remains `requires_review`.

A known collection may declare a parser such as “artist is the final segment, at least three segments, separator is exact”. That declaration belongs to the input manifest, not global code assumptions.

Rules:

- explicit artist and title must be supplied together;
- exact separate fields are compared, never prefix/substrings;
- mixed separators are ambiguous;
- a trailing bracketed source ID may be extracted separately;
- the preacher/artist name is not repeated in the title unless the user explicitly wants it;
- no model guess becomes `ready` without a declared policy;
- `already_correct` in any future metadata writer requires exact post-write readback of both fields.

Canonical duplicate selection is deterministic and evidence-ranked:

1. explicit exact metadata wins canonical selection;
2. declared-policy ready metadata ranks after explicit exact metadata;
3. unresolved metadata ranks last;
4. path is only the deterministic tie-breaker inside the same evidence rank;
5. identity conflicts bypass canonical selection entirely and require review.

This prevents an alphabetically earlier ambiguous copy from suppressing a later exact copy.

## 4. Probe contract

`probe_audio_file` is read-only and:

- accepts configured audio extensions, `.mp3` by default;
- rejects missing, empty, or wrong-extension files;
- requires a positive-duration audio stream;
- permits attached cover art;
- rejects a normal video stream in MP3 intake;
- records normalized embedded tags;
- preserves the original bytes.

A future local tag writer must be a different module with backup, atomic replacement, no re-encode by default, and ffprobe readback. The read-only probe must never gain mutation behavior.

## 5. Batch states

Wave 16 local plan states:

- `ready` — exact or declared-policy metadata plus non-conflicting identity;
- `requires_review` — metadata policy is missing/ambiguous or identity mappings conflict;
- `duplicate_input` — exact duplicate bytes remain after one metadata-ranked canonical item is selected.

Important reasons include:

- `explicit_exact_fields`;
- `filename_convention_not_declared`;
- `duplicate_sha256`;
- `source_id_sha256_conflict`;
- `sha256_multiple_source_ids`.

Future provider states must extend, not replace, these states:

- `intent_persisted`;
- `uploading`;
- `accepted`;
- `processing`;
- `upload_verified`;
- `metadata_verified`;
- `playlist_verified`;
- `rejected`;
- `unknown_requires_reconciliation`.

Each track has its own result. A batch-level final line is supplementary.

## 6. Chunking, scale, and concurrency

Default chunk size is one ready item. This matches a single authenticated browser profile and makes unknown outcomes bounded.

A larger local chunk may be prepared with an exact item and byte budget, but it is not provider authorization. Wave 16 regression proves that 1,000 ready tracks produce a deterministic manifest, 1,000 unique operation IDs, and 40 deterministic chunks of 25 independent items.

A future provider chunk larger than one requires evidence for:

- transport capacity;
- total byte budget;
- request framing;
- independent per-track result persistence;
- safe resume after partial completion;
- provider throttling behavior.

HTTP 413 is classified as `binary_transport_rejected`. It does not permit metadata changes, alternate title guesses, or playlist retries. The item remains separate and requires a new transport hypothesis.

Do not infer a universal byte limit from one response. Record the exact file size, transport, request shape, and response.

## 7. Future browser session contract

A future browser adapter must:

- use one exact automation profile and one root process owner;
- refuse concurrent writers;
- archive prior result JSON rather than overwrite it silently;
- bind the active page/modal before every action;
- use visibility and hit-testing;
- record before/after DOM/state evidence;
- separate upload, metadata, selector save, final playlist save, and postflight;
- stop if user/manual action changes the active state unexpectedly;
- never repeat upload after visibility or an unknown outcome;
- allow playlist-only or metadata-only resume from verified upload state.

Internal-web requests discovered through a browser may support diagnostics, but remain `internal_web_read` until a separately reviewed contract exists.

## 8. Manifest shape

```json
{
  "schema_name": "video-manager.audio-batch-plan",
  "schema_version": "1.1",
  "project_key": "lord-god-strength",
  "transport": "local_only",
  "items": [
    {
      "operation_id": "audio-...",
      "ordinal": 1,
      "path": "C:\\...\\track.mp3",
      "source_id": "exact-source-id",
      "artist": "Exact artist",
      "title": "Exact title",
      "size_bytes": 123,
      "sha256": "sha256:...",
      "duration_seconds": 3600.0,
      "status": "ready",
      "reason": "explicit_exact_fields",
      "duplicate_of": null
    }
  ],
  "counts": {
    "total": 1,
    "ready": 1,
    "requires_review": 0,
    "duplicate_input": 0
  },
  "manifest_sha256": "sha256:..."
}
```

The manifest SHA is derived from canonical content without its own digest field. Reversing input order must not change the manifest.

## 9. Completion levels

- `local_inventory_verified` — bytes, probe, identity, conflicts, and metadata decisions recorded;
- `local_metadata_verified` — future exact local tag readback completed;
- `upload_verified` — future exact remote audio object verified;
- `playlist_verified` — future exact playlist and membership verified;
- `batch_verified` — every intended child operation is verified, skipped exact duplicate, or explicitly unresolved.

Do not call a local manifest “uploaded”, “operational”, or “ready to publish”.

## 10. Resume rules

A future resume begins from durable per-track state:

- `ready` may begin a new separately authorized upload;
- `upload_verified` skips upload and may enter an authorized metadata/playlist child operation;
- `accepted`/`processing` waits and postflights;
- `unknown_requires_reconciliation` performs read-only reconciliation and never resubmits;
- `playlist_verified` is complete and no-write;
- `duplicate_input` never enters provider execution automatically;
- `source_id_sha256_conflict` and `sha256_multiple_source_ids` require explicit local identity resolution before any provider plan can exist.

Historical ZIP names or console prompts are not resume tokens.
