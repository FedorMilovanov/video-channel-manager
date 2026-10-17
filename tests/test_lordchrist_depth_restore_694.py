from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_cross_track_effect_guard import (
    DEPTH_V3_LEDGER_FILENAME,
    require_no_cross_track_unresolved_effects,
)
from video_channel_manager.telegram_models import LedgerEntry, TelegramLedger, canonical_json, sha256_text
from video_channel_manager.telegram_quote_depth import (
    DEPTH_QUEUE_DIGEST,
    DEPTH_RELEASE_ID,
    DEPTH_V3_QUEUE_DIGEST,
    DEPTH_V3_RELEASE_ID,
    RESTORE_SEQUENCES,
    V3_HANDOFF_PUBLISHED_PREFIX,
    build_depth_runtime_queue,
    build_depth_v3_runtime_queue,
    initialize_depth_v3_ledger,
    load_depth_restore,
    require_exact_depth_v2_handoff,
)
from video_channel_manager.telegram_quote_standalone_review import load_standalone_review

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
CANDIDATE = CONTENT / "successor-quotes-v1.json"
TRANSLATION = CONTENT / "successor-translation-ledger-v1.json"
AMENDMENTS = CONTENT / "successor-integrity-amendments-v1.json"
RESTORE = CONTENT / "successor-depth-restore-v1.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
ATTEMPTED_AT = datetime(2026, 10, 17, 10, 40, 0, tzinfo=UTC)


def _depth_v2_queue():
    return build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )


def _depth_v3_queue():
    return build_depth_v3_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )


def _published_entry(publication_id: str, payload_sha256: str, message_id: int, intent_seed: int = 0) -> LedgerEntry:
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
        published_at_utc=ATTEMPTED_AT + timedelta(seconds=4),
        message_id=message_id,
        message_url=f"https://t.me/lordchrist/{message_id}",
        actual_chat_id=CHAT_ID,
        actual_chat_username="lordchrist",
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )


def _depth_v2_ledger(published_prefix: int = V3_HANDOFF_PUBLISHED_PREFIX) -> TelegramLedger:
    queue = _depth_v2_queue()
    entries: dict[str, LedgerEntry] = {}
    for index, post in enumerate(queue.posts):
        if index < published_prefix:
            entries[post.publication_id] = _published_entry(
                post.publication_id, post.payload_sha256, 1551 + index, intent_seed=index
            )
        else:
            entries[post.publication_id] = LedgerEntry(
                publication_id=post.publication_id,
                payload_sha256=post.payload_sha256,
            )
    return TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        queue_digest=queue.digest,
        entries=entries,
    )


def test_depth_restore_release_binds_the_exact_reviewed_identity() -> None:
    restore = load_depth_restore(RESTORE)

    assert restore.release_id == DEPTH_V3_RELEASE_ID
    assert restore.base_release_id == DEPTH_RELEASE_ID
    assert restore.base_queue_digest == DEPTH_QUEUE_DIGEST
    assert restore.handoff_published_prefix == 17
    assert tuple(entry.sequence for entry in restore.restores) == RESTORE_SEQUENCES == (32, 36)
    assert restore.normalized_queue_digest == DEPTH_V3_QUEUE_DIGEST
    assert restore.owning_issue == 694
    # Sequence 17 was published under quote-v4 before this release; the restore
    # reason must record it as immutable history instead of rewriting it.
    assert "message 1567" in restore.reason
    for entry in restore.restores:
        assert entry.publication_id.startswith(f"lordchrist-successor-depth-v2-{entry.sequence:02d}-")


def test_depth_restore_identity_digest_binds_the_exact_entries() -> None:
    restore = load_depth_restore(RESTORE)
    identity = {
        "release_id": restore.release_id,
        "base_release_id": restore.base_release_id,
        "base_queue_digest": restore.base_queue_digest,
        "restores": [entry.model_dump(mode="json") for entry in restore.restores],
    }

    assert sha256_text(canonical_json(identity)) == restore.normalized_queue_digest == DEPTH_V3_QUEUE_DIGEST


