# Milovi Cake Telegram — video conversion readiness

Status: **provider-inert / all 16 native-video outputs blocked**  
Owning issue: #353

This lane exists because the canonical Milovi Cake gallery stores 16 finished-work videos as WebM. Those files are valid editorial source assets, but they are not automatically treated as native Telegram `sendVideo` payloads.

## Source boundary

All 16 video binaries are pinned to one exact Milovi Cake commit:

`c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370`

The gallery identity at that same commit is pinned by `js/gallery/data.js` blob:

`e20e60c07479e8b20c1db700f1a40364b81eb669`

The machine-readable source set is `video-source-readiness-2026-08.json`. It records the exact Git blob SHA-1 and repository-reported byte size of each WebM, plus the canonical media ID, title and poster.

Repository metadata proves identity and byte size. It does **not** prove:

- the actual container reported by ffprobe;
- source video codec;
- pixel format;
- width / height;
- frame rate;
- duration;
- whether an audio stream exists;
- source audio codec.

Those fields remain null until the exact pinned bytes are materialized and probed. Do not infer them from `.webm`, browser playback, poster dimensions or memory.

## Why source size is not readiness

Every current source file is far below Telegram's reviewed 50 MB bot-video hard limit. That is useful evidence about likely practicality, but it does not make any WebM a reviewed native Telegram video.

A native-video release requires an accepted output record, not merely a small source file.

## Deterministic output intent

The current conversion contract targets:

- MP4 container;
- H.264 video (`libx264`);
- `yuv420p` pixel format;
- `+faststart` for progressive MP4 playback;
- preserved source aspect ratio and orientation;
- no upscaling;
- even output dimensions if scaling is required;
- no invented/synthetic audio;
- AAC-LC only if the exact source actually contains reviewed audio;
- nonessential metadata stripped by default;
- exact output SHA-256 recorded before acceptance.

These are preparation rules, not a hidden converter invocation. The exact ffmpeg and ffprobe versions, execution-environment digest and command argv remain unresolved until a real conversion run is prepared.

## Probe first, convert second

For each media ID `v01`–`v16`, the sequence is:

1. Materialize the exact source bytes from the pinned Milovi Cake commit.
2. Verify the Git blob identity and compute a byte SHA-256.
3. Run ffprobe against those exact bytes and freeze the probe result.
4. Review source geometry/timing/audio state.
5. Freeze the exact ffmpeg/ffprobe toolchain and execution environment.
6. Build one explicit argv list; no shell interpolation and no unreviewed filter graph.
7. Convert to a new output file. Never overwrite the Milovi Cake source.
8. Probe the output.
9. Compute output SHA-256 and byte size.
10. Check every acceptance gate in `video-conversion-contract-2026-08.json`.
11. Write the accepted evidence into `video-output-records-2026-08.json` only through a separately reviewed change.

No step above talks to Telegram.

## Geometry rule

Do not make every video the same dimensions just for cosmetic symmetry. Preserve the source composition. Scale only when an exact source probe demonstrates a compatibility or size reason.

If scaling is required:

- scale down only;
- preserve display aspect ratio;
- use even width and height for H.264 compatibility;
- record the source and output dimensions;
- reject a materially changed aspect ratio unless a separate editorial crop was deliberately reviewed.

Cropping and conversion are different operations. This lane does not authorize editorial reframing.

## Frame-rate rule

Preserve source timing by default. Do not force 30 fps or 60 fps just because those are common values. If a specific input requires a frame-rate change for compatibility, document the source probe, reason and exact output frame rate.

## Audio rule

If the source has no audio, the output must have no audio. Do not synthesize silence or add music.

If the source has audio, preserve only reviewed source audio semantics. The conversion contract allows a single AAC-LC output track after the source audio state is known. It does not allow replacing, mixing or decorating audio during transport preparation.

## v04 identity guard

`v04` is the known filename trap:

- physical file: `video-04-eclair.webm`;
- canonical gallery identity: **`Видео: меренговый рулет`**.

No converter, manifest generator or future publisher may infer the product identity from `eclair` in the filename. The stable identity key is `v04`, and its editorial title comes from the canonical gallery source.

## Output acceptance is not publication authorization

An accepted MP4 proves only that one exact output is ready to become a future native-video payload candidate. It does not authorize:

- `sendVideo`;
- a queue entry;
- scheduling;
- pinning;
- a Telegram album;
- VK/Dzen/YouTube cross-posting;
- reusing the output for another media ID;
- automatic rollout after the photo canary.

Target binding, exact release review and provider authorization remain separate.

## No silent document fallback

If an output fails native-video readiness, the response is to block and diagnose it. Do not silently call `sendDocument` with the source WebM or failed MP4 merely to get something into Telegram. That changes the product experience and bypasses the reviewed native-video intent.

## Current completion state

At this stage:

- source identities: known for all 16;
- source byte sizes: known for all 16;
- source probe: unresolved for all 16;
- conversion toolchain lock: unresolved;
- accepted MP4 outputs: **0 / 16**;
- Telegram-native video readiness: **0 / 16**;
- provider write authorization: **false**.

This is an intentionally useful blocked state: future conversion can proceed from exact evidence without rediscovering which source file belongs to which Milovi work.
