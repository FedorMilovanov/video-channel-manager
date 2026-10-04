from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, build_depth_runtime_queue
from video_channel_manager.telegram_quote_v4_render_proof import build_render_proof

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
ACTIVATION = CONTENT / "successor-depth-runtime-activation-v4.json"
V4_POLICY = CONTENT / "presentation-policy-v4.json"
V3_POLICY = CONTENT / "presentation-policy-v3.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
ATTEMPTED_AT = datetime(2026, 9, 19, 10, 56, 0, tzinfo=UTC)


def _depth_queue():
    return build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )


def _published_entry(publication_id: str, payload_sha256: str, message_id: int, intent_seed: int = 0) -> LedgerEntry:
    published_at = ATTEMPTED_AT + timedelta(seconds=4)
    return LedgerEntry(
        publication_id=publication_id,
        payload_sha256=payload_sha256,
        state="published",
        provider_effect="verified",
        intent_id=f"{intent_seed:031x}a",
        dispatch_mode="scheduled",
        scheduled_slot="morning",
        workflow_run_id="37120208117",
        workflow_run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="b" * 40,
        attempted_at_utc=ATTEMPTED_AT,
        published_at_utc=published_at,
        message_id=message_id,
        message_url=f"https://t.me/lordchrist/{message_id}",
        actual_chat_id=CHAT_ID,
        actual_chat_username="lordchrist",
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )


def _state_paths(tmp_path: Path, *, published_prefix: int = 15) -> tuple[Path, Path]:
    queue = _depth_queue()
    queue_path = tmp_path / "lordchrist-successor-depth-v2-runtime-queue.json"
    queue_path.write_text(queue.model_dump_json(indent=2) + "\n", encoding="utf-8")

    entries: dict[str, LedgerEntry] = {}
    for index, post in enumerate(queue.posts):
        if index < published_prefix:
            entries[post.publication_id] = _published_entry(
                post.publication_id, post.payload_sha256, 1534 + index, intent_seed=index
            )
        else:
            entries[post.publication_id] = LedgerEntry(
                publication_id=post.publication_id,
                payload_sha256=post.payload_sha256,
            )
    ledger = TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        queue_digest=queue.digest,
        entries=entries,
    )
    assert ledger.queue_digest == DEPTH_QUEUE_DIGEST
    ledger_path = tmp_path / "successor-depth-v2-publication-ledger.json"
    ledger_path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return queue_path, ledger_path


def _activation_copy(tmp_path: Path, **updates: object) -> Path:
    payload = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    payload.update(updates)
    path = tmp_path / "successor-depth-runtime-activation-v4.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_render_proof_confirms_exact_next_publication_and_tight_reading_unit(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    proof = build_render_proof(
        queue_path=queue_path,
        ledger_path=ledger_path,
        presentation_policy_path=V4_POLICY,
        activation_path=ACTIVATION,
    )

    assert proof["release_id"] == "lordchrist-successor-depth-v2"
    assert proof["queue_digest"] == DEPTH_QUEUE_DIGEST
    assert proof["published_prefix"] == 15
    assert proof["pending_suffix"] == 45
    assert proof["next_sequence"] == 16
    assert proof["next_publication_id"] == "lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort"
    assert proof["entity_layout"] == ["bold", "blockquote", "italic"]
    assert proof["attribution_line_immediately_follows_quotation"] is True
    assert proof["provider_writes_authorized"] is False
    assert proof["rendered_text_length"] < 4096


def test_render_proof_rejects_stale_checkpoint_boundary(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    activation = _activation_copy(tmp_path, required_published_prefix=14, required_pending_suffix=46)

    with pytest.raises(ValueError, match="published prefix is 15, checkpoint requires 14"):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V4_POLICY,
            activation_path=activation,
        )


def test_render_proof_rejects_publication_that_skipped_the_strict_next_sequence(tmp_path: Path) -> None:
    # Sequence 15 is still pending while sequence 16 was already published: the
    # published/pending counts stay 15/45, so only the strict-order proof can
    # detect the skipped publication and it must fail closed.
    queue_path, ledger_path = _state_paths(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    queue = _depth_queue()
    skipped = queue.posts[14]
    later = queue.posts[15]
    payload["entries"][skipped.publication_id] = {
        "publication_id": skipped.publication_id,
        "payload_sha256": skipped.payload_sha256,
        "state": "pending",
        "provider_effect": "impossible",
    }
    payload["entries"][later.publication_id] = json.loads(
        _published_entry(later.publication_id, later.payload_sha256, 1600, intent_seed=99).model_dump_json()
    )
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        ValueError, match=r"strict next publication is sequence 15, but the verified published prefix is 15"
    ):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V4_POLICY,
            activation_path=ACTIVATION,
        )


def test_render_proof_rejects_non_pristine_pending_suffix(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    queue = _depth_queue()
    blocked = queue.posts[30]
    payload["entries"][blocked.publication_id] = json.loads(
        LedgerEntry(
            publication_id=blocked.publication_id,
            payload_sha256=blocked.payload_sha256,
            state="dispatching",
            provider_effect="may_exist",
            intent_id="f" * 32,
            dispatch_mode="scheduled",
            scheduled_slot="morning",
            workflow_run_id="37120208117",
            workflow_run_attempt="1",
            github_sha="c" * 40,
            github_workflow_sha="c" * 40,
            attempted_at_utc=ATTEMPTED_AT,
            actual_chat_id=CHAT_ID,
            actual_chat_username="lordchrist",
            bot_id=BOT_ID,
            bot_username=BOT_USERNAME,
        ).model_dump_json()
    )
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requires an exact published/pending ledger split"):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V4_POLICY,
            activation_path=ACTIVATION,
        )


def test_quote_v3_presentation_would_reintroduce_the_blank_air_defect(tmp_path: Path) -> None:
    """Document the original production defect and its exact v4 correction."""

    post = _depth_queue().posts[15]
    attribution = f"— {post.source.author}, «{post.source.work}»"

    v3_rendered = render_post(post, load_presentation_policy(V3_POLICY))
    v4_rendered = render_post(post, load_presentation_policy(V4_POLICY))

    assert f"\n\n{attribution}" in v3_rendered.text
    assert [entity.type for entity in v3_rendered.expected_entities] == ["blockquote", "italic"]
    assert f"\n\n{attribution}" not in v4_rendered.text
    assert [entity.type for entity in v4_rendered.expected_entities] == ["bold", "blockquote", "italic"]
