from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import cast

import httpx

_MAX_PROVIDER_DETAIL_CHARS = 512
_RUPLOAD_URL_PATTERN = re.compile(r"https://rupload\.facebook\.com/[^\s\"'<>]+", re.IGNORECASE)
_AUTH_VALUE_PATTERN = re.compile(r"(?i)\b(?:OAuth|Bearer)\s+[^\s,;]+")
_ACCESS_TOKEN_PATTERN = re.compile(r"(?i)(access_token\s*[=:]\s*)[^\s&;,]+")


@dataclass(frozen=True, slots=True)
class ResumablePhaseFailure:
    """Provider-visible terminal failure hidden below a container's top-level status."""

    phase: str
    status: str
    error_code: str | None
    error_message: str | None
    bytes_transferred: int | None = None
    source_file_size: int | None = None

    def durable_message(self) -> str:
        parts = [f"Instagram resumable {self.phase} phase reported {self.status}"]
        if self.bytes_transferred is not None:
            parts.append(f"bytes_transferred={self.bytes_transferred}")
        if self.source_file_size is not None:
            parts.append(f"source_file_size={self.source_file_size}")
        if self.error_code is not None:
            parts.append(f"provider_error_code={self.error_code}")
        if self.error_message:
            parts.append(f"provider_error_message={self.error_message}")
        return "; ".join(parts)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _phase_failure(phase_name: str, raw_phase: object) -> ResumablePhaseFailure | None:
    if not isinstance(raw_phase, dict):
        return None
    status = raw_phase.get("status")
    if not isinstance(status, str) or status.strip().lower() != "error":
        return None

    error_code: str | None = None
    error_message: str | None = None
    raw_errors = raw_phase.get("errors")
    if isinstance(raw_errors, list):
        messages: list[str] = []
        codes: list[str] = []
        for raw_error in raw_errors:
            if not isinstance(raw_error, dict):
                continue
            raw_code = raw_error.get("code")
            if raw_code is not None:
                codes.append(str(raw_code))
            raw_message = raw_error.get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                messages.append(raw_message.strip())
        if codes:
            error_code = ",".join(codes)
        if messages:
            error_message = " | ".join(messages)

    return ResumablePhaseFailure(
        phase=phase_name,
        status=status.strip().lower(),
        error_code=error_code,
        error_message=error_message,
        bytes_transferred=_optional_int(raw_phase.get("bytes_transferred")),
        source_file_size=_optional_int(raw_phase.get("source_file_size")),
    )


def extract_resumable_phase_failure(payload: dict[str, object]) -> ResumablePhaseFailure | None:
    """Return the first terminal upload/processing phase even when status_code remains IN_PROGRESS."""

    raw_video_status = payload.get("video_status")
    if not isinstance(raw_video_status, dict):
        return None

    upload_failure = _phase_failure("uploading", raw_video_status.get("uploading_phase"))
    if upload_failure is not None:
        return upload_failure
    return _phase_failure("processing", raw_video_status.get("processing_phase"))


def _secret_safe_detail(value: str, *, secret: str, upload_uri: str | None = None) -> str:
    detail = " ".join(value.split())
    if secret:
        detail = detail.replace(secret, "[REDACTED_TOKEN]")
    if upload_uri:
        detail = detail.replace(upload_uri, "[REDACTED_UPLOAD_URI]")
    detail = _RUPLOAD_URL_PATTERN.sub("[REDACTED_UPLOAD_URI]", detail)
    detail = _AUTH_VALUE_PATTERN.sub("[REDACTED_AUTHORIZATION]", detail)
    detail = _ACCESS_TOKEN_PATTERN.sub(r"\1[REDACTED_TOKEN]", detail)
    return detail


def secret_safe_exception_detail(
    exc: BaseException,
    *,
    secret: str,
    upload_uri: str | None = None,
) -> str:
    detail = str(exc).strip() or type(exc).__name__
    return _secret_safe_detail(detail, secret=secret, upload_uri=upload_uri)


