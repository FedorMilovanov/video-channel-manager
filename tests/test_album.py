from pathlib import Path

from video_channel_manager.album import (
    build_album_timing,
    build_artwork_plan,
    configure_local_track,
    configure_youtube_track,
    create_album_manifest,
    load_album_manifest,
    save_album_manifest,
)


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


def test_timing_aligns_track_starts_to_grid() -> None:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=2)
    manifest = configure_youtube_track(manifest, ordinal=1, video_id="8ULM0GD_HdU", title="Version 1")
    manifest = configure_youtube_track(manifest, ordinal=2, video_id="S_3XdEGW4cU", title="Version 2")

    first = manifest.tracks[0].model_copy(update={"status": "probed", "duration_seconds": 237.0})
    second = manifest.tracks[1].model_copy(update={"status": "probed", "duration_seconds": 255.0})
    manifest = manifest.model_copy(update={"tracks": [first, second]})

    timing = build_album_timing(manifest, grid_seconds=5, minimum_gap_seconds=1.0)

    assert timing.tracks[0].start_seconds == 0.0
    assert timing.tracks[0].gap_after_seconds == 3.0
    assert timing.tracks[1].start_seconds == 240.0
    assert timing.tracks[1].chapter_timestamp == "04:00"
    assert timing.total_duration_seconds == 495.0


def test_artwork_plan_reserves_neutral_plus_seven_active_states() -> None:
    manifest = create_album_manifest(project_key="legendary-poet", album_key="black-man", total_tracks=7)
    plan = build_artwork_plan(manifest)

    assert plan["width"] == 1920
    assert plan["height"] == 1080
    assert len(plan["states"]) == 8
    assert plan["states"][0]["filename"] == "cover-neutral.png"
    assert plan["states"][-1]["filename"] == "track-07.png"
