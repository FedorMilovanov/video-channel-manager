from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, build_depth_runtime_queue
from video_channel_manager.telegram_quote_v4_render_proof import build_render_proof
from video_channel_manager.telegram_quote_progress import published_history_digest

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
    _activation_copy(tmp_path, published_history_sha256=published_history_digest(ledger, 15))
    for post in queue.posts[15:published_prefix]:
        entry = ledger.entries[post.publication_id]
        evidence = tmp_path / "dispatches" / f"{entry.workflow_run_id}-{entry.workflow_run_attempt}" / "rendered.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(render_post(post, load_presentation_policy(V4_POLICY)).model_dump_json())
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
        activation_path=tmp_path / ACTIVATION.name,
    )

    assert proof["release_id"] == "lordchrist-successor-depth-v2"
    assert proof["queue_digest"] == DEPTH_QUEUE_DIGEST
    assert proof["published_prefix"] == 15
    assert proof["pending_suffix"] == 45
    assert proof["next_sequence"] == 16
    assert proof["next_publication_id"] == "lordchrist-successor-depth-v2-16-spurgeon-sovereignty-comfort"
    assert proof["entity_layout"] == ["bold", "blockquote", "italic"]
    assert proof["attribution_line_immediately_follows_quotation"] is True
    # The proof reports the reviewed authorization state of the checkpoint it was bound
    # to; it never dispatches, so building it stays read-only in either state.
    assert (
        proof["provider_writes_authorized"]
        == json.loads(ACTIVATION.read_text(encoding="utf-8"))["provider_writes_authorized"]
    )
    assert proof["rendered_text_length"] < 4096


