import pytest

from video_channel_manager.application.cross_platform import compare_audit_packages
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _video(platform: PlatformName, channel_id: str, remote_id: str, title: str, duration: int) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        duration_seconds=duration,
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _audit(platform: PlatformName, channel_id: str, videos: list[VideoRecord]) -> AuditPackage:
    kind = ChannelKind.VIDEO_CHANNEL if platform == PlatformName.YOUTUBE else ChannelKind.COMMUNITY
    return AuditPackage(
        channel=ChannelRecord(ref=_ref(platform, channel_id, channel_id), title=channel_id, kind=kind),
        videos=videos,
    )


def test_reviewed_mapping_runs_before_titles() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Исходное название", 120)],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Совсем другое название", 120)],
    )

    result = compare_audit_packages(source, target, reviewed_video_mapping={"yt-1": "vk-1"})

    assert len(result.matches) == 1
    assert result.matches[0].match_method == "reviewed_mapping"
    assert result.matches[0].source_ref.remote_id == "yt-1"
    assert result.matches[0].target_ref.remote_id == "vk-1"


def test_reviewed_mapping_rejects_duplicate_target() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Один", 120),
            _video(PlatformName.YOUTUBE, "youtube-channel", "yt-2", "Два", 120),
        ],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Цель", 120)],
    )

    with pytest.raises(ValueError, match="one-to-one"):
        compare_audit_packages(
            source,
            target,
            reviewed_video_mapping={"yt-1": "vk-1", "yt-2": "vk-1"},
        )


def test_exact_title_duration_mismatch_is_conflict_not_missing() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Россия — Александр Блок", 300)],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Россия — Александр Блок", 500)],
    )

    result = compare_audit_packages(source, target)

    assert result.matches == []
    assert result.conflicts[0].reason == "exact_title_duration_mismatch"
    assert result.conflicts[0].candidates[0].duration_delta_seconds == 200
    assert result.missing_on_target == []
    assert result.extra_on_target == []


def test_unique_fuzzy_candidate_is_selected_after_exact_phase() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза Сергей Есенин live", 200)],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Береза Сергей Есенин концерт", 200)],
    )

    result = compare_audit_packages(source, target)

    assert len(result.matches) == 1
    assert result.matches[0].match_method == "fuzzy_unique"
    assert result.conflicts == []


def test_non_unique_fuzzy_component_becomes_conflict() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза Сергей Есенин live", 200)],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [
            _video(PlatformName.VK, "vk-channel", "vk-1", "Береза Сергей Есенин концерт", 200),
            _video(PlatformName.VK, "vk-channel", "vk-2", "Береза Сергей Есенин запись", 200),
        ],
    )

    result = compare_audit_packages(source, target)

    assert result.matches == []
    assert result.conflict_count == 1
    assert result.conflicts[0].reason == "non_unique_fallback"
    assert len(result.conflicts[0].candidates) == 2
    assert result.missing_on_target == []
    assert result.extra_on_target == []


def test_result_is_independent_of_input_order() -> None:
    source_videos = [
        _video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Берёза — Сергей Есенин", 242),
        _video(PlatformName.YOUTUBE, "youtube-channel", "yt-2", "Россия — Александр Блок", 315),
        _video(PlatformName.YOUTUBE, "youtube-channel", "yt-3", "Парус Михаил Лермонтов live", 210),
    ]
    target_videos = [
        _video(PlatformName.VK, "vk-channel", "vk-1", "Береза — Сергей Есенин", 242),
        _video(PlatformName.VK, "vk-channel", "vk-2", "Россия — Александр Блок", 315),
        _video(PlatformName.VK, "vk-channel", "vk-3", "Парус Михаил Лермонтов концерт", 210),
    ]

    forward = compare_audit_packages(
        _audit(PlatformName.YOUTUBE, "youtube-channel", source_videos),
        _audit(PlatformName.VK, "vk-channel", target_videos),
    )
    reversed_result = compare_audit_packages(
        _audit(PlatformName.YOUTUBE, "youtube-channel", list(reversed(source_videos))),
        _audit(PlatformName.VK, "vk-channel", list(reversed(target_videos))),
    )

    forward_pairs = [
        (item.source_ref.remote_id, item.target_ref.remote_id, item.match_method) for item in forward.matches
    ]
    reversed_pairs = [
        (item.source_ref.remote_id, item.target_ref.remote_id, item.match_method) for item in reversed_result.matches
    ]
    assert forward_pairs == reversed_pairs
    assert forward.conflicts == reversed_result.conflicts


def test_unrelated_equal_duration_titles_do_not_create_fuzzy_candidate() -> None:
    source = _audit(
        PlatformName.YOUTUBE,
        "youtube-channel",
        [_video(PlatformName.YOUTUBE, "youtube-channel", "yt-1", "Россия Александр Блок", 300)],
    )
    target = _audit(
        PlatformName.VK,
        "vk-channel",
        [_video(PlatformName.VK, "vk-channel", "vk-1", "Фотография Борис Пастернак", 300)],
    )

    result = compare_audit_packages(source, target)

    assert result.matches == []
    assert result.conflicts == []
    assert [item.ref.remote_id for item in result.missing_on_target] == ["yt-1"]
    assert [item.ref.remote_id for item in result.extra_on_target] == ["vk-1"]
