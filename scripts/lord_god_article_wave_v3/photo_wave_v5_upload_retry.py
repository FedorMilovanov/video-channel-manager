from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from . import mutations
from . import photo_wave_v5 as v5
from .common import bytes_sha

SAFE_UPLOAD_MAX_ATTEMPTS = 3
SAFE_UPLOAD_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_SAFE_UPLOAD_STAGES = frozenset({"photo_upload_intent", "photo_upload_failed"})
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)

_original_prepare_photo_token = v5.prepare_photo_token


def _error_summary(exc: BaseException) -> str:
    """Return a bounded error string without upload URLs or query secrets."""

    value = f"{type(exc).__name__}: {exc}"
    value = _URL_RE.sub("<redacted-url>", value)
    return value[:500]


def _entry(journal: dict[str, Any], operation_id: str) -> dict[str, Any]:
    operations = journal.get("operations")
    if not isinstance(operations, dict):
        return {}
    value = operations.get(operation_id)
    return value if isinstance(value, dict) else {}


def _safe_to_retry_upload(entry: dict[str, Any]) -> bool:
    """Allow another attempt only while no persistent VK mutation can exist."""

    stage = str(entry.get("stage") or "")
    return (
        stage in _SAFE_UPLOAD_STAGES
        and entry.get("post_id") in (None, "")
        and not entry.get("photo_token")
        and not isinstance(entry.get("upload_payload"), dict)
    )


def prepare_photo_token(
    *,
    operation: dict[str, Any],
    jpeg: bytes,
    read_client: Any,
    mutation_client: Any,
    journal: dict[str, Any],
    journal_path: Path,
) -> str:
    """Retry only the disposable upload phase, using a fresh VK upload URL each time."""

    operation_id = str(operation["operation_id"])
    initial = _entry(journal, operation_id)
    initial_stage = str(initial.get("stage") or "")

    # Establish an explicit pre-mutation checkpoint. This is safe to replace on
    # restart because no photos.saveWallPhoto or wall.post call has occurred.
    if initial_stage in {"", "photo_upload_intent", "photo_upload_failed"}:
        mutations.set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_upload_intent",
            asset_sha256=bytes_sha(jpeg),
            upload_retry_policy="fresh-upload-url-before-save-only",
            upload_attempts_allowed=SAFE_UPLOAD_MAX_ATTEMPTS,
            upload_attempts_exhausted=False,
            error=None,
        )

    attempts: list[dict[str, object]] = []
    for attempt in range(1, SAFE_UPLOAD_MAX_ATTEMPTS + 1):
        try:
            token = _original_prepare_photo_token(
                operation=operation,
                jpeg=jpeg,
                read_client=read_client,
                mutation_client=mutation_client,
                journal=journal,
                journal_path=journal_path,
            )
        except Exception as exc:
            current = _entry(journal, operation_id)
            if not _safe_to_retry_upload(current):
                raise

            summary = _error_summary(exc)
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "safe_upload_failed",
                    "error": summary,
                }
            )
            exhausted = attempt >= SAFE_UPLOAD_MAX_ATTEMPTS
            mutations.set_journal_stage(
                journal,
                journal_path,
                operation,
                "photo_upload_failed",
                asset_sha256=bytes_sha(jpeg),
                upload_retry_policy="fresh-upload-url-before-save-only",
                upload_attempts_allowed=SAFE_UPLOAD_MAX_ATTEMPTS,
                upload_attempt_count=attempt,
                upload_attempts=attempts,
                upload_attempts_exhausted=exhausted,
                error=summary,
            )
            if exhausted:
                raise RuntimeError(
                    "VK photo upload failed safely after three attempts; "
                    "photos.saveWallPhoto and wall.post were not attempted: "
                    f"{operation_id}"
                ) from exc

            time.sleep(SAFE_UPLOAD_RETRY_DELAYS_SECONDS[attempt - 1])
            # The base implementation sees photo_upload_failed and obtains a
            # new photos.getWallUploadServer URL on the next iteration.
            continue

        attempts.append(
            {
                "attempt": attempt,
                "status": "uploaded_and_saved",
            }
        )
        mutations.set_journal_stage(
            journal,
            journal_path,
            operation,
            "photo_saved",
            photo_token=token,
            upload_retry_policy="fresh-upload-url-before-save-only",
            upload_attempts_allowed=SAFE_UPLOAD_MAX_ATTEMPTS,
            upload_attempt_count=attempt,
            upload_attempts=attempts,
            upload_attempts_exhausted=False,
            error=None,
        )
        return token

    raise AssertionError("unreachable upload retry state")


def install() -> None:
    """Install the retry hook only for the active inherited v5 executor."""

    v5.base.prepare_photo_token = prepare_photo_token
