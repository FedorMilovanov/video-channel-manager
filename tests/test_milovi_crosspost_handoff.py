"""Exact-media handoff protects all six destination routes from mistaken dispatch."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from video_channel_manager.milovi_crosspost_handoff import (
    HandoffError,
    ROUTES,
    build_handoff,
)


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_json(path: Path, obj: dict) -> bytes:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    path.write_bytes(payload)
    return payload


def fixture(tmp_path: Path, *, source_id: str = "OXC3BjtlU1g") -> tuple[Path, str, Path, Path]:
    folder = tmp_path / "video"
    folder.mkdir()
    video = folder / "ORIGINAL-MUSIC-REEL.mp4"
    video.write_bytes(b"valid-source-identity-for-unit-test")
    media_sha = digest(video.read_bytes())
    caption = "Прекрасный торт 🎂 #MiloviCake"
    key = f"milovi-cake.2026-11-23.yt-{source_id}.original-audio-v1"
    manifest = {
        "publication_key": key,
        "account_id": "17841407843933779",
        "media_sha256": f"sha256:{media_sha}",
        "media_size_bytes": video.stat().st_size,
        "caption": caption,
    }
    manifest_file = folder / "exact-local-publish-manifest.json"
    write_json(manifest_file, manifest)
    approval = {
        "project_key": "milovi-cake",
        "instagram_id": "17841407843933779",
        "publication_key": key,
        "media_sha256": f"sha256:{media_sha}",
        "owner_directed_repost": True,
        "soundtrack_license_independently_verified": False,
    }
    approval_file = folder / "OWNER_DIRECTED_RISK_ACCEPTED.json"
    write_json(approval_file, approval)
    index = {
        "project_key": "milovi-cake",
        "target_instagram_id": "17841407843933779",
        "meta_app_id": "989716813600695",
        "rows": [
            {
                "youtube_id": source_id,
                "title": "Торт на заказ",
                "folder": str(folder),
                "proposed_moscow_slot": "2026-11-23T19:00:00",
                "publication_key": key,
                "manifest_sha256": digest(manifest_file.read_bytes()),
                "media_sha256": media_sha,
                "caption_sha256": digest(caption.encode("utf-8")),
                "rights_verified": False,
            }
        ],
    }
    index_file = tmp_path / "index.json"
    raw = write_json(index_file, index)
    return index_file, digest(raw), video, approval_file


def build(index: Path, sha: str) -> dict:
    return build_handoff(
        index,
        start_date=date(2026, 11, 23),
        end_date=date(2026, 11, 28),
        expected_index_sha256=sha,
    )


def test_six_routes_all_provider_inert(tmp_path: Path) -> None:
    path, sha, _, _ = fixture(tmp_path)
    result = build(path, sha)
    assert result["source_count"] == 1
    assert result["destination_count"] == len(ROUTES) == 6
    assert result["new_schedules_armed"] is False
    assert result["provider_writes_performed"] is False
    row = result["candidates"][0]
    assert row["youtube_channel_id"] == "UCMDnxfGZiBqcDzgUV1zjFpw"
    assert row["instagram_publication_key"].startswith("milovi-cake.2026-11-23.")
    assert not row["music_license_independently_verified"]
    assert {x["platform"] for x in row["destinations"]} == {
        "youtube",
        "instagram",
        "vk_clips",
        "telegram",
        "rutube",
        "threads",
    }
    assert all(not x["may_dispatch"] and not x["provider_receipt_verified"] for x in row["destinations"])
    assert row["destinations"][0]["state"] == "already_source"
    assert row["destinations"][1]["state"] == "existing_single_writer"


def test_mp4_tamper_refused(tmp_path: Path) -> None:
    path, sha, video, _ = fixture(tmp_path)
    video.write_bytes(b"changed")
    with pytest.raises(HandoffError, match="MP4/Instagram manifest mismatch"):
        build(path, sha)


def test_owner_acknowledgement_not_optional(tmp_path: Path) -> None:
    path, sha, _, approval = fixture(tmp_path)
    data = json.loads(approval.read_text(encoding="utf-8"))
    data["owner_directed_repost"] = False
    write_json(approval, data)
    with pytest.raises(HandoffError, match="Owner acknowledgement"):
        build(path, sha)


def test_index_digest_required(tmp_path: Path) -> None:
    path, sha, _, _ = fixture(tmp_path)
    with pytest.raises(HandoffError, match="Frozen index"):
        build(path, "0" * 64)


def test_caption_tamper_refused(tmp_path: Path) -> None:
    path, _, _, _ = fixture(tmp_path)
    index = json.loads(path.read_text(encoding="utf-8"))
    folder = Path(index["rows"][0]["folder"])
    mf = folder / "exact-local-publish-manifest.json"
    value = json.loads(mf.read_text(encoding="utf-8"))
    value["caption"] = "changed caption"
    write_json(mf, value)
    index["rows"][0]["manifest_sha256"] = digest(mf.read_bytes())
    sha = digest(write_json(path, index))
    with pytest.raises(HandoffError, match="Caption digest"):
        build(path, sha)


def test_duplicate_source_refused_even_when_outside_window(tmp_path: Path) -> None:
    path, _, _, _ = fixture(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rows"].append({**data["rows"][0], "proposed_moscow_slot": "2026-11-01T19:00:00"})
    sha = digest(write_json(path, data))
    with pytest.raises(HandoffError, match="Duplicate source"):
        build(path, sha)


def test_wrong_target_refused(tmp_path: Path) -> None:
    path, _, _, _ = fixture(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["target_instagram_id"] = "other_account"
    sha = digest(write_json(path, data))
    with pytest.raises(HandoffError, match="Index project/target/app mismatch"):
        build(path, sha)


def test_outside_date_range_creates_no_dispatch(tmp_path: Path) -> None:
    path, sha, _, _ = fixture(tmp_path)
    result = build_handoff(path, start_date=date(2026, 12, 1), end_date=date(2026, 12, 2), expected_index_sha256=sha)
    assert result["source_count"] == result["destination_count"] == 0
    assert not result["new_schedules_armed"]


def test_backward_dates_refused(tmp_path: Path) -> None:
    path, sha, _, _ = fixture(tmp_path)
    with pytest.raises(HandoffError, match="Reversed"):
        build_handoff(path, start_date=date(2026, 11, 28), end_date=date(2026, 11, 23), expected_index_sha256=sha)


def test_source_id_validated_before_file_access(tmp_path: Path) -> None:
    path, _, _, _ = fixture(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rows"][0]["youtube_id"] = "../../escape"
    sha = digest(write_json(path, data))
    with pytest.raises(HandoffError, match="Invalid YouTube"):
        build(path, sha)
