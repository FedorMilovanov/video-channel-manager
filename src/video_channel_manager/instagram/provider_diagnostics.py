from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

import httpx

_MAX_DIAGNOSTIC_BODY_CHARS = 4_000


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


def redact_secret(value: str, secret: str) -> str:
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")


def secret_safe_exception_detail(exc: BaseException, *, secret: str) -> str:
    detail = str(exc).strip()
    if not detail:
        detail = type(exc).__name__
    return redact_secret(detail, secret)


def _response_body(response: httpx.Response, *, secret: str) -> str:
    raw = response.text
    safe = redact_secret(raw, secret)
    if len(safe) > _MAX_DIAGNOSTIC_BODY_CHARS:
        safe = safe[:_MAX_DIAGNOSTIC_BODY_CHARS] + "...[truncated]"
    return safe


def _json_payload(response: httpx.Response) -> dict[str, object] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return cast(dict[str, object], payload) if isinstance(payload, dict) else None


def describe_provider_http_error(
    response: httpx.Response,
    *,
    secret: str,
    prefix: str,
) -> tuple[str, str | None]:
    """Preserve useful Meta diagnostics while guaranteeing the configured token is redacted."""

    payload = _json_payload(response)
    error_code: str | None = None
    summary: str | None = None

    if payload is not None:
        raw_error = payload.get("error")
        if isinstance(raw_error, dict):
            raw_message = raw_error.get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                summary = raw_message.strip()
            raw_code = raw_error.get("code")
            if raw_code is not None:
                error_code = str(raw_code)
            raw_subcode = raw_error.get("error_subcode")
            if raw_subcode is not None:
                suffix = f"subcode={raw_subcode}"
                summary = f"{summary}; {suffix}" if summary else suffix

        raw_debug = payload.get("debug_info")
        if isinstance(raw_debug, dict):
            raw_message = raw_debug.get("message")
            raw_type = raw_debug.get("type")
            debug_parts: list[str] = []
            if raw_type is not None:
                debug_parts.append(f"type={raw_type}")
                if error_code is None:
                    error_code = str(raw_type)
            if isinstance(raw_message, str) and raw_message.strip():
                debug_parts.append(raw_message.strip())
            if debug_parts:
                debug_text = "; ".join(debug_parts)
                summary = f"{summary}; {debug_text}" if summary else debug_text

        if summary is None:
            raw_message = payload.get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                summary = raw_message.strip()

    summary = redact_secret(summary or f"{prefix} returned HTTP {response.status_code}", secret)
    parts = [summary, f"HTTP {response.status_code}"]

    body = _response_body(response, secret=secret)
    if body:
        # Compact JSON produces a durable, operator-readable diagnostic without newline noise.
        if payload is not None:
            body = redact_secret(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), secret)
            if len(body) > _MAX_DIAGNOSTIC_BODY_CHARS:
                body = body[:_MAX_DIAGNOSTIC_BODY_CHARS] + "...[truncated]"
        parts.append(f"body={body}")

    request_id = response.headers.get("x-fb-request-id")
    trace_id = response.headers.get("x-fb-trace-id")
    if request_id:
        parts.append(f"x-fb-request-id={redact_secret(request_id, secret)}")
    if trace_id:
        parts.append(f"x-fb-trace-id={redact_secret(trace_id, secret)}")

    return "; ".join(parts), error_code
