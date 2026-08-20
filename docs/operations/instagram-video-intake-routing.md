# Instagram video intake and media routing

Status: provider-inert  
Owner issue: #492  
Scope: repository-owned preparation only; no Instagram/Meta provider mutation

This runbook is the canonical operator path for turning an exact YouTube inventory into an Instagram/Reels production-routing artifact. It deliberately separates provider inventory, YouTube surface classification, source-master evidence, rights/provenance review, and publication authorization.

## Invariants

1. YouTube inventory is acquired only through the existing read-only YouTube adapter.
2. `project_key` is resolved against the canonical repository identity registry; a display name or vanity handle is never a target identity.
3. Duration, title, `#Shorts`, or `snippet.publishedAt` alone never proves that a YouTube video is a Short.
4. Owner-only YouTube `fileDetails` may be used to prove uploaded-source geometry and exact file duration, but it is not a clean-master license or local-master proof.
5. `MediaArtifactEvidence` is the only technical local-media evidence contract used by this lane. Do not create an Instagram-specific second ffprobe registry.
6. A YouTube/VK/social delivery encoding is not a clean source master merely because it is downloadable.
7. Technical compatibility does not prove reuse rights. Rights/provenance review is a separate exact-manifest record.
8. Every generated intake/route artifact is provider-inert and carries `provider_writes_authorized=false`.
9. No Reel cut timing is frozen until exact source bytes are bound.

## Stage 1 — fresh read-only YouTube snapshot

Use the exact canonical channel ID, not only the local account alias:

```powershell
video-manager youtube scan `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --output .\data\exports\legendary-poet-youtube-current.json
```

The existing owner-authenticated scan requests `snippet,contentDetails,status,fileDetails` for the channel's videos. `fileDetails` is owner-only provider evidence and can retain the uploaded file's millisecond duration, video-stream dimensions, rotation and file creation time inside `VideoRecord.metadata` without downloading the media.

The resulting `AuditPackage` is a read-only provider snapshot. Keep its exact bytes unchanged after review; the intake command hashes the actual input bytes.

## Stage 2 — typed Instagram intake and YouTube surface classification

```powershell
video-manager instagram video-intake `
  .\data\exports\legendary-poet-youtube-current.json `
  --project legendary-poet `
  --output .\data\reports\legendary-poet-instagram-video-intake.json
```

For `legendary-poet`, the command automatically binds the repository-owned historical identity floor and reviewed editorial corpus:

- `content/mappings/youtube-vk-reviewed-20260727.json`;
- `content/youtube-comments/*.json`.

The output validates against `InstagramVideoIntakeArtifact` and freezes:

- exact project/channel identity;
- exact source snapshot ID and generation time;
- SHA-256 of the source `AuditPackage` bytes;
- SHA-256 of the historical mapping bytes;
- deterministic SHA-256 of the ordered reviewed editorial corpus;
- current/new/historical-missing reconciliation;
- one record for every current upload;
- owner-backed source geometry/duration evidence when YouTube supplied `fileDetails`;
- explicit `short`, `longform`, `short_candidate`, or unresolved classification state.

### Surface-classification contract

The classifier is deliberately asymmetric: it confirms only what current exact evidence proves.

| Exact evidence | Result |
| --- | --- |
| source display geometry is landscape | confirmed `longform` |
| exact/fallback duration is over 180 seconds | confirmed `longform` |
| square/vertical, at most 180 seconds, and timezone-aware uploaded-file `creationTime` is on/after 2025-12-08 | confirmed `short` |
| square/vertical and at most 180 seconds, but conservative post-cutoff proof is absent | `unknown` + `youtube_short_candidate=true` |
| geometry/duration evidence is insufficient | `unknown` |

The 2025-12-08 boundary is intentionally conservative: it is the later three-minute-Shorts rollout boundary needed for Official Artist Channels. Using the later date avoids guessing whether the project channel has that special channel type. A source file created on or after that date cannot have been uploaded before the file existed.

`fileDetails.creationTime` is **file creation time, not upload time**. The classifier uses it only as a lower-bound proof when it is timezone-aware and falls after the conservative boundary. Date-only or timezone-naive values are not promoted into upload-time evidence.

`snippet.publishedAt` is also **not** treated as upload time.

YouTube stream `rotation` is applied before geometry is classified:

- `none` / missing / `upsideDown` preserve width and height;
- `clockwise` / `counterClockwise` swap display width and height;
- unknown rotation values fail closed to unknown geometry;
- conflicting orientations across reported video streams fail closed rather than picking one.

This classification describes the YouTube upload surface. It does **not** prove that the same bytes are locally available, rights-cleared, or appropriate as an Instagram source master.

