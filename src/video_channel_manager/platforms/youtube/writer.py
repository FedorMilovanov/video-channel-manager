from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any, TypeAlias

import httpx

from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow, YOUTUBE_FORCE_SSL_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
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


class YouTubeDescriptionWriter:
    """Narrow YouTube writer for guarded description replacement only."""

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
    ) -> None:
        self.client_config = client_config
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self._http_client = http_client
        self.api_base_url = api_base_url.rstrip("/")

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
        client = self._http_client or httpx.Client(timeout=45.0, follow_redirects=True)
        close_client = self._http_client is None
        try:
            response = client.request(
                method,
                f"{self.api_base_url}/{resource.lstrip('/')}",
                params=httpx.QueryParams(params),
                headers={"Authorization": f"Bearer {self._token(require_write=require_write).access_token}"},
                json=json_body,
            )
            if response.status_code >= 400:
                message = response.text[:500]
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        error = _dict_field(payload, "error")
                        message = str(error.get("message") or message)
                except ValueError:
                    pass
                raise YouTubeWriteError(f"YouTube API {response.status_code}: {message}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise YouTubeWriteError("YouTube API returned a non-object response.")
            return payload
        except httpx.HTTPError as exc:
            raise YouTubeWriteError(f"YouTube API request failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def read_description(self, video_id: str) -> VideoDescriptionSnapshot:
        payload = self._request(
            "GET",
            "videos",
            params={
                "part": "snippet,contentDetails,status",
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
        if isinstance(tags, list):
            update_snippet["tags"] = [str(tag) for tag in tags]
        for field in ("defaultLanguage", "defaultAudioLanguage"):
            value = snippet.get(field)
            if value:
                update_snippet[field] = str(value)

        self._request(
            "PUT",
            "videos",
            params={"part": "snippet"},
            json_body={"id": current.video_id, "snippet": update_snippet},
            require_write=True,
        )
        verified = self.read_description(current.video_id)
        if not descriptions_equivalent(verified.description, new_description):
            raise YouTubeWriteError(f"Verification failed after updating description for {current.video_id}.")
        return verified

    def replace_description(
        self,
        *,
        video_id: str,
        expected_channel_id: str,
        expected_revision: str,
        expected_description: str,
        new_description: str,
    ) -> VideoDescriptionSnapshot:
        current = self.read_description(video_id)
        if current.channel_id != expected_channel_id:
            raise YouTubeRevisionConflictError(
                f"Channel mismatch for {video_id}: expected {expected_channel_id}, got {current.channel_id}."
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
