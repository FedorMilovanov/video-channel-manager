from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_feed import (
    MiloviFeedMediaBinding,
    MiloviOwnedCoverSource,
    materialize_photo,
    validate_bundle,
)
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericRichPhotoPayload

ROOT = Path(__file__).resolve().parents[1]
ID = "milovi-feed-20261107-003"
COVER = ROOT / "content/telegram/milovi-cake/assets/patisserie-history-cover-20261107.webp"
PROOF = ROOT / "content/telegram/milovi-cake/assets/patisserie-history-cover-20261107.proof.json"
MEDIA = ROOT / f"content/telegram/milovi-cake/releases/{ID}-media.json"
RELEASE = ROOT / f"content/telegram/milovi-cake/releases/{ID}-runtime.json"
CANDIDATE = ROOT / f"content/telegram/milovi-cake/candidates/{ID}.json"
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-feed-publisher.yml"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def test_owner_selected_cover_uses_exact_vintage_pastry_artwork_not_school_careme() -> None:
    source = COVER.read_bytes()
    media = MiloviFeedMediaBinding.model_validate_json(MEDIA.read_text(encoding="utf-8"))
    assert isinstance(media.source, MiloviOwnedCoverSource)
    assert media.source.path == COVER.relative_to(ROOT).as_posix()
    assert media.source.provenance == "owner_selected_original_vintage_pastry_cover_20261107"
    assert media.source.git_blob_sha1 == _git_blob(source)
    assert media.source.sha256 == _sha(source)
    assert media.source.byte_size == len(source)
    assert len(source) < 600_000
    # Core CI deliberately excludes Pillow; validate WebP container header with stdlib.
    assert source[:4] == b"RIFF" and source[8:12] == b"WEBP"
    assert media.source.pixel_width == 1672 and media.source.pixel_height == 941

    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    assert proof["original_png_sha256"] == "sha256:eea0a795c5b45b3503a9bb6475e82dd633b1002060c6c142405a43309de2599a"
    assert proof["source_webp_sha256"] == _sha(source)
    assert proof["preview_role"].startswith("editorial/")


def test_same_existing_article_id_schedule_unchanged_caption_and_links(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(ROOT)
    bundle = validate_bundle(ID, require_execution_authorized=True)
    assert bundle["valid"] and bundle["payload_kind"] == "photo"
    release = load_release(RELEASE)
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    media = MiloviFeedMediaBinding.model_validate_json(MEDIA.read_text(encoding="utf-8"))
    assert release.items[0].scheduled_at.isoformat() == "2026-11-08T14:00:00+03:00"
    assert release.channel_username == "@MiloviCake"
    assert release.chat_id == -1002215328390
    assert release.bot_id == 8716602202
    assert isinstance(release.items[0].payload, GenericRichPhotoPayload)
    p = release.items[0].payload
    assert p.caption == candidate["caption"]
    assert p.caption.count("https://milovicake.ru/") == 1
    assert p.caption.count("telegra.ph/Kto-pridumal-konditerskoe-delo") == 1
    assert {e.type for e in p.expected_caption_entities} >= {"bold", "italic", "text_link"}
    assert sum(e.type == "text_link" for e in p.expected_caption_entities) == 2
    assert len(p.expected_plain_caption) < 1024
    assert candidate["selected_cover"]["not_customer_order_photo"] is True
    assert release.items[0].source_sha256 == media.source.sha256


def test_actual_photo_materializes_with_production_pillow_13_exact_bytes(
    monkeypatch,
) -> None:
    # Pillow is installed by the canonical live-photo publisher, not by base CI.
    pytest.importorskip("PIL")
    from PIL import Image

    monkeypatch.chdir(ROOT)
    media = MiloviFeedMediaBinding.model_validate_json(MEDIA.read_text(encoding="utf-8"))
    created = materialize_photo(ID, source_path=COVER)
    output = ROOT / media.transport.media_path
    try:
        raw = output.read_bytes()
        assert created["verified"] is True
        assert _sha(raw) == media.transport.sha256
        assert len(raw) == media.transport.byte_size
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            assert image.format == "JPEG" and image.size == (1672, 941)
    finally:
        output.unlink(missing_ok=True)


def test_publisher_supports_only_pinned_first_party_cover_or_legacy_pinned_git_blob() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "owner_selected_original_vintage_pastry_cover_20261107" in workflow
    assert "content/telegram/milovi-cake/assets/patisserie-history-cover-20261107.webp" in workflow
    assert 'output.write_bytes(Path(source["path"]).read_bytes())' in workflow
    assert "raw.githubusercontent.com" in workflow
    assert "materialize-photo" in workflow
    assert "$GITHUB_SHA" in workflow
