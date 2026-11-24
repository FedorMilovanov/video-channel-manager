from __future__ import annotations

import copy
import hashlib
import random
import json
import time
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeAlias

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
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow, YOUTUBE_FORCE_SSL_SCOPE
from video_channel_manager.platforms.youtube.store import (
    ProjectQuotaGuard,
    TokenStore,
    YouTubeQuotaBlocked,
    quota_exhaustion_reason,
    reserve_shared_quota,
)

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
# Observed official YouTube videos.update PUT ReadTimeouts clustered near the
# previous 45-second response limit. Keep GET and other phases at their
# existing default and only allow more time for one ambiguous mutation
# response; NEVER resend a PUT when this longer deadline is exceeded.
_MUTATION_RESPONSE_TIMEOUT = httpx.Timeout(45.0, read=120.0)
QueryParam: TypeAlias = str | int
QueryParams: TypeAlias = dict[str, QueryParam]

# YouTube may remove harmless invisible separators while storing a description.
# Do not remove U+200D ZERO WIDTH JOINER because it is meaningful inside emoji.
_IGNORABLE_DESCRIPTION_CODEPOINTS = {
    ord("\ufeff"): None,  # ZERO WIDTH NO-BREAK SPACE / BOM
    ord("\u200b"): None,  # ZERO WIDTH SPACE
    ord("\u2060"): None,  # WORD JOINER
}


class YouTubeWriteError(RuntimeError):
    pass


class YouTubeWriteScopeError(YouTubeWriteError):
    pass


class YouTubeRevisionConflictError(YouTubeWriteError):
    pass


@dataclass(frozen=True)
class VideoDescriptionSnapshot:
    video_id: str
    channel_id: str
    title: str
    description: str
    revision: str
    raw: dict[str, Any]


def canonicalize_description(value: str) -> str:
    """Normalize storage-only differences without changing visible wording."""

    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = normalized.translate(_IGNORABLE_DESCRIPTION_CODEPOINTS)
    # Trailing spaces and a final newline are not visible in YouTube descriptions.
    return "\n".join(line.rstrip() for line in normalized.split("\n")).rstrip("\n")


def descriptions_equivalent(left: str, right: str) -> bool:
    return canonicalize_description(left) == canonicalize_description(right)


