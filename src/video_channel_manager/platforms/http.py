from __future__ import annotations

import random
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from types import TracebackType
from typing import Self

import httpx


class HttpOperationClass(StrEnum):
    """Retry authority for one concrete provider operation."""

    SAFE_READ = "safe_read"
    AMBIGUOUS_MUTATION = "ambiguous_mutation"


class HttpFailureKind(StrEnum):
    TRANSPORT = "transport"
    RATE_LIMIT = "rate_limit"
    TRANSIENT_HTTP = "transient_http"
    PERMANENT_HTTP = "permanent_http"
    PROVIDER_TRANSIENT = "provider_transient"
    PROVIDER_ERROR = "provider_error"
    INVALID_JSON = "invalid_json"
    INVALID_PAYLOAD = "invalid_payload"


_RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(access_token|refresh_token|client_secret|authorization|api_key|key)=([^&\s]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_URL_RE = re.compile(r"https?://[^\s\]\[(){}<>\"']+")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    max_retry_after_seconds: float = 30.0
    jitter_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        for name, value in (
            ("base_delay_seconds", self.base_delay_seconds),
            ("max_delay_seconds", self.max_delay_seconds),
            ("max_retry_after_seconds", self.max_retry_after_seconds),
            ("jitter_seconds", self.jitter_seconds),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds cannot be lower than base_delay_seconds")

    def delay_seconds(
        self,
        *,
        failed_attempt: int,
        retry_after_seconds: float | None,
        jitter_value: float,
    ) -> float:
        if retry_after_seconds is not None:
            return min(max(0.0, retry_after_seconds), self.max_retry_after_seconds)
        exponential = self.base_delay_seconds * (2 ** max(0, failed_attempt - 1))
        jitter = min(1.0, max(0.0, jitter_value)) * self.jitter_seconds
        return min(exponential + jitter, self.max_delay_seconds)


class RequestRateLimiter:
    """Thread-safe minimum-interval limiter with injectable time functions.

    A zero interval is intentionally a no-op. Callers may inject one shared
    instance across provider clients when they have a verified policy. The core
    library does not invent a provider request-per-second value.
    """

    def __init__(
        self,
        min_interval_seconds: float = 0.0,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative")
        self.min_interval_seconds = float(min_interval_seconds)
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def wait(self) -> float:
        if self.min_interval_seconds == 0:
            return self._monotonic()
        with self._lock:
            now = self._monotonic()
            delay = max(0.0, self._next_allowed_at - now)
            if delay:
                self._sleep(delay)
                now = self._monotonic()
            acquired_at = max(now, self._next_allowed_at)
            self._next_allowed_at = acquired_at + self.min_interval_seconds
            return acquired_at


@dataclass(frozen=True, slots=True)
class HttpRequestResult:
    response: httpx.Response
    attempts: int
    failure_kind: HttpFailureKind | None


class HttpTransportFailure(RuntimeError):
    def __init__(
        self,
        *,
        provider: str,
        operation: HttpOperationClass,
        method: str,
        resource: str,
        attempts: int,
        cause_type: str,
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.method = method.upper()
        self.resource = resource
        self.attempts = attempts
        self.kind = HttpFailureKind.TRANSPORT
        self.cause_type = cause_type
        super().__init__(
            f"{provider} {operation.value} {self.method} {resource} failed after "
            f"{attempts} attempt(s): {self.kind.value} ({cause_type})"
        )


def redact_sensitive_text(value: object, *, secrets: tuple[str, ...] = (), limit: int = 500) -> str:
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _URL_RE.sub("<url>", text)
    return text[: max(0, limit)]


def classify_http_status(status_code: int) -> HttpFailureKind | None:
    if status_code < 400:
        return None
    if status_code == 429:
        return HttpFailureKind.RATE_LIMIT
    if status_code in _RETRYABLE_HTTP_STATUS_CODES or 500 <= status_code <= 599:
        return HttpFailureKind.TRANSIENT_HTTP
    return HttpFailureKind.PERMANENT_HTTP


def parse_retry_after_seconds(
    value: str | None,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = (retry_at.astimezone(UTC) - now().astimezone(UTC)).total_seconds()
    if seconds < 0:
        return None
    return seconds


def _is_retryable(kind: HttpFailureKind | None) -> bool:
    return kind in {
        HttpFailureKind.RATE_LIMIT,
        HttpFailureKind.TRANSIENT_HTTP,
        HttpFailureKind.PROVIDER_TRANSIENT,
    }


def execute_http_request(
    request: Callable[[], httpx.Response],
    *,
    provider: str,
    operation: HttpOperationClass,
    method: str,
    resource: str,
    retry_policy: RetryPolicy | None = None,
    limiter: RequestRateLimiter | None = None,
    response_classifier: Callable[[httpx.Response], HttpFailureKind | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> HttpRequestResult:
    """Execute one request under explicit read/mutation retry authority.

    HTTP status responses are returned to the provider adapter so it can retain
    provider-specific error types and codes. Transport failures have no response
    to inspect and therefore raise the shared redaction-safe failure directly.
    """

    policy = retry_policy or RetryPolicy()
    max_attempts = policy.max_attempts if operation is HttpOperationClass.SAFE_READ else 1
    active_limiter = limiter or RequestRateLimiter()

    for attempt in range(1, max_attempts + 1):
        active_limiter.wait()
        try:
            response = request()
        except httpx.HTTPError as exc:
            if operation is HttpOperationClass.SAFE_READ and attempt < max_attempts:
                sleep(
                    policy.delay_seconds(
                        failed_attempt=attempt,
                        retry_after_seconds=None,
                        jitter_value=jitter(),
                    )
                )
                continue
            raise HttpTransportFailure(
                provider=provider,
                operation=operation,
                method=method,
                resource=resource,
                attempts=attempt,
                cause_type=type(exc).__name__,
            ) from exc

        kind = classify_http_status(response.status_code)
        if kind is None and response_classifier is not None:
            kind = response_classifier(response)
        if (
            operation is HttpOperationClass.SAFE_READ
            and attempt < max_attempts
            and _is_retryable(kind)
        ):
            retry_after = parse_retry_after_seconds(response.headers.get("Retry-After"), now=now)
            sleep(
                policy.delay_seconds(
                    failed_attempt=attempt,
                    retry_after_seconds=retry_after,
                    jitter_value=jitter(),
                )
            )
            continue
        return HttpRequestResult(response=response, attempts=attempt, failure_kind=kind)

    raise AssertionError("HTTP request loop terminated without a result")


class HttpClientOwner:
    """Own or borrow one persistent synchronous HTTPX client.

    Provider clients call ``_initialize_http_client`` once in their constructor.
    When no client is injected, this object owns one persistent client and closes
    it through ``close`` or the context-manager protocol. Injected clients remain
    owned by their caller and are never closed here.
    """

    _http_client: httpx.Client
    _owns_http_client: bool
    _owned_http_client_closed: bool

    def _initialize_http_client(
        self,
        http_client: httpx.Client | None,
        *,
        timeout: float | httpx.Timeout,
        follow_redirects: bool = True,
    ) -> None:
        if hasattr(self, "_http_client"):
            raise RuntimeError("HTTP client lifecycle was initialized more than once")
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout,
            follow_redirects=follow_redirects,
        )
        self._owned_http_client_closed = False

    @property
    def owns_http_client(self) -> bool:
        return self._owns_http_client

    def close(self) -> None:
        """Close only a client created by this object; safe to call repeatedly."""

        if not self._owns_http_client or self._owned_http_client_closed:
            return
        self._http_client.close()
        self._owned_http_client_closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()


__all__ = [
    "HttpClientOwner",
    "HttpFailureKind",
    "HttpOperationClass",
    "HttpRequestResult",
    "HttpTransportFailure",
    "RequestRateLimiter",
    "RetryPolicy",
    "classify_http_status",
    "execute_http_request",
    "parse_retry_after_seconds",
    "redact_sensitive_text",
]
