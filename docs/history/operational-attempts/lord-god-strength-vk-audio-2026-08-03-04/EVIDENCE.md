# Evidence boundary — Lord God Strength VK Audio history

## Source transcript

- supplied file: `Вставленный текст(272).txt`;
- byte size: `67662`;
- rendered line count: `1828`;
- SHA-256: `319c125c54cc41ebe4cbc578b0e54c31e28ea23e5b106bc33ccb4a868b28a61a`;
- covered period: 2026-08-03 through 2026-08-04;
- source type: pasted conversation transcript containing operator logs, package names, expected SHA-256 values, diagnoses, and partial outcomes.

## What this evidence supports

The transcript directly supports:

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
- correlation between failing `vk.ru` upload slots with HTTP 413 and successful `pu.vk.ru` slots.

## What this evidence does not support

The transcript does not contain every exact ZIP or script body referenced in the conversation. Therefore this archive does not claim byte-exact preservation of:

- `vk_mp3_canary_v1_3`;
- PlaylistOnly v1.4 or v1.7;
- Metadata Manager v1.0 or v1.1;
- Rename AUTO v2.0 or v2.1;
- VK Audio Web Read Probe v1.1;
- manual edit network observer;
- series importer v1.2;
- Reliable Batch v3.0 or v3.1.

Expected package/script SHA-256 strings quoted in the transcript are historical references only until the corresponding bytes are recovered and independently hashed.

The transcript also does not prove:

- final successful playlist membership for the canary track;
- final successful metadata correction by Metadata Manager v1.1 or Rename AUTO v2.1;
- a completed eight-track Reliable Batch run;
- that `pu.vk.ru` is the only valid host for all future VK Audio upload contracts;
- long-term stability of undocumented VK web endpoints.

## Privacy and secret handling

The archive intentionally excludes cookies, tokens, action hashes, upload URLs, browser profiles, raw network payloads, and media files. The transcript states that cookie values were not persisted by the read probe, but any future raw evidence import must still undergo secret scanning and redaction.

## Future exact-source recovery

If exact historical packages are found locally, add them only as non-executable Markdown source snapshots or redacted fixtures with:

1. exact original filename;
2. locally computed SHA-256;
3. package-internal manifest if present;
4. secret scan result;
5. relation to the timeline stage;
6. explicit statement that the source is unsupported and must not be executed.