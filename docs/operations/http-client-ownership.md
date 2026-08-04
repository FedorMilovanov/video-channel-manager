# HTTP client ownership inventory

Updated: 2026-08-04  
Owner: Wave 3 / issue #69

This inventory is enforced by `tests/test_http_client_inventory.py`. A direct `httpx.Client()` constructor is allowed only when its lifecycle and operation semantics are recorded here. Reusable provider classes must use `HttpClientOwner`; they may own one persistent client or borrow an injected client, but may not construct a client per request.

## Reusable library paths

| Path | Ownership | Operation class | Decision |
|---|---|---|---|
| `src/video_channel_manager/platforms/http.py` | central owned/borrowed factory | shared | The only direct constructor allowed under `src/`. |
| `YouTubeApiClient` | owned or borrowed persistent client | safe reads | Uses bounded safe-read retry and caches the uploads playlist ID per client lifecycle. |
| `YouTubeCommentWriter` | owned or borrowed persistent client | safe reads plus ambiguous mutations | Migrated from per-request construction. Reads may retry; comment create/update never replay after an ambiguous response. |
| `YouTubeDescriptionWriter` | owned or borrowed persistent client | safe reads plus ambiguous mutations | Reads may retry; `videos.update` remains one attempt and is followed only by read verification. |
| `InstalledOAuthFlow` | owned or borrowed persistent client | ambiguous credential mutations | Authorization-code exchange and refresh are single-attempt operations. Lost responses are not replayed; errors use safe resource names and redact credential material. |
| `VkApiClient` | owned or borrowed persistent client | safe reads | Uses shared retry classification and an injectable limiter. |
| `VkVideoWriter` | owned or borrowed persistent client | explicit safe-read verification plus ambiguous mutations | `retry_transient=True` is limited to read verification; reservation, upload, album, and other writes remain one attempt and surface `retryable=False`. |
| `VkThumbnailWriter` | owned or borrowed persistent client | safe upload-URL reservation plus ambiguous mutations | `video.getThumbUploadUrl` may use bounded retry; upload-server POST and `video.saveUploadedThumb` are single attempt, surface `retryable=False`, and never expose the opaque upload URL in errors. |

The default limiter interval is zero. A nonzero VK interval must be explicitly configured or injected from a verified provider policy; the library does not invent a request-per-second value.

## Reviewed one-shot script constructors

These scripts are historical or bounded operator entrypoints rather than reusable provider clients. Their constructors remain allowlisted only for the exact reviewed purpose below.

| Path | Count | Reviewed lifecycle and reason |
|---|---:|---|
| `scripts/complete_vk_longform_tail.py` | 1 | `thumbnail_candidates()` owns one client for the bounded thumbnail-candidate loop, then closes it. Read-only. |
| `scripts/lord_god_article_wave_v3/mutations.py` | 1 | `upload_photo_bytes()` owns one client for one ephemeral upload-server mutation and closes it. Ambiguous outcome is not retried. |
| `scripts/run_vk_wall_wave.py` | 1 | `_verify_required_urls()` owns one client for one bounded URL-verification batch. Read-only. |
| `scripts/schedule_lord_god_article_wave.py` | 1 | `verify_live_sources()` owns one client for one bounded article/image verification batch. Read-only. |
| `scripts/schedule_lord_god_article_wave_current.py` | 3 | One bounded read-only image-verification client, one bounded image-download client, and one single-attempt ephemeral wall-photo upload client. |
| `scripts/sync_youtube_thumbnails_to_vk.py` | 1 | Legacy thumbnail downloader creates one client per bounded retry attempt. It is not a provider writer; future retirement/consolidation belongs to Wave 6. |
| `scripts/vk_shorts_reset.py` | 2 | Historical gateway uses one single-attempt client for each explicitly unknown-outcome API mutation/read and one single-attempt upload-server client. This executor remains governed/retired and must not be reactivated casually. |

## Enforcement rules

1. No direct `httpx.Client()` constructor may appear in reusable `src/` code outside `platforms/http.py`.
2. Script constructor counts must exactly match this reviewed inventory; a new constructor fails CI.
3. Owned clients close exactly once. Borrowed clients are never closed by the borrower.
4. Retry authority is explicit through `HttpOperationClass`; HTTP method alone does not authorize replay.
5. Safe reads use bounded attempts and bounded delay. Ambiguous mutations use one attempt and must surface `retryable=False`, including transport loss, HTTP 429/5xx, and provider-transient errors.
6. Exceptions use safe provider/resource identifiers and never include tokens, authorization headers, upload URLs, or full sensitive payloads.
7. A nonzero provider limiter requires explicit configuration; zero remains the fail-neutral default when no verified numeric provider rule is available.
