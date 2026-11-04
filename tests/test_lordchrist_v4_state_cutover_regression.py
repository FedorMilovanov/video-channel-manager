"""Fail-closed channel-wide predecessor and quote-v4 ledger cutover checks."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_cross_track_effect_guard import require_no_cross_track_unresolved_effects
from video_channel_manager.telegram_models import LedgerEntry
from video_channel_manager.telegram_state import initialize_ledger, load_queue

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
OLD_QUEUE = CONTENT / "archived-old-queues/verified-30-posts.json"
NEW_QUEUE = CONTENT / "verified-30-posts.json"
PROFILE = ROOT / "content/telegram/channels/lordchrist.json"


def _arrange_cutover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    old = load_queue(OLD_QUEUE)
    new = load_queue(NEW_QUEUE)
    assert old.digest == "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
    assert new.digest == "sha256:a3e5bd757b49996f5db27d46427ce3e6909ce1cf8146d41f6bd316081a2065dd"
    state = tmp_path / "publication-ledger.json"
    state.write_text(initialize_ledger(old).model_dump_json(indent=2) + "\n", encoding="utf-8")
    archive = tmp_path / f"publication-ledger-archive-{old.digest.removeprefix('sha256:')[:12]}.json"
    monkeypatch.setenv("LORDCHRIST_PREDECESSOR_QUEUE_PATH", str(OLD_QUEUE))
    monkeypatch.setenv("LORDCHRIST_PREDECESSOR_LEDGER_PATH", str(state))
    return state, archive


def _guard(state: Path) -> dict[str, object]:
    return require_no_cross_track_unresolved_effects(
        profile_path=PROFILE,
        legacy_queue_path=NEW_QUEUE,
        legacy_ledger_path=state,
        research_ledger_path=state.parent / "research-v2/publication-ledger.json",
    )


def test_predecessor_receipts_remain_bound_before_and_after_v4_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, archive = _arrange_cutover(tmp_path, monkeypatch)
    old_bytes = state.read_bytes()
    assert _guard(state)["v4_ledger_present"] is False

    archive.write_bytes(old_bytes)
    state.write_text(initialize_ledger(load_queue(NEW_QUEUE)).model_dump_json(indent=2) + "\n", encoding="utf-8")
    result = _guard(state)
    assert result["v4_ledger_present"] is True
    assert result["v4_unresolved"] == []
    assert archive.read_bytes() == old_bytes


def test_v4_state_without_exact_predecessor_archive_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, _archive = _arrange_cutover(tmp_path, monkeypatch)
    state.write_text(initialize_ledger(load_queue(NEW_QUEUE)).model_dump_json(indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="without the exact archived predecessor"):
        _guard(state)


def test_v4_cutover_rejects_archive_with_wrong_queue_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state, archive = _arrange_cutover(tmp_path, monkeypatch)
    new_ledger = initialize_ledger(load_queue(NEW_QUEUE))
    archive.write_text(new_ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    state.write_text(new_ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="queue digest differs"):
        _guard(state)


def test_unresolved_v4_provider_intent_blocks_other_lordchrist_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, archive = _arrange_cutover(tmp_path, monkeypatch)
    archive.write_bytes(state.read_bytes())
    queue = load_queue(NEW_QUEUE)
    ledger = initialize_ledger(queue)
    post = queue.posts[0]
    ledger.entries[post.publication_id] = LedgerEntry(
        publication_id=post.publication_id,
        payload_sha256=post.payload_sha256,
        state="dispatching",
        provider_effect="may_exist",
        intent_id="e" * 32,
        dispatch_mode="scheduled",
        scheduled_slot="morning",
        workflow_run_id="42",
        workflow_run_attempt="1",
        github_sha="e" * 40,
        github_workflow_sha="f" * 40,
        attempted_at_utc=datetime(2026, 11, 3, 8, 0, tzinfo=UTC),
        actual_chat_id=-1001295216957,
        actual_chat_username="lordchrist",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
    )
    state.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="v4=.*"):
        _guard(state)