def test_depth_restore_rejects_the_published_anaphora_slot(tmp_path: Path) -> None:
    payload = json.loads(RESTORE.read_text(encoding="utf-8"))
    entry = dict(payload["restores"][0])
    entry["sequence"] = 17
    entry["publication_id"] = "lordchrist-successor-depth-v2-17-gurnall-defend-in-suffering"
    payload["restores"] = [entry, payload["restores"][1]]
    path = tmp_path / RESTORE.name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # The published 17 cannot be restored at all: it is outside the pending suffix.
    with pytest.raises(ValueError, match="greater than or equal to 18"):
        load_depth_restore(path)


def test_depth_restore_requires_the_verbatim_sealed_first_sentence(tmp_path: Path) -> None:
    payload = json.loads(RESTORE.read_text(encoding="utf-8"))
    payload["restores"][0]["restored_quote_ru"] = "Христос стал послушным, но это совсем другая редакция текста."
    path = tmp_path / RESTORE.name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # A re-edited quotation breaks the reviewed identity digest and is rejected.
    with pytest.raises(ValueError, match="identity digest mismatch"):
        build_depth_v3_runtime_queue(
            candidate_path=CANDIDATE,
            translation_ledger_path=TRANSLATION,
            integrity_amendment_path=AMENDMENTS,
            restore_path=path,
        )


def test_depth_v3_queue_changes_only_the_restored_slots() -> None:
    v2 = _depth_v2_queue()
    v3 = _depth_v3_queue()

    assert v3.release_id == DEPTH_V3_RELEASE_ID
    assert v3.digest == DEPTH_V3_QUEUE_DIGEST
    assert v3.digest != v2.digest
    changed = [p2.sequence for p2, p3 in zip(v2.posts, v3.posts, strict=True) if p2 != p3]
    assert changed == [32, 36]
    # The published 1..17 history stays byte-identical to the durable depth-v2 queue.
    for post_v2, post_v3 in zip(v2.posts[:17], v3.posts[:17], strict=True):
        assert post_v2 == post_v3
    # The restored quotations are complete thoughts with named subjects.
    assert v3.posts[31].text.startswith("Христос стал послушным Отцу как Сын")
    assert v3.posts[35].text.startswith("Если Христос и я соединены")


def test_exact_depth_v2_handoff_accepts_only_17_published_and_43_pristine() -> None:
    queue = _depth_v2_queue()
    ledger = _depth_v2_ledger()

    require_exact_depth_v2_handoff(queue, ledger, published_prefix=V3_HANDOFF_PUBLISHED_PREFIX)

    contaminated = TelegramLedger.model_validate(ledger.model_dump(mode="json"))
    post_18 = queue.posts[V3_HANDOFF_PUBLISHED_PREFIX]
    contaminated.entries[post_18.publication_id] = _published_entry(
        post_18.publication_id, post_18.payload_sha256, 1568
    )
    with pytest.raises(ValueError, match="pristine unpublished suffix"):
        require_exact_depth_v2_handoff(
            queue,
            contaminated,
            published_prefix=V3_HANDOFF_PUBLISHED_PREFIX,
        )


def test_depth_v3_ledger_rebinds_history_and_keeps_the_suffix_pristine(tmp_path: Path) -> None:
    v3 = _depth_v3_queue()
    v2 = _depth_v2_queue()
    v2_ledger = _depth_v2_ledger()
    restore = load_depth_restore(RESTORE)
    path = tmp_path / "successor-depth-v3-publication-ledger.json"

    migrated = initialize_depth_v3_ledger(
        path=path,
        depth_v3_queue=v3,
        depth_v2_queue=v2,
        depth_v2_ledger=v2_ledger,
        restore=restore,
    )

    assert migrated.queue_digest == DEPTH_V3_QUEUE_DIGEST
    assert list(migrated.entries) == [post.publication_id for post in v3.posts]
    handoff = restore.handoff_published_prefix
    assert all(migrated.entries[post.publication_id].state == "published" for post in v3.posts[:handoff])
    assert all(migrated.entries[post.publication_id].message_id for post in v3.posts[:handoff])
    assert all(migrated.entries[post.publication_id].state == "pending" for post in v3.posts[handoff:])
    assert all(migrated.entries[post.publication_id].provider_effect == "impossible" for post in v3.posts[handoff:])
    assert all(
        migrated.entries[post.publication_id].payload_sha256 == post.payload_sha256 for post in v3.posts[handoff:]
    )
    # Refuses to overwrite an already-durable ledger.
    with pytest.raises(ValueError, match="refusing to overwrite"):
        initialize_depth_v3_ledger(
            path=path,
            depth_v3_queue=v3,
            depth_v2_queue=v2,
            depth_v2_ledger=v2_ledger,
            restore=restore,
        )


