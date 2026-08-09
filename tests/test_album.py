from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

import video_channel_manager.album as album_module
import video_channel_manager.album_quality as album_quality
from video_channel_manager.album import (
    AlbumError,
    AlbumManifest,
    QualityMasterManifest,
    bind_quality_master,
    build_album_timing,
    build_artwork_plan,
    configure_local_track,
    configure_youtube_track,
    create_album_manifest,
    create_quality_master_manifest,
    load_album_manifest,
    render_album,
    save_album_manifest,
    save_quality_master_manifest,
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _probed_youtube_manifest(tmp_path: Path, *, tracks: int = 2) -> AlbumManifest:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=tracks)
    for ordinal in range(1, tracks + 1):
        video_id = f"VID{ordinal:08d}"[:11]
        manifest = configure_youtube_track(manifest, ordinal=ordinal, video_id=video_id, title=f"Version {ordinal}")
        source = tmp_path / f"source-{ordinal}.m4a"
        source.write_bytes(f"source-{ordinal}".encode())
        current = manifest.tracks[ordinal - 1]
        probed = current.model_copy(
            update={
                "status": "probed",
                "acquired_path": str(source.resolve()),
                "sha256": _sha(source),
                "duration_seconds": float(100 * ordinal),
                "probe": {"fixture": True, "source": ordinal},
            }
        )
        items = [probed if item.ordinal == ordinal else item for item in manifest.tracks]
        manifest = manifest.model_copy(update={"tracks": items})
    return manifest


def _probed_local_manifest(tmp_path: Path) -> tuple[AlbumManifest, Path]:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=1)
    source = tmp_path / "bonus.wav"
    source.write_bytes(b"bonus-local-source")
    manifest = configure_local_track(manifest, ordinal=1, path=source, title="Bonus")
    current = manifest.tracks[0]
    probed = current.model_copy(
        update={
            "status": "probed",
            "sha256": _sha(source),
            "duration_seconds": 42.0,
            "probe": {"fixture": True, "local": True},
        }
    )
    return manifest.model_copy(update={"tracks": [probed]}), source


class _FakeReport:
    def __init__(self, path: Path, duration: float) -> None:
        self.sha256 = _sha(path)
        self.duration_seconds = duration
        self._path = path

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self._path.resolve()),
            "sha256": self.sha256,
            "duration_seconds": self.duration_seconds,
            "fixture": True,
        }


def _bind_masters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest: AlbumManifest,
    durations: tuple[float, ...],
) -> tuple[QualityMasterManifest, list[Path]]:
    duration_by_name: dict[str, float] = {}
    masters: list[Path] = []
    for ordinal, duration in enumerate(durations, start=1):
        path = tmp_path / f"master-{ordinal}.flac"
        path.write_bytes(f"master-{ordinal}-accepted".encode())
        masters.append(path)
        duration_by_name[path.name] = duration

    def fake_probe(path: Path, **_: object) -> _FakeReport:
        return _FakeReport(path, duration_by_name[path.name])

    monkeypatch.setattr(album_quality, "probe_audio_file", fake_probe)
    quality = create_quality_master_manifest(manifest)
    for ordinal, path in enumerate(masters, start=1):
        quality = bind_quality_master(manifest, quality, ordinal=ordinal, path=path, ffprobe="unused")
    return quality, masters


def test_seven_track_album_supports_six_youtube_and_pending_local_bonus(tmp_path: Path) -> None:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=7)
    youtube_ids = [
        "8ULM0GD_HdU",
        "S_3XdEGW4cU",
        "abcdefghijk",
        "b0VHXLc6rnc",
        "12345678901",
        "ZYXWVUTSRQP",
    ]
    for ordinal, video_id in enumerate(youtube_ids, start=1):
        manifest = configure_youtube_track(manifest, ordinal=ordinal, video_id=video_id)

    bonus_path = tmp_path / "version-7.wav"
    manifest = configure_local_track(manifest, ordinal=7, path=bonus_path, title="Bonus Track")

    assert manifest.expected_channel_id == "UC-78ys2S3cQ3lpqgXfo-SvQ"
    assert [track.source_kind for track in manifest.tracks[:6]] == ["youtube_exact_source"] * 6
    assert manifest.tracks[6].source_kind == "local_controlled_master"
    assert manifest.tracks[6].status == "pending_local_master"
    assert manifest.tracks[6].youtube_video_id is None
    assert manifest.tracks[6].source_url is None

    path = tmp_path / "album.json"
    saved = save_album_manifest(path, manifest)
    loaded = load_album_manifest(path)
    assert loaded.manifest_sha256 == saved.manifest_sha256
    assert loaded.tracks[6].local_path == str(bonus_path.resolve())


