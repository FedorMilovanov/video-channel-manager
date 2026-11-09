"""Regression contracts for new LordChrist quote-v6 owner-requested publication lane."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.lordchrist_quote_v6_publisher import (
    EXPECTED_DIGEST,
    FIRST_ID,
    RELEASE_PATH,
    STATE_LEDGER,
    guard_cross_track,
    make_rendered,
    release_and_queue,
    validate_schedule,
)
from video_channel_manager.telegram_models import TargetProof
from video_channel_manager.telegram_state import (
    initialize_ledger,
    prepare_next,
    strict_next_post,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-quote-v6-publisher.yml"
OLD_WORKFLOW = ROOT / ".github/workflows/lordchrist-telegram-poster.yml"


def test_30_immutable_candidate_items_are_source_bound_not_promoted() -> None:
    queue = release_and_queue(ROOT)
    assert queue.candidate_digest == EXPECTED_DIGEST
    assert len(queue.posts) == 30
    assert queue.posts[0].publication_id == FIRST_ID
    assert queue.provider_writes_authorized is False
    assert queue.release_state == "provider_inert_candidate"
    assert len({post.publication_id for post in queue.posts}) == 30


@pytest.mark.parametrize("index", range(30))
def test_exact_html_plain_text_and_entities_roundtrip(index: int) -> None:
    post = release_and_queue(ROOT).posts[index]
    html_text, plain, entities = make_rendered(post)
    assert html_text == post.html_text
    assert plain == post.text
    assert len(plain.encode("utf-16-le")) // 2 <= 4096
    assert {entity.type for entity in entities} == {"blockquote", "italic"}


def test_release_does_not_mutate_old_queue_or_editorial_evidence() -> None:
    queue = release_and_queue(ROOT)
    import json

    raw = json.loads((ROOT / RELEASE_PATH).read_text(encoding="utf-8"))
    assert raw["candidate_digest"] == queue.digest
    assert raw["quote_v4_replay_authorized"] is False
    assert raw["new_state_ledger_relative_path"] == STATE_LEDGER.as_posix()
    old = OLD_WORKFLOW.read_text(encoding="utf-8")
    assert "false &&" in old.split("\n  publish-next:\n", 1)[1].split("\n    runs-on:", 1)[0]
    assert '- cron: "0 7 * * *"' not in old
    assert '- cron: "0 18 * * 2,5,0"' not in old


def test_first_v6_entry_requires_exact_manual_canary() -> None:
    queue = release_and_queue(ROOT)
    ledger = initialize_ledger(queue)
    post, reason = strict_next_post(queue, ledger)
    assert post is not None and post.publication_id == FIRST_ID
    assert reason == "next pending publication"
    proof = TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог - Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 11, 6, 8, 0, tzinfo=UTC),
    )
    result = prepare_next(
        queue,
        ledger,
        run_id="42",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="a" * 40,
        mode="scheduled",
        scheduled_slot="morning",
        target=proof,
        now=datetime(2026, 11, 6, 8, 1, tzinfo=UTC),
    )
    assert result.envelope is None
    assert "manual canary" in result.reason
    manual = prepare_next(
        queue,
        ledger,
        run_id="42",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="a" * 40,
        mode="manual",
        expected_publication_id=FIRST_ID,
        target=proof,
        now=datetime(2026, 11, 6, 8, 1, tzinfo=UTC),
    )
    assert manual.envelope is not None
    assert ledger.entries[FIRST_ID].state == "dispatching"
    assert ledger.entries[FIRST_ID].provider_effect == "may_exist"
    assert strict_next_post(queue, ledger)[0] is None


def test_scheduled_start_has_no_early_send_or_backfill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    moscow = ZoneInfo("Europe/Moscow")
    with pytest.raises(ValueError, match="before"):
        validate_schedule("scheduled", datetime(2026, 11, 7, 10, 0, tzinfo=moscow))
    validate_schedule("scheduled", datetime(2026, 11, 8, 10, 0, tzinfo=moscow))
    validate_schedule("scheduled", datetime(2026, 11, 8, 12, 59, tzinfo=moscow))
    # The observed Nov 8 GitHub event arrived seven hours after the cron.
    validate_schedule("scheduled", datetime(2026, 11, 8, 17, 3, tzinfo=moscow))
    validate_schedule("scheduled", datetime(2026, 11, 8, 20, 59, tzinfo=moscow))
    with pytest.raises(ValueError, match="not due"):
        validate_schedule("scheduled", datetime(2026, 11, 8, 9, 59, tzinfo=moscow))
    with pytest.raises(ValueError, match="late"):
        validate_schedule("scheduled", datetime(2026, 11, 8, 21, 0, tzinfo=moscow))
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    with pytest.raises(ValueError, match="re-run"):
        validate_schedule("scheduled", datetime(2026, 11, 8, 10, 0, tzinfo=moscow))


def test_delayed_fallback_does_not_prepare_a_second_quote_same_day() -> None:
    queue = release_and_queue(ROOT)
    ledger = initialize_ledger(queue)
    first = ledger.entries[queue.posts[0].publication_id]
    first.state = "published"
    first.provider_effect = "verified"
    first.dispatch_mode = "manual"
    first.published_at_utc = datetime(2026, 11, 6, 3, 50, tzinfo=UTC)
    first.message_id = 1604
    first.actual_chat_id = -1001295216957
    first.bot_id = 8716602202
    first.bot_username = "preaching_mp3_bot"

    second = ledger.entries[queue.posts[1].publication_id]
    second.state = "published"
    second.provider_effect = "verified"
    second.dispatch_mode = "scheduled"
    second.scheduled_slot = "morning"
    second.published_at_utc = datetime(2026, 11, 8, 14, 3, tzinfo=UTC)
    second.message_id = 1605

    proof = TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог - Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 11, 8, 14, 19, tzinfo=UTC),
    )
    result = prepare_next(
        queue,
        ledger,
        run_id="delayed-fallback-123",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="a" * 40,
        mode="scheduled",
        scheduled_slot="morning",
        target=proof,
        now=datetime(2026, 11, 8, 14, 20, tzinfo=UTC),
    )
    assert result.envelope is None
    assert "already verified" in result.reason
    assert ledger.entries[queue.posts[2].publication_id].state == "pending"
    assert ledger.entries[queue.posts[2].publication_id].provider_effect == "impossible"


def test_shared_writer_lock_and_state_first_send_last() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "group: lordchrist-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    assert 'cron: "0 7 * * *"' in workflow
    assert 'cron: "23 7 * * *"' in workflow
    assert "GITHUB_WORKFLOW_SHA" in workflow
    assert "telegram_github_quality_gate" in workflow
    assert "Persist immutable pre-send intent" in workflow
    assert "Send exactly one v6 message" in workflow
    assert workflow.index("Persist immutable pre-send intent") < workflow.index("Send exactly one v6 message")
    assert workflow.index("Send exactly one v6 message") < workflow.index("Persist verified publication")
    assert "quote-v6-publication-ledger.json" in workflow
    assert "lordchrist-ryle-religion-cost" in workflow
    assert "PUBLISH:$V6_PUBLICATION_ID" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "if: steps.send.outcome == 'success'" in workflow


def test_v6_guard_uses_all_historical_provider_effect_tracks() -> None:
    # The real state branch is checked out only in Actions; no accidental state
    # writes or provider credentials are needed in the normal test environment.
    import inspect

    source = inspect.getsource(guard_cross_track)
    assert "require_no_cross_track_unresolved_effects" in source
    assert "archived-old-queues/verified-30-posts.json" in source
    assert "LORDCHRIST_PREDECESSOR_QUEUE_PATH" in source


def test_no_external_user_interface_automation() -> None:
    source = (ROOT / "scripts/lordchrist_quote_v6_publisher.py").read_text(encoding="utf-8")
    assert all(
        forbidden not in source
        for forbidden in ("pyautogui", "SetForegroundWindow", "keybd_event", "win32clipboard", "ImageGrab")
    )


def _prepared_v6_fault_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Produce immutable, stateful pre-send evidence without any provider request."""
    import scripts.lordchrist_quote_v6_publisher as publisher
    from video_channel_manager.telegram_state import save_ledger

    queue = release_and_queue(ROOT)
    ledger = initialize_ledger(queue)
    attempt_at = datetime(2026, 11, 6, 8, 1, tzinfo=UTC)
    proof = TargetProof(
        schema_name="video-channel-manager.telegram-target-proof",
        schema_version=2,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог - Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=attempt_at,
    )
    prepared = prepare_next(
        queue,
        ledger,
        run_id="fault-stage-run",
        run_attempt="1",
        github_sha="b" * 40,
        github_workflow_sha="b" * 40,
        mode="manual",
        target=proof,
        expected_publication_id=FIRST_ID,
        now=attempt_at,
    )
    assert prepared.envelope is not None
    ledger_path = tmp_path / publisher.STATE_PATH / publisher.STATE_LEDGER
    save_ledger(ledger_path, ledger)
    monkeypatch.setattr(publisher, "release_and_queue", lambda _root: queue)
    monkeypatch.setattr(publisher, "guard_cross_track", lambda _root: None)
    monkeypatch.setattr(publisher, "load_dispatch", lambda _path: prepared.envelope)
    monkeypatch.setattr(publisher, "utc_now", lambda: attempt_at + timedelta(minutes=1))
    monkeypatch.setenv("LORDCHRIST_TELEGRAM_BOT_TOKEN", "fixture-token-not-a-real-credential")
    return publisher, queue, ledger_path, prepared.envelope


