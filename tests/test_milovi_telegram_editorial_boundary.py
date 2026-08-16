from __future__ import annotations

import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content" / "telegram" / "milovi-cake"


def _load_json(name: str) -> dict[str, object]:
    payload = json.loads((MILOVI / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_first_screen_has_no_school_or_french_positioning() -> None:
    candidates = _load_json("bootstrap-first-screen-candidates-2026-08.json")
    assert candidates["school_items_in_first_screen"] == 0
    items = candidates["candidates"]
    assert isinstance(items, list)
    assert len(items) == 10

    forbidden = ("milovi school", "french.milovicake.ru", "француз")
    for item in items:
        assert isinstance(item, dict)
        caption = str(item["caption"]).casefold()
        for fragment in forbidden:
            assert fragment not in caption
        assert item["execution_ready"] is False
        assert item["publication_authorized"] is False

    assert candidates["provider_mutation_allowed"] is False


def test_brand_boundary_explicitly_separates_cake_and_school() -> None:
    text = (MILOVI / "editorial-brand-boundary-2026-08.md").read_text(encoding="utf-8").casefold()
    assert "milovi school is a separate educational / content project" in text
    assert "not evidence" in text
    assert "makes its cakes from the school's recipes" in text
    assert "french kitchen" in text
    assert "first ten launch posts" in text
    assert "zero milovi school posts" in text
    assert "do-not-republish" in text


def test_quiet_hours_are_hard_and_provider_inert() -> None:
    window = _load_json("publishing-window-2026-08.json")
    assert window["timezone"] == "Europe/Moscow"
    assert window["earliest_publication_local"] == "09:00"
    assert window["latest_publication_local"] == "21:00"
    assert window["preferred_slots_local"] == ["10:30", "13:30", "17:00", "20:00"]
    assert "before Telegram provider access" in str(window["quiet_hours_rule"])
    assert "does not override" in str(window["manual_authorization_rule"])
    assert window["provider_mutation_allowed_by_this_file"] is False


def test_deleted_bad_canary_is_retained_only_as_historical_evidence() -> None:
    correction = _load_json("live/operator-correction-2026-08-16.json")
    assert correction["publication_id"] == "milovi-cake-canary-001"
    assert correction["historical_dispatch_status"] == "verified"
    assert correction["historical_message_id"] == 25
    assert correction["operator_reported_current_visibility"] == "deleted"
    assert correction["provider_absence_readback_performed"] is False
    assert correction["do_not_republish_exact_payload"] is True
    assert correction["public_rollout_paused_until_daylight_window"] is True
    assert correction["provider_mutation_allowed_by_this_record"] is False


def test_bootstrap_transport_proof_is_complete_and_matches_candidates() -> None:
    proof = _load_json("bootstrap-photo-transport-proof-2026-08.json")
    readiness = _load_json("bootstrap-photo-source-readiness-2026-08.json")
    candidates = _load_json("bootstrap-first-screen-candidates-2026-08.json")

    assert proof["status"] == "provider_inert_exact_transport_verified"
    assert proof["photo_count"] == 9
    assert proof["transport_ready_count"] == 9
    assert proof["provider_write_performed"] is False
    assert proof["provider_mutation_allowed"] is False
    assert readiness["transport_ready_count"] == 9
    assert readiness["provider_mutation_allowed"] is False

    photos = proof["photos"]
    assert isinstance(photos, list)
    assert len(photos) == 9
    photo_ids: set[str] = set()
    sha_re = re.compile(r"^sha256:[0-9a-f]{64}$")
    for photo in photos:
        assert isinstance(photo, dict)
        media_id = str(photo["media_id"])
        assert media_id not in photo_ids
        photo_ids.add(media_id)
        assert photo["transport_ready"] is True
        assert int(photo["source_byte_size"]) > 0
        assert int(photo["transport_byte_size"]) > 0
        assert int(photo["pixel_width"]) > 0
        assert int(photo["pixel_height"]) > 0
        assert sha_re.fullmatch(str(photo["source_sha256"]))
        assert sha_re.fullmatch(str(photo["transport_sha256"]))

    items = candidates["candidates"]
    assert isinstance(items, list)
    candidate_photo_ids = {
        str(item["media_id"])
        for item in items
        if isinstance(item, dict) and item.get("operation") == "sendPhoto"
    }
    assert candidate_photo_ids == photo_ids


def test_exact_review_remains_exact_and_sourced() -> None:
    candidates = _load_json("bootstrap-first-screen-candidates-2026-08.json")
    items = candidates["candidates"]
    assert isinstance(items, list)
    review = next(item for item in items if isinstance(item, dict) and item["publication_id"] == "milovi-bootstrap-008")
    caption = str(review["caption"])
    exact_quote = "Спасибо за прекрасно выполненную работу к 40-летию свадьбы. И вкусовые качества, и дизайн, и упаковка — гости были в восторге."
    assert exact_quote in caption
    source = review["fact_source"]
    assert isinstance(source, dict)
    assert source["review_author"] == "Ирина Силантьева"
    assert source["git_blob_sha1"] == "cccfbc9c12d9d3724b0a27a481cbb1347f77716a"


def test_historical_bad_canary_caption_is_not_reused_by_first_screen() -> None:
    canary = _load_json("canary-candidate-2026-08.json")
    caption_block = canary["caption"]
    assert isinstance(caption_block, dict)
    historical_caption = str(caption_block["text"])
    historical_digest = "sha256:" + hashlib.sha256(historical_caption.encode("utf-8")).hexdigest()
    correction = _load_json("live/operator-correction-2026-08-16.json")
    assert historical_digest == correction["historical_caption_sha256"]

    candidates = _load_json("bootstrap-first-screen-candidates-2026-08.json")
    items = candidates["candidates"]
    assert isinstance(items, list)
    assert historical_caption not in {str(item["caption"]) for item in items if isinstance(item, dict)}