def test_same_youtube_source_retitle_preserves_acquisition_probe_and_master_eligibility(tmp_path: Path) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=1)
    before = manifest.tracks[0]

    updated = configure_youtube_track(
        manifest,
        ordinal=1,
        video_id=before.youtube_video_id or "",
        title="Чёрный человек — версия 1",
    )
    after = updated.tracks[0]

    assert after.title == "Чёрный человек — версия 1"
    assert after.status == "probed"
    assert after.acquired_path == before.acquired_path
    assert after.sha256 == before.sha256
    assert after.duration_seconds == before.duration_seconds
    assert after.probe == before.probe

    changed = configure_youtube_track(updated, ordinal=1, video_id="DIFFERENT01", title="Different source")
    changed_track = changed.tracks[0]
    assert changed_track.status == "configured"
    assert changed_track.acquired_path is None
    assert changed_track.sha256 is None
    assert changed_track.duration_seconds is None
    assert changed_track.probe is None


def test_same_local_source_retitle_preserves_probe_and_sha(tmp_path: Path) -> None:
    manifest, source = _probed_local_manifest(tmp_path)
    before = manifest.tracks[0]

    updated = configure_local_track(manifest, ordinal=1, path=source, title="Bonus final title")
    after = updated.tracks[0]

    assert after.title == "Bonus final title"
    assert after.status == "probed"
    assert after.local_path == before.local_path
    assert after.sha256 == before.sha256
    assert after.duration_seconds == before.duration_seconds
    assert after.probe == before.probe


def test_timing_uses_exact_bound_quality_master_durations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=2)
    quality, _ = _bind_masters(monkeypatch, tmp_path, manifest, (10.0, 12.0))

    timing = build_album_timing(
        manifest,
        grid_seconds=5,
        minimum_gap_seconds=1.0,
        quality_masters=quality,
    )

    assert [item.duration_seconds for item in timing.tracks] == [10.0, 12.0]
    assert timing.tracks[0].start_seconds == 0.0
    assert timing.tracks[0].gap_after_seconds == 5.0
    assert timing.tracks[1].start_seconds == 15.0
    assert timing.tracks[1].chapter_timestamp == "00:15"
    assert timing.total_duration_seconds == 27.0


def test_timing_fails_without_every_quality_master(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=2)
    quality, _ = _bind_masters(monkeypatch, tmp_path, manifest, (10.0,))

    with pytest.raises(AlbumError, match="bound quality master for every track"):
        build_album_timing(manifest, grid_seconds=5, quality_masters=quality)


def test_tampered_quality_master_bytes_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=1)
    quality, masters = _bind_masters(monkeypatch, tmp_path, manifest, (10.0,))
    masters[0].write_bytes(b"tampered-after-review")

    with pytest.raises(AlbumError, match="bytes differ from bound SHA-256"):
        build_album_timing(manifest, grid_seconds=5, quality_masters=quality)


def test_quality_master_bound_to_stale_source_evidence_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=1)
    quality, _ = _bind_masters(monkeypatch, tmp_path, manifest, (10.0,))
    track = manifest.tracks[0].model_copy(update={"sha256": "sha256:" + "f" * 64})
    stale_manifest = manifest.model_copy(update={"tracks": [track]})

    with pytest.raises(AlbumError, match="belongs to stale source evidence"):
        build_album_timing(stale_manifest, grid_seconds=5, quality_masters=quality)


def test_render_receives_only_quality_master_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=2)
    quality, masters = _bind_masters(monkeypatch, tmp_path, manifest, (10.0, 12.0))
    timing = build_album_timing(manifest, grid_seconds=5, quality_masters=quality)
    output = tmp_path / "build" / "album.mp4"

    def fake_render(mastered: AlbumManifest, passed_timing: object, *, root: Path, ffmpeg: str) -> Path:
        assert passed_timing == timing
        assert root == tmp_path
        assert ffmpeg == "unused"
        assert [track.acquired_path for track in mastered.tracks] == [str(path.resolve()) for path in masters]
        assert [track.duration_seconds for track in mastered.tracks] == [10.0, 12.0]
        return output

    monkeypatch.setattr(album_module._core, "render_album", fake_render)
    assert (
        render_album(
            manifest,
            timing,
            root=tmp_path,
            ffmpeg="unused",
            quality_masters=quality,
        )
        == output
    )


def test_loaded_manifest_auto_loads_exact_quality_master_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = _probed_youtube_manifest(tmp_path, tracks=1)
    quality, _ = _bind_masters(monkeypatch, tmp_path, manifest, (10.0,))
    manifest_file = tmp_path / "manifest.json"
    save_album_manifest(manifest_file, manifest)
    save_quality_master_manifest(tmp_path / "quality-masters.json", quality)

    loaded = load_album_manifest(manifest_file)
    timing = build_album_timing(loaded, grid_seconds=5)

    assert timing.tracks[0].duration_seconds == 10.0


def test_artwork_plan_reserves_neutral_plus_seven_active_states() -> None:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=7)
    plan = build_artwork_plan(manifest)

    assert plan["width"] == 1920
    assert plan["height"] == 1080
    assert len(plan["states"]) == 8
    assert plan["states"][0]["filename"] == "cover-neutral.png"
    assert plan["states"][-1]["filename"] == "track-07.png"
