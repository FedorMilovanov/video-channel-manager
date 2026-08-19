from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
INTAKE = ROOT / "content" / "instagram" / "legendary-poet-channel-video-intake.md"
FACTORY = ROOT / "content" / "instagram" / "legendary-poet-reels-factory-plan.md"
COMMENTS = ROOT / "content" / "youtube-comments"


def _intake_ids(text: str) -> list[str]:
    marker = "## Full exact-ID intake floor (111)"
    assert marker in text
    tail = text.split(marker, 1)[1]
    match = re.search(r"```text\n(?P<body>.*?)\n```", tail, flags=re.DOTALL)
    assert match is not None
    return [line.strip() for line in match.group("body").splitlines() if line.strip()]


def test_instagram_intake_covers_exact_frozen_youtube_mapping() -> None:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    intake_ids = _intake_ids(INTAKE.read_text(encoding="utf-8"))

    assert len(mapping) == 111
    assert len(intake_ids) == 111
    assert len(set(intake_ids)) == 111
    assert set(intake_ids) == set(mapping)


def test_reviewed_editorial_subset_is_exactly_the_current_comment_corpus() -> None:
    text = INTAKE.read_text(encoding="utf-8")
    reviewed_section = text.split("## Reviewed editorial subset", 1)[1].split(
        "## Full exact-ID intake floor", 1
    )[0]
    reviewed_ids = set(re.findall(r"`([A-Za-z0-9_-]{11})`", reviewed_section))
    comment_ids = {path.stem for path in COMMENTS.glob("*.json")}

    assert len(comment_ids) == 15
    assert reviewed_ids == comment_ids


def test_intake_remains_provider_inert_and_fail_closed_on_short_classification() -> None:
    text = INTAKE.read_text(encoding="utf-8")

    assert "provider-inert" in text
    assert "duration_seconds` alone is **not** accepted" in text
    assert "currently confirmed Shorts from frozen evidence | 0" in text
    assert "currently confirmed long-form from frozen evidence | 0" in text
    assert "video-manager youtube scan --account legendary-poet" in text


def test_reels_factory_has_59_unique_editorial_jobs() -> None:
    text = FACTORY.read_text(encoding="utf-8")
    reel_ids = re.findall(r"^### ([A-Z]+-R\d{2})\b", text, flags=re.MULTILINE)

    assert len(reel_ids) == 59
    assert len(set(reel_ids)) == 59
    assert "| **TOTAL** | **59** |" in text
    assert "59 editorially distinct Reel slots" in text
