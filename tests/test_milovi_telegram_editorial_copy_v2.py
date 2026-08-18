from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content/telegram/milovi-cake"
FOOTER = MILOVI / "editorial-public-footer-2026-08.json"
CONTINUATION = MILOVI / "first-screen-continuation-copy-2026-08.json"
NEXT = MILOVI / "next-publication-candidate-2026-08-19.json"
TRANSPORT = MILOVI / "bootstrap-photo-transport-proof-2026-08.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_footer_uses_only_registered_milovi_resources() -> None:
    footer = _load(FOOTER)
    assert footer["project_key"] == "milovi-cake"
    assert footer["publication_authorized"] is False
    assert footer["provider_mutation_allowed"] is False
    assert [item["url"] for item in footer["links"]] == [
        "https://milovicake.ru/",
        "https://vk.ru/milovi_cake",
        "https://www.youtube.com/@milovi_cake",
        "https://dzen.ru/milovicake.ru",
    ]
    assert "https://t.me/MiloviCake" not in footer["rendered_footer"]


def test_continuation_copy_treats_brand_authorship_as_implicit() -> None:
    footer = _load(FOOTER)
    continuation = _load(CONTINUATION)
    forbidden = [phrase.casefold() for phrase in footer["editorial_rules"]["forbidden_service_phrases"]]
    assert len(continuation["items"]) == 7
    assert continuation["publication_authorized"] is False
    assert continuation["provider_mutation_allowed"] is False

    publication_ids: set[str] = set()
    for item in continuation["items"]:
        caption = item["caption"]
        folded = caption.casefold()
        assert item["publication_id"] not in publication_ids
        publication_ids.add(item["publication_id"])
        assert all(phrase not in folded for phrase in forbidden)
        assert "реальная работа" not in folded
        assert "хороший референс" not in folded
        assert "https://milovicake.ru/" in caption
        assert "https://vk.ru/milovi_cake" in caption
        assert "https://www.youtube.com/@milovi_cake" in caption
        assert "https://dzen.ru/milovicake.ru" in caption
        hashtags = [token for token in caption.split() if token.startswith("#")]
        assert len(hashtags) <= footer["editorial_rules"]["max_hashtags"]


def test_next_post_is_exact_provider_inert_and_transport_bound() -> None:
    continuation = _load(CONTINUATION)
    candidate = _load(NEXT)
    transport = _load(TRANSPORT)

    assert candidate["publication_id"] == "milovi-feed-20260819-001"
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False
    assert candidate["caption"] == continuation["items"][0]["caption"]

    digest = hashlib.sha256(candidate["caption"].encode("utf-8")).hexdigest()
    assert candidate["caption_sha256"] == f"sha256:{digest}"

    photo = next(item for item in transport["photos"] if item["media_id"] == "p03")
    assert photo["transport_ready"] is True
    assert candidate["media"]["source_git_blob_sha1"] == photo["source_git_blob_sha1"]
    assert candidate["media"]["source_sha256"] == photo["source_sha256"]
    assert candidate["media"]["transport_sha256"] == photo["transport_sha256"]
    assert candidate["media"]["transport_byte_size"] == photo["transport_byte_size"]
    assert candidate["media"]["pixel_width"] == photo["pixel_width"]
    assert candidate["media"]["pixel_height"] == photo["pixel_height"]

    scheduled = datetime.fromisoformat(candidate["scheduled_at"])
    assert scheduled.hour == 10 and scheduled.minute == 30
    assert 9 <= scheduled.hour <= 21


def test_review_quote_remains_exact_and_is_not_bound_to_photo() -> None:
    continuation = _load(CONTINUATION)
    review = next(item for item in continuation["items"] if item["role"] == "verified_social_proof")
    assert review["operation"] == "sendMessage"
    assert review["media_id"] is None
    assert review["fact_source"]["review_author"] == "Ирина Силантьева"
    assert (
        "«Спасибо за прекрасно выполненную работу к 40-летию свадьбы. "
        "И вкусовые качества, и дизайн, и упаковка — гости были в восторге.»"
        in review["caption"]
    )