def _bounded_detail(value: str) -> str:
    if len(value) <= _MAX_PROVIDER_DETAIL_CHARS:
        return value
    return value[: _MAX_PROVIDER_DETAIL_CHARS - 3] + "..."


def _json_payload(response: httpx.Response) -> dict[str, object] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return cast(dict[str, object], payload) if isinstance(payload, dict) else None


def provider_http_retryable(response: httpx.Response) -> bool | None:
    """Return Meta's explicit retryability decision when present in JSON diagnostics."""

    payload = _json_payload(response)
    if payload is None:
        return None
    raw_debug = payload.get("debug_info")
    if isinstance(raw_debug, dict):
        raw_retriable = raw_debug.get("retriable")
        if isinstance(raw_retriable, bool):
            return raw_retriable
    raw_error = payload.get("error")
    if isinstance(raw_error, dict):
        raw_retriable = raw_error.get("retriable")
        if isinstance(raw_retriable, bool):
            return raw_retriable
    return None


def describe_provider_http_error(
    response: httpx.Response,
    *,
    secret: str,
    upload_uri: str,
    prefix: str,
) -> tuple[str, str | None]:
    """Preserve bounded Meta diagnostics without leaking credentials or the one-time upload URI."""

    payload = _json_payload(response)
    error_code: str | None = None
    summaries: list[str] = []

    if payload is not None:
        raw_error = payload.get("error")
        if isinstance(raw_error, dict):
            raw_code = raw_error.get("code")
            if raw_code is not None:
                error_code = str(raw_code)
            raw_subcode = raw_error.get("error_subcode")
            raw_message = raw_error.get("message")
            raw_user_message = raw_error.get("error_user_msg")
            if isinstance(raw_message, str) and raw_message.strip():
                summaries.append(raw_message.strip())
            elif isinstance(raw_user_message, str) and raw_user_message.strip():
                summaries.append(raw_user_message.strip())
            if raw_subcode is not None:
                summaries.append(f"subcode={raw_subcode}")
        elif isinstance(raw_error, str) and raw_error.strip():
            summaries.append(raw_error.strip())

        if error_code is None:
            raw_code = payload.get("code")
            if raw_code is not None:
                error_code = str(raw_code)

        raw_debug = payload.get("debug_info")
        if isinstance(raw_debug, dict):
            raw_type = raw_debug.get("type")
            raw_message = raw_debug.get("message")
            if raw_type is not None:
                summaries.append(f"type={raw_type}")
                if error_code is None:
                    error_code = str(raw_type)
            if isinstance(raw_message, str) and raw_message.strip():
                summaries.append(raw_message.strip())

        if not summaries:
            raw_message = payload.get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                summaries.append(raw_message.strip())

    parts = [f"{prefix} returned HTTP {response.status_code}"]
    if summaries:
        safe_summary = _secret_safe_detail("; ".join(summaries), secret=secret, upload_uri=upload_uri)
        if safe_summary:
            parts.append(_bounded_detail(safe_summary))

    if payload is not None:
        raw_body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        raw_body = response.text
    safe_body = _bounded_detail(_secret_safe_detail(raw_body, secret=secret, upload_uri=upload_uri))
    if safe_body:
        parts.append(f"body={safe_body}")

    request_id = response.headers.get("x-fb-request-id")
    trace_id = response.headers.get("x-fb-trace-id")
    if request_id:
        parts.append(f"x-fb-request-id={_secret_safe_detail(request_id, secret=secret, upload_uri=upload_uri)}")
    if trace_id:
        parts.append(f"x-fb-trace-id={_secret_safe_detail(trace_id, secret=secret, upload_uri=upload_uri)}")

    return "; ".join(parts), error_code


__all__ = [
    "ResumablePhaseFailure",
    "describe_provider_http_error",
    "extract_resumable_phase_failure",
    "provider_http_retryable",
    "secret_safe_exception_detail",
]
