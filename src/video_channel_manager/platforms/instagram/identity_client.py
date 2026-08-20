from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from video_channel_manager.exchange.instagram_identity import InstagramAccountObservation
from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpFailureKind,
    HttpOperationClass,
    RequestRateLimiter,
    RetryPolicy,
    execute_http_request,
    redact_sensitive_text,
)


_API_VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+$")
_ACCOUNT_FIELDS = "id,name,tasks,instagram_business_account"
_PROVIDER = "instagram"


class InstagramIdentityReadError(RuntimeError):
    pass


def _evidence_digest(raw_responses: list[bytes]) -> str:
    digest = hashlib.sha256()
    for raw in raw_responses:
        digest.update(len(raw).to_bytes(8, byteorder="big", signed=False))
        digest.update(raw)
    return f"sha256:{digest.hexdigest()}"


def _graph_response_classifier(response: httpx.Response) -> HttpFailureKind | None:
    try:
        payload = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpFailureKind.INVALID_JSON
    if isinstance(payload, dict) and "error" in payload:
        return HttpFailureKind.PROVIDER_ERROR
    return None


class InstagramFacebookIdentityClient(HttpClientOwner):
    """Read exact Facebook-Login Instagram Professional identities without provider writes."""

    def __init__(
        self,
        *,
        user_access_token: str,
        debug_authorization_token: str,
        api_version: str,
        http_client: httpx.Client | None = None,
        retry_policy: RetryPolicy | None = None,
        limiter: RequestRateLimiter | None = None,
        timeout_seconds: float = 30.0,
        max_pages: int = 100,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not user_access_token.strip():
            raise ValueError("user_access_token must not be empty")
        if not debug_authorization_token.strip():
            raise ValueError("debug_authorization_token must not be empty")
        if user_access_token == debug_authorization_token:
            raise ValueError("debug authorization must be distinct from the inspected user token")
        if _API_VERSION_RE.fullmatch(api_version) is None:
            raise ValueError("api_version must use v<major>.<minor>")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")

        self._user_access_token = user_access_token
        self._debug_authorization_token = debug_authorization_token
        self.api_version = api_version
        self.retry_policy = retry_policy or RetryPolicy()
        self.limiter = limiter or RequestRateLimiter()
        self.max_pages = max_pages
        self._now = now
        self._initialize_http_client(http_client, timeout=timeout_seconds)

    @property
    def _base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    def _read_json(
        self,
        *,
        path: str,
        bearer_token: str,
        params: dict[str, str],
        resource: str,
    ) -> tuple[dict[str, Any], bytes]:
        url = f"{self._base_url}{path}"
        result = execute_http_request(
            lambda: self._http_client.get(
                url,
                headers={"Authorization": f"Bearer {bearer_token}"},
                params=params,
            ),
            provider=_PROVIDER,
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource=resource,
            retry_policy=self.retry_policy,
            limiter=self.limiter,
            response_classifier=_graph_response_classifier,
        )
        response = result.response
        if result.failure_kind is not None:
            raise InstagramIdentityReadError(
                f"Instagram identity read failed for {resource}: "
                f"{result.failure_kind.value} status={response.status_code} attempts={result.attempts}"
            )
        try:
            payload = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InstagramIdentityReadError(f"Instagram identity read returned invalid JSON for {resource}") from exc
        if not isinstance(payload, dict):
            raise InstagramIdentityReadError(f"Instagram identity read returned a non-object payload for {resource}")
        return payload, response.content

    def _read_scope_evidence(self) -> tuple[tuple[str, ...], bytes]:
        payload, raw = self._read_json(
            path="/debug_token",
            bearer_token=self._debug_authorization_token,
            params={"input_token": self._user_access_token},
            resource="/debug_token",
        )
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("is_valid") is not True:
            raise InstagramIdentityReadError("Instagram Facebook user token is not provider-confirmed as valid")
        scopes = data.get("scopes")
        if not isinstance(scopes, list) or not scopes or not all(isinstance(scope, str) and scope for scope in scopes):
            raise InstagramIdentityReadError("Instagram token-debug evidence does not contain a valid scopes list")
        normalized = tuple(sorted(set(scopes)))
        required = {"instagram_basic", "pages_show_list"}
        missing = sorted(required - set(normalized))
        if missing:
            raise InstagramIdentityReadError(f"Instagram Facebook Login identity read lacks required scopes: {missing}")
        return normalized, raw

    def _read_managed_pages(self) -> tuple[list[tuple[str, str]], list[bytes]]:
        linked_accounts: list[tuple[str, str]] = []
        raw_responses: list[bytes] = []
        after: str | None = None
        seen_cursors: set[str] = set()
        exhausted = False

        for _ in range(self.max_pages):
            params = {"fields": _ACCOUNT_FIELDS}
            if after is not None:
                params["after"] = after
            payload, raw = self._read_json(
                path="/me/accounts",
                bearer_token=self._user_access_token,
                params=params,
                resource="/me/accounts",
            )
            raw_responses.append(raw)
            data = payload.get("data")
            if not isinstance(data, list):
                raise InstagramIdentityReadError("Instagram Page discovery payload is missing a data list")

            for item in data:
                if not isinstance(item, dict):
                    raise InstagramIdentityReadError("Instagram Page discovery contains a non-object item")
                page_id = item.get("id")
                ig_account = item.get("instagram_business_account")
                if ig_account is None:
                    continue
                if not isinstance(page_id, str) or not page_id.isdigit():
                    raise InstagramIdentityReadError("Instagram Page discovery contains an invalid Page ID")
                if not isinstance(ig_account, dict):
                    raise InstagramIdentityReadError("instagram_business_account must be an object")
                instagram_id = ig_account.get("id")
                if not isinstance(instagram_id, str) or not instagram_id.isdigit():
                    raise InstagramIdentityReadError(
                        "Instagram Page discovery contains an invalid Professional account ID"
                    )
                linked_accounts.append((instagram_id, page_id))

            paging = payload.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            next_after = cursors.get("after") if isinstance(cursors, dict) else None
            if not isinstance(next_after, str) or not next_after:
                exhausted = True
                break
            if next_after in seen_cursors:
                raise InstagramIdentityReadError("Instagram Page discovery repeated a pagination cursor")
            seen_cursors.add(next_after)
            after = next_after

        if not exhausted:
            raise InstagramIdentityReadError("Instagram Page discovery exceeded the configured pagination limit")

        instagram_ids = [instagram_id for instagram_id, _ in linked_accounts]
        if len(instagram_ids) != len(set(instagram_ids)):
            raise InstagramIdentityReadError("Instagram Page discovery returned a duplicate Professional account ID")
        linked_accounts.sort()
        return linked_accounts, raw_responses

    def discover(self) -> tuple[InstagramAccountObservation, ...]:
        """Return all linked Professional account observations proven by two provider-read evidence streams."""

        scopes, scope_raw = self._read_scope_evidence()
        linked_accounts, account_raw = self._read_managed_pages()
        account_digest = _evidence_digest(account_raw)
        scope_digest = _evidence_digest([scope_raw])
        if account_digest == scope_digest:
            raise InstagramIdentityReadError("account and scope evidence digests unexpectedly collide")
        observed_at = self._now()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise InstagramIdentityReadError("identity observation clock must return a timezone-aware datetime")

        return tuple(
            InstagramAccountObservation(
                login_mode="facebook_login",
                provider_host="graph.facebook.com",
                api_version=self.api_version,
                instagram_professional_account_id=instagram_id,
                facebook_page_id=page_id,
                granted_scopes=scopes,
                observed_at=observed_at,
                account_evidence_sha256=account_digest,
                scope_evidence_sha256=scope_digest,
            )
            for instagram_id, page_id in linked_accounts
        )

    def redacted_error_context(self, value: object) -> str:
        """Expose shared redaction for operator diagnostics without returning credentials."""

        return redact_sensitive_text(
            value,
            secrets=(self._user_access_token, self._debug_authorization_token),
        )
