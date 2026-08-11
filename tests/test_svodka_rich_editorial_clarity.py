"""Reader-first editorial invariants for the Svodka rich-v1 article set."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RICH_ROOT = ROOT / "content/telegram/svodka/rich-v1"
ARTICLES_DIR = RICH_ROOT / "articles"
MANIFEST_PATH = RICH_ROOT / "manifest.json"
STANDARD_PATH = RICH_ROOT / "EDITORIAL_STANDARD.md"

ALLOWED_EDITORIAL_BLOCK_TYPES = {"paragraph", "list", "quote"}
CAPABILITY_DEMO_BLOCK_TYPES = {
    "mathematical_expression",
    "table",
    "details",
    "collage",
    "slideshow",
}


def _manifest_mappings() -> list[dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mappings = manifest["mappings"]
    assert isinstance(mappings, list)
    return mappings


def _mapped_json_paths() -> list[Path]:
    paths: list[Path] = []
    for mapping in _manifest_mappings():
        rich_files = mapping["rich_files"]
        assert isinstance(rich_files, list)
        json_files = [ROOT / str(path) for path in rich_files if str(path).endswith(".json")]
        assert len(json_files) == 1
        paths.extend(json_files)
    return paths


def test_clarity_pass_still_covers_exactly_fourteen_articles() -> None:
    mappings = _manifest_mappings()
    assert len(mappings) == 14
    paths = _mapped_json_paths()
    assert len(paths) == 14
    assert len(set(paths)) == 14
    assert all(path.exists() for path in paths)


def test_all_articles_remain_editorial_only_and_reader_first() -> None:
    for path in _mapped_json_paths():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["status"] == "editorial_draft_review_required"
        assert payload["provider_writes_authorized"] is False
        assert payload["premium_emoji_dependency"] is False
        assert len(payload["lead"].strip()) >= 100
        assert len(payload["sections"]) >= 3

        for section in payload["sections"]:
            assert section["heading"].strip()
            assert section["blocks"]
            for block in section["blocks"]:
                assert block["type"] in ALLOWED_EDITORIAL_BLOCK_TYPES
                assert block["type"] not in CAPABILITY_DEMO_BLOCK_TYPES


def test_markdown_companions_match_titles_and_section_hierarchy() -> None:
    for json_path in _mapped_json_paths():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        md_path = json_path.with_suffix(".md")
        assert md_path.exists()
        markdown = md_path.read_text(encoding="utf-8")
        assert markdown.startswith(f"# {payload['title']}\n")
        for section in payload["sections"]:
            assert f"## {section['heading']}\n" in markdown


def test_eclipse_production_article_is_not_the_capability_canary_demo() -> None:
    path = ARTICLES_DIR / "svodka-rich-2026-august-total-solar-eclipse.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload["sections"], ensure_ascii=False)
    assert "mathematical_expression" not in serialized
    assert '"type": "table"' not in serialized
    assert '"type": "details"' not in serialized
    assert "theta" not in serialized.lower()
    assert "углов" not in serialized.lower()
    assert "прожектор" in serialized


def test_reader_first_standard_explicitly_rejects_feature_demo_editorial() -> None:
    standard = STANDARD_PATH.read_text(encoding="utf-8")
    assert "A Rich Message is an article, not a Telegram feature demo." in standard
    assert "capability proof" in standard
    assert "not the production editorial template" in standard
    assert "provider writes remain separately authorised" in standard