def test_render_proof_is_read_only_for_an_authorized_checkpoint(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    before = ledger_path.read_bytes()

    proof = build_render_proof(
        queue_path=queue_path,
        ledger_path=ledger_path,
        presentation_policy_path=V4_POLICY,
        activation_path=tmp_path / ACTIVATION.name,
    )

    assert proof["provider_writes_authorized"] is True
    assert proof["next_sequence"] == 16
    assert ledger_path.read_bytes() == before


def test_render_proof_rejects_stale_checkpoint_boundary(tmp_path: Path) -> None:
    queue_path, ledger_path = _state_paths(tmp_path)
    activation = _activation_copy(
        tmp_path,
        schema_version=1,
        progress_policy="exact_checkpoint",
        published_history_sha256=None,
        required_published_prefix=14,
        required_pending_suffix=46,
    )

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

    with pytest.raises(ValueError, match="immutable published history differs"):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V4_POLICY,
            activation_path=tmp_path / ACTIVATION.name,
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

    with pytest.raises(ValueError, match="requires pristine pending suffix"):
        build_render_proof(
            queue_path=queue_path,
            ledger_path=ledger_path,
            presentation_policy_path=V4_POLICY,
            activation_path=tmp_path / ACTIVATION.name,
        )


def test_quote_v3_presentation_would_reintroduce_the_blank_air_defect(tmp_path: Path) -> None:
    """Document the original production defect and its exact v4 correction."""

    post = _depth_queue().posts[15]
    attribution = f"— {post.attribution_text}"

    v3_rendered = render_post(post, load_presentation_policy(V3_POLICY))
    v4_rendered = render_post(post, load_presentation_policy(V4_POLICY))

    assert f"\n\n{attribution}" in v3_rendered.text
    assert [entity.type for entity in v3_rendered.expected_entities] == ["blockquote", "italic"]
    assert f"\n\n{attribution}" not in v4_rendered.text
    assert [entity.type for entity in v4_rendered.expected_entities] == ["bold", "blockquote", "italic"]


# Continuous-production regressions for #692. Every positional boundary is exercised,
# including the old 15->16->17 dead-end and natural queue exhaustion.
def _checkpoint_kwargs(tmp_path: Path, ledger_path: Path) -> dict:
    return dict(
        activation_path=tmp_path / ACTIVATION.name,
        presentation_policy_path=V4_POLICY,
        v3_policy_path=V3_POLICY,
        migration_path=CONTENT / "successor-depth-presentation-migration-v1.json",
        source_web_audit_path=CONTENT / "quote-source-web-audit-v2.json",
        source_live_probe_path=CONTENT / "quote-source-live-probe-v2.json",
        ledger_path=ledger_path,
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
        depth_audit_path=CONTENT / "quote-depth-audit-v1.json",
        replacements_path=CONTENT / "quote-depth-replacements-v1.json",
    )


@pytest.mark.parametrize("boundary", range(15, 61))
def test_continuous_checkpoint_migration_and_render_allow_every_verified_boundary(
    tmp_path: Path, boundary: int
) -> None:
    from video_channel_manager.telegram_quote_runtime_activation import validate_runtime_checkpoint

    queue_path, ledger_path = _state_paths(tmp_path, published_prefix=boundary)
    before = ledger_path.read_bytes()
    checkpoint = validate_runtime_checkpoint(**_checkpoint_kwargs(tmp_path, ledger_path), require_provider_writes=True)
    proof = build_render_proof(
        queue_path=queue_path,
        ledger_path=ledger_path,
        presentation_policy_path=V4_POLICY,
        activation_path=tmp_path / ACTIVATION.name,
    )
    assert checkpoint["initial_published_prefix"] == 15
    assert checkpoint["published_verified"] == proof["published_prefix"] == boundary
    assert checkpoint["pending_pristine"] == proof["pending_suffix"] == 60 - boundary
    assert checkpoint["next_sequence"] == proof["next_sequence"] == (boundary + 1 if boundary < 60 else None)
    assert checkpoint["queue_complete"] is proof["queue_complete"] is (boundary == 60)
    assert ledger_path.read_bytes() == before


@pytest.mark.parametrize("damage", ["missing", "wrong_policy", "wrong_payload"])
def test_verified_canary_requires_exact_durable_v4_render_before_next_send(tmp_path: Path, damage: str) -> None:
    from video_channel_manager.telegram_quote_runtime_activation import validate_runtime_checkpoint

    _, ledger_path = _state_paths(tmp_path, published_prefix=16)
    post = _depth_queue().posts[15]
    ledger = TelegramLedger.model_validate_json(ledger_path.read_text())
    entry = ledger.entries[post.publication_id]
    evidence = tmp_path / "dispatches" / f"{entry.workflow_run_id}-{entry.workflow_run_attempt}" / "rendered.json"
    if damage == "missing":
        evidence.unlink()
    elif damage == "wrong_policy":
        evidence.write_text(render_post(post, load_presentation_policy(V3_POLICY)).model_dump_json())
    else:
        payload = json.loads(evidence.read_text())
        payload["provider_payload_sha256"] = "sha256:" + "0" * 64
        evidence.write_text(json.dumps(payload))
    with pytest.raises(
        ValueError, match="invalid rendered Telegram post|differs from the reviewed presentation policy"
    ):
        validate_runtime_checkpoint(**_checkpoint_kwargs(tmp_path, ledger_path), require_provider_writes=True)


@pytest.mark.parametrize("damage", ["target", "bot", "duplicate_message", "history", "gap", "payload", "pending_trace"])
def test_continuous_progress_never_weakens_integrity_or_no_replay(tmp_path: Path, damage: str) -> None:
    from video_channel_manager.telegram_quote_runtime_activation import validate_runtime_checkpoint

    _, ledger_path = _state_paths(tmp_path, published_prefix=17)
    payload = json.loads(ledger_path.read_text())
    entries = list(payload["entries"].values())
    errors = {
        "target": "target differs",
        "bot": "target differs",
        "duplicate_message": "duplicate Telegram message",
        "history": "immutable published history differs",
        "gap": "after pending gap",
        "payload": "payload changed after ledger initialization",
        "pending_trace": "retains dispatch/provider identity",
    }
    if damage == "target":
        entries[15]["actual_chat_id"] = -1001111111111
    elif damage == "bot":
        entries[15]["bot_id"] = 1111111111
    elif damage == "duplicate_message":
        entries[16]["message_id"] = entries[15]["message_id"]
        entries[16]["message_url"] = entries[15]["message_url"]
    elif damage == "history":
        entries[0]["last_error"] = "rewritten history"
    elif damage == "gap":
        post = _depth_queue().posts[15]
        payload["entries"][post.publication_id] = LedgerEntry(
            publication_id=post.publication_id, payload_sha256=post.payload_sha256
        ).model_dump(mode="json")
    elif damage == "payload":
        entries[20]["payload_sha256"] = "sha256:" + "0" * 64
    else:
        entries[20]["workflow_run_id"] = "12345"
    ledger_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=errors[damage]):
        validate_runtime_checkpoint(**_checkpoint_kwargs(tmp_path, ledger_path), require_provider_writes=True)