def _revision(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _dict_items(payload: dict[str, Any], key: str = "items") -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _postwrite_metadata_drift(
    before: VideoDescriptionSnapshot, after: VideoDescriptionSnapshot, new_description: str
) -> list[str]:
    """Compare the fields a description-only PUT must not silently change."""
    old_snippet = _dict_field(before.raw, "snippet")
    new_snippet = _dict_field(after.raw, "snippet")
    drift = [
        f"snippet.{field}"
        for field in ("channelId", "title", "categoryId", "defaultLanguage", "defaultAudioLanguage")
        if old_snippet.get(field) != new_snippet.get(field)
    ]
    if (old_snippet.get("tags") or []) != (new_snippet.get("tags") or []):
        drift.append("snippet.tags")
    if _dict_field(before.raw, "status").get("privacyStatus") != _dict_field(after.raw, "status").get("privacyStatus"):
        drift.append("status.privacyStatus")

    old_locales = _dict_field(before.raw, "localizations")
    new_locales = _dict_field(after.raw, "localizations")
    if old_locales.keys() != new_locales.keys():
        drift.append("localizations.languages")
    for language in old_locales.keys() & new_locales.keys():
        original = old_locales[language]
        observed = new_locales[language]
        if not isinstance(original, dict) or not isinstance(observed, dict):
            drift.append(f"localizations.{language}")
            continue
        if original.get("title") != observed.get("title"):
            drift.append(f"localizations.{language}.title")
        original_description = str(original.get("description") or "")
        observed_description = str(observed.get("description") or "")
        if language == old_snippet.get("defaultLanguage"):
            # YouTube may synchronize the primary-language locale automatically.
            accepted = descriptions_equivalent(observed_description, original_description) or (
                descriptions_equivalent(observed_description, new_description)
            )
        else:
            accepted = descriptions_equivalent(observed_description, original_description)
        if not accepted:
            drift.append(f"localizations.{language}.description")
    return drift


class YouTubeDescriptionWriter(HttpClientOwner):
    """Narrow YouTube writer for guarded description replacement only."""

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
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
        self._initialize_http_client(
            http_client,
            timeout=45.0,
            follow_redirects=True,
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.retry_policy = retry_policy or RetryPolicy()
        self.request_limiter = request_limiter or RequestRateLimiter()
        self._request_sleep = sleep
        self._jitter = jitter

    def _token(self, *, require_write: bool) -> OAuthToken:
        token = self.token_store.load_token(self.account_alias)
        if token.needs_refresh():
            token = InstalledOAuthFlow(self.client_config, http_client=self._http_client).refresh(token)
            self.token_store.save_token(self.account_alias, token)
        if require_write and YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
            raise YouTubeWriteScopeError(
                "Stored token is read-only. Re-authorize with: "
                f"video-manager youtube login --account {self.account_alias} --write --force"
            )
        return token

    def _request(
        self,
        method: str,
        resource: str,
        *,
        params: QueryParams,
        json_body: dict[str, Any] | None = None,
        require_write: bool = False,
    ) -> dict[str, Any]:
        operation = HttpOperationClass.AMBIGUOUS_MUTATION if require_write else HttpOperationClass.SAFE_READ
        access_token = self._token(require_write=require_write).access_token
        try:
            result = execute_http_request(
                lambda: self._http_client.request(
                    method,
                    f"{self.api_base_url}/{resource.lstrip('/')}",
                    params=httpx.QueryParams(params),
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=json_body,
                    timeout=_MUTATION_RESPONSE_TIMEOUT if require_write else self._http_client.timeout,
                ),
                provider="YouTube",
                attempt_guard=self._quota_guard,
                operation=operation,
                method=method,
                resource=resource,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                sleep=self._request_sleep,
                jitter=self._jitter,
            )
        except (HttpTransportFailure, YouTubeQuotaBlocked) as exc:
            raise YouTubeWriteError(str(exc)) from exc

        response = result.response
        if response.status_code >= 400:
            message = response.text
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict):
                    error = _dict_field(error_payload, "error")
                    message = str(error.get("message") or message)
            except ValueError:
                pass
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            safe_message = redact_sensitive_text(message, secrets=(access_token,))
            quota_reason = quota_exhaustion_reason(response)
            if quota_reason is not None:
                safe_message = f"{quota_reason}: {safe_message}"
            raise YouTubeWriteError(
                f"YouTube API {response.status_code} in {resource}: {safe_message} "
                f"[kind={kind.value} attempts={result.attempts}]"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise YouTubeWriteError(
                f"YouTube API returned invalid JSON in {resource} "
                f"[kind={HttpFailureKind.INVALID_JSON.value} attempts={result.attempts}]"
            ) from exc
        if not isinstance(payload, dict):
            raise YouTubeWriteError(
                f"YouTube API returned a non-object response in {resource} "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]"
            )
        return payload

    def read_description(self, video_id: str) -> VideoDescriptionSnapshot:
        payload = self._request(
            "GET",
            "videos",
            params={
                "part": "snippet,contentDetails,status,localizations",
                "id": video_id,
                "maxResults": 1,
            },
        )
        items = _dict_items(payload)
        if not items:
            raise YouTubeWriteError(f"Video not found or inaccessible: {video_id}")
        raw = items[0]
        snippet = _dict_field(raw, "snippet")
        actual_id = str(raw.get("id") or "").strip()
        channel_id = str(snippet.get("channelId") or "").strip()
        if actual_id != video_id or not channel_id:
            raise YouTubeWriteError(f"YouTube returned an invalid video record for: {video_id}")
        return VideoDescriptionSnapshot(
            video_id=video_id,
            channel_id=channel_id,
            title=str(snippet.get("title") or video_id),
            description=str(snippet.get("description") or ""),
            revision=_revision(raw),
            raw=raw,
        )

    def _write_description(
        self,
        *,
        current: VideoDescriptionSnapshot,
        new_description: str,
        require_exact_state: bool = False,
    ) -> VideoDescriptionSnapshot:
        snippet = _dict_field(current.raw, "snippet")
        title = str(snippet.get("title") or "").strip()
        category_id = str(snippet.get("categoryId") or "").strip()
        if not title or not category_id:
            raise YouTubeWriteError(f"Video {current.video_id} lacks title/categoryId required by videos.update.")

        update_snippet: dict[str, Any] = {
            "title": title,
            "categoryId": category_id,
            "description": new_description,
        }
        tags = snippet.get("tags")
        # YouTube owner GET can intermittently omit an existing video's tags.
        # A PUT built from that incomplete snapshot could silently erase them.
        # Lord God has a strict source-preserving operator contract: fail before
        # dispatch if the currently read owner snippet does not expose its tag
        # collection. An actually tagless video needs separate owner review.
        if current.channel_id == LORD_GOD_OWNER_CHANNEL and not isinstance(tags, list):
            raise YouTubeWriteError(
                f"Owner API did not return snippet.tags for {current.video_id}; "
                "cannot prove tag preservation. No videos.update PUT was sent."
            )
        if isinstance(tags, list):
            update_snippet["tags"] = [str(tag) for tag in tags]
        for field in ("defaultLanguage", "defaultAudioLanguage"):
            value = snippet.get(field)
            if value:
                update_snippet[field] = str(value)

        # YouTube may auto-translate non-default locales on a snippet-only PUT.
        # When existing localizations are present, submit the full, exact map
        # with the snippet in ONE update. Omitting a locale from an update can
        # delete it; never send a partial or malformed localization map.
        body: dict[str, Any] = {"id": current.video_id, "snippet": update_snippet}
        parts = "snippet"
        if "localizations" in current.raw:
            existing = current.raw["localizations"]
            if not isinstance(existing, dict) or not snippet.get("defaultLanguage"):
                raise YouTubeWriteError(f"Cannot safely preserve localizations for {current.video_id}; no PUT sent.")
            preserved: dict[str, dict[str, str]] = {}
            for language, locale in existing.items():
                if (
                    not isinstance(language, str)
                    or not language
                    or not isinstance(locale, dict)
                    or not isinstance(locale.get("title"), str)
                    or not locale["title"]
                    or not isinstance(locale.get("description"), str)
                ):
                    raise YouTubeWriteError(f"Incomplete localization for {current.video_id}; no PUT sent.")
                preserved[language] = {
                    "title": locale["title"],
                    "description": (
                        new_description if language == snippet["defaultLanguage"] else locale["description"]
                    ),
                }
            body["localizations"] = preserved
            parts = "snippet,localizations"

        if require_exact_state:
            if (
                not isinstance(current.raw.get("localizations"), dict)
                or not isinstance(tags, list)
                or not all(isinstance(tag, str) for tag in tags)
                or snippet.get("title") != title
                or snippet.get("categoryId") != category_id
                or not snippet.get("defaultLanguage")
                or not snippet.get("defaultAudioLanguage")
                or not _dict_field(current.raw, "contentDetails").get("duration")
                or not _dict_field(current.raw, "status").get("privacyStatus")
                or not new_description.strip()
                or len(new_description.encode("utf-8")) > 5000
            ):
                raise YouTubeWriteError("Incomplete exact owner state; no PUT sent.")
            primary = current.raw["localizations"].get(snippet["defaultLanguage"])
            if primary is not None and primary["description"] != current.description:
                raise YouTubeWriteError("Primary locale differs from source description; no PUT sent.")

        with reserve_shared_quota(self._quota_guard, 50 + self.retry_policy.max_attempts, YouTubeWriteError):
            self._request(
                "PUT",
                "videos",
                params={"part": parts},
                json_body=body,
                require_write=True,
            )
            verified = self.read_description(current.video_id)
            if not descriptions_equivalent(verified.description, new_description):
                raise YouTubeWriteError(f"Verification failed after updating description for {current.video_id}.")
            drift = _postwrite_metadata_drift(current, verified, new_description)
            if require_exact_state:
                if verified.description != new_description:
                    drift.append("snippet.description.exact")
                if verified.raw.get("localizations") != body.get("localizations"):
                    drift.append("localizations.exact_map")
                if _dict_field(verified.raw, "status") != _dict_field(current.raw, "status"):
                    drift.append("status.exact")
                if _dict_field(verified.raw, "contentDetails").get("duration") != _dict_field(
                    current.raw, "contentDetails"
                ).get("duration"):
                    drift.append("contentDetails.duration")
                if _dict_field(verified.raw, "snippet").get("tags") != tags:
                    drift.append("snippet.tags.exact")
            if drift:
                raise YouTubeWriteError(
                    f"Postflight metadata drift after updating description for {current.video_id}: "
                    f"{', '.join(drift)}. Reconcile the video before another write."
                )
            return verified

    def replace_localized_description(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_title: str,
        expected_primary_description: str,
        expected_snippet_fields: dict[str, Any],
        expected_privacy: str,
        expected_duration: str,
        expected_localizations: dict[str, dict[str, str]],
        language: str,
        expected_localized_description: str,
        new_description: str,
    ) -> VideoDescriptionSnapshot:
        """Update exactly one non-default locale; preserve all others in one official PUT.

        This never updates the snippet/status parts. Ambiguous PUT failures are not
        retried or rolled back; reconcile with an independent owner GET instead.
        """
        current = self.read_description(video_id)
        sn = _dict_field(current.raw, "snippet")
        if current.channel_id != expected_channel_id or current.title != expected_title:
            raise YouTubeRevisionConflictError(f"Owner/title mismatch for {video_id}; no PUT sent.")
        if current.description != expected_primary_description:
            raise YouTubeRevisionConflictError(f"Primary description changed for {video_id}; no PUT sent.")
        protected_fields = ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage")
        if {k: sn.get(k) for k in protected_fields} != expected_snippet_fields:
            raise YouTubeRevisionConflictError(f"Snippet metadata changed for {video_id}; no PUT sent.")
        if _dict_field(current.raw, "status").get("privacyStatus") != expected_privacy:
            raise YouTubeRevisionConflictError(f"Privacy changed for {video_id}; no PUT sent.")
        if _dict_field(current.raw, "contentDetails").get("duration") != expected_duration:
            raise YouTubeRevisionConflictError(f"Duration changed for {video_id}; no PUT sent.")
        if not isinstance(language, str) or not language or language == sn.get("defaultLanguage"):
            raise YouTubeRevisionConflictError(f"Expected non-default locale for {video_id}; no PUT sent.")
        if not sn.get("defaultLanguage") or not sn.get("defaultAudioLanguage"):
            raise YouTubeRevisionConflictError(f"Incomplete language metadata for {video_id}; no PUT sent.")
        live_locales = current.raw.get("localizations")
        if not isinstance(live_locales, dict) or live_locales != expected_localizations:
            raise YouTubeRevisionConflictError(f"Localized metadata changed for {video_id}; no PUT sent.")
        if language not in live_locales:
            raise YouTubeRevisionConflictError(f"Locale {language} is missing for {video_id}; no PUT sent.")
        for key, locale in live_locales.items():
            if (
                not isinstance(key, str)
                or not key
                or not isinstance(locale, dict)
                or not isinstance(locale.get("title"), str)
                or not locale["title"]
                or not isinstance(locale.get("description"), str)
            ):
                raise YouTubeWriteError(f"Incomplete locale data for {video_id}; no PUT sent.")
        if live_locales[language]["description"] != expected_localized_description:
            raise YouTubeRevisionConflictError(f"Localized description changed for {video_id}; no PUT sent.")
        if (
            not isinstance(new_description, str)
            or not new_description.strip()
            or len(new_description.encode("utf-8")) > 5000
        ):
            raise YouTubeWriteError(f"Invalid localized description for {video_id}; no PUT sent.")

        replacement = copy.deepcopy(live_locales)
        replacement[language]["description"] = new_description
        if replacement == live_locales:
            return current

        with reserve_shared_quota(self._quota_guard, 50 + self.retry_policy.max_attempts, YouTubeWriteError):
            self._request(
                "PUT",
                "videos",
                params={"part": "localizations"},
                json_body={"id": video_id, "localizations": replacement},
                require_write=True,
            )
            verified = self.read_description(video_id)
            expected_raw = copy.deepcopy(current.raw)
            expected_raw["localizations"] = replacement
            expected = VideoDescriptionSnapshot(
                video_id=current.video_id,
                channel_id=current.channel_id,
                title=current.title,
                description=current.description,
                revision=current.revision,
                raw=expected_raw,
            )
            drift = _postwrite_metadata_drift(expected, verified, current.description)
            if verified.description != current.description:
                drift.append("snippet.description")
            if _dict_field(verified.raw, "localizations") != replacement:
                drift.append("localizations.exact_map")
            if _dict_field(current.raw, "contentDetails").get("duration") != _dict_field(
                verified.raw, "contentDetails"
            ).get("duration"):
                drift.append("contentDetails.duration")
            if drift:
                raise YouTubeWriteError(
                    f"Localized postflight drift for {video_id}: {', '.join(sorted(set(drift)))}. "
                    "Reconcile by GET; do not replay the PUT."
                )
            return verified

    @contextmanager
    def reserve_exact_description_execution(self) -> Iterator[None]:
        """Reserve preflight, predispatch GET, PUT and both verification GETs."""
        guard = self._quota_guard
        if guard is None:
            raise YouTubeWriteError("Exact historical execution requires a shared project quota guard")
        units = 50 + 4 * self.retry_policy.max_attempts
        try:
            status = guard.budget_status()
            buckets = status.get("buckets")
            shared = buckets.get("shared") if isinstance(buckets, dict) else None
            remaining = shared.get("local_remaining") if isinstance(shared, dict) else None
            if (
                status.get("quota_policy_enabled") is not True
                or status.get("provider_stop") is not None
                or type(remaining) is not int
                or remaining < units
            ):
                raise YouTubeWriteError("Exact historical execution requires reviewed current shared quota headroom")
            with guard.reserve(units):
                yield
        except YouTubeQuotaBlocked as exc:
            raise YouTubeWriteError(str(exc)) from exc

    def replace_description(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_revision: str,
        expected_description: str,
        new_description: str,
        require_exact_state: bool = False,
    ) -> VideoDescriptionSnapshot:
        current = self.read_description(video_id)
        if current.channel_id != expected_channel_id:
            raise YouTubeRevisionConflictError(
                f"Channel mismatch for {video_id}: expected {expected_channel_id}, got {current.channel_id}."
            )
        if require_exact_state and (
            current.revision != expected_revision or current.description != expected_description
        ):
            raise YouTubeRevisionConflictError(
                f"Exact owner state changed for {video_id}; no PUT sent. Re-audit before proceeding."
            )
        if not descriptions_equivalent(current.description, expected_description):
            raise YouTubeRevisionConflictError(
                f"Description mismatch for {video_id}; refusing to overwrite newer or manually edited text."
            )
        # The CLI preflight still checks the full audit revision before any writes.
        # Between that preflight and a write, YouTube can refresh etags or other
        # server-managed fields. Since this operation preserves the current live
        # title/tags/category and replaces only a description whose text still
        # matches the expected state, revision drift alone is not a conflict.
        _ = expected_revision
        if require_exact_state:
            return self._write_description(current=current, new_description=new_description, require_exact_state=True)
        return self._write_description(current=current, new_description=new_description)

    def restore_description_if_current(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_current_description: str,
        restore_description: str,
    ) -> VideoDescriptionSnapshot:
        """Restore only when live text still equals the exact state written by this tool.

        This deliberately does not depend on YouTube's full-record revision. YouTube can
        refresh etags or other server-managed fields after an update even when the
        description has not changed. Exact canonical description equality remains the
        mutation guard during recovery.
        """

        current = self.read_description(video_id)
        if current.channel_id != expected_channel_id:
            raise YouTubeRevisionConflictError(
                f"Channel mismatch for {video_id}: expected {expected_channel_id}, got {current.channel_id}."
            )
        if descriptions_equivalent(current.description, restore_description):
            return current
        if not descriptions_equivalent(current.description, expected_current_description):
            raise YouTubeRevisionConflictError(
                f"Description mismatch for {video_id}; refusing recovery because live text is neither the "
                "planned after-state nor the original backup."
            )
        return self._write_description(current=current, new_description=restore_description)