Historical mappings or old prose audits may remain useful evidence, but they do not replace a fresh owner scan for current source-file classification.

## Stage 3 — exact local source-master evidence

Reuse the existing `MediaArtifactEvidence` implementation under `video_channel_manager.local_media`. A valid manifest binds one exact source identity to:

- acquisition provenance;
- authoritative final path;
- exact file SHA-256 and size;
- ffprobe-derived duration;
- container/codecs;
- video/audio stream counts;
- width and height;
- compatibility profile;
- self-validating manifest SHA-256.

A controlled project master may use `controlled_master` acquisition. A `yt_dlp` acquisition remains a provider-delivery copy and is never promoted to a clean master by the Instagram router.

Store reviewed manifests in an operator-owned directory outside tracked repository content, for example:

```text
data/reports/instagram-media-manifests/
```

The routing CLI loads every JSON manifest deterministically and rejects duplicate source IDs.

## Stage 4 — exact rights/provenance review

Technical media evidence is insufficient for reuse. Each media object that should progress past `hold` needs a versioned `InstagramMediaReview` record bound to the exact `media_manifest_sha256`.

Example shape:

```json
{
  "schema_name": "video-manager.instagram-media-review",
  "schema_version": 1,
  "project_key": "legendary-poet",
  "youtube_channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
  "youtube_video_id": "EXACT_VIDEO_ID",
  "media_manifest_sha256": "sha256:EXACT_64_HEX_DIGEST",
  "rights_status": "cleared",
  "master_provenance": "project_owned_clean_master",
  "reviewed_at": "2026-08-20T00:00:00+00:00",
  "reviewed_by": "human-reviewer",
  "editorial_rebuild_authorized": false,
  "note": "Exact review note"
}
```

Never manufacture `rights_status=cleared` from the fact that a file exists or was already published on YouTube/VK.

Accepted provenance vocabulary:

- `project_owned_clean_master`;
- `derived_from_project_owned_master`;
- `social_delivery_copy`;
- `unknown`.

## Stage 5 — deterministic batch routing

```powershell
video-manager instagram media-route `
  .\data\reports\legendary-poet-instagram-video-intake.json `
  --media-manifest-dir .\data\reports\instagram-media-manifests `
  --media-review-dir .\data\reports\instagram-media-reviews `
  --output .\data\reports\legendary-poet-instagram-media-route.json
```

The routing table is deterministic:

| Evidence state | Route |
| --- | --- |
| no exact `MediaArtifactEvidence` | `source_binding_required` |
| media exists, exact rights review absent | `hold` |
| `yt_dlp` / `social_delivery_copy` | `hold` unless a separate source-led rebuild is explicitly authorized |
| rights blocked | `hold` |
| rights unknown | `hold`, or `editorial_rebuild` only with separate rebuild authorization and reviewed editorial authority |
| cleared rights + clean project master + height > width | `direct_remaster` |
| cleared rights + clean project master + width >= height | `editorial_extract` |
| clean-master provenance not proved | `hold`, or separately authorized source-led rebuild |

`direct_remaster` means the local source-master geometry is already vertical enough to stay in the direct-master lane. It does not authorize publication and does not mean the file has passed a future Instagram-provider-specific encoding preflight.

`editorial_extract` means the exact project master can be used as source material, but a vertical editorial cut/reframe still must be produced and reviewed. The router does not invent timestamps.

`editorial_rebuild` means the blocked/unsuitable video bytes are not reused; a new Reel can be built only from separately reviewed source-led material.

## Versioned schemas

Export the machine-readable contracts with the normal schema command:

```powershell
video-manager schema export --output-dir .\schemas\generated
```

This lane exports:

- `instagram-youtube-video-intake-v1.schema.json`;
- `instagram-media-review-v1.schema.json`;
- `instagram-video-route-v1.schema.json`;
- `instagram-reel-factory-v1.schema.json`;
- `instagram-reel-queue-v1.schema.json`;
- `instagram-reel-factory-coverage-v1.schema.json`.

Unknown fields are rejected by the Pydantic exchange models rather than silently accepted.

## What this lane does not do

It does not:

- publish, edit or delete anything on Instagram/Meta;
- log into Meta;
- create tokens or secrets;
- download a social-platform copy as a convenience master;
- infer rights from prior publication;
- infer Shorts from duration, title, hashtags, or `publishedAt` alone;
- invent Reel cut points;
- choose a provider account from a public handle;
- turn YouTube `fileDetails` into local-master or rights proof;
- turn a route artifact into provider-write authorization.

The next execution layer, if separately reviewed and authorized later, must consume an exact reviewed Reel output, prove the Instagram Professional account ID, bind exact output bytes/SHA-256, run provider preflight, and verify postconditions after any write.