def test_depth_v3_ledger_rejects_history_payload_drift(tmp_path: Path) -> None:
    v3 = _depth_v3_queue()
    v2 = _depth_v2_queue()
    v2_ledger = _depth_v2_ledger()
    drifted = TelegramLedger.model_validate(v2_ledger.model_dump(mode="json"))
    drifted_post = v2.posts[16]
    drifted.entries[drifted_post.publication_id] = _published_entry(
        drifted_post.publication_id, drifted_post.payload_sha256, 1567
    )
    drifted.entries[drifted_post.publication_id].payload_sha256 = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="locked history payload differs"):
        initialize_depth_v3_ledger(
            path=tmp_path / "depth-v3-ledger.json",
            depth_v3_queue=v3,
            depth_v2_queue=v2,
            depth_v2_ledger=drifted,
            restore=load_depth_restore(RESTORE),
        )


def test_standalone_review_v2_forbids_title_resolved_openings(tmp_path: Path) -> None:
    payload = json.loads((CONTENT / "quote-standalone-review-v2.json").read_text(encoding="utf-8"))
    payload["entries"][0]["opening"] = "title_resolved_anaphora"
    payload["entries"][0]["title_context_reference"] = "Заголовок-костыль"
    path = tmp_path / "quote-standalone-review-v2.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="must not accept context-dependent openings"):
        load_standalone_review(path)


def test_cross_track_guard_tracks_the_depth_v3_ledger(tmp_path: Path) -> None:
    from video_channel_manager.telegram_state import initialize_ledger, load_queue

    v3 = _depth_v3_queue()
    v2_ledger = _depth_v2_ledger()
    handoff = V3_HANDOFF_PUBLISHED_PREFIX
    entries: dict[str, LedgerEntry] = {}
    for index, post in enumerate(v3.posts):
        if index < handoff:
            entries[post.publication_id] = v2_ledger.entries[post.publication_id]
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
        queue_digest=v3.digest,
        entries=entries,
    )
    predecessor = load_queue(ROOT / "content/telegram/lordchrist/verified-30-posts.json")
    predecessor_ledger = initialize_ledger(predecessor)
    (tmp_path / "publication-ledger.json").write_text(
        predecessor_ledger.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    ledger_path = tmp_path / DEPTH_V3_LEDGER_FILENAME
    ledger_path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")

    result = require_no_cross_track_unresolved_effects(
        profile_path=ROOT / "content/telegram/channels/lordchrist.json",
        legacy_queue_path=ROOT / "content/telegram/lordchrist/verified-30-posts.json",
        legacy_ledger_path=tmp_path / "publication-ledger.json",
        research_ledger_path=tmp_path / "research-v2/publication-ledger.json",
    )

    assert result["depth_v3_ledger_present"] is True
    assert result["depth_v3_unresolved"] == []
    assert result["clear"] is True

    drifted = json.loads(ledger_path.read_text(encoding="utf-8"))
    drifted["queue_digest"] = "sha256:" + "0" * 64
    ledger_path.write_text(json.dumps(drifted, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="depth-v3 ledger queue digest differs"):
        require_no_cross_track_unresolved_effects(
            profile_path=ROOT / "content/telegram/channels/lordchrist.json",
            legacy_queue_path=ROOT / "content/telegram/lordchrist/verified-30-posts.json",
            legacy_ledger_path=tmp_path / "publication-ledger.json",
            research_ledger_path=tmp_path / "research-v2/publication-ledger.json",
        )
