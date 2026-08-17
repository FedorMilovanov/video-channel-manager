from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

import video_channel_manager.platforms.vk.milovi_rollout_sources as sources
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_SOURCE_ALLOWLIST
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    SourceAsset,
    build_description,
    build_wall_message,
)


def _cached_assets(tmp_path: Path) -> list[SourceAsset]:
    media_dir = tmp_path / "legacy-media"
    media_dir.mkdir(parents=True)
    assets: list[SourceAsset] = []
    for source_id in ROLL_OUT_IDS:
        media_path = media_dir / f"{source_id}.mp4"
        media_path.write_bytes(f"legacy:{source_id}".encode())
        assets.append(
            SourceAsset(
                source_id=source_id,
                source_url=f"https://www.youtube.com/shorts/{source_id}",
                title=f"Title {source_id}",
                duration_seconds=30,
                media_path=str(media_path),
                media_sha256=sources.sha256_file(media_path),
                width=1080,
                height=1920,
                description=f"Description {source_id}",
                wall_message=f"Wall {source_id}",
            )
        )
    return assets


def _write_manifest(work_dir: Path, assets: list[SourceAsset]) -> None:
    sources.write_json_atomic(
        work_dir / "prepared-sources.json",
        {
            "schema_name": sources.PREPARED_SCHEMA,
            "schema_version": 1,
            "source_snapshot_id": sources.SOURCE_SNAPSHOT_ID,
            "assets": [asdict(asset) for asset in assets],
        },
    )


def test_issue323_reviewed_source_allowlist_is_exact() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert frozenset(ROLL_OUT_IDS) == MILOVI_SOURCE_ALLOWLIST
    assert ROLL_OUT_IDS[0] == "d48QLgOuiTs"
    assert "SiluLt5Bz1c" not in ROLL_OUT_IDS
    assert SOURCE_SNAPSHOT_ID == "milovi-cake-issue-323-reviewed-public106-final-d48-a8841ece-v1"


def test_source_description_and_wall_copy_keep_exact_source_marker() -> None:
    source_id = "d48QLgOuiTs"
    description = build_description("Торт", source_id)
    wall_message = build_wall_message("Торт", source_id)

    assert description.endswith(f"https://www.youtube.com/shorts/{source_id}")
    assert wall_message.count(f"https://www.youtube.com/shorts/{source_id}") == 1
    assert "https://milovicake.ru/" in wall_message


def test_download_selector_requires_avc_h264_and_aac() -> None:
    assert "vcodec^=avc1" in sources.VK_CLIP_FORMAT_SELECTOR
    assert "acodec^=mp4a" in sources.VK_CLIP_FORMAT_SELECTOR
    assert "ext=mp4" in sources.VK_CLIP_FORMAT_SELECTOR
    assert sources.VK_VIDEO_CODEC == "h264"
    assert sources.VK_AUDIO_CODEC == "aac"


def test_source_probe_rejects_codec_incompatible_media(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "streams": [
            {"codec_type": "video", "codec_name": "vp9", "width": 1080, "height": 1920},
            {"codec_type": "audio", "codec_name": "opus"},
        ],
        "format": {"duration": "30.0"},
    }
    monkeypatch.setattr(sources, "_run_checked", lambda args, timeout: json.dumps(payload))

    with pytest.raises(sources.MiloviSourceCodecError, match="h264/aac"):
        sources._probe_media("ffprobe", tmp_path / "legacy.mp4")


def test_legacy_codec_cache_is_refreshed_locally_before_provider_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assets = _cached_assets(tmp_path)
    _write_manifest(tmp_path, assets)
    required: list[str] = []

    def fake_require(name: str) -> str:
        required.append(name)
        return name

    monkeypatch.setattr(sources, "_require_tool", fake_require)

    def reject_legacy(ffprobe: str, media_path: Path) -> tuple[int, int, float]:
        del ffprobe, media_path
        raise sources.MiloviSourceCodecError("legacy codecs")

    monkeypatch.setattr(sources, "_probe_media", reject_legacy)
    transcoded: list[str] = []

    def fake_transcode(ffmpeg: str, ffprobe: str, asset: SourceAsset, media_dir: Path) -> SourceAsset:
        assert ffmpeg == "ffmpeg"
        assert ffprobe == "ffprobe"
        transcoded.append(asset.source_id)
        media_path = media_dir / f"{asset.source_id}.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(f"h264-aac:{asset.source_id}".encode())
        return SourceAsset(
            source_id=asset.source_id,
            source_url=asset.source_url,
            title=asset.title,
            duration_seconds=asset.duration_seconds,
            media_path=str(media_path),
            media_sha256=sources.sha256_file(media_path),
            width=asset.width,
            height=asset.height,
            description=asset.description,
            wall_message=asset.wall_message,
        )

    monkeypatch.setattr(sources, "_transcode_legacy_asset", fake_transcode)
    refreshed = sources.prepare_sources(tmp_path)

    assert tuple(transcoded) == ROLL_OUT_IDS
    assert "ffmpeg" in required
    assert "yt-dlp" not in required
    assert tuple(asset.source_id for asset in refreshed) == ROLL_OUT_IDS
    manifest = json.loads((tmp_path / "prepared-sources.json").read_text(encoding="utf-8"))
    assert manifest["media_profile"] == "vk-h264-aac-v1"


def test_changed_cached_bytes_hard_fail_instead_of_refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assets = _cached_assets(tmp_path)
    _write_manifest(tmp_path, assets)
    Path(assets[0].media_path).write_bytes(b"tampered")
    monkeypatch.setattr(sources, "_require_tool", lambda name: name)

    with pytest.raises(sources.MiloviSourceError, match="missing or changed"):
        sources.prepare_sources(tmp_path)
