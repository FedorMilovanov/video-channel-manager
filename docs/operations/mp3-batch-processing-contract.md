# Local MP3 batch-processing and future VK Audio contract

Status: local-only foundation  
Provider mutation support: none  
Default transport: `local_only`

This contract prepares the repository for future large MP3 collections without promoting the historical browser experiments to a supported writer.

## 1. Scope split

The system treats these as separate operations:

1. discover local MP3 files;
2. probe file integrity and audio properties;
3. derive or review exact artist/title metadata;
4. build a deterministic manifest and duplicate report;
5. optionally prepare local metadata changes in a future reviewed module;
6. upload one track in a future provider adapter;
7. verify upload visibility;
8. edit remote metadata in a future child operation;
9. create/select a playlist in a future child operation;
10. add exact track membership;
11. verify exact playlist title and membership;
12. optionally publish elsewhere under a separate authorization.

Wave 15 implements only steps 1–4. It never writes ID3 tags, renames files, transcodes audio, opens a browser, calls VK, or creates a provider plan.

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
- deterministic operation ID.

SHA-256 detects byte duplicates. Source ID detects semantically duplicated downloads with different bytes. Neither filename nor title is sufficient identity.

## 3. Metadata derivation is policy-driven

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

Wave 15 local plan states:

- `ready` — exact metadata and unique identity;
- `requires_review` — metadata policy is missing or ambiguous;
- `duplicate_input` — exact SHA or source ID repeats an earlier candidate.

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

## 6. Chunking and concurrency

Default chunk size is one ready item. This matches a single authenticated browser profile and makes unknown outcomes bounded.

A larger chunk requires evidence for:

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

## 8. Future manifest shape

```json
{
  "schema_name": "video-manager.audio-batch-plan",
  "schema_version": "1.0",
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

The manifest SHA is derived from canonical content without its own digest field.

## 9. Completion levels

- `local_inventory_verified` — bytes, probe, identity, and metadata decisions recorded;
- `local_metadata_verified` — future exact local tag readback completed;
- `upload_verified` — future exact remote audio object verified;
- `playlist_verified` — future exact playlist and membership verified;
- `batch_verified` — every intended child operation is verified, skipped exact duplicate, or explicitly unresolved.

Do not call a local manifest “uploaded”, “operational”, or “ready to publish”.

## 10. Resume rules

A future resume begins from durable per-track state:

- `ready` may begin a new authorized upload;
- `upload_verified` skips upload and may enter an authorized metadata/playlist child operation;
- `accepted`/`processing` waits and postflights;
- `unknown_requires_reconciliation` performs read-only reconciliation and never resubmits;
- `playlist_verified` is complete and no-write;
- `duplicate_input` never enters provider execution automatically.

Historical ZIP names or console prompts are not resume tokens.
