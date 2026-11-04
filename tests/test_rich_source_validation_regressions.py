"""Adversarial read-only validations for rich article metadata and archived canary evidence.

These are negative provider-inert proofs, not permission to re-enable old
publication pathways.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager import lordchrist_rich_live_canary as canary
from video_channel_manager.telegram_rich_models import (
    RichArticleFooter,
    RichArticleMetadata,
    RichBlockCaption,
    RichBlockMap,
)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("text", "   ", "visible text"),
        ("credit", "    ", "visible text"),
    ],
)
def test_media_caption_rejects_empty_text_or_credit(field: str, value: str, error: str) -> None:
    payload = {"text": "A reviewed caption", "credit": "Verified source"}
    payload[field] = value
    with pytest.raises(ValidationError, match=error):
        RichBlockCaption.model_validate(payload)


@pytest.mark.parametrize(
    ("patch", "error"),
    [
        ({"location": [91, 4]}, "latitude"),
        ({"location": [44, 181]}, "longitude"),
        ({"width": 9000, "height": 2000}, "dimensions"),
        ({"width": 4000, "height": 1}, "aspect ratio"),
    ],
)
def test_rich_map_rejects_out_of_range_geometry(patch: dict[str, object], error: str) -> None:
    raw = {"block_id": "map-01", "location": [44, 34]}
    raw.update(patch)
    with pytest.raises(ValidationError, match=error):
        RichBlockMap.model_validate(raw)


@pytest.mark.parametrize(
    ("patch", "error"),
    [
        ({"tags": ["#source", "#source"]}, "unique"),
        ({"tags": ["  "]}, "visible characters"),
        ({"updated_at": "2026-11-03"}, "cannot precede"),
    ],
)
def test_rich_article_metadata_rejects_dubious_revision(patch: dict[str, object], error: str) -> None:
    raw = {"title": "Reviewed article", "language": "ru", "created_at": "2026-11-04"}
    raw.update(patch)
    with pytest.raises(ValidationError, match=error):
        RichArticleMetadata.model_validate(raw)


@pytest.mark.parametrize(
    ("hashtags", "error"),
    [
        (("missing-hash",), "start with"),
        (("#duplicate", "#duplicate"), "unique"),
    ],
)
def test_rich_article_footer_rejects_invalid_tags(hashtags: tuple[str, ...], error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        RichArticleFooter(tagline="Reviewed", hashtags=hashtags)


def test_archived_canary_rejects_unreviewed_media_byte_replacement(tmp_path: Path) -> None:
    original = b"exact-archive-fixture"
    f = tmp_path / "artifact.bin"
    f.write_bytes(original)
    exact = {"path": f.name, "git_blob_sha": canary._blob(original)}
    assert canary._verify(tmp_path, exact) == f
    f.write_bytes(original + b"-changed")
    with pytest.raises(ValueError, match="Git blob differs"):
        canary._verify(tmp_path, exact)


def test_archived_canary_json_and_attachment_readback_fail_closed(tmp_path: Path) -> None:
    record = tmp_path / "audit.json"
    canary._write(record, {"project_key": "lord-god-strength"})
    assert canary._read(record)["project_key"] == "lord-god-strength"
    record.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON root must be object"):
        canary._read(record)

    assert canary._attachment_reference("media-calvin") == "attach://lc_calvin"
    with pytest.raises(ValueError, match="unknown LordChrist live attachment"):
        canary._attachment_reference("unknown-media")
    with pytest.raises(ValueError, match="empty LordChrist multipart"):
        canary._attachment_names({"media": "attach://"})
    assert canary._attachment_names({"blocks": [{"media": "attach://lc_tape"}]}) == frozenset({"lc_tape"})


def test_archived_canary_no_provider_claim_from_an_opaque_source_record() -> None:
    records = canary._media_records(
        {
            "blocks": [
                {"type": "photo", "photo": {"media": "attach://lc_calvin"}},
                {"type": "photo", "photo": {"unreviewed": True}},
                {"type": "video", "video": "not-a-provider-media-object"},
            ]
        }
    )
    assert len(records) == 1
    assert records[0]["type"] == "photo"
    assert records[0]["media"] == "attach://lc_calvin"


def test_archived_canary_attachment_conversion_preserves_all_other_content() -> None:
    from types import SimpleNamespace

    names = ("calvin", "spurgeon", "tape")
    media_ids = ("media-calvin", "media-spurgeon", "media-tape")
    original = {
        "type": "article",
        "blocks": [
            *[{"media": f"https://assets.example.invalid/{name}.jpg", "caption": f"Verified {name}"} for name in names],
            {"text": "Untouched body"},
        ],
    }
    source = SimpleNamespace(
        media=tuple(
            SimpleNamespace(media_id=media_id, uri=f"https://assets.example.invalid/{name}.jpg")
            for name, media_id in zip(names, media_ids, strict=True)
        )
    )
    changed = canary._replace_source_urls_with_attachments(original, source)
    assert [item["media"] for item in changed["blocks"][:3]] == [
        "attach://lc_calvin",
        "attach://lc_spurgeon",
        "attach://lc_tape",
    ]
    assert [item["caption"] for item in changed["blocks"][:3]] == [f"Verified {name}" for name in names]
    assert changed["blocks"][3] == original["blocks"][3]
    assert original["blocks"][0]["media"] == "https://assets.example.invalid/calvin.jpg"
