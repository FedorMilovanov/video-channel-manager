from video_channel_manager.local_media import scan_local_media


def test_local_scanner_only_indexes_video_extensions(tmp_path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    records = scan_local_media([tmp_path], include_hash=True)

    assert len(records) == 1
    assert records[0].filename == "clip.mp4"
    assert records[0].sha256 is not None
