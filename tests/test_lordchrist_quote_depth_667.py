from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_models import LedgerEntry, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import (
    DEPTH_QUEUE_DIGEST,
    build_depth_runtime_queue,
    initialize_depth_ledger,
    load_depth_audit,
    load_depth_release,
    require_exact_v1_handoff,
)
from video_channel_manager.telegram_quote_runtime import build_successor_runtime_queue
from video_channel_manager.telegram_state import initialize_ledger

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
CANDIDATE = CONTENT / "successor-quotes-v1.json"
TRANSLATION = CONTENT / "successor-translation-ledger-v1.json"
AMENDMENTS = CONTENT / "successor-integrity-amendments-v1.json"
SOURCE_RELEASE = CONTENT / "successor-release-v2.json"
SOURCE_ACTIVATION = CONTENT / "successor-activation-v1.json"
DEPTH_RELEASE = CONTENT / "successor-depth-release-v1.json"
AUDIT = CONTENT / "quote-depth-audit-v1.json"
POLICY_V2 = CONTENT / "presentation-policy.json"
POLICY_V3 = CONTENT / "presentation-policy-v3.json"
CHAT_ID = -1001295216957
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def _source_v1_queue():
    policy = load_presentation_policy(POLICY_V2)
    return build_successor_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
        release_path=SOURCE_RELEASE,
        activation_path=SOURCE_ACTIVATION,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )


def _published_entry(post, index: int) -> LedgerEntry:
    attempted = datetime(2026, 9, 19, 9, 0, tzinfo=UTC) + timedelta(days=index)
    published = attempted + timedelta(seconds=5)
    message_id = 1500 + index
    return LedgerEntry(
        publication_id=post.publication_id,
        payload_sha256=post.payload_sha256,
        state="published",
        provider_effect="verified",
        intent_id=f"depth-history-{index}",
        dispatch_mode="scheduled",
        scheduled_slot="morning",
        workflow_run_id=str(35000000000 + index),
        workflow_run_attempt="1",
        github_sha="1" * 40,
        github_workflow_sha="2" * 40,
        attempted_at_utc=attempted,
        published_at_utc=published,
        message_id=message_id,
        message_url=f"https://t.me/lordchrist/{message_id}",
        actual_chat_id=CHAT_ID,
        actual_chat_username="lordchrist",
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
    )


def _exact_source_v1_ledger(queue) -> TelegramLedger:
    release = load_depth_release(DEPTH_RELEASE)
    ledger = initialize_ledger(queue)
    for index, post in enumerate(queue.posts[: release.handoff_published_prefix], start=1):
        ledger.entries[post.publication_id] = _published_entry(post, index)
    return TelegramLedger.model_validate(ledger.model_dump(mode="json"))


def test_depth_audit_remains_the_immutable_original_10_29_21_snapshot() -> None:
    audit = load_depth_audit(AUDIT)

    assert len(audit.entries) == 60
    assert [entry.verdict for entry in audit.entries[:10]] == ["history_locked"] * 10
    assert sum(entry.verdict == "keep" for entry in audit.entries[10:]) == 29
    assert sum(entry.verdict == "replace" for entry in audit.entries[10:]) == 21


def test_depth_release_records_13_published_and_47_future_without_rewriting_audit() -> None:
    release = load_depth_release(DEPTH_RELEASE)

    assert release.handoff_published_prefix == 13
    assert release.future_post_count == 47
    assert release.future_keep_count == 27
    assert release.future_replace_count == 20
    assert release.replacement_pool_count == 21
    assert release.superseded_replacement_count == 1
    assert release.normalized_queue_digest == DEPTH_QUEUE_DIGEST


def test_depth_v2_preserves_13_published_payloads_and_rekeys_only_future_suffix() -> None:
    source = _source_v1_queue()
    release = load_depth_release(DEPTH_RELEASE)
    depth = build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )
    handoff = release.handoff_published_prefix

    assert depth.digest == DEPTH_QUEUE_DIGEST
    assert len(depth.posts) == 60
    assert [post.publication_id for post in depth.posts[:handoff]] == [
        post.publication_id for post in source.posts[:handoff]
    ]
    assert [post.payload_sha256 for post in depth.posts[:handoff]] == [
        post.payload_sha256 for post in source.posts[:handoff]
    ]

    source_future_ids = {post.publication_id for post in source.posts[handoff:]}
    depth_future_ids = [post.publication_id for post in depth.posts[handoff:]]
    assert len(depth_future_ids) == 47
    assert len(depth_future_ids) == len(set(depth_future_ids))
    assert source_future_ids.isdisjoint(depth_future_ids)
    assert all(publication_id.startswith("lordchrist-successor-depth-v2-") for publication_id in depth_future_ids)


