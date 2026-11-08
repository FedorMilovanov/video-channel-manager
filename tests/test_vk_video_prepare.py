from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import video_channel_manager.wave_engine.vk_video_prepare as prepare_module
from video_channel_manager.domain.enums import ChannelKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.wave_engine.vk_video_prepare import (
    VkVideoPreparationError,
    prepare_vk_video_wave,
)


YT_CHANNEL = "UC-78ys2S3cQ3lpqgXfo-SvQ"
VK_COMMUNITY = "235216998"


def _ref(platform: PlatformName, channel_id: str, remote_id: str) -> RemoteRef:
    return RemoteRef(platform=platform, channel_id=channel_id, remote_id=remote_id)


def _audit(
    platform: PlatformName,
    channel_id: str,
    videos: list[VideoRecord],
) -> AuditPackage:
    kind = ChannelKind.VIDEO_CHANNEL if platform is PlatformName.YOUTUBE else ChannelKind.COMMUNITY
    return AuditPackage(
        channel=ChannelRecord(
            ref=_ref(platform, channel_id, channel_id),
            title="The Legendary Poet",
            kind=kind,
        ),
        videos=videos,
    )


def _video(
    platform: PlatformName,
    channel_id: str,
    remote_id: str,
    title: str,
    duration: int,
) -> VideoRecord:
    return VideoRecord(
        ref=_ref(platform, channel_id, remote_id),
        title=title,
        description="Описание",
        duration_seconds=duration,
        published_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        privacy_status="public",
        revision=f"sha256:{remote_id}",
    )


def _write_audit(path: Path, audit: AuditPackage) -> None:
    path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")


def _patch_reused_media(
    monkeypatch: pytest.MonkeyPatch,
    *,
    media: Path,
    manifest: Path,
) -> None:
    artifact = SimpleNamespace(
        source=SimpleNamespace(source_id="yt-1"),
        manifest_sha256="a" * 64,
    )
    monkeypatch.setattr(prepare_module, "load_media_artifact_manifest", lambda _path: artifact)
    monkeypatch.setattr(
        prepare_module,
        "_reuse_media_manifest",
        lambda **_kwargs: (media.resolve(), manifest.resolve()),
    )


