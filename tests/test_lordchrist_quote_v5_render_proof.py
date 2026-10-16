from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, build_depth_runtime_queue
from video_channel_manager.telegram_quote_progress import published_history_digest
from video_channel_manager.telegram_quote_v5_render_proof import build_render_proof

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
ACTIVATION = CONTENT / "successor-depth-runtime-activation-v5.json"
V5_POLICY = CONTENT / "presentation-policy-v5.json"
STANDALONE_REVIEW = CONTENT / "quote-standalone-review-v1.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
ATTEMPTED_AT = datetime(2026, 10, 17, 8, 17, 0, tzinfo=UTC)


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
        workflow_run_id=str(37120208117 + intent_seed),
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


def _state_paths(tmp_path: Path, *, published_prefix: int = 16) -> tuple[Path, Path]:
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
    _activation_copy(tmp_path, published_history_sha256=published_history_digest(ledger, 16))
    for post in queue.posts[15:published_prefix]:
        entry = ledger.entries[post.publication_id]
        evidence = tmp_path / "dispatches" / f"{entry.workflow_run_id}-{entry.workflow_run_attempt}" / "rendered.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(render_post(post, load_presentation_policy(V5_POLICY)).model_dump_json())
    return queue_path, ledger_path


def _activation_copy(tmp_path: Path, **updates: object) -> Path:
    payload = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    payload.update(updates)
    path = tmp_path / "successor-depth-runtime-activation-v5.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_render_proof_confirms_exact_next_publication_and_title_air(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    proof = build_render_proof(
        queue_path=queue_path,
        ledger_path=ledger_path,
        presentation_policy_path=V5_POLICY,
        activation_path=tmp_path / ACTIVATION.name,
        standalone_review_path=STANDALONE_REVIEW,
    )

    assert proof["published_prefix"] == 16
    assert proof["pending_suffix"] == 44
    assert proof["next_sequence"] == 17
    assert proof["next_publication_id"] == "lordchrist-successor-depth-v2-17-gurnall-defend-in-suffering"
    # Sequence 17 is a reviewed load-bearing opening: the proof must show the
    # title, the paragraph air before the quotation and the tight source line.
    assert proof["title_rendered"] is True
    assert proof["entity_layout"] == ["bold", "blockquote", "italic"]
    assert proof["attribution_line_immediately_follows_quotation"] is True
    assert proof["provider_payload_sha256"].startswith("sha256:")
    assert proof["provider_writes_authorized"] is True


def test_render_proof_binds_policy_title_set_to_the_reviewed_standalone_evidence(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    activation_path = tmp_path / ACTIVATION.name
    payload = json.loads(activation_path.read_text(encoding="utf-8"))
    payload["presentation_policy_sha256"] = "sha256:" + "f" * 64
    activation_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="presentation policy differs"):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V5_POLICY,
            activation_path=activation_path,
            standalone_review_path=STANDALONE_REVIEW,
        )


def test_render_proof_rejects_policy_title_bindings_drifting_from_the_review(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    drifted_policy = tmp_path / "drifting-policy.json"
    payload = json.loads(V5_POLICY.read_text(encoding="utf-8"))
    payload["reviewed_title_payload_sha256s"] = list(payload["reviewed_title_payload_sha256s"])[:1]
    drifted_policy.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=drifted_policy,
            activation_path=tmp_path / ACTIVATION.name,
            standalone_review_path=STANDALONE_REVIEW,
        )


def test_render_proof_tracks_verified_progress_beyond_the_v5_boundary(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path, published_prefix=17)
    proof = build_render_proof(
        queue_path=queue_path,
        ledger_path=ledger_path,
        presentation_policy_path=V5_POLICY,
        activation_path=tmp_path / ACTIVATION.name,
        standalone_review_path=STANDALONE_REVIEW,
    )

    assert proof["published_prefix"] == 17
    assert proof["pending_suffix"] == 43
    # Sequence 18 is self-contained: no title, quotation opens the post.
    assert proof["next_sequence"] == 18
    assert proof["title_rendered"] is False
    assert proof["entity_layout"] == ["blockquote", "italic"]
