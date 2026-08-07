"""Guarded @lordchrist Telegram publication facade.

The public API stays in one repository-owned module while the implementation is
split into immutable models, strict state transitions, and provider transport.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from video_channel_manager import telegram_state as _state
from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    DEFAULT_API_BASE,
    MAX_TELEGRAM_TEXT_LENGTH,
    PRIMARY_SOURCE_HOSTS,
    PROJECT_KEY,
    PUBLICATION_TIMEZONE,
    DispatchEnvelope,
    DispatchMode,
    LedgerEntry,
    PreparedDispatch,
    ProviderEffect,
    SourceProof,
    StateName,
    TargetProof,
    TelegramLedger,
    TelegramPost,
    TelegramQueue,
)
from video_channel_manager.telegram_state import (
    initialize_ledger,
    initialize_ledger_file,
    load_dispatch,
    load_queue,
    load_target_proof,
    prepare_next,
    preview_next,
    publication_local_date,
    require_execution_enabled,
    require_preflight_config,
    resolve_entry,
    save_model,
    strict_next_post,
    utc_now,
    verify_dispatch_against_queue,
    verify_persisted_intent,
)
from video_channel_manager.telegram_transport import TelegramApiError, dispatch_prepared, preflight_target


def _precheck_ledger_identity(path: Path, queue: TelegramQueue) -> None:
    """Report queue-binding failures before low-level schema details obscure them."""

    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return

    recorded_digest = payload.get("queue_digest")
    if isinstance(recorded_digest, str) and recorded_digest != queue.digest:
        raise ValueError("queue digest differs from the immutable digest recorded in the ledger")

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return

    queue_by_id = {post.publication_id: post for post in queue.posts}
    entry_ids = set(entries)
    queue_ids = set(queue_by_id)
    missing_ids = sorted(queue_ids - entry_ids)
    extra_ids = sorted(entry_ids - queue_ids)
    if missing_ids or extra_ids:
        raise ValueError(
            f"ledger publication coverage differs from immutable queue; missing={missing_ids}, extra={extra_ids}"
        )

    for publication_id, post in queue_by_id.items():
        raw_entry = entries.get(publication_id)
        if isinstance(raw_entry, dict) and raw_entry.get("payload_sha256") != post.payload_sha256:
            raise ValueError(f"payload changed after ledger initialization: {publication_id}")


def load_ledger(path: Path, queue: TelegramQueue) -> TelegramLedger:
    _precheck_ledger_identity(path, queue)
    return _state.load_ledger(path, queue)


def load_or_initialize_ledger(path: Path, queue: TelegramQueue) -> TelegramLedger:
    """Backward-compatible name with intentionally strict production semantics."""

    return load_ledger(path, queue)


def save_ledger(path: Path, ledger: TelegramLedger) -> None:
    """Persist only schema-valid state while keeping operator diagnostics precise."""

    for publication_id, entry in ledger.entries.items():
        if entry.state == "published" and (entry.message_id is None or entry.message_id <= 0):
            raise ValidationError.from_exception_data(
                "TelegramLedger",
                [
                    {
                        "type": "value_error",
                        "loc": ("entries", publication_id, "message_id"),
                        "input": entry.message_id,
                        "ctx": {"error": ValueError("published entries require a positive message_id")},
                    }
                ],
            )
    _state.save_ledger(path, ledger)


__all__ = [
    "CHANNEL_USERNAME",
    "DEFAULT_API_BASE",
    "MAX_TELEGRAM_TEXT_LENGTH",
    "PRIMARY_SOURCE_HOSTS",
    "PROJECT_KEY",
    "PUBLICATION_TIMEZONE",
    "DispatchEnvelope",
    "DispatchMode",
    "LedgerEntry",
    "PreparedDispatch",
    "ProviderEffect",
    "SourceProof",
    "StateName",
    "TargetProof",
    "TelegramApiError",
    "TelegramLedger",
    "TelegramPost",
    "TelegramQueue",
    "dispatch_prepared",
    "initialize_ledger",
    "initialize_ledger_file",
    "load_dispatch",
    "load_ledger",
    "load_or_initialize_ledger",
    "load_queue",
    "load_target_proof",
    "preflight_target",
    "prepare_next",
    "preview_next",
    "publication_local_date",
    "require_execution_enabled",
    "require_preflight_config",
    "resolve_entry",
    "save_ledger",
    "save_model",
    "strict_next_post",
    "utc_now",
    "verify_dispatch_against_queue",
    "verify_persisted_intent",
]
