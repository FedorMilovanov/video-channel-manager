# VK wall flood and Shorts presentation incident

Date: 2026-08-01
Project: `lord-god-strength`
Community: `60805374`
Owner ID: `-60805374`

## Owner report

The owner reports two separate unwanted outcomes:

1. a previous YouTube → VK transfer produced many one-video wall posts instead of building a gradual postponed publication queue;
2. directly uploaded YouTube Shorts look and behave differently from copied/imported YouTube videos, including clip-style playback when opening the wall.

These are related to platform surfaces but must be investigated separately.

## Finding 1: catalog upload and wall publication were not kept visibly separate

VK exposes independent controls and methods:

- `video.save.wallpost` controls whether a saved video is posted to the wall;
- `video.save.auto_publish` is a separate publication flag;
- `wall.post` is the explicit wall-writing method;
- `wall.post.publish_date` creates a postponed post;
- `wall.post.guid` supports duplicate prevention.

Therefore a video transfer must never rely on omitted/default publication parameters. Upload and wall publication are two separate reviewed operations.

### Historical audit evidence

The independent 2026-07-29 wall audit recorded:

- `published_wall_posts=3133`;
- `published_videos=1200`;
- `unposted_videos=2082`;
- `postponed_wall_posts=0`;
- `duplicate_post_references=104`.

This proves that the historical wall was not being managed as a gradual postponed queue. It does not, by itself, identify which historical tool created each post.

The later protected transfer transcripts explicitly printed `Wallpost: отключён` for both:

- the reviewed 26-item long-form transfer;
- the Shorts transfer packages.

Do not attribute the complete historical wall flood to those later packages without inspecting the exact executor bytes and live post timestamps.

## Finding 2: external imports, native videos, and native clips are different

### External YouTube import

Calling `video.save` with `link=<external URL>` creates an external embedded-video route. The resulting player and metadata are not equivalent to a VK-hosted upload.

### Native VK upload

Calling `video.save` without `link`, then uploading the MP4 to the returned `upload_url`, creates a VK-hosted object. VK processes and converts the file before the final object becomes stable.

### Native VK Clip

VK video objects expose a separate `type=short_video`. Official VK/RuStore guidance states that vertical 9:16 or square 1:1 videos up to 60 seconds can be automatically published as clips and that the appropriate clip or regular-video player is chosen automatically.

That explains the different visual card/player and clip-feed-style immediate playback. It is not merely an altered thumbnail.

`repeat=1` controls looping. It is not sufficient to explain initial autoplay or the use of the clip player.

## Project evidence from the Shorts transfer

The protected Shorts workflow:

- disabled wall posts;
- classified all 108 canonical YouTube Shorts;
- uploaded native files through `video.save` only after a canary;
- required the canary to become `type=short_video` before continuing;
- stored exact VK IDs in a separate ledger.

Last reviewed reconciliation state for 64 accepted native Shorts:

- confirmed `short_video`: `44`;
- still processing: `6`;
- accepted but not yet visible through exact-object reconciliation: `14`;
- wrong completed type: `0`.

Some objects temporarily appeared as ordinary `video` during conversion. Final type must be checked only after processing finishes.

## Required upload modes

### Mode A: native VK Clip

Use when clip-feed behavior is desired.

- upload the source MP4, not an external YouTube embed;
- use a separate Shorts manifest and ledger;
- explicitly send `wallpost=0`, `auto_publish=0`, and `repeat=0`;
- upload one canary first;
- wait for processing to finish;
- require exact object `type=short_video`;
- do not share the clip to the wall automatically.

### Mode B: ordinary VK Video

Use when a regular video card/player is desired.

- upload through the regular VK Video surface when operating manually;
- API upload still requires a canary because the public `video.save` schema does not expose a documented force-ordinary/force-clip parameter;
- use a horizontal 16:9 master/canvas when editorially acceptable to reduce automatic clip classification risk;
- explicitly send `wallpost=0`, `auto_publish=0`, and `repeat=0`;
- after conversion require exact object `type=video`;
- keep wall publication separate.

The 16:9 master recommendation is an engineering safeguard, not a documented guarantee from the public API.

### Mode C: external YouTube embed

Use only when the intended result is an external player.

- call `video.save(link=...)`;
- do not treat the result as equivalent to a native VK Clip or native VK Video;
- do not use it when native VK processing, clip distribution, or stable VK-hosted playback is required.

## Mandatory wall-safety policy

All future upload executors must:

1. include `wall_mutation_authorized=false` in the immutable manifest;
2. send explicit `wallpost=0`, `auto_publish=0`, and `repeat=0`;
3. snapshot published and postponed wall posts before upload;
4. perform upload only;
5. re-read the wall after upload;
6. fail the run if any unexpected post appeared;
7. never call `wall.post` from an upload executor.

Wall publication must use a separate postponed plan containing:

- `project_key=lord-god-strength`;
- community `60805374` and owner `-60805374`;
- exact video attachment;
- exact `publish_date` and human-readable `publish_at`;
- deterministic `guid`;
- duplicate scan across published and postponed posts;
- dry-run, lock, repeated preflight, and postflight.

Immediate wall publication is prohibited by default.

## Existing wall remediation

Do not bulk-delete the historical wall.

First build a fresh read-only classification with exact post IDs:

- intentional editorial/historical posts;
- auto-generated one-video transfer posts;
- duplicate video references;
- posts with comments, likes, reposts, or meaningful views;
- safe removal candidates;
- posts whose origin is unknown.

Deletion, if approved later, requires a separate immutable plan, engagement guards, exact confirmations, durable result journal, and postflight.

## Tracking

- Issue #32 — reconcile the real VK Clips surface and final Shorts types.
- Issue #36 — block upload-triggered wall mutations and require postponed publishing.

## Primary technical references

- VK API schema repository: https://github.com/VKCOM/vk-api-schema
- Video methods schema: https://raw.githubusercontent.com/VKCOM/vk-api-schema/master/video/methods.json
- Video objects schema: https://raw.githubusercontent.com/VKCOM/vk-api-schema/master/video/objects.json
- Video responses schema: https://raw.githubusercontent.com/VKCOM/vk-api-schema/master/video/responses.json
- Wall methods schema: https://raw.githubusercontent.com/VKCOM/vk-api-schema/master/wall/methods.json
- VK PHP SDK video-upload example: https://github.com/VKCOM/vk-php-sdk
- VK Java SDK: https://github.com/VKCOM/vk-java-sdk
- VK iOS SDK: https://github.com/VKCOM/vk-ios-sdk
- VK Clips application: https://play.google.com/store/apps/details?id=com.vk.clips
- VK Video application: https://play.google.com/store/apps/details?id=com.vk.vkvideo
- RuStore VK Video player and clip-classification guidance: https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication
