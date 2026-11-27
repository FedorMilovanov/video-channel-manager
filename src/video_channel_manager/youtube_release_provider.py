from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpFailureKind,
    HttpOperationClass,
    HttpTransportFailure,
    RequestRateLimiter,
    RetryPolicy,
    execute_http_request,
    redact_sensitive_text,
)
from video_channel_manager.platforms.youtube.client import _parse_duration
from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow, YOUTUBE_FORCE_SSL_SCOPE
from video_channel_manager.platforms.youtube.store import (
    ProjectQuotaGuard,
    TokenStore,
    YouTubeQuotaBlocked,
    reserve_shared_quota,
)
from video_channel_manager.youtube_provider_semantics import (
    canonical_srt_sha256,
    exact_caption_inventory,
    manual_caption_ids,
    playlist_item_video_id,
    validate_caption_identity,
)
from video_channel_manager.youtube_release_state import ProviderEffect
from video_channel_manager.youtube_upload_plan import canonical_sha256

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_UPLOAD_API_BASE_URL = "https://www.googleapis.com/upload/youtube/v3"
_ALLOWED_SESSION_HOSTS = frozenset({"www.googleapis.com", "youtube.googleapis.com"})
_RANGE_RE = re.compile(r"^bytes=0-(?P<last>\d+)$")


class YouTubeReleaseProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseProviderResult:
    provider_effect: ProviderEffect
    remote_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)


def _json_digest(payload: object) -> str:
    return canonical_sha256(payload)


def _dict_items(payload: dict[str, Any], key: str = "items") -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def playlist_rename_target(before: dict[str, Any], new_title: str) -> dict[str, Any]:
    """Change the primary name and its exact default-language mirror, nothing else."""
    if not new_title.strip():
        raise ValueError("Playlist title cannot be blank.")
    after = copy.deepcopy(before)
    snippet = after["snippet"]
    old_title = snippet["title"]
    snippet["title"] = new_title
    primary = after["localizations"].get(snippet.get("defaultLanguage"))
    if primary is not None and primary["title"] == old_title:
        primary["title"] = new_title
    return after


def _session_url_sha256(url: str) -> str:
    return "sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest()


def _validate_session_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_SESSION_HOSTS:
        raise YouTubeReleaseProviderError(
            "Stored resumable upload session URL is outside the allowed Google API host set."
        )
    if "/upload/youtube/v3/videos" not in parsed.path:
        raise YouTubeReleaseProviderError("Stored resumable upload session URL has an unexpected path.")
    return url


def _range_next_offset(value: str | None, *, total_bytes: int) -> int | None:
    if value is None or not value.strip():
        return 0
    match = _RANGE_RE.fullmatch(value.strip())
    if match is None:
        return None
    next_offset = int(match.group("last")) + 1
    if not 0 <= next_offset <= total_bytes:
        return None
    return next_offset


def _file_chunks(path: Path, *, offset: int, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
    with path.open("rb") as handle:
        handle.seek(offset)
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                return
            yield chunk


class YouTubeReleaseProvider(HttpClientOwner):
    """Repository-owned YouTube release transport with zero blind mutation retries."""

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        upload_api_base_url: str = _UPLOAD_API_BASE_URL,
        retry_policy: RetryPolicy | None = None,
        request_limiter: RequestRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.client_config = client_config
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self._quota_guard = ProjectQuotaGuard.for_client(
            getattr(token_store, "data_dir", None), client_config.client_id, self.account_alias
        )
        self._initialize_http_client(http_client, timeout=90.0, follow_redirects=True)
        self.api_base_url = api_base_url.rstrip("/")
        self.upload_api_base_url = upload_api_base_url.rstrip("/")
        self.retry_policy = retry_policy or RetryPolicy()
        self.request_limiter = request_limiter or RequestRateLimiter()
        self._sleep = sleep
        self._jitter = jitter

    def _token(self, *, require_write: bool) -> OAuthToken:
        token = self.token_store.load_token(self.account_alias)
        if token.needs_refresh():
            token = InstalledOAuthFlow(self.client_config, http_client=self._http_client).refresh(token)
            self.token_store.save_token(self.account_alias, token)
        if require_write and YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
            raise YouTubeReleaseProviderError(
                "Stored YouTube token is read-only; re-authorize the exact account with --write --force."
            )
        return token

    def _safe_request(
        self,
        method: str,
        url: str,
        *,
        resource: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        token = self._token(require_write=False)
        request_headers = {"Authorization": f"Bearer {token.access_token}"}
        request_headers.update(headers or {})
        try:
            result = execute_http_request(
                lambda: self._http_client.request(
                    method,
                    url,
                    params=httpx.QueryParams(params) if params else None,
                    headers=request_headers,
                ),
                provider="YouTube",
                attempt_guard=self._quota_guard,
                operation=HttpOperationClass.SAFE_READ,
                method=method,
                resource=resource,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except (HttpTransportFailure, YouTubeQuotaBlocked) as exc:
            raise YouTubeReleaseProviderError(str(exc)) from exc
        response = result.response
        if response.status_code >= 400:
            safe = redact_sensitive_text(response.text, secrets=(token.access_token,))
            raise YouTubeReleaseProviderError(
                f"YouTube safe read {resource} returned HTTP {response.status_code}: {safe}"
            )
        return response

    def _mutation_request(
        self,
        method: str,
        url: str,
        *,
        resource: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        content: Any = None,
    ) -> tuple[httpx.Response | None, ReleaseProviderResult | None]:
        token = self._token(require_write=True)
        request_headers = {"Authorization": f"Bearer {token.access_token}"}
        request_headers.update(headers or {})
        try:
            result = execute_http_request(
                lambda: self._http_client.request(
                    method,
                    url,
                    params=httpx.QueryParams(params) if params else None,
                    headers=request_headers,
                    json=json_body,
                    content=content,
                ),
                provider="YouTube",
                attempt_guard=self._quota_guard,
                operation=HttpOperationClass.AMBIGUOUS_MUTATION,
                method=method,
                resource=resource,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except YouTubeQuotaBlocked as exc:
            return None, ReleaseProviderResult(provider_effect="confirmed_absent", evidence={"quota_blocked": str(exc)})
        except HttpTransportFailure as exc:
            known_no_dispatch = exc.cause_type in {
                "ConnectError",
                "ConnectTimeout",
                "PoolTimeout",
            }
            effect: ProviderEffect = "confirmed_absent" if known_no_dispatch else "may_exist"
            return None, ReleaseProviderResult(
                provider_effect=effect,
                evidence={
                    "transport_failure": exc.cause_type,
                    "attempts": exc.attempts,
                    "known_no_dispatch": known_no_dispatch,
                },
            )

        response = result.response
        status = response.status_code
        if status >= 500 or status in {408, 429}:
            return None, ReleaseProviderResult(
                provider_effect="may_exist",
                evidence={
                    "http_status": status,
                    "failure_kind": (result.failure_kind or HttpFailureKind.TRANSIENT_HTTP).value,
                },
            )
        if status >= 400:
            safe = redact_sensitive_text(response.text, secrets=(token.access_token,))
            return None, ReleaseProviderResult(
                provider_effect="confirmed_absent",
                evidence={"http_status": status, "error": safe},
            )
        return response, None

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def read_video(self, video_id: str) -> dict[str, Any]:
        response = self._safe_request(
            "GET",
            f"{self.api_base_url}/videos",
            resource="videos.read-exact",
            params={
                "part": "snippet,contentDetails,status,processingDetails",
                "id": video_id,
                "maxResults": 1,
            },
        )
        payload = self._json_object(response)
        items = _dict_items(payload or {})
        if len(items) != 1 or str(items[0].get("id") or "") != video_id:
            raise YouTubeReleaseProviderError(f"Video not found or inaccessible: {video_id}")
        return items[0]

    def read_caption_inventory(self, video_id: str) -> dict[str, Any]:
        response = self._safe_request(
            "GET",
            f"{self.api_base_url}/captions",
            resource="captions.list",
            params={"part": "snippet", "videoId": video_id},
        )
        try:
            return exact_caption_inventory(self._json_object(response) or {}, video_id)
        except ValueError as exc:
            raise YouTubeReleaseProviderError(str(exc)) from exc

    def download_caption_srt(self, caption_id: str) -> bytes:
        """Download the selected track in its own language; do not request translation."""
        if not caption_id.strip() or caption_id != caption_id.strip():
            raise ValueError("Exact nonblank caption ID is required.")
        response = self._safe_request(
            "GET",
            f"{self.api_base_url}/captions/{quote(caption_id, safe='')}",
            resource="captions.download",
            params={"tfmt": "srt"},
        )
        try:
            text = response.content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise YouTubeReleaseProviderError("Caption download is not UTF-8 SRT.") from exc
        # Reject empty or non-SRT success bodies (for example JSON/HTML errors).
        # Preserve provider bytes; this is format admission, not editorial QA.
        if not re.match(r"^\s*1[ \t]*\r?\n\d{2,}:\d{2}:\d{2},\d{3}[ \t]+-->[ \t]+", text):
            raise YouTubeReleaseProviderError("Caption download has no initial SRT cue.")
        return response.content

    def verified_caption_id(
        self,
        tracks: dict[str, Any],
        *,
        language: str,
        name: str,
        srt_sha256: str,
        expected_id: str | None = None,
    ) -> str | None:
        ids = manual_caption_ids(tracks, language, name)
        if len(ids) != 1 or (expected_id is not None and ids[0] != expected_id):
            return None
        track_id = ids[0]
        snippet = tracks[track_id]
        if snippet.get("status") != "serving" or snippet.get("isDraft") is not False:
            return None
        if snippet.get("trackKind") != "standard":
            return None
        return track_id if canonical_srt_sha256(self.download_caption_srt(track_id)) == srt_sha256 else None

    def insert_caption_srt(
        self,
        *,
        video_id: str,
        channel_id: str,
        language: str,
        name: str,
        srt: bytes,
        expected_before: dict[str, Any],
        before_dispatch: Callable[[], None],
    ) -> ReleaseProviderResult:
        """Insert one reviewed manual SRT; only exact serving-content readback proves completion."""
        validate_caption_identity(language, name)
        if len(srt) > 100_000_000:
            raise ValueError("Caption exceeds the provider's 100 MB size limit.")
        with reserve_shared_quota(
            self._quota_guard, 400 + 301 * self.retry_policy.max_attempts, YouTubeReleaseProviderError
        ):
            video = self.read_video(video_id)
            if (video.get("snippet") or {}).get("channelId") != channel_id:
                raise YouTubeReleaseProviderError("Video owner changed; no caption POST sent.")
            duration = _parse_duration((video.get("contentDetails") or {}).get("duration"))
            if not duration:
                raise ValueError("Exact video duration is required for SRT admission.")
            digest = canonical_srt_sha256(srt, duration_seconds=duration)
            before = self.read_caption_inventory(video_id)
            if before != expected_before or manual_caption_ids(before, language, name):
                raise YouTubeReleaseProviderError("Caption inventory changed or track already exists; no POST sent.")
            self._token(require_write=True)
            metadata = json.dumps(
                {"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}},
                ensure_ascii=False,
            ).encode("utf-8")
            boundary = "vcm-" + uuid.uuid4().hex
            marker = ("--" + boundary).encode("ascii")
            body = (
                marker
                + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                + metadata
                + b"\r\n"
                + marker
                + b"\r\nContent-Type: application/octet-stream\r\n\r\n"
                + srt
                + b"\r\n"
                + marker
                + b"--\r\n"
            )
            before_dispatch()
            response, failure = self._mutation_request(
                "POST",
                f"{self.upload_api_base_url}/captions",
                resource="captions.insert",
                params={"part": "snippet", "uploadType": "multipart"},
                headers={"Content-Type": f"multipart/related; boundary={boundary}"},
                content=body,
            )
            # A conflict establishes an existing identity, not absence of a track.
            # Reconcile it by GET; do not make a new insert eligible automatically.
            if (
                failure is not None
                and failure.provider_effect != "may_exist"
                and failure.evidence.get("http_status") != 409
            ):
                return failure
            evidence = dict(failure.evidence) if failure is not None else {}
            remote_id = (self._json_object(response) or {}).get("id") if response is not None else None
            if not isinstance(remote_id, str) or not remote_id:
                remote_id = None
            try:
                after = self.read_caption_inventory(video_id)
                verified = (
                    self.verified_caption_id(
                        after, language=language, name=name, srt_sha256=digest, expected_id=remote_id
                    )
                    if set(before) <= set(after)
                    else None
                )
            except (ValueError, YouTubeReleaseProviderError) as exc:
                evidence["readback_error"] = str(exc)
                verified = None
            if verified is None:
                evidence["reason"] = "Exact serving caption content not yet verified"
                return ReleaseProviderResult(provider_effect="may_exist", remote_id=remote_id, evidence=evidence)
            evidence["srt_sha256"] = digest
            return ReleaseProviderResult(provider_effect="verified", remote_id=verified, evidence=evidence)

    def read_playlist_metadata(self, playlist_id: str, *, channel_id: str) -> dict[str, Any]:
        response = self._safe_request(
            "GET",
            f"{self.api_base_url}/playlists",
            resource="playlists",
            params={"part": "snippet,status,localizations", "id": playlist_id, "maxResults": 1},
        )
        items = _dict_items(self._json_object(response) or {})
        if len(items) != 1 or items[0].get("id") != playlist_id:
            raise YouTubeReleaseProviderError("Playlist not found or inaccessible.")
        raw = items[0]
        snippet = raw.get("snippet")
        status = raw.get("status")
        locales = raw.get("localizations", {})
        if (
            not isinstance(snippet, dict)
            or snippet.get("channelId") != channel_id
            or not isinstance(snippet.get("title"), str)
            or not snippet["title"]
            or not isinstance(snippet.get("description"), str)
            or not isinstance(status, dict)
            or status.get("privacyStatus") not in {"public", "private", "unlisted"}
            or not isinstance(locales, dict)
        ):
            raise YouTubeReleaseProviderError("Playlist owner or metadata is incomplete.")
        fields = {key: snippet[key] for key in ("channelId", "title", "description")}
        if "defaultLanguage" in snippet:
            language = snippet["defaultLanguage"]
            if not isinstance(language, str) or not language:
                raise YouTubeReleaseProviderError("Invalid playlist default language.")
            fields["defaultLanguage"] = language
        # Playlist snippet.tags is deprecated, not an updateable property.
        # Compare only supported metadata; never echo legacy tags into a PUT.
        if locales and not fields.get("defaultLanguage"):
            raise YouTubeReleaseProviderError("Cannot preserve playlist localizations without default language.")
        for language, locale in locales.items():
            if (
                not isinstance(language, str)
                or not language
                or not isinstance(locale, dict)
                or not isinstance(locale.get("title"), str)
                or not isinstance(locale.get("description"), str)
            ):
                raise YouTubeReleaseProviderError("Incomplete playlist localization.")
        return {"id": playlist_id, "snippet": fields, "status": status, "localizations": locales}

    def rename_playlist(
        self,
        *,
        playlist_id: str,
        channel_id: str,
        expected_before: dict[str, Any],
        new_title: str,
        before_dispatch: Callable[[], None],
    ) -> ReleaseProviderResult:
        """One official playlist metadata PUT, with preservation and independent readback."""
        with reserve_shared_quota(
            self._quota_guard, 50 + 2 * self.retry_policy.max_attempts, YouTubeReleaseProviderError
        ):
            current = self.read_playlist_metadata(playlist_id, channel_id=channel_id)
            if current != expected_before:
                raise YouTubeReleaseProviderError("Playlist metadata drifted; no PUT sent.")
            after = playlist_rename_target(current, new_title)
            if current == after:
                return ReleaseProviderResult(provider_effect="verified", remote_id=playlist_id)
            self._token(require_write=True)
            snippet = {key: value for key, value in after["snippet"].items() if key != "channelId"}
            body = {"id": playlist_id, "snippet": snippet}
            # The primary-language mirror is maintained by YouTube when snippet
            # changes. Do not rewrite the localization map for a title-only edit.
            before_dispatch()
            response, failure = self._mutation_request(
                "PUT",
                f"{self.api_base_url}/playlists",
                resource="playlists.update",
                params={"part": "snippet"},
                json_body=body,
            )
            if failure is not None and failure.provider_effect != "may_exist":
                return failure
            if failure is None:
                if response is None:
                    raise AssertionError("mutation request returned neither response nor failure")
                payload = self._json_object(response)
                if (payload or {}).get("id") != playlist_id:
                    return ReleaseProviderResult(
                        provider_effect="may_exist", evidence={"reason": "Unexpected playlists.update response ID"}
                    )
            # A timeout may follow a committed update. Use the already reserved
            # independent GET; never send a second PUT or infer absence.
            evidence = dict(failure.evidence) if failure is not None else {}
            try:
                verified = self.read_playlist_metadata(playlist_id, channel_id=channel_id)
            except YouTubeReleaseProviderError as exc:
                evidence["readback_error"] = str(exc)
                return ReleaseProviderResult(provider_effect="may_exist", evidence=evidence)
            if verified != after:
                evidence["reason"] = "Playlist readback differs from requested state"
                return ReleaseProviderResult(provider_effect="may_exist", evidence=evidence)
            evidence["readback_sha256"] = _json_digest(verified)
            return ReleaseProviderResult(provider_effect="verified", remote_id=playlist_id, evidence=evidence)

    def list_playlist_items(self, playlist_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {
                "part": "id,snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            response = self._safe_request(
                "GET",
                f"{self.api_base_url}/playlistItems",
                resource="playlistItems.list",
                params=params,
            )
            payload = self._json_object(response)
            if payload is None:
                raise YouTubeReleaseProviderError("YouTube playlistItems.list returned invalid JSON.")
            records.extend(_dict_items(payload))
            next_token = str(payload.get("nextPageToken") or "").strip()
            if not next_token:
                return records
            page_token = next_token

    def playlist_contains_video(self, playlist_id: str, video_id: str) -> bool:
        return any(playlist_item_video_id(item) == video_id for item in self.list_playlist_items(playlist_id))

    def start_upload_session(
        self,
        *,
        snippet: dict[str, Any],
        status: dict[str, Any],
        media_size_bytes: int,
        media_mime_type: str,
    ) -> ReleaseProviderResult:
        response, failure = self._mutation_request(
            "POST",
            f"{self.upload_api_base_url}/videos",
            resource="videos.insert.resumable-session",
            params={
                "uploadType": "resumable",
                "part": "snippet,status",
                "notifySubscribers": "false",
            },
            headers={
                "X-Upload-Content-Length": str(media_size_bytes),
                "X-Upload-Content-Type": media_mime_type,
                "Content-Type": "application/json; charset=UTF-8",
            },
            json_body={"snippet": snippet, "status": status},
        )
        if failure is not None:
            return failure
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        session_url = response.headers.get("Location", "").strip()
        if not session_url:
            return ReleaseProviderResult(
                provider_effect="may_exist",
                evidence={
                    "http_status": response.status_code,
                    "reason": "resumable session response omitted Location",
                },
            )
        try:
            _validate_session_url(session_url)
        except YouTubeReleaseProviderError as exc:
            return ReleaseProviderResult(
                provider_effect="may_exist",
                evidence={"http_status": response.status_code, "reason": str(exc)},
            )
        session_sha = _session_url_sha256(session_url)
        return ReleaseProviderResult(
            provider_effect="verified",
            evidence={"http_status": response.status_code, "session_url_sha256": session_sha},
            runtime={"session_url": session_url, "session_url_sha256": session_sha},
        )

    def upload_media(
        self,
        *,
        session_url: str,
        media_path: Path,
        media_size_bytes: int,
        media_mime_type: str,
        offset: int,
    ) -> ReleaseProviderResult:
        _validate_session_url(session_url)
        if not 0 <= offset < media_size_bytes:
            raise YouTubeReleaseProviderError("Upload offset is outside the immutable media range.")
        remaining = media_size_bytes - offset
        media_headers = {
            "Content-Length": str(remaining),
            "Content-Type": media_mime_type,
        }
        # Google's full-file PUT must preserve the exact upload session URL and
        # must not send Content-Range. Partial resumes require Content-Range.
        if offset:
            media_headers["Content-Range"] = f"bytes {offset}-{media_size_bytes - 1}/{media_size_bytes}"
        response, failure = self._mutation_request(
            "PUT",
            session_url,
            resource="videos.insert.resumable-media",
            headers=media_headers,
            content=_file_chunks(media_path, offset=offset),
        )
        if failure is not None:
            runtime = dict(failure.runtime)
            runtime["resume_requires_status_query"] = True
            return ReleaseProviderResult(
                provider_effect=failure.provider_effect,
                remote_id=failure.remote_id,
                evidence=failure.evidence,
                runtime=runtime,
            )
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        if response.status_code == 308:
            next_offset = _range_next_offset(
                response.headers.get("Range"),
                total_bytes=media_size_bytes,
            )
            if next_offset is None:
                return ReleaseProviderResult(
                    provider_effect="may_exist",
                    evidence={"http_status": 308, "reason": "invalid resumable Range header"},
                    runtime={"resume_requires_status_query": True},
                )
            return ReleaseProviderResult(
                provider_effect="confirmed_absent",
                evidence={
                    "http_status": 308,
                    "range": response.headers.get("Range"),
                    "final_video_absent": True,
                },
                runtime={"next_offset": next_offset, "resume_requires_status_query": False},
            )
        payload = self._json_object(response)
        video_id = str((payload or {}).get("id") or "").strip()
        if response.status_code in {200, 201} and video_id:
            return ReleaseProviderResult(
                provider_effect="verified",
                remote_id=video_id,
                evidence={
                    "http_status": response.status_code,
                    "provider_payload_sha256": _json_digest(payload),
                },
                runtime={
                    "next_offset": media_size_bytes,
                    "resume_requires_status_query": False,
                },
            )
        return ReleaseProviderResult(
            provider_effect="may_exist",
            evidence={
                "http_status": response.status_code,
                "reason": "upload completion response lacked exact video ID",
            },
            runtime={"resume_requires_status_query": True},
        )

    def query_upload_status(
        self,
        *,
        session_url: str,
        media_size_bytes: int,
    ) -> ReleaseProviderResult:
        _validate_session_url(session_url)
        token = self._token(require_write=True)
        try:
            result = execute_http_request(
                lambda: self._http_client.put(
                    session_url,
                    headers={
                        "Authorization": f"Bearer {token.access_token}",
                        "Content-Length": "0",
                        "Content-Range": f"bytes */{media_size_bytes}",
                    },
                    content=b"",
                ),
                provider="YouTube",
                attempt_guard=self._quota_guard,
                operation=HttpOperationClass.SAFE_READ,
                method="PUT",
                resource="videos.insert.resumable-status",
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except YouTubeQuotaBlocked as exc:
            return ReleaseProviderResult(provider_effect="may_exist", evidence={"status_query_quota_blocked": str(exc)})
        except HttpTransportFailure as exc:
            return ReleaseProviderResult(
                provider_effect="may_exist",
                evidence={
                    "status_query_transport_failure": exc.cause_type,
                    "attempts": exc.attempts,
                },
            )
        response = result.response
        if response.status_code == 308:
            next_offset = _range_next_offset(
                response.headers.get("Range"),
                total_bytes=media_size_bytes,
            )
            if next_offset is None:
                return ReleaseProviderResult(
                    provider_effect="may_exist",
                    evidence={"http_status": 308, "reason": "invalid resumable Range header"},
                )
            return ReleaseProviderResult(
                provider_effect="confirmed_absent",
                evidence={
                    "http_status": 308,
                    "range": response.headers.get("Range"),
                    "final_video_absent": True,
                },
                runtime={"next_offset": next_offset, "resume_requires_status_query": False},
            )
        payload = self._json_object(response)
        video_id = str((payload or {}).get("id") or "").strip()
        if response.status_code in {200, 201} and video_id:
            return ReleaseProviderResult(
                provider_effect="verified",
                remote_id=video_id,
                evidence={
                    "http_status": response.status_code,
                    "provider_payload_sha256": _json_digest(payload),
                },
                runtime={
                    "next_offset": media_size_bytes,
                    "resume_requires_status_query": False,
                },
            )
        return ReleaseProviderResult(
            provider_effect="may_exist",
            evidence={
                "http_status": response.status_code,
                "reason": "resumable status did not prove final or incomplete state",
            },
        )

    def update_metadata_status(
        self,
        *,
        video_id: str,
        snippet: dict[str, Any],
        status: dict[str, Any],
    ) -> ReleaseProviderResult:
        response, failure = self._mutation_request(
            "PUT",
            f"{self.api_base_url}/videos",
            resource="videos.update.metadata-status",
            params={"part": "snippet,status"},
            json_body={"id": video_id, "snippet": snippet, "status": status},
        )
        if failure is not None:
            return failure
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        payload = self._json_object(response)
        actual_id = str((payload or {}).get("id") or "").strip()
        if actual_id != video_id:
            return ReleaseProviderResult(
                provider_effect="may_exist",
                remote_id=actual_id or None,
                evidence={
                    "http_status": response.status_code,
                    "reason": "videos.update returned unexpected ID",
                },
            )
        return ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id=video_id,
            evidence={
                "http_status": response.status_code,
                "provider_payload_sha256": _json_digest(payload),
            },
            runtime={"accepted_response": True},
        )

    def set_thumbnail(
        self,
        *,
        video_id: str,
        thumbnail_path: Path,
        mime_type: str,
    ) -> ReleaseProviderResult:
        response, failure = self._mutation_request(
            "POST",
            f"{self.upload_api_base_url}/thumbnails/set",
            resource="thumbnails.set",
            params={"videoId": video_id, "uploadType": "media"},
            headers={
                "Content-Type": mime_type,
                "Content-Length": str(thumbnail_path.stat().st_size),
            },
            content=_file_chunks(thumbnail_path, offset=0),
        )
        if failure is not None:
            return failure
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        payload = self._json_object(response)
        if payload is None:
            return ReleaseProviderResult(
                provider_effect="may_exist",
                evidence={
                    "http_status": response.status_code,
                    "reason": "thumbnail response was not JSON",
                },
            )
        return ReleaseProviderResult(
            provider_effect="verified",
            remote_id=video_id,
            evidence={
                "http_status": response.status_code,
                "provider_payload_sha256": _json_digest(payload),
            },
        )

    def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
    ) -> ReleaseProviderResult:
        response, failure = self._mutation_request(
            "POST",
            f"{self.api_base_url}/playlistItems",
            resource="playlistItems.insert",
            params={"part": "snippet"},
            json_body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
        if failure is not None:
            return failure
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        payload = self._json_object(response)
        membership_id = str((payload or {}).get("id") or "").strip()
        return ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id=membership_id or None,
            evidence={
                "http_status": response.status_code,
                "provider_payload_sha256": _json_digest(payload) if payload is not None else None,
                "accepted_response": True,
            },
        )

    def update_visibility(
        self,
        *,
        video_id: str,
        status: dict[str, Any],
    ) -> ReleaseProviderResult:
        response, failure = self._mutation_request(
            "PUT",
            f"{self.api_base_url}/videos",
            resource="videos.update.visibility",
            params={"part": "status"},
            json_body={"id": video_id, "status": status},
        )
        if failure is not None:
            return failure
        if response is None:
            raise AssertionError("mutation request returned neither response nor failure")
        payload = self._json_object(response)
        actual_id = str((payload or {}).get("id") or "").strip()
        return ReleaseProviderResult(
            provider_effect="may_exist",
            remote_id=actual_id or video_id,
            evidence={
                "http_status": response.status_code,
                "provider_payload_sha256": _json_digest(payload) if payload is not None else None,
                "accepted_response": True,
            },
        )

    def create_top_level_comment(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        text: str,
    ) -> ReleaseProviderResult:
        writer = YouTubeCommentWriter(
            client_config=self.client_config,
            token_store=self.token_store,
            account_alias=self.account_alias,
            http_client=self._http_client,
            retry_policy=self.retry_policy,
            request_limiter=self.request_limiter,
            sleep=self._sleep,
            jitter=self._jitter,
        )
        snapshot = writer.create_top_level_comment(
            video_id=video_id,
            expected_channel_id=expected_channel_id,
            text=text,
        )
        return ReleaseProviderResult(
            provider_effect="verified",
            remote_id=snapshot.comment_id,
            evidence={
                "thread_id": snapshot.thread_id,
                "comment_id": snapshot.comment_id,
                "text_sha256": snapshot.text_sha256,
                "channel_id": snapshot.channel_id,
            },
        )


__all__ = [
    "ReleaseProviderResult",
    "YouTubeReleaseProvider",
    "YouTubeReleaseProviderError",
]
