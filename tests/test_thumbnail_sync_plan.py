from __future__ import annotations

from pathlib import Path

from scripts.sync_youtube_thumbnails_to_vk import (
    PreparedThumbnail,
    ThumbnailCandidate,
    _candidate_identity,
    _candidates,
    _cover_complete,
    _manifest_sha256,
)
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.local_media.image_quality import ImageQualityReport


def _source() -> AuditPackage:
    return AuditPackage(
        channel=ChannelRecord(
            ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id="channel", remote_id="channel"),
            title="The Legendary Poet",
            kind=ChannelKind.VIDEO_CHANNEL,
        ),
        videos=[
            VideoRecord(
                ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id="channel", remote_id="yt-1"),
                title="Берёза",
                thumbnail_url="https://img.youtube.test/one.jpg",
                privacy_status="public",
                revision="sha256:one",
            ),
            VideoRecord(
                ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id="channel", remote_id="yt-2"),
                title="Россия",
                thumbnail_url="https://img.youtube.test/two.jpg",
                privacy_status="public",
                revision="sha256:two",
            ),
        ],
    )


def _journal() -> dict[str, object]:
    return {
        "uploads": {
            "yt-1": {"remote_id": "-235216998_1"},
            "yt-2": {"remote_id": "-235216998_2"},
        },
        "covers": {},
    }


def test_only_successful_cover_status_is_excluded() -> None:
    assert _cover_complete({"status": "installed_youtube_thumbnail_copied_to_vk"}) is True
    assert _cover_complete({"status": "thumbnail_upload_pending"}) is False
    assert _cover_complete({"status": "thumbnail_upload_failed"}) is False
    assert _cover_complete(None) is False


def test_failed_or_pending_cover_remains_candidate() -> None:
    journal = _journal()
    journal["covers"] = {
        "yt-1": {"status": "installed_youtube_thumbnail_copied_to_vk"},
        "yt-2": {"status": "thumbnail_upload_failed"},
    }

    candidates = _candidates(_source(), journal)

    assert [item.source_video_id for item in candidates] == ["yt-2"]
    assert candidates[0].remote_id == "-235216998_2"


def test_candidate_identity_contains_exact_source_target_and_url() -> None:
    candidates = _candidates(_source(), _journal())

    assert _candidate_identity(candidates) == [
        {
            "source_video_id": "yt-1",
            "remote_id": "-235216998_1",
            "thumbnail_url": "https://img.youtube.test/one.jpg",
        },
        {
            "source_video_id": "yt-2",
            "remote_id": "-235216998_2",
            "thumbnail_url": "https://img.youtube.test/two.jpg",
        },
    ]


def _prepared(path: Path, *, remote_id: str = "-235216998_1", sha256: str = "sha256:image") -> PreparedThumbnail:
    return PreparedThumbnail(
        candidate=ThumbnailCandidate(
            source_video_id="yt-1",
            title="Берёза",
            thumbnail_url="https://img.youtube.test/one.jpg",
            remote_id=remote_id,
        ),
        path=path,
        quality=ImageQualityReport(
            path=str(path),
            size_bytes=100,
            sha256=sha256,
            format="jpeg",
            width=1280,
            height=720,
        ),
    )


def test_thumbnail_manifest_is_stable_and_binds_target_and_bytes(tmp_path: Path) -> None:
    path = tmp_path / "one.jpg"
    first = _manifest_sha256([_prepared(path)])

    assert first == _manifest_sha256([_prepared(path)])
    assert first != _manifest_sha256([_prepared(path, remote_id="-235216998_9")])
    assert first != _manifest_sha256([_prepared(path, sha256="sha256:different")])
