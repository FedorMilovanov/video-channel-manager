from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_research import load_research_queue, validate_public_copy
from video_channel_manager.telegram_research_release import (
    build_research_release_candidate,
    research_evidence_sha256,
)
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
QUEUE_PATH = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"


def test_research_adapter_builds_exact_relative_generic_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    start = datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow"))

    release = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=start,
    )

    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert release.project_key == research.project_key == profile.project_key
    assert release.channel_username == research.channel_username == profile.channel_username
    assert [item.scheduled_at for item in release.items] == [
        datetime(2026, 8, day, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")) for day in (10, 12, 14, 16, 18)
    ]
    assert [item.source_sha256 for item in release.items] == [
        research_evidence_sha256(research, post) for post in research.posts
    ]
    assert [item.source_sha256 for item in release.items] != [post.payload_sha256 for post in research.posts]


def test_release_source_binding_changes_when_evidence_registry_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    start = datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow"))
    original = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=start,
    )

    changed = research.model_copy(update={"source_registry_sha256": "sha256:" + "0" * 64})
    rebuilt = build_research_release_candidate(
        profile,
        changed,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=start,
    )

    assert [item.payload for item in rebuilt.items] == [item.payload for item in original.items]
    assert [item.source_sha256 for item in rebuilt.items] != [item.source_sha256 for item in original.items]
    assert rebuilt.candidate_digest() != original.candidate_digest()


def test_release_source_binding_changes_when_evidence_contract_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    research = load_research_queue(QUEUE_PATH)
    post = research.posts[0]
    original = research_evidence_sha256(research, post)

    changed_verification = research.verification.model_copy(
        update={"reviewed_pages": research.verification.reviewed_pages + 1}
    )
    changed = research.model_copy(update={"verification": changed_verification})
    assert changed.posts[0].payload_sha256 == post.payload_sha256
    assert changed.source_registry_sha256 == research.source_registry_sha256
    assert changed.evidence_digest != research.evidence_digest
    assert research_evidence_sha256(changed, changed.posts[0]) != original


def test_activation_state_changes_queue_digest_but_not_evidence_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    research = load_research_queue(QUEUE_PATH)
    post = research.posts[0]
    original_source = research_evidence_sha256(research, post)
    armed_schedule = research.schedule.model_copy(
        update={
            "state": "armed",
            "activation_at_utc": datetime(2026, 8, 10, 16, 20, tzinfo=UTC),
            "canary_publication_id": post.publication_id,
            "canary_message_id": 1500,
        }
    )
    armed = research.model_copy(update={"schedule": armed_schedule})

    assert armed.digest != research.digest
    assert armed.evidence_digest == research.evidence_digest
    assert research_evidence_sha256(armed, armed.posts[0]) == original_source


def test_research_adapter_preserves_canonical_reader_text_and_only_bolds_heading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    release = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    for post, item in zip(research.posts, release.items, strict=True):
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        payload = item.payload
        assert payload.schema_name == "video-channel-manager.telegram-generic-message-payload"
        assert payload.expected_plain_text == body
        assert payload.html_text.startswith("<b>")
        assert len(payload.expected_entities) == 1
        entity = payload.expected_entities[0]
        assert entity.type == "bold"
        assert entity.offset == 0
        assert entity.length == len(body.splitlines()[0].encode("utf-16-le")) // 2


def test_research_adapter_accepts_exact_read_only_target_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    binding = TelegramTargetBinding(
        schema_name="video-channel-manager.telegram-target-binding",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        chat_id=-1001295216957,
        chat_username="lordchrist",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        can_post_messages=True,
        discovered_at_utc=datetime(2026, 8, 8, 8, 0, tzinfo=UTC),
        discovery_method="getMe + getChat(@username) + getChat(numeric id) + getChatAdministrators",
        provider_write_performed=False,
    )

    release = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
        binding=binding,
    )

    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username
    assert release.release_authorized is False


def test_research_adapter_rejects_naive_start_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_research_release_candidate(
            profile,
            research,
            release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
            start_at=datetime(2026, 8, 10, 19, 17),
        )


def test_research_adapter_rejects_identity_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    profile = load_channel_profile(PROFILE_PATH)
    research = load_research_queue(QUEUE_PATH)
    changed = research.model_copy(update={"channel_username": "@not_lordchrist"})
    with pytest.raises(ValueError, match="identity differs"):
        build_research_release_candidate(
            profile,
            changed,
            release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
            start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
        )
