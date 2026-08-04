from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from video_channel_manager.platforms.http import (
    HttpFailureKind,
    HttpOperationClass,
    HttpTransportFailure,
    RequestRateLimiter,
    RetryPolicy,
    execute_http_request,
    parse_retry_after_seconds,
    redact_sensitive_text,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []
        self._lock = threading.Lock()

    def monotonic(self) -> float:
        with self._lock:
            return self.value

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.value += seconds


def test_safe_read_retries_transport_and_retry_after_with_bounds() -> None:
    calls = 0
    sleeps: list[float] = []

    def request() -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectTimeout("token=https://secret.example/upload")
        if calls == 2:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(200, json={"ok": True})

    result = execute_http_request(
        request,
        provider="YouTube",
        operation=HttpOperationClass.SAFE_READ,
        method="GET",
        resource="videos.list",
        retry_policy=RetryPolicy(
            max_attempts=4,
            base_delay_seconds=0.5,
            max_delay_seconds=4.0,
            max_retry_after_seconds=5.0,
            jitter_seconds=0.0,
        ),
        sleep=sleeps.append,
    )

    assert result.response.status_code == 200
    assert result.attempts == 3
    assert result.failure_kind is None
    assert calls == 3
    assert sleeps == [0.5, 5.0]


def test_ambiguous_mutation_never_retries_transport_failure() -> None:
    calls = 0

    def request() -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("lost response from https://upload.example/secret")

    with pytest.raises(HttpTransportFailure) as captured:
        execute_http_request(
            request,
            provider="VK",
            operation=HttpOperationClass.AMBIGUOUS_MUTATION,
            method="POST",
            resource="video.save",
            retry_policy=RetryPolicy(max_attempts=9),
        )

    assert captured.value.attempts == 1
    assert captured.value.kind is HttpFailureKind.TRANSPORT
    assert "upload.example" not in str(captured.value)
    assert calls == 1


def test_ambiguous_mutation_returns_transient_status_after_one_attempt() -> None:
    calls = 0

    def request() -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="uncertain")

    result = execute_http_request(
        request,
        provider="VK",
        operation=HttpOperationClass.AMBIGUOUS_MUTATION,
        method="POST",
        resource="video.save",
        retry_policy=RetryPolicy(max_attempts=8),
    )

    assert result.attempts == 1
    assert result.failure_kind is HttpFailureKind.TRANSIENT_HTTP
    assert calls == 1


def test_permanent_safe_read_error_is_not_retried() -> None:
    calls = 0

    def request() -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, json={"error": "forbidden"})

    result = execute_http_request(
        request,
        provider="YouTube",
        operation=HttpOperationClass.SAFE_READ,
        method="GET",
        resource="channels.list",
        retry_policy=RetryPolicy(max_attempts=4),
    )

    assert result.attempts == 1
    assert result.failure_kind is HttpFailureKind.PERMANENT_HTTP
    assert calls == 1


def test_provider_transient_classifier_uses_same_bounded_policy() -> None:
    calls = 0
    sleeps: list[float] = []

    def request() -> httpx.Response:
        nonlocal calls
        calls += 1
        code = 6 if calls == 1 else None
        payload = {"error": {"error_code": code}} if code is not None else {"response": 1}
        return httpx.Response(200, json=payload)

    def classify(response: httpx.Response) -> HttpFailureKind | None:
        payload = response.json()
        return HttpFailureKind.PROVIDER_TRANSIENT if "error" in payload else None

    result = execute_http_request(
        request,
        provider="VK",
        operation=HttpOperationClass.SAFE_READ,
        method="POST",
        resource="video.get",
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.25, jitter_seconds=0.0),
        response_classifier=classify,
        sleep=sleeps.append,
    )

    assert result.attempts == 2
    assert calls == 2
    assert sleeps == [0.25]


def test_retry_after_supports_http_date_and_rejects_past_or_invalid_values() -> None:
    now_value = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)
    future = format_datetime(now_value + timedelta(seconds=7), usegmt=True)
    past = format_datetime(now_value - timedelta(seconds=1), usegmt=True)

    assert parse_retry_after_seconds(future, now=lambda: now_value) == 7.0
    assert parse_retry_after_seconds(past, now=lambda: now_value) is None
    assert parse_retry_after_seconds("not-a-date", now=lambda: now_value) is None


def test_rate_limiter_serializes_concurrent_callers_under_fake_clock() -> None:
    clock = FakeClock()
    limiter = RequestRateLimiter(1.0, monotonic=clock.monotonic, sleep=clock.sleep)
    observed: list[float] = []
    observed_lock = threading.Lock()

    def worker() -> None:
        acquired_at = limiter.wait()
        with observed_lock:
            observed.append(acquired_at)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(observed) == [0.0, 1.0, 2.0]
    assert clock.sleeps == [1.0, 1.0]


def test_redaction_removes_tokens_authorization_and_urls() -> None:
    message = (
        "Bearer abc123 access_token=secret refresh_token=refresh "
        "client_secret=client https://upload.example/private/path"
    )
    safe = redact_sensitive_text(message, secrets=("abc123", "secret", "refresh", "client"))

    assert "abc123" not in safe
    assert "secret" not in safe
    assert "refresh" not in safe
    assert "upload.example" not in safe
    assert "<redacted>" in safe
    assert "<url>" in safe
