"""All 19 new quote presentations must stay source-bound and provider-inert."""

from pathlib import Path


from scripts.lordchrist_quote_v6_native_readonly import (
    SOURCE_PATH,
    build_quote_v6_native_queue,
    build_restyled_quote_v6_native_queue,
)
from scripts.lordchrist_quote_v6_restyle import build_restyle_preview

ROOT = Path(__file__).resolve().parents[1]


def test_19_new_presentations_have_exact_source_and_preserve_11_publications() -> None:
    old = build_quote_v6_native_queue(ROOT / SOURCE_PATH)
    queue = build_restyled_quote_v6_native_queue(ROOT)
    preview = build_restyle_preview(ROOT)
    assert old.digest == preview["original_queue_digest"]
    assert queue.digest == preview["prospective_queue_digest"]
    assert len(queue.posts) == 30
    changed = [p for p in queue.posts if p.presentation_style == "inline_emphasis"]
    original = {p.publication_id: p for p in old.posts}
    unchanged = [p for p in queue.posts if p.presentation_style == "legacy_blockquote"]
    assert len(changed) == 19 and len(unchanged) == 11
    assert [p.publication_id for p in unchanged] == [
        p.publication_id
        for p in old.posts
        if p.publication_id in {entry["publication_id"] for entry in preview["published_immutable"]}
    ]
    for p in unchanged:
        assert p.html_text == original[p.publication_id].html_text
        assert p.payload_sha256 == original[p.publication_id].payload_sha256
    for p in changed:
        assert "<blockquote>" not in p.html_text
        assert "«" != p.text[0]
        assert "_" not in p.hashtags
        body = p.html_text.rpartition("\n<i>")[0]
        assert body.count("<b>") + body.count("<i>") in {1, 2}
        assert p.source.original_ru_quote_sha256 == original[p.publication_id].source.original_ru_quote_sha256
    lengths = [len(p.text) for p in changed]
    assert min(lengths) < 450 < max(lengths)
    assert preview["state_ledger_mutated"] is False
    assert preview["provider_inert"] is True


def test_restyle_cannot_change_history_or_source(tmp_path: Path) -> None:
    import json
    from scripts.lordchrist_quote_v6_restyle import MANIFEST_PATH

    data = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    assert len(data["baseline_published_ids"]) == 11
    assert set(data["baseline_published_ids"]).isdisjoint({entry["publication_id"] for entry in data["pending"]})


def _legacy_ledger_before_migration():
    from scripts.lordchrist_quote_v6_native_readonly import SOURCE_PATH, build_quote_v6_native_queue
    from video_channel_manager.telegram_state import initialize_ledger
    from scripts.lordchrist_quote_v6_restyle import build_restyle_preview

    queue = build_quote_v6_native_queue(ROOT / SOURCE_PATH)
    proposal = build_restyle_preview(ROOT)
    ledger = initialize_ledger(queue)
    for index, published in enumerate(proposal["published_immutable"], start=1):
        entry = ledger.entries[published["publication_id"]]
        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = 1603 + index
    return ledger, proposal


def test_migration_preserves_published_and_only_updates_19_pending(monkeypatch) -> None:
    from scripts import lordchrist_quote_v6_publisher as publisher

    ledger, proposal = _legacy_ledger_before_migration()
    original = ledger.model_copy(deep=True)
    saved = []
    monkeypatch.setattr(publisher, "load_ledger", lambda path, queue: ledger)
    monkeypatch.setattr(publisher, "save_ledger", lambda path, value: saved.append(value.model_copy(deep=True)))
    monkeypatch.setattr(publisher, "guard_cross_track", lambda root: None)
    publisher.migrate_pending_restyle(ROOT)
    assert len(saved) == 1
    assert saved[0].queue_digest == proposal["prospective_queue_digest"]
    for item in proposal["published_immutable"]:
        key = item["publication_id"]
        assert saved[0].entries[key] == original.entries[key]
    for item in proposal["items"]:
        key = item["publication_id"]
        before, after = original.entries[key], saved[0].entries[key]
        assert before.state == after.state == "pending"
        assert before.provider_effect == after.provider_effect == "impossible"
        assert before.payload_sha256 != after.payload_sha256
        assert after.payload_sha256 == item["provider_payload_sha256"]


def test_migration_refuses_any_new_publishing_or_unknown_provider_effect(monkeypatch) -> None:
    import pytest
    from scripts import lordchrist_quote_v6_publisher as publisher

    ledger, proposal = _legacy_ledger_before_migration()
    first_pending = proposal["items"][0]["publication_id"]
    ledger.entries[first_pending].state = "dispatching"
    ledger.entries[first_pending].provider_effect = "may_exist"
    saved = []
    monkeypatch.setattr(publisher, "load_ledger", lambda path, queue: ledger)
    monkeypatch.setattr(publisher, "save_ledger", lambda path, value: saved.append(value))
    monkeypatch.setattr(publisher, "guard_cross_track", lambda root: None)
    with pytest.raises(ValueError, match="not safely rebindable"):
        publisher.migrate_pending_restyle(ROOT)
    assert saved == []


def test_workflow_separates_state_migration_from_sending() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-quote-v6-publisher.yml").read_text(encoding="utf-8")
    assert "migrate-restyle" in workflow
    assert "steps.invocation.outputs.migrate == 'true'" in workflow
    assert (
        'python -m scripts.lordchrist_quote_v6_publisher "${{ steps.invocation.outputs.migration_command }}"'
        in workflow
    )
    assert "steps.invocation.outputs.migrate != 'true'" in workflow
    assert workflow.index("Guarded migration of exact 19 pending") < workflow.index("Preflight exact Telegram bot")


def test_migration_fails_closed_if_a_new_quote_publishes_before_cutover(monkeypatch) -> None:
    import pytest
    from scripts import lordchrist_quote_v6_publisher as publisher

    ledger, proposal = _legacy_ledger_before_migration()
    next_id = proposal["items"][0]["publication_id"]
    entry = ledger.entries[next_id]
    entry.state = "published"
    entry.provider_effect = "verified"
    entry.message_id = 1630
    saved = []
    monkeypatch.setattr(publisher, "load_ledger", lambda path, queue: ledger)
    monkeypatch.setattr(publisher, "save_ledger", lambda path, value: saved.append(value))
    monkeypatch.setattr(publisher, "guard_cross_track", lambda root: None)
    with pytest.raises(ValueError, match="not safely rebindable"):
        publisher.migrate_pending_restyle(ROOT)
    assert not saved


def test_scheduled_invocation_cannot_accidentally_select_migration() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-quote-v6-publisher.yml").read_text(encoding="utf-8")
    assert 'if [[ "$GITHUB_EVENT_NAME" == "schedule" ]]; then' in workflow
    scheduled_gate = workflow.split('if [[ "$GITHUB_EVENT_NAME" == "schedule" ]]; then', 1)[1]
    assert 'echo "mode=scheduled"' in scheduled_gate.split("exit 0", 1)[0]
    migration_gate = 'if [[ "$V6_ACTION" == "migrate-restyle" ]]; then'
    assert workflow.index(migration_gate) > workflow.index('if [[ "$GITHUB_EVENT_NAME" == "schedule" ]]; then')
    assert (
        workflow.count(
            'python -m scripts.lordchrist_quote_v6_publisher "${{ steps.invocation.outputs.migration_command }}"'
        )
        == 1
    )
