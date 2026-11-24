"""Provider-inert format-only chapter correction regressions."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_panorama_chapter_evidence import verify_format_preview
from video_channel_manager.platforms.youtube.copy_plan import sha256_text
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL

from video_channel_manager.platforms.youtube.chapter_release import normalize_existing_chapter_stamps

CHAPTERS = [("00:00", "Opening"), ("58:00", "Source"), ("65:00", "Canon"), ("84:00", "Closing")]
BEFORE = (
    "Intro 65:00 stays\r\nhttps://example.com/65:00\r\n"
    + "\r\n".join(f"{stamp} {heading}" for stamp, heading in CHAPTERS)
    + "\r\nEnd."
)
AFTER = BEFORE.replace("\r\n65:00 Canon", "\r\n1:05:00 Canon").replace("\r\n84:00 Closing", "\r\n1:24:00 Closing")


def test_exact_format_only_preserves_every_other_character() -> None:
    assert normalize_existing_chapter_stamps(BEFORE, CHAPTERS, duration_seconds=5500) == AFTER


@pytest.mark.parametrize(
    "before, chapters, duration",
    [
        (BEFORE + "\n90:00 Extra", CHAPTERS, 6000),
        (BEFORE, CHAPTERS[:-1], 5500),
        (BEFORE, list(reversed(CHAPTERS)), 5500),
        (BEFORE.replace("65:00 Canon", "65:00 Other"), CHAPTERS, 5500),
        (BEFORE.replace("65:00 Canon", " 65:00 Canon"), CHAPTERS, 5500),
        (BEFORE.replace("65:00 Canon", "65:60 Canon"), [*CHAPTERS[:2], ("65:60", "Canon"), CHAPTERS[3]], 5500),
        (BEFORE, CHAPTERS, 5045),
        (BEFORE, CHAPTERS, True),
        (AFTER, [*CHAPTERS[:2], ("1:05:00", "Canon"), ("1:24:00", "Closing")], 5500),
        ("x" * 5000 + "\n" + BEFORE, CHAPTERS, 5500),
    ],
)
def test_invalid_or_unbound_inventory_refused(before: str, chapters: list[tuple[str, str]], duration: int) -> None:
    with pytest.raises(ValueError):
        normalize_existing_chapter_stamps(before, chapters, duration_seconds=duration)


def _save(path: Path, obj: object) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("defect", ["none", "after", "source", "duplicate", "authority", "missing_chapter"])
def test_archived_preview_rederivation(tmp_path: Path, defect: str) -> None:
    video = "example0001"
    source = tmp_path / f"{video}-plan.json"
    src_hash = _save(
        source, {"operations": [{"video_id": video, "after_description": BEFORE, "after_sha256": sha256_text(BEFORE)}]}
    )
    chapters = [
        {"stamp": stamp, "heading": heading, "second": second, "canonical_stamp": canonical}
        for (stamp, heading), second, canonical in zip(
            CHAPTERS, [0, 3480, 3900, 5040], ["00:00", "58:00", "1:05:00", "1:24:00"], strict=True
        )
    ]
    audit_file = tmp_path / "audit.json"
    audit_sha = _save(
        audit_file,
        {
            "schema": "panorama-historical-chapter-evidence-audit-v2",
            "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
            "is_executable_plan": False,
            "results": [{"video_id": video, "episode": 1, "chapters": chapters, "last_tail_ms": 460000}],
        },
    )
    item = {
        "episode": 1,
        "video_id": video,
        "historical_plan": source.name,
        "historical_plan_sha256": src_hash,
        "before_description": BEFORE,
        "before_sha256": sha256_text(BEFORE).removeprefix("sha256:"),
        "proposed_description": AFTER,
        "proposed_sha256": sha256_text(AFTER).removeprefix("sha256:"),
        "proposed_utf8_bytes": len(AFTER.encode()),
        "changes": chapters[2:],
    }
    items = [item, item] if defect == "duplicate" else [item]
    preview = {
        "schema": "panorama-format-only-review-report-v1",
        "owner_channel_id": LORD_GOD_OWNER_CHANNEL,
        "project_key": "lord-god-strength",
        "source_audit": audit_file.name,
        "source_audit_sha256": audit_sha,
        "is_executable_plan": defect == "authority",
        "semantic_approval": False,
        "fresh_owner_snapshot": False,
        "provider_reads": 0,
        "provider_writes": 0,
        "items": items,
    }
    if defect == "after":
        item["proposed_description"] = AFTER + " edited"
    if defect == "source":
        source.write_text("{}", encoding="utf-8")
    if defect == "missing_chapter":
        item["changes"] = chapters[2:3]
    preview_file = tmp_path / "preview.json"
    _save(preview_file, preview)
    if defect != "none":
        with pytest.raises(ValueError):
            verify_format_preview(audit_file, preview_file)
    else:
        report = verify_format_preview(audit_file, preview_file)
        assert report["videos_checked"] == 1
        assert report["stamps_verified"] == 2
        assert report["is_executable_plan"] is False
