from __future__ import annotations

import inspect
import json
from dataclasses import asdict
from pathlib import Path

import pytest

import video_channel_manager.platforms.vk.milovi_rollout_sources as sources
import video_channel_manager.platforms.vk.milovi_token_clip_rollout as rollout
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS, SourceAsset


def _facts(*, duration: float = 59.0, width: int = 1080, height: int = 1920) -> dict[str, tuple[int, int, float]]:
    return {source_id: (width, height, duration) for source_id in ROLL_OUT_IDS}


def _asset() -> SourceAsset:
    return SourceAsset(
        source_id=ROLL_OUT_IDS[0],
        source_url=f"https://www.youtube.com/shorts/{ROLL_OUT_IDS[0]}",
        title="Milovi test",
        duration_seconds=59,
        media_path="unused.mp4",
        media_sha256="0" * 64,
        width=1080,
        height=1920,
        description="source marker",
        wall_message="wall",
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


def test_token_rollout_uses_exact_reviewed_canary_and_confirmation() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert ROLL_OUT_IDS[0] == rollout.CANARY_SOURCE_ID == "d48QLgOuiTs"
    assert rollout.EXECUTION_CONFIRMATION == "ISSUE_323_UPLOAD_12_CLIPS_AND_POSTPONE_DAILY"


def test_all_12_short_vertical_media_facts_pass_provider_inert_gate() -> None:
    rollout.validate_token_clip_media_facts(_facts(duration=60.0))


def test_any_over_60_seconds_blocks_whole_batch_before_writes() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[7]] = (1080, 1920, 60.001)
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match=r"<=60\.0s"):
        rollout.validate_token_clip_media_facts(facts)


def test_any_nonvertical_asset_blocks_whole_batch_before_writes() -> None:
    facts = _facts()
    facts[ROLL_OUT_IDS[3]] = (1920, 1080, 30.0)
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="not_vertical"):
        rollout.validate_token_clip_media_facts(facts)


def test_token_clip_readiness_accepts_only_native_short_video() -> None:
    readiness = rollout.clip_readiness(_asset())
    assert readiness.allowed_types == ("short_video",)
    assert readiness.require_playable is True


def test_rollout_module_has_no_browser_adapter_dependency() -> None:
    source = inspect.getsource(rollout)
    assert "milovi_native_clip_browser" not in source
    assert "playwright" not in source.casefold()


def test_wrong_execution_phrase_stops_before_creating_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.json"
    with pytest.raises(rollout.MiloviTokenRolloutBlocked, match="Exact confirmation"):
        rollout.run_issue_323_token_rollout(
            confirmation="WRONG",
            output_path=output,
            journal_path=journal,
            schedule_path=tmp_path / "schedule.json",
            work_dir=tmp_path / "work",
        )
    assert not output.exists()
    assert not journal.exists()


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


def test_legacy_codec_cache_is_refreshed_before_provider_use(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assets = _cached_assets(tmp_path)
    _write_manifest(tmp_path, assets)
    monkeypatch.setattr(sources, "_require_tool", lambda name: name)

    def reject_legacy(ffprobe: str, media_path: Path) -> tuple[int, int, float]:
        del ffprobe, media_path
        raise sources.MiloviSourceCodecError("legacy codecs")

    monkeypatch.setattr(sources, "_probe_media", reject_legacy)
    downloaded: list[str] = []

    def fake_download(yt_dlp: str, ffprobe: str, source_id: str, media_dir: Path) -> SourceAsset:
        assert yt_dlp == "yt-dlp"
        assert ffprobe == "ffprobe"
        assert media_dir.name == sources.VK_MEDIA_CACHE_DIR
        downloaded.append(source_id)
        media_path = media_dir / f"{source_id}.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(f"h264-aac:{source_id}".encode())
        return SourceAsset(
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

    monkeypatch.setattr(sources, "_download_source", fake_download)
    refreshed = sources.prepare_sources(tmp_path)

    assert tuple(downloaded) == ROLL_OUT_IDS
    assert tuple(asset.source_id for asset in refreshed) == ROLL_OUT_IDS
    assert all(Path(asset.media_path).parent.name == sources.VK_MEDIA_CACHE_DIR for asset in refreshed)
    manifest = json.loads((tmp_path / "prepared-sources.json").read_text(encoding="utf-8"))
    assert manifest["media_profile"] == "vk-h264-aac-v1"


def test_changed_cached_bytes_hard_fail_instead_of_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assets = _cached_assets(tmp_path)
    _write_manifest(tmp_path, assets)
    Path(assets[0].media_path).write_bytes(b"tampered")
    monkeypatch.setattr(sources, "_require_tool", lambda name: name)

    def forbidden_download(*args: object, **kwargs: object) -> SourceAsset:
        raise AssertionError("tampered cache must never trigger a redownload")

    monkeypatch.setattr(sources, "_download_source", forbidden_download)

    with pytest.raises(sources.MiloviSourceError, match="missing or changed"):
        sources.prepare_sources(tmp_path)
