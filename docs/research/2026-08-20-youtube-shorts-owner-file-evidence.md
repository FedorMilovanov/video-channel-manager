# YouTube Shorts / owner source-file evidence — primary-source ledger

Checked: 2026-08-20  
Scope: read-only YouTube inventory classification for Instagram/Reels preparation  
Provider mutations authorized: no

This ledger records the external provider facts used by `youtube_surface_classification.py`. It does not authorize publication, download, edit, or re-upload.

## Primary sources

### YouTube Help — three-minute Shorts

- https://support.google.com/youtube/answer/15424877
- https://support.google.com/youtube/answer/10059070

Provider facts used by the classifier:

- standard channels: square or vertical videos up to three minutes uploaded on or after **2024-10-15** are categorized as Shorts;
- Official Artist Channels have the later three-minute-Shorts transition date **2025-12-08**;
- therefore `2025-12-08T00:00:00Z` is used as the conservative channel-type-independent lower boundary when exact owner source-file evidence is available.

The classifier intentionally uses the later boundary. It does not guess whether `legendary-poet` is or is not an Official Artist Channel.

## YouTube Data API — `videos` resource

Primary documentation:

- https://developers.google.com/youtube/v3/docs/videos
- https://developers.google.com/youtube/v3/docs/videos/list

Provider facts used by the inventory layer:

- `fileDetails` is available to the owner of a video;
- `fileDetails.durationMs` reports uploaded-file duration in milliseconds;
- `fileDetails.videoStreams[]` exposes source video stream metadata including `widthPixels`, `heightPixels`, codec/frame-rate fields and `rotation`;
- `fileDetails.creationTime` is the uploaded file's creation time;
- `snippet.publishedAt` is publication/public-availability metadata and is not treated by this repository as an exact upload timestamp.

## Repository interpretation boundary

The repository makes only these bounded inferences:

1. **Landscape source geometry** cannot satisfy the square/vertical Shorts geometry requirement, so it can be classified `longform`.
2. **Duration over 180 seconds** cannot satisfy the current three-minute Shorts cap, so it can be classified `longform`.
3. A square/vertical source at or below 180 seconds whose owner-reported file `creationTime` is on/after `2025-12-08T00:00:00Z` can be classified `short` conservatively: the video cannot have been uploaded before the source file itself existed, and that lower bound is already after the later three-minute-Shorts transition.
4. A square/vertical source at or below 180 seconds without that post-boundary proof remains `unknown` + `youtube_short_candidate=true`.
5. `#Shorts`, title text, duration alone below the cap, thumbnail shape, or `snippet.publishedAt` alone are not accepted as exact positive Shorts proof.

## Rotation handling

Display geometry is derived after source-stream rotation:

- missing / `none` / `upsideDown` preserve width and height for orientation purposes;
- `clockwise` / `counterClockwise` swap display width and height;
- unknown rotation values fail closed to unknown geometry;
- conflicting reported stream orientations also fail closed.

## Explicit non-equivalence

Owner YouTube `fileDetails` proves provider-side source-file metadata. It does **not** prove any of the following:

- that exact source bytes are locally available;
- that a downloaded YouTube delivery copy equals the uploaded clean master;
- that reuse rights for Instagram are cleared;
- that an Instagram Professional account is bound or authorized;
- that a Reel cut/timestamp has been editorially approved.

Those remain separate `MediaArtifactEvidence`, `InstagramMediaReview`, exact-output and provider-authorization gates.
