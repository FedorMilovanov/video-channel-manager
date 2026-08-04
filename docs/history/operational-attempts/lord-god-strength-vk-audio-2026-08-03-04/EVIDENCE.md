# Evidence boundary — Lord God Strength VK Audio history

## Source transcripts

### Source A — earlier attempt history

- supplied file: `Вставленный текст(272).txt`;
- byte size: `67662`;
- rendered line count: `1828`;
- SHA-256: `319c125c54cc41ebe4cbc578b0e54c31e28ea23e5b106bc33ccb4a868b28a61a`;
- covered period: 2026-08-03 through 2026-08-04;
- source type: pasted conversation transcript containing operator logs, package names, expected SHA-256 values, diagnoses, and partial outcomes.

### Source B — playlist completion and extended history

- supplied file: `Вставленный текст(281).txt`;
- byte size: `93296`;
- physical text line count: `2155`;
- SHA-256: `cf72b5bd605a8aadfd7f34e9de48354cc7d9ab2a897364e97166f7b598b779c5`;
- covered period: 2026-08-03 through 2026-08-04;
- source type: expanded pasted transcript containing the earlier history plus batch summaries, playlist Workhorse evolution, package inventory, diagnostic reasoning, and final exact playlist verification.

Source B overlaps Source A. It is not treated as an independent confirmation of every repeated statement; it adds later evidence that was absent from Source A.

## What the combined evidence directly supports

The transcripts directly support:

- initial upload interruption caused by premature browser closure;
- successful visibility verification of one MP3 in canary v1.3;
- later playlist-add failure after that upload;
- wrong UI target causing playback instead of selection;
- a PlaylistOnly hang;
- metadata manager failures before save;
- a false `already_correct` diagnosis in Rename AUTO v2.0;
- successful read-only network probe with zero writes attempted;
- failed live network observation after a manual metadata edit;
- canonical preparation of ten playlist positions into eight unique tracks;
- Reliable Batch v3.0 crashing on PowerShell `.Count` before provider writes;
- Reliable Batch v3.1 partial success and deferred items;
- correlation between failing `vk.ru` upload slots with HTTP 413 and successful `pu.vk.ru` slots;
- a later Reliable Batch summary with four verified tracks, four HTTP 413 failures, fourteen writes used, and `safe_to_create_playlist: false`;
- Workhorse v1.0 selecting all eight tracks and reaching the nested save boundary;
- a false/ambiguous local transition failure caused by page-global search-state detection;
- Workhorse v1.1 performing an exact no-write verification of an already complete playlist;
- exact remote playlist title `Анатомия церкви — Джон МакАртур`;
- playlist ID `85093900`;
- owner/community `-60805374`;
- exactly eight members, no extras, no duplicates, and exact order `01` through `08`.

## Verified result versus causal attribution

The evidence proves the exact final remote playlist state and proves that the v1.1 verification run did not dispatch a final create save.

The evidence does **not** contain the exact successful write response or network event that created playlist `85093900`.

Therefore:

- `remote_playlist_exactly_verified`: supported;
- `v1_1_rerun_performed_zero_create_writes`: supported;
- `v1_0_definitely_created_playlist_85093900`: not supported;
- `exact_originating_write`: unknown.

A later remote read can prove that a mutation occurred, but not always which prior click/request caused it.

## What this evidence does not preserve byte-exactly

The transcripts list many package names and historical expected SHA-256 values, but do not embed every exact ZIP or script body. Therefore this archive does not yet claim byte-exact preservation of every referenced implementation, including:

- `vk_mp3_canary_v1_3`;
- PlaylistOnly v1.4 through v2.2;
- Metadata Manager v1.0 or v1.1;
- Rename AUTO v2.0 or v2.1;
- VK Audio Web Read Probe v1.1;
- manual edit network observers;
- series importer versions;
- Reliable Batch v3.0 through v3.3;
- Audio Workhorse v4.0;
- Playlist Workhorse v1.0 or v1.1.

The historical SHA-256 strings remain references until the corresponding local bytes are recovered and independently hashed.

## Remaining limitations

The combined evidence does not prove:

- the exact request or final click that originally created playlist `85093900`;
- that every referenced package is secret-free or safe to execute;
- final successful metadata correction by Metadata Manager v1.1 or Rename AUTO v2.1;
- that `pu.vk.ru` is the only valid host for all future VK Audio upload contracts;
- long-term stability of undocumented VK web endpoints;
- that the archived Workhorse v1.1 is suitable as a supported general-purpose playlist implementation;
- behavior for playlists with duplicate titles, partial pre-existing membership, reorder-only changes, or concurrent operator edits.

## Privacy and secret handling

The archive intentionally excludes cookies, tokens, action hashes, upload URLs, browser profiles, raw network payloads, and media files.

Any future raw package or network-evidence import must undergo:

1. secret scanning;
2. cookie/token/action-hash redaction;
3. removal of reusable upload URLs;
4. verification that no browser profile or private media is included;
5. storage as unsupported non-executable evidence.

## Future exact-source recovery

If exact historical packages are found locally, add them only as non-executable Markdown source snapshots or redacted fixtures with:

1. exact original filename;
2. locally computed SHA-256;
3. package-internal manifest if present;
4. secret scan result;
5. relation to the timeline stage;
6. evidence level: designed, self-tested, canary-verified, batch-verified, or exact remote readback;
7. explicit statement that the source is unsupported and must not be executed.
