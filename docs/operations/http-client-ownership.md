# HTTP client ownership inventory

Updated: 2026-10-22
Owner: Wave 3 / issue #69

This inventory is enforced by `tests/test_http_client_inventory.py` in both directions: the test fails when a constructor appears in a file this document does not record, and it fails when this document records a file whose constructor count no longer matches the code. A direct `httpx.Client()` constructor is allowed only when its lifecycle and operation semantics are recorded below, with a count. Reusable provider classes must use `HttpClientOwner`; they may own one persistent client or borrow an injected client, but may not construct a client per request.

The inventory is 27 reviewed constructors: 17 in `src/` across 12 modules and 10 in reviewed one-shot scripts. Until 2026-10-22 this document claimed that `src/` had no constructor outside `platforms/http.py` while the test silently allowed 16 more in 11 modules: the rule was not the rule the code obeyed, and nothing compared the two.

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
| `HttpxTelegramRichMutationProvider` | owned or borrowed persistent client | exact same-credential read plus ambiguous `sendRichMessage` mutation | Uses `HttpClientOwner`; one bounded `getMe` read binds the credential to the expected bot before at most one `HttpOperationClass.AMBIGUOUS_MUTATION` POST. Mutation retries are zero, and ambiguous failures never trigger retry or the legacy `sendMessage` fallback. |
| `SvodkaRichMediaProofReader` | owned or borrowed persistent client | two exact HTTPS media safe reads | Uses `HttpClientOwner` once for the bounded two-asset batch. Reads have explicit timeouts, no redirects or environment proxy inheritance, bounded safe-read retry, exact MIME/signature checks, and byte SHA-256 evidence; it has no Telegram credential or mutation method. |

The default limiter interval is zero. A nonzero VK interval must be explicitly configured or injected from a verified provider policy; the library does not invent a request-per-second value.

## Direct client constructors in `src/`

Every reusable module that constructs a client, with the operation class that constructor may carry. Reads may use
bounded retry; an ambiguous mutation gets zero transport retries and one attempt.

| Path | Count | Operation class | Reviewed lifecycle |
|---|---:|---|---|
| `src/video_channel_manager/platforms/http.py` | 1 | shared owned/borrowed factory | The only general-purpose constructor; everything reusable goes through it. |
| `src/video_channel_manager/cli/instagram_production.py` | 1 | safe reads (credential-free) | `with httpx.Client(...)` scope for hosted manifest media verification; no Instagram credentials and no Graph request. |
| `src/video_channel_manager/instagram/production.py` | 2 | safe reads plus ambiguous publish mutations | `InstagramProductionClient` owns an API client and a media client unless injected; `close()` closes only the ones it owns. |
| `src/video_channel_manager/platforms/vk/milovi_gap_thumbnail_evidence.py` | 1 | safe reads | `with httpx.Client(follow_redirects=True)` for bounded clip-frame evidence; the client is closed by the block. |
| `src/video_channel_manager/telegram_channel_discovery.py` | 1 | safe reads | Owned-or-borrowed client with bounded safe-read retries; only `getMe`, `getChat`, `getChatMember` are dispatched. |
| `src/video_channel_manager/telegram_custom_emoji_harvest.py` | 1 | safe reads | Bounded public-page harvest with `retries=2`, redirects disabled, closed only when owned. |
| `src/video_channel_manager/telegram_historical_media.py` | 1 | safe reads | `_build_acquisition_client()` builds one bounded acquisition client (redirects on, explicit timeouts) that the caller closes. |
| `src/video_channel_manager/telegram_multichannel_transport.py` | 4 | safe reads plus ambiguous mutations | Two preflight clients with bounded safe-read retries and two publisher clients with `MUTATION_TRANSPORT_RETRIES == 0`; each closes only when owned. |
| `src/video_channel_manager/telegram_multichannel_video.py` | 1 | ambiguous mutation | `sendVideo` client with `MUTATION_TRANSPORT_RETRIES == 0`, closed only when owned. |
| `src/video_channel_manager/telegram_research_public_permalink_probe.py` | 1 | safe reads | Bounded public-page recovery scan with `retries=2` and redirects disabled. |
| `src/video_channel_manager/telegram_research_update_probe.py` | 1 | safe reads | Probe client used only for `getWebhookInfo` and chat reads, closed only when owned. |
| `src/video_channel_manager/telegram_transport.py` | 2 | safe reads plus ambiguous mutations | Read-only preflight client with bounded retries and one publisher client with zero retries; `_api_call` classifies a lost mutation response as `may_exist` and non-retryable. |

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

1. A direct `httpx.Client()` constructor may appear only in a file listed in one of the inventory tables above, with exactly the recorded count; a new constructor, a moved constructor or an undocumented count fails CI.
2. Script constructor counts must exactly match this reviewed inventory; a new constructor fails CI.
3. Owned clients close exactly once. Borrowed clients are never closed by the borrower.
4. Retry authority is explicit through `HttpOperationClass`; HTTP method alone does not authorize replay.
5. Safe reads use bounded attempts and bounded delay. Ambiguous mutations use one attempt and must surface `retryable=False`, including transport loss, HTTP 429/5xx, and provider-transient errors.
6. Exceptions use safe provider/resource identifiers and never include tokens, authorization headers, upload URLs, or full sensitive payloads.
7. A nonzero provider limiter requires explicit configuration; zero remains the fail-neutral default when no verified numeric provider rule is available.
