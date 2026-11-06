"""Regression contracts for new LordChrist quote-v6 owner-requested publication lane."""

from __future__ import annotations

from datetime import UTC, datetime
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
    with pytest.raises(ValueError, match="late"):
        validate_schedule("scheduled", datetime(2026, 11, 8, 13, 1, tzinfo=moscow))
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    with pytest.raises(ValueError, match="re-run"):
        validate_schedule("scheduled", datetime(2026, 11, 8, 10, 0, tzinfo=moscow))


def test_shared_writer_lock_and_state_first_send_last() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "group: lordchrist-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "queue: max" in workflow
    assert 'cron: "0 7 * * *"' in workflow
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
