# Instagram video intake and media routing

Status: provider-inert  
Owner issue: #495  
Scope: repository-owned preparation only; no Instagram/Meta provider mutation

This runbook is the canonical operator path for turning an exact YouTube inventory into an Instagram/Reels production-routing artifact. It deliberately separates provider inventory, source-master evidence, rights/provenance review, and publication authorization.

## Invariants

1. YouTube inventory is acquired only through the existing read-only YouTube adapter.
2. `project_key` is resolved against the canonical repository identity registry; a display name or vanity handle is never a target identity.
3. Duration alone never proves that a YouTube video is a Short.
4. `MediaArtifactEvidence` is the only technical media-evidence contract used by this lane. Do not create an Instagram-specific second ffprobe registry.
5. A YouTube/VK/social delivery encoding is not a clean source master merely because it is downloadable.
6. Technical compatibility does not prove reuse rights. Rights/provenance review is a separate exact-manifest record.
7. Every generated intake/route artifact is provider-inert and carries `provider_writes_authorized=false`.
8. No Reel cut timing is frozen until exact source bytes are bound.

## Stage 1 — fresh read-only YouTube snapshot

Use the exact canonical channel ID, not only the local account alias:

```powershell
video-manager youtube scan `
  --account legendary-poet `
  --channel UC-78ys2S3cQ3lpqgXfo-SvQ `
  --output .\data\exports\legendary-poet-youtube-current.json
```

The resulting `AuditPackage` is a read-only provider snapshot. Keep its exact bytes unchanged after review; the intake command hashes the actual input bytes.

## Stage 2 — typed Instagram intake

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
- one record for every current upload.

V1 deliberately emits `youtube_format_status=unknown` for every current upload. That is not missing work: it is a fail-closed statement that the YouTube Data API metadata used by the snapshot does not itself prove Shorts-surface membership or clean-master geometry.

## Stage 3 — exact media evidence

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

`direct_remaster` means the source geometry is already vertical enough to stay in the direct-master lane. It does not authorize publication and does not mean the file has passed a future Instagram-provider-specific encoding preflight.

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
- `instagram-video-route-v1.schema.json`.

Unknown fields are rejected by the Pydantic exchange models rather than silently accepted.

## What this lane does not do

It does not:

- publish, edit or delete anything on Instagram/Meta;
- log into Meta;
- create tokens or secrets;
- download a social-platform copy as a convenience master;
- infer rights from prior publication;
- infer Shorts from duration;
- invent Reel cut points;
- choose a provider account from a public handle;
- turn a route artifact into provider-write authorization.

The next execution layer, if separately reviewed and authorized later, must consume an exact reviewed Reel output, prove the Instagram Professional account ID, bind exact output bytes/SHA-256, run provider preflight, and verify postconditions after any write.