def test_video_prepare_builds_digest_locked_canary_operator_bundle_without_provider_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_path = root / "youtube.json"
    target_path = root / "vk.json"
    source = _audit(
        PlatformName.YOUTUBE,
        YT_CHANNEL,
        [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-1", "Новый ролик", 305)],
    )
    target = _audit(PlatformName.VK, VK_COMMUNITY, [])
    _write_audit(source_path, source)
    _write_audit(target_path, target)

    media = root / "yt-1.mp4"
    media.write_bytes(b"video")
    media_manifest = root / "yt-1-manifest.json"
    media_manifest.write_text('{"manifest":true}\n', encoding="utf-8")
    _patch_reused_media(monkeypatch, media=media, manifest=media_manifest)

    output = root / "wave"
    summary = prepare_vk_video_wave(
        project_key="legendary-poet",
        source_audit_path=source_path,
        target_audit_path=target_path,
        candidate_ids=["yt-1"],
        canary_id="yt-1",
        repository_root=root,
        output_root=output,
        reuse_media_manifests=[media_manifest],
    )

    assert summary["provider_writes"] == 0
    assert summary["candidate_ids"] == ["yt-1"]
    assert summary["canary_id"] == "yt-1"
    assert summary["batch"] is None

    request_path = root / summary["canary"]["request_path"]
    manifest_path = root / summary["canary"]["manifest_path"]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    operator_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert request["mode"] == "apply"
    assert request["confirm_project_key"] == "legendary-poet"
    assert request["confirm_community_id"] == 235216998
    assert request["confirm_operation_count"] == 1
    assert operator_manifest["operation_class"] == "ambiguous_mutation"
    assert operator_manifest["provider_mutation"] is True
    assert operator_manifest["arguments"][:2] == ["wave", "apply"]
    assert "--enable-provider-writes" in operator_manifest["arguments"]

    selection = json.loads((output / "evidence" / "selection.json").read_text(encoding="utf-8"))
    assert selection["selected_candidate_ids"] == ["yt-1"]
    assert selection["provider_writes_during_preparation"] == 0
    assert selection["media"][0]["reused"] is True


def test_video_prepare_rejects_candidate_that_is_already_present_on_vk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_path = root / "youtube.json"
    target_path = root / "vk.json"
    source = _audit(
        PlatformName.YOUTUBE,
        YT_CHANNEL,
        [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-1", "Уже есть", 305)],
    )
    target = _audit(
        PlatformName.VK,
        VK_COMMUNITY,
        [_video(PlatformName.VK, VK_COMMUNITY, "-235216998_501", "Уже есть", 305)],
    )
    _write_audit(source_path, source)
    _write_audit(target_path, target)

    media = root / "yt-1.mp4"
    media.write_bytes(b"video")
    media_manifest = root / "yt-1-manifest.json"
    media_manifest.write_text('{"manifest":true}\n', encoding="utf-8")
    _patch_reused_media(monkeypatch, media=media, manifest=media_manifest)

    with pytest.raises(VkVideoPreparationError, match="not proof-backed missing on target"):
        prepare_vk_video_wave(
            project_key="legendary-poet",
            source_audit_path=source_path,
            target_audit_path=target_path,
            candidate_ids=["yt-1"],
            canary_id="yt-1",
            repository_root=root,
            output_root=root / "wave",
            reuse_media_manifests=[media_manifest],
        )


def test_video_prepare_allows_no_target_snapshot_and_relies_on_live_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_path = root / "youtube.json"
    source = _audit(
        PlatformName.YOUTUBE,
        YT_CHANNEL,
        [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-1", "Новый ролик", 305)],
    )
    _write_audit(source_path, source)
    media = root / "yt-1.mp4"
    media.write_bytes(b"video")
    media_manifest = root / "yt-1-manifest.json"
    media_manifest.write_text('{"manifest":true}\n', encoding="utf-8")
    _patch_reused_media(monkeypatch, media=media, manifest=media_manifest)

    summary = prepare_vk_video_wave(
        project_key="legendary-poet",
        source_audit_path=source_path,
        target_audit_path=None,
        candidate_ids=["yt-1"],
        canary_id="yt-1",
        repository_root=root,
        output_root=root / "wave",
        reuse_media_manifests=[media_manifest],
    )

    assert summary["vk_snapshot_id"] is None
    assert summary["batch"] is None
    selection = json.loads((root / "wave" / "evidence" / "selection.json").read_text(encoding="utf-8"))
    assert selection["vk_snapshot_id"] is None


def test_video_prepare_rejects_multi_source_batch() -> None:
    with pytest.raises(VkVideoPreparationError, match="one-source-per-run"):
        prepare_vk_video_wave(
            project_key="legendary-poet",
            source_audit_path=Path("unused"),
            target_audit_path=None,
            candidate_ids=["a", "b"],
            canary_id="a",
            repository_root=Path("."),
            output_root=Path("wave"),
        )


def test_short_horizontal_video_remains_blocked_without_reviewed_opt_in(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_file = root / "youtube.json"
    source = _audit(
        PlatformName.YOUTUBE,
        YT_CHANNEL,
        [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-179", "Short landscape", 179)],
    )
    _write_audit(source_file, source)

    with pytest.raises(VkVideoPreparationError, match="explicit reviewed override"):
        prepare_vk_video_wave(
            project_key="legendary-poet",
            source_audit_path=source_file,
            target_audit_path=None,
            candidate_ids=["yt-179"],
            canary_id="yt-179",
            repository_root=root,
            output_root=root / "wave",
        )

    assert not (root / "wave").exists()


@pytest.mark.parametrize(
    ("width", "height", "video_streams", "audio_streams"),
    [
        (1080, 1920, 1, 1),
        (1080, 1080, 1, 1),
        (1920, 1080, 0, 1),
        (1920, 1080, 1, 0),
    ],
)
def test_reviewed_short_horizontal_video_rejects_unproved_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    width: int,
    height: int,
    video_streams: int,
    audio_streams: int,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_file = root / "youtube.json"
    _write_audit(
        source_file,
        _audit(
            PlatformName.YOUTUBE,
            YT_CHANNEL,
            [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-179", "Short landscape", 179)],
        ),
    )
    media = root / "yt-179.mp4"
    media.write_bytes(b"video")
    manifest = root / "yt-179-manifest.json"
    manifest.write_text('{"manifest":true}\n', encoding="utf-8")
    _patch_reused_media(monkeypatch, media=media, manifest=manifest)
    monkeypatch.setattr(
        prepare_module,
        "load_media_artifact_manifest",
        lambda _path: SimpleNamespace(
            source=SimpleNamespace(source_id="yt-179"),
            manifest_sha256="sha256:" + "a" * 64,
            probe=SimpleNamespace(
                width=width,
                height=height,
                video_stream_count=video_streams,
                audio_stream_count=audio_streams,
            ),
        ),
    )

    with pytest.raises(VkVideoPreparationError, match="probed horizontal media"):
        prepare_vk_video_wave(
            project_key="legendary-poet",
            source_audit_path=source_file,
            target_audit_path=None,
            candidate_ids=["yt-179"],
            canary_id="yt-179",
            repository_root=root,
            output_root=root / "wave",
            reuse_media_manifests=[manifest],
            reviewed_short_horizontal_video=True,
        )

    assert not (root / "wave" / "canary" / "plan.json").exists()


def test_reviewed_short_horizontal_video_accepts_179_seconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source_file = root / "youtube.json"
    _write_audit(
        source_file,
        _audit(
            PlatformName.YOUTUBE,
            YT_CHANNEL,
            [_video(PlatformName.YOUTUBE, YT_CHANNEL, "yt-179", "Short landscape", 179)],
        ),
    )
    media = root / "yt-179.mp4"
    media.write_bytes(b"video")
    manifest = root / "yt-179-manifest.json"
    manifest.write_text('{"manifest":true}\n', encoding="utf-8")
    _patch_reused_media(monkeypatch, media=media, manifest=manifest)
    monkeypatch.setattr(
        prepare_module,
        "load_media_artifact_manifest",
        lambda _path: SimpleNamespace(
            source=SimpleNamespace(source_id="yt-179"),
            manifest_sha256="sha256:" + "a" * 64,
            probe=SimpleNamespace(width=1920, height=1080, video_stream_count=1, audio_stream_count=1),
        ),
    )

    summary = prepare_vk_video_wave(
        project_key="legendary-poet",
        source_audit_path=source_file,
        target_audit_path=None,
        candidate_ids=["yt-179"],
        canary_id="yt-179",
        repository_root=root,
        output_root=root / "wave",
        reuse_media_manifests=[manifest],
        reviewed_short_horizontal_video=True,
    )
    plan = json.loads((root / "wave" / "canary" / "plan.json").read_text(encoding="utf-8"))
    payload = plan["operations"][0]["payload"]

    assert summary["provider_writes"] == 0
    assert payload["source_duration_seconds"] == 179
    assert payload["reviewed_short_horizontal_video"] is True
    assert payload["wallpost"] is False
    assert payload["auto_publish"] is False
    assert payload["repeat"] is False
