from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from video_channel_manager.svodka_rich_reconciliation import reconcile_archived, semantic_structure_sha256
from video_channel_manager.svodka_rich_successor import build_document, load_release, new_ledger, release_digest

ROOT = Path(".")
RELEASE_PATH = Path("content/telegram/svodka/rich-v1/successor-release-2026-08.json")
WORKFLOW_PATH = Path(".github/workflows/svodka-rich-reconcile-message-28.yml")
PUBLICATION_ID = "svodka-rich-goldfish-three-second-memory-myth"
RUN_ID = "32147454449"
ATTEMPT = "1"
MESSAGE_ID = 28


def test_semantic_hash_coalesces_only_adjacent_plain_rich_text_strings() -> None:
    fragmented = {
        "blocks": [
            {"type": "heading", "size": 1, "text": ["🔬", " ", "Заголовок"]},
            {
                "type": "paragraph",
                "text": ["До ", {"type": "bold", "text": ["важ", "но"]}, " после"],
            },
        ]
    }
    telegram = {
        "blocks": [
            {"type": "heading", "size": 1, "text": "🔬 Заголовок"},
            {
                "type": "paragraph",
                "text": ["До ", {"type": "bold", "text": "важно"}, " после"],
            },
        ]
    }
    assert semantic_structure_sha256(fragmented) == semantic_structure_sha256(telegram)


def test_semantic_hash_keeps_entities_and_block_order_strict() -> None:
    expected = {
        "blocks": [
            {"type": "paragraph", "text": ["До ", {"type": "bold", "text": "факт"}]},
            {"type": "paragraph", "text": [{"type": "hashtag", "text": "#Сводка", "hashtag": "Сводка"}]},
        ]
    }
    flattened_entity = {
        "blocks": [
            {"type": "paragraph", "text": "До факт"},
            {"type": "paragraph", "text": [{"type": "hashtag", "text": "#Сводка", "hashtag": "Сводка"}]},
        ]
    }
    changed_hashtag = {
        "blocks": [
            {"type": "paragraph", "text": ["До ", {"type": "bold", "text": "факт"}]},
            {"type": "paragraph", "text": [{"type": "hashtag", "text": "#Сводка", "hashtag": "Наука"}]},
        ]
    }
    reordered = {"blocks": list(reversed(expected["blocks"]))}

    expected_hash = semantic_structure_sha256(expected)
    assert semantic_structure_sha256(flattened_entity) != expected_hash
    assert semantic_structure_sha256(changed_hashtag) != expected_hash
    assert semantic_structure_sha256(reordered) != expected_hash


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], SimpleNamespace]:
    release = load_release(RELEASE_PATH, ROOT)
    ledger = new_ledger(release)
    item = next(
        raw for raw in cast(list[dict[str, Any]], release["items"]) if raw["publication_id"] == PUBLICATION_ID
    )
    document, render, _article = build_document(ROOT, release, item)
    intent = {
        "release_sha256": release_digest(release),
        "publication_id": PUBLICATION_ID,
        "dispatch_mode": "canary",
        "workflow_run_id": RUN_ID,
        "workflow_run_attempt": ATTEMPT,
        "document_sha256": document.document_sha256,
        "render_sha256": render.render_sha256,
        "target_proof_sha256": "sha256:" + "1" * 64,
        "mutation_request_limit": 1,
        "automatic_retry_allowed": False,
        "blind_retry_allowed": False,
    }
    entry = cast(dict[str, dict[str, Any]], ledger["entries"])[PUBLICATION_ID]
    entry.update(
        {
            "state": "may_exist",
            "provider_effect": "may_exist",
            "dispatch_mode": "canary",
            "workflow_run_id": RUN_ID,
            "workflow_run_attempt": ATTEMPT,
            "document_sha256": document.document_sha256,
            "error": "strict rich structure mismatch",
        }
    )
    authorization = {
        "release_sha256": release_digest(release),
        "publication_id": PUBLICATION_ID,
        "workflow_run_id": RUN_ID,
        "workflow_run_attempt": ATTEMPT,
        "observed_message_id": MESSAGE_ID,
    }
    outcome = SimpleNamespace(
        publication_id=PUBLICATION_ID,
        provider_effect="may_exist",
        dispatch_phase="response_received",
        http_status_code=200,
        provider_call_count=1,
        mutation_request_count=1,
        automatic_retry_allowed=False,
        bot_identity_verification="exact_same_credential",
        provider_write_gate_verified=True,
        exact_target_binding_verified=True,
        returned_chat_verified=True,
        observed_message_id=MESSAGE_ID,
        observed_chat_id=document.target.chat_id,
        observed_chat_username=document.target.chat_username,
        message_id=None,
        message_url=None,
        structure_verification="mismatch",
        media_verification="exact",
        returned_rich_message=document.expected_returned_rich_message,
        document_sha256=document.document_sha256,
        input_rich_message_sha256=document.input_rich_message_sha256,
        expected_rich_structure_sha256=document.expected_rich_structure_sha256,
        expected_media_sha256=document.expected_media_sha256,
        returned_media_sha256=document.expected_media_sha256,
        provider_assigned_media_paths=document.provider_assigned_media_paths,
        target_proof_sha256=intent["target_proof_sha256"],
        expected_chat_id=document.target.chat_id,
        expected_bot_id=document.target.bot_id,
        target_binding_sha256=document.target.target_binding_sha256,
        returned_rich_structure_sha256="sha256:" + "2" * 64,
        outcome_sha256="sha256:" + "3" * 64,
    )
    return release, ledger, intent | {"authorization": authorization}, outcome


def test_provider_free_reconciliation_marks_only_exact_ambiguous_message_published() -> None:
    release, ledger, fixture, outcome = _fixture()
    authorization = cast(dict[str, Any], fixture.pop("authorization"))
    proof, reconciled = reconcile_archived(ROOT, release, ledger, fixture, outcome, authorization)

    entry = cast(dict[str, dict[str, Any]], reconciled["entries"])[PUBLICATION_ID]
    assert entry["state"] == "published"
    assert entry["provider_effect"] == "verified"
    assert entry["message_id"] == MESSAGE_ID
    assert entry["message_url"] == "https://t.me/deep_info_life/28"
    assert entry["error"] is None
    assert proof["provider_access_performed"] is False
    assert proof["provider_write_performed"] is False
    assert proof["replay_performed"] is False


def test_reconciliation_refuses_non_exact_media_even_when_text_matches() -> None:
    release, ledger, fixture, outcome = _fixture()
    authorization = cast(dict[str, Any], fixture.pop("authorization"))
    outcome.media_verification = "mismatch"

    with pytest.raises(ValueError, match="one-response ambiguous publication"):
        reconcile_archived(ROOT, release, ledger, fixture, outcome, authorization)


def test_reconciliation_workflow_has_no_telegram_or_secret_surface() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "secrets." not in workflow
    assert "SVODKA_TELEGRAM_BOT_TOKEN" not in workflow
    assert "sendRichMessage" not in workflow
    assert "provider_access_performed'] is False" in workflow
    assert "provider_write_performed'] is False" in workflow
    assert "replay_performed'] is False" in workflow
    assert "EXPECTED_INTENT_BLOB" in workflow
    assert "EXPECTED_OUTCOME_BLOB" in workflow