def test_sequence_13_is_immutable_even_though_original_audit_marked_it_for_replacement() -> None:
    source = _source_v1_queue()
    depth = build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )

    assert depth.posts[12].publication_id == source.posts[12].publication_id
    assert depth.posts[12].payload_sha256 == source.posts[12].payload_sha256


def test_future_depth_posts_use_reviewed_replacements_without_legacy_labels() -> None:
    depth = build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )
    by_sequence = {post.sequence: post for post in depth.posts}

    assert by_sequence[25].publication_id.endswith("watson-sin-ungod")
    assert "лишил бы Его Божества" in by_sequence[25].text
    assert by_sequence[46].publication_id.endswith("macarthur-scripture-sufficiency")
    assert "записанного Слова Божьего" in by_sequence[46].text
    assert by_sequence[58].publication_id.endswith("spurgeon-justification-faith")
    assert "ни в какой мере и ни в какой степени" in by_sequence[58].text
    assert by_sequence[59].publication_id.endswith("spurgeon-resurrection-keystone")
    assert "Иисус распятый и воскресший" in by_sequence[59].text

    for post in depth.posts[13:]:
        assert "Пояснение:" not in post.text
        assert "© " not in post.text
        blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
        attribution = f"— {post.source.author}, «{post.source.work}»"
        assert attribution in blocks
        attribution_index = blocks.index(attribution)
        assert attribution_index >= 1
        assert attribution_index < len(blocks) - 2
        assert len("\n\n".join(blocks[attribution_index + 1 : -1])) >= 80
        assert blocks[-1].startswith("#")


def test_quote_v3_renders_native_blockquote_then_attribution_context_and_tags() -> None:
    depth = build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )
    policy = load_presentation_policy(POLICY_V3)
    rendered = render_post(depth.posts[13], policy)

    assert rendered.presentation_policy_id == "lordchrist-quote-v3"
    assert rendered.html_text.startswith("<blockquote>")
    assert "</blockquote>\n\n<i>— " in rendered.html_text
    assert "Пояснение:" not in rendered.text
    assert "© " not in rendered.text
    assert [entity.type for entity in rendered.expected_entities] == ["blockquote", "italic"]
    assert rendered.text.endswith(depth.posts[13].text.split("\n\n")[-1])


def test_exact_v1_handoff_accepts_only_13_published_and_47_pristine_pending() -> None:
    source = _source_v1_queue()
    release = load_depth_release(DEPTH_RELEASE)
    ledger = _exact_source_v1_ledger(source)

    require_exact_v1_handoff(source, ledger, published_prefix=release.handoff_published_prefix)

    contaminated = TelegramLedger.model_validate(ledger.model_dump(mode="json"))
    post_14 = source.posts[release.handoff_published_prefix]
    contaminated.entries[post_14.publication_id] = _published_entry(post_14, 14)
    with pytest.raises(ValueError, match="pristine unpublished suffix"):
        require_exact_v1_handoff(
            source,
            contaminated,
            published_prefix=release.handoff_published_prefix,
        )


def test_depth_ledger_copies_verified_history_exactly_and_creates_new_pending_suffix(tmp_path: Path) -> None:
    source = _source_v1_queue()
    source_ledger = _exact_source_v1_ledger(source)
    release = load_depth_release(DEPTH_RELEASE)
    depth = build_depth_runtime_queue(
        candidate_path=CANDIDATE,
        translation_ledger_path=TRANSLATION,
        integrity_amendment_path=AMENDMENTS,
    )
    path = tmp_path / "depth-ledger.json"

    migrated = initialize_depth_ledger(
        path=path,
        depth_queue=depth,
        source_v1_queue=source,
        source_v1_ledger=source_ledger,
        release=release,
    )

    handoff = release.handoff_published_prefix
    assert migrated.queue_digest == DEPTH_QUEUE_DIGEST
    assert len(migrated.entries) == 60
    assert all(migrated.entries[post.publication_id].state == "published" for post in depth.posts[:handoff])
    assert all(
        migrated.entries[post.publication_id].provider_effect == "verified" for post in depth.posts[:handoff]
    )
    assert all(migrated.entries[post.publication_id].state == "pending" for post in depth.posts[handoff:])
    assert all(
        migrated.entries[post.publication_id].provider_effect == "impossible" for post in depth.posts[handoff:]
    )
    assert all(
        migrated.entries[post.publication_id].payload_sha256 == post.payload_sha256
        for post in depth.posts[handoff:]
    )


def test_depth_release_fails_closed_if_audit_blob_changes(tmp_path: Path) -> None:
    tampered = tmp_path / AUDIT.name
    tampered.write_text(
        AUDIT.read_text(encoding="utf-8").replace("Сильная никейская", "Тампер: сильная никейская", 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="audit Git blob differs"):
        build_depth_runtime_queue(
            candidate_path=CANDIDATE,
            translation_ledger_path=TRANSLATION,
            integrity_amendment_path=AMENDMENTS,
            audit_path=tampered,
        )