def test_quote_v6_fault_before_dispatch_rejects_unverified_intent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No request is attempted when the immutable intent text differs."""
    publisher, queue, ledger_path, envelope = _prepared_v6_fault_fixture(monkeypatch, tmp_path)
    import video_channel_manager.telegram_state as state

    monkeypatch.setattr(publisher, "load_dispatch", lambda _path: envelope.model_copy(update={"text": "tampered"}))
    calls: list[str] = []
    monkeypatch.setattr(publisher, "_api_call", lambda *args, **kwargs: calls.append("send"))
    with pytest.raises(ValueError, match="text differs"):
        publisher.send(tmp_path)
    assert calls == []
    durable = state.load_ledger(ledger_path, queue)
    assert durable.entries[FIRST_ID].state == "dispatching"
    assert strict_next_post(queue, durable)[0] is None


def test_quote_v6_fault_after_dispatch_before_response_is_unknown_without_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Lost response causes one send and a durable may_exist blocker."""
    publisher, queue, ledger_path, _envelope = _prepared_v6_fault_fixture(monkeypatch, tmp_path)
    import video_channel_manager.telegram_state as state
    from video_channel_manager.telegram_transport import TelegramApiError

    count = 0

    def lost_response(*args, **kwargs):
        nonlocal count
        count += 1
        raise TelegramApiError("response lost", provider_effect="may_exist")

    monkeypatch.setattr(publisher, "_api_call", lost_response)
    assert publisher.send(tmp_path) == 6
    assert count == 1
    durable = state.load_ledger(ledger_path, queue)
    entry = durable.entries[FIRST_ID]
    assert (entry.state, entry.provider_effect) == ("unknown", "may_exist")
    assert strict_next_post(queue, durable)[0] is None


def test_quote_v6_fault_after_response_before_commit_cannot_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If disk commit fails after provider response, persisted intent blocks replay."""
    publisher, queue, ledger_path, _envelope = _prepared_v6_fault_fixture(monkeypatch, tmp_path)
    import video_channel_manager.telegram_state as state

    first = queue.posts[0]
    _, plain, entities = make_rendered(first)
    count = 0

    def one_reply(*args, **kwargs):
        nonlocal count
        count += 1
        return {
            "chat": {"id": -1001295216957, "username": "lordchrist", "type": "channel"},
            "text": plain,
            "entities": [entity.model_dump(mode="json") for entity in entities],
            "message_id": 99123,
        }

    monkeypatch.setattr(publisher, "_api_call", one_reply)
    monkeypatch.setattr(publisher, "save_ledger", lambda *_args: (_ for _ in ()).throw(OSError("disk unavailable")))
    with pytest.raises(OSError, match="disk unavailable"):
        publisher.send(tmp_path)
    assert count == 1
    durable = state.load_ledger(ledger_path, queue)
    assert durable.entries[FIRST_ID].state == "dispatching"
    assert durable.entries[FIRST_ID].provider_effect == "may_exist"
    assert strict_next_post(queue, durable)[0] is None
