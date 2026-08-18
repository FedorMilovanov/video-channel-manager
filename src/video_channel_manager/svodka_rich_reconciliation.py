from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence, cast

from video_channel_manager import svodka_rich_production as legacy
from video_channel_manager.svodka_rich_successor import build_document, load_ledger, load_release, release_digest
from video_channel_manager.telegram_rich_provider import TelegramRichProviderOutcome

_MEDIA_BLOCK_FIELDS = {
    "animation": "animation",
    "audio": "audio",
    "photo": "photo",
    "video": "video",
    "voice_note": "voice_note",
}
_RICH_TEXT_FIELDS = frozenset({"text", "credit", "summary"})


def _semantic_value(value: Any) -> Any:
    if isinstance(value, dict):
        block_type = value.get("type")
        media_field = _MEDIA_BLOCK_FIELDS.get(block_type) if isinstance(block_type, str) else None
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if media_field is not None and key == media_field:
                normalized[key] = {"verified_exact_media": block_type}
            elif key in _RICH_TEXT_FIELDS:
                normalized[key] = _semantic_rich_text(child)
            else:
                normalized[key] = _semantic_value(child)
        return normalized
    if isinstance(value, list):
        return [_semantic_value(item) for item in value]
    return value


def _semantic_rich_text(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _semantic_value(value)
    if not isinstance(value, list):
        return value

    normalized: list[Any] = []
    for item in value:
        child = _semantic_rich_text(item) if isinstance(item, (str, dict, list)) else item
        if isinstance(child, str) and normalized and isinstance(normalized[-1], str):
            normalized[-1] += child
        else:
            normalized.append(child)
    if len(normalized) == 1 and isinstance(normalized[0], str):
        return normalized[0]
    return normalized


def semantic_structure_sha256(value: dict[str, Any]) -> str:
    """Hash visible rich semantics after one reviewed Telegram normalization.

    Only adjacent plain-string fragments inside RichText fields are coalesced.
    Entity dictionaries remain hard boundaries. Media payloads are masked here
    only because reconciliation separately requires the archived provider's
    exact media-verification digest to match the reviewed document.
    """

    return legacy._sha(_semantic_value(value))


def _authorization(path: Path) -> dict[str, Any]:
    value = legacy._read(path)
    if (
        value.get("schema_name") != "video-channel-manager.svodka-rich-successor-reconciliation-authorization"
        or value.get("schema_version") != 1
        or value.get("release_id") != "svodka-rich-v2-successor-2026-08"
        or value.get("provider_access_authorized") is not False
        or value.get("provider_write_authorized") is not False
        or value.get("replay_authorized") is not False
        or value.get("approved") is not True
    ):
        raise ValueError("invalid Svodka reconciliation authorization")
    return value


def reconcile_archived(
    root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    intent: dict[str, Any],
    outcome: TelegramRichProviderOutcome | SimpleNamespace,
    authorization: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    publication_id = str(authorization["publication_id"])
    expected_message_id = int(authorization["observed_message_id"])
    expected_run_id = str(authorization["workflow_run_id"])
    expected_attempt = str(authorization["workflow_run_attempt"])

    if (
        authorization.get("release_sha256") != release_digest(release)
        or intent.get("release_sha256") != release_digest(release)
        or intent.get("publication_id") != publication_id
        or intent.get("workflow_run_id") != expected_run_id
        or intent.get("workflow_run_attempt") != expected_attempt
        or intent.get("dispatch_mode") != "canary"
        or intent.get("mutation_request_limit") != 1
        or intent.get("automatic_retry_allowed") is not False
        or intent.get("blind_retry_allowed") is not False
    ):
        raise ValueError("reconciliation authorization differs from the exact durable intent")

    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[publication_id]
    if (
        entry.get("state") != "may_exist"
        or entry.get("provider_effect") != "may_exist"
        or entry.get("dispatch_mode") != "canary"
        or str(entry.get("workflow_run_id")) != expected_run_id
        or str(entry.get("workflow_run_attempt")) != expected_attempt
        or entry.get("document_sha256") != intent.get("document_sha256")
        or entry.get("message_id") is not None
        or entry.get("message_url") is not None
    ):
        raise ValueError("durable successor ledger is not the exact ambiguous canary state")

    item = next(
        (
            raw
            for raw in cast(list[dict[str, Any]], release["items"])
            if raw.get("publication_id") == publication_id
        ),
        None,
    )
    if item is None:
        raise ValueError("reconciliation publication is absent from the exact release")
    document, render, _article = build_document(root, release, item)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("reviewed document differs from the exact durable intent")

    if (
        outcome.publication_id != publication_id
        or outcome.provider_effect != "may_exist"
        or outcome.dispatch_phase != "response_received"
        or outcome.http_status_code != 200
        or outcome.provider_call_count != 1
        or outcome.mutation_request_count != 1
        or outcome.automatic_retry_allowed is not False
        or outcome.bot_identity_verification != "exact_same_credential"
        or outcome.provider_write_gate_verified is not True
        or outcome.exact_target_binding_verified is not True
        or outcome.returned_chat_verified is not True
        or outcome.observed_message_id != expected_message_id
        or outcome.observed_chat_id != document.target.chat_id
        or (outcome.observed_chat_username or "").casefold() != document.target.chat_username.casefold()
        or outcome.message_id is not None
        or outcome.message_url is not None
        or outcome.structure_verification != "mismatch"
        or outcome.media_verification != "exact"
        or outcome.returned_rich_message is None
    ):
        raise ValueError("archived provider outcome is not the exact one-response ambiguous publication")

    if (
        outcome.document_sha256 != intent.get("document_sha256")
        or outcome.input_rich_message_sha256 != document.input_rich_message_sha256
        or outcome.expected_rich_structure_sha256 != document.expected_rich_structure_sha256
        or outcome.expected_media_sha256 != document.expected_media_sha256
        or outcome.returned_media_sha256 != document.expected_media_sha256
        or tuple(outcome.provider_assigned_media_paths) != tuple(document.provider_assigned_media_paths)
        or outcome.target_proof_sha256 != intent.get("target_proof_sha256")
        or outcome.expected_chat_id != document.target.chat_id
        or outcome.expected_bot_id != document.target.bot_id
        or outcome.target_binding_sha256 != document.target.target_binding_sha256
    ):
        raise ValueError("archived provider evidence differs from the exact reviewed document or intent")

    expected_semantic_sha256 = semantic_structure_sha256(document.expected_returned_rich_message)
    returned_semantic_sha256 = semantic_structure_sha256(outcome.returned_rich_message)
    if returned_semantic_sha256 != expected_semantic_sha256:
        raise ValueError("returned RichMessage differs semantically from the reviewed document")

    message_url = f"https://t.me/{document.target.chat_username}/{expected_message_id}"
    proof = {
        "schema_name": "video-channel-manager.svodka-rich-successor-reconciliation",
        "schema_version": 1,
        "release_id": release["release_id"],
        "release_sha256": release_digest(release),
        "publication_id": publication_id,
        "workflow_run_id": expected_run_id,
        "workflow_run_attempt": expected_attempt,
        "document_sha256": document.document_sha256,
        "archived_outcome_sha256": outcome.outcome_sha256,
        "observed_message_id": expected_message_id,
        "message_url": message_url,
        "strict_expected_rich_structure_sha256": outcome.expected_rich_structure_sha256,
        "strict_returned_rich_structure_sha256": outcome.returned_rich_structure_sha256,
        "semantic_rich_structure_sha256": expected_semantic_sha256,
        "media_sha256": outcome.expected_media_sha256,
        "normalization": "coalesce adjacent plain strings inside RichText fields only; entity dictionaries remain boundaries",
        "target_verified": True,
        "media_verified": True,
        "provider_access_performed": False,
        "provider_write_performed": False,
        "replay_performed": False,
    }

    entry.update(
        {
            "state": "published",
            "provider_effect": "verified",
            "message_id": expected_message_id,
            "message_url": message_url,
            "error": None,
        }
    )
    return proof, ledger


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provider-free Svodka archived RichMessage reconciliation")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--proof-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    release = load_release(args.release, args.root)
    ledger = load_ledger(args.ledger, release)
    intent = legacy._read(args.intent)
    outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
    authorization = _authorization(args.authorization)
    proof, ledger = reconcile_archived(args.root, release, ledger, intent, outcome, authorization)
    legacy._write(args.ledger, ledger)
    legacy._write(args.proof_output, proof)
    print(
        json.dumps(
            {
                "publication_id": proof["publication_id"],
                "message_id": proof["observed_message_id"],
                "message_url": proof["message_url"],
                "provider_access_performed": False,
                "provider_write_performed": False,
                "replay_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
