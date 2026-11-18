"""Editorial v2: exact old-state migration and meaning-led quote typography."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts import lordchrist_quote_v6_publisher as publisher
from scripts.lordchrist_quote_v6_native_readonly import build_restyled_quote_v6_native_queue
from scripts.lordchrist_quote_v6_restyle import V1_MANIFEST_PATH, build_restyle_preview
from video_channel_manager.telegram_state import initialize_ledger

ROOT = Path(__file__).resolve().parents[1]
V1_DIGEST = "sha256:62a15d4b19057509fb38023847ccbdbde319f9d428a9d6463074ae11b3940b03"


def old_state():
    old = build_restyled_quote_v6_native_queue(ROOT, manifest_path=V1_MANIFEST_PATH)
    assert old.digest == V1_DIGEST
    assert build_restyle_preview(ROOT, manifest_path=V1_MANIFEST_PATH)["prospective_queue_digest"] == old.digest
    state = initialize_ledger(old)
    old_ids = {p["publication_id"] for p in build_restyle_preview(ROOT)["published_immutable"]}
    for i, p in enumerate(old.posts, 1):
        if p.publication_id in old_ids:
            e = state.entries[p.publication_id]
            e.state = "published"
            e.provider_effect = "verified"
            e.message_id = 1600 + i
            e.published_at_utc = datetime(2026, 11, 18, 16, 13, tzinfo=UTC)
    return old, state


def test_new_queue_preserves_v1_snapshot_and_source_provenance() -> None:
    old, _ = old_state()
    new = publisher.release_and_queue(ROOT)
    manifest = build_restyle_preview(ROOT)
    assert new.digest != old.digest
    assert len(new.posts) == 30
    assert len(manifest["items"]) == 19
    old_by_id = {p.publication_id: p for p in old.posts}
    new_by_id = {p.publication_id: p for p in new.posts}
    changed = 0
    forms = set()
    for item in manifest["items"]:
        before, after = old_by_id[item["publication_id"]], new_by_id[item["publication_id"]]
        assert before.source == after.source
        assert before.quote_text == after.quote_text
        assert after.text.split("\n")[0] in before.quote_text
        if before.payload_sha256 != after.payload_sha256:
            changed += 1
        html = after.html_text.rpartition("\n<i>")[0]
        forms.add((html.count("<b>"), html.count("<i>")))
        assert not html.startswith("«")
        assert "_" not in after.hashtags
    assert changed >= 10
    assert (1, 0) in forms and (0, 1) in forms and (1, 1) in forms
    for item in manifest["published_immutable"]:
        oldpost = old_by_id[item["publication_id"]]
        newpost = new_by_id[item["publication_id"]]
        assert oldpost.payload_sha256 == newpost.payload_sha256
        assert oldpost.html_text == newpost.html_text
    by_seq = {p.sequence: p for p in new.posts}
    assert by_seq[14].text.startswith("У Бога нет недостатка в силе")
    assert by_seq[18].text.startswith("Кто хочет понять природу подлинной святости")
    assert by_seq[19].text.startswith("Павел смотрит вниз")
    assert by_seq[22].text.startswith("Во-первых, довольство — дар Божественный.")
    assert "migrate-editorial-v2" in (ROOT / ".github/workflows/lordchrist-quote-v6-publisher.yml").read_text(
        encoding="utf-8"
    )


def test_v2_migration_preserves_11_published_and_updates_only_pending(monkeypatch) -> None:
    old, ledger = old_state()
    original = ledger.model_copy(deep=True)
    writes = []
    monkeypatch.setattr(publisher, "load_ledger", lambda path, queue: ledger)
    monkeypatch.setattr(publisher, "save_ledger", lambda path, value: writes.append(value.model_copy(deep=True)))
    monkeypatch.setattr(publisher, "guard_cross_track", lambda root: None)
    publisher.migrate_editorial_revision(ROOT)
    assert len(writes) == 1
    revised = writes[0]
    assert revised.queue_digest == publisher.release_and_queue(ROOT).digest
    changed = 0
    new_posts = {p.publication_id: p for p in publisher.release_and_queue(ROOT).posts}
    for id, before in original.entries.items():
        after = revised.entries[id]
        if before.state == "published":
            assert before == after
        else:
            assert after.state == "pending"
            assert after.provider_effect == "impossible"
            assert after.payload_sha256 == new_posts[id].payload_sha256
            if before.payload_sha256 != after.payload_sha256:
                changed += 1
    assert changed >= 10


@pytest.mark.parametrize("unsafe", ["may_exist", "new_published", "old_digest_mismatch"])
def test_v2_migration_refuses_state_drift_without_write(monkeypatch, unsafe: str) -> None:
    _old, ledger = old_state()
    pending = next(e for e in ledger.entries.values() if e.state == "pending")
    if unsafe == "may_exist":
        pending.state = "dispatching"
        pending.provider_effect = "may_exist"
    elif unsafe == "new_published":
        pending.state = "published"
        pending.provider_effect = "verified"
        pending.message_id = 1630
        pending.published_at_utc = datetime(2026, 11, 19, 8, tzinfo=UTC)
    else:
        ledger.queue_digest = "sha256:" + "0" * 64
    calls = []
    from video_channel_manager.telegram_state import load_ledger as real_load

    def load(path, queue):
        from tempfile import TemporaryDirectory
        from video_channel_manager.telegram_state import save_ledger

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "ledger.json"
            save_ledger(target, ledger)
            return real_load(target, queue)

    monkeypatch.setattr(publisher, "load_ledger", load)
    monkeypatch.setattr(publisher, "save_ledger", lambda path, value: calls.append(value))
    monkeypatch.setattr(publisher, "guard_cross_track", lambda root: None)
    with pytest.raises(ValueError):
        publisher.migrate_editorial_revision(ROOT)
    assert not calls
