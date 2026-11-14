"""Release provenance: Blok's parts and two Scythians musical arrangements stay distinct."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "content/editorial/legendary-poet/blok-six-audio-releases-20261114.json"
QUEUE = ROOT / "content/instagram/legendary-poet-daily-reels-queue-20260913.json"


def test_blok_parts_and_versions_are_not_conflated() -> None:
    data = json.loads(INTAKE.read_text(encoding="utf-8"))
    releases = {entry["id"]: entry for entry in data["releases"]}
    assert len(releases) == 6
    assert releases["blok-kulikovo-part-1"]["unit"] == "poem-cycle-part-1-of-5"
    assert releases["blok-kulikovo-part-2"]["unit"] == "poem-cycle-part-2-of-5"
    assert releases["blok-kulikovo-part-1"]["youtube_id"] == "U4D40EQg10U"
    assert releases["blok-kulikovo-part-2"]["youtube_id"] == "RuTmtXUuxm8"
    assert releases["blok-scythians-version-1"]["unit"] == "complete-poem-music-arrangement-v1"
    assert releases["blok-scythians-version-2"]["unit"] == "complete-poem-music-arrangement-v2"
    assert releases["blok-rossiya"]["website_status"] == "published_verified_in_main_music_catalog"
    assert len({release["local_review_sha256"] for release in releases.values()}) == 6


def test_scythians_instagram_author_is_blok() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    items = [item for item in queue["items"] if item["source_title"].startswith("Скифы - Version")]
    assert len(items) == 2
    for item in items:
        assert item["author"] == "Александр Блок"
        assert "Александр Пушкин" not in item["caption"]
        assert "#АлександрПушкин" not in item["caption"]
        assert "#АлександрБлок" in item["caption"]