def test_schema_v1_checkpoint_does_not_silently_acquire_continuous_authority(tmp_path: Path) -> None:
    from video_channel_manager.telegram_quote_runtime_activation import validate_runtime_checkpoint

    _, ledger_path = _state_paths(tmp_path, published_prefix=16)
    _activation_copy(tmp_path, schema_version=1, progress_policy="exact_checkpoint", published_history_sha256=None)
    with pytest.raises(ValueError, match="published prefix is 16, checkpoint requires 15"):
        validate_runtime_checkpoint(**_checkpoint_kwargs(tmp_path, ledger_path), require_provider_writes=True)


def test_continuous_authority_cannot_be_inferred_from_schedule_or_credentials(tmp_path: Path) -> None:
    from video_channel_manager.telegram_quote_runtime_activation import validate_runtime_checkpoint

    _, ledger_path = _state_paths(tmp_path)
    payload = json.loads((tmp_path / ACTIVATION.name).read_text())
    payload["provider_writes_authorized"] = False
    (tmp_path / ACTIVATION.name).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="provider writes are not authorized"):
        validate_runtime_checkpoint(**_checkpoint_kwargs(tmp_path, ledger_path), require_provider_writes=True)


@pytest.mark.parametrize(
    ("boundary", "job_status", "reason", "durable", "expected"),
    [
        (15, "success", "scheduled_inactive:production schedule disabled", "skipped", "PAUSED"),
        (15, "success", "manual_preview", "skipped", "NO_SEND"),
        (16, "success", "scheduled_morning_execution", "success", "PUBLISHED"),
        (16, "success", "scheduled_morning_execution", "failure", "BLOCKED"),
        (16, "failure", "scheduled_morning_execution", "success", "BLOCKED"),
        (60, "success", "scheduled_morning_execution", "skipped", "EXHAUSTED"),
    ],
)
def test_operational_status_never_mistakes_preview_or_unpersisted_result_for_publication(
    tmp_path: Path, boundary: int, job_status: str, reason: str, durable: str, expected: str
) -> None:
    from video_channel_manager.telegram_quote_status import publication_status

    _, ledger_path = _state_paths(tmp_path, published_prefix=boundary)
    ledger = TelegramLedger.model_validate_json(ledger_path.read_text())
    status = publication_status(
        ledger,
        job_status=job_status,
        execution_reason=reason,
        run_id=str(37120208117 + 15) if boundary == 16 else "different-run",
        run_attempt="1",
        durable_result=durable,
    )
    assert status["status"] == expected
    assert bool(status["message_url"]) is (expected == "PUBLISHED")
    assert status["replenishment_required"] is (boundary >= 53)


def test_publisher_gates_and_status_share_the_production_workflow() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-telegram-poster.yml").read_text()
    quote_job = workflow.split("  historical-rich:\n", 1)[0]
    assert "video_channel_manager.telegram_quote_runtime_activation" in quote_job
    assert "video_channel_manager.telegram_quote_v4_render_proof" in quote_job
    assert "video_channel_manager.telegram_quote_status" in quote_job
    assert quote_job.index("Prove the exact next quote-v4 reading unit") < quote_job.index(
        "Enable publication ledger writer"
    )
    assert "id: persist_result" in quote_job
    assert "DURABLE_RESULT: ${{ steps.persist_result.outcome }}" in quote_job
    assert "Report actual quote publication status\n        if: always()" in quote_job
    assert quote_job.count("send \\") == 1
    assert "cancel-in-progress: false" in quote_job
