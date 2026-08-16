from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content" / "telegram" / "milovi-cake"


def _load(name: str) -> dict[str, object]:
    payload = json.loads((MILOVI / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_follow_on_copy_is_exactly_nine_cake_three_school_and_provider_inert() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    assert wave["status"] == "provider_inert_frozen_copy_candidate"
    assert wave["execution_authorized"] is False
    assert wave["provider_mutation_allowed"] is False
    assert wave["becomes_operational_queue"] is False

    items = wave["items"]
    assert isinstance(items, list)
    assert len(items) == 12
    assert [item["position"] for item in items] == list(range(1, 13))
    assert [item["publication_id"] for item in items] == [f"milovi-follow-on-{number:03d}" for number in range(1, 13)]

    cake = [item for item in items if item["brand_stream"] == "milovi-cake"]
    school = [item for item in items if item["brand_stream"] == "milovi-school"]
    assert len(cake) == 9
    assert len(school) == 3
    assert [item["position"] for item in school] == [3, 7, 11]
    assert items[-1]["brand_stream"] == "milovi-cake"
    assert all(left["brand_stream"] != "milovi-school" or right["brand_stream"] != "milovi-school" for left, right in zip(items, items[1:], strict=False))


def test_follow_on_cake_media_is_unique_and_does_not_repeat_launch_screen() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    launch = _load("bootstrap-rollout-candidate-2026-08.json")

    items = wave["items"]
    launch_items = launch["items"]
    assert isinstance(items, list)
    assert isinstance(launch_items, list)

    follow_on_media = [str(item["media_id"]) for item in items if item["brand_stream"] == "milovi-cake"]
    launch_media = {str(item["media_id"]) for item in launch_items if item.get("media_id")}
    assert follow_on_media == ["p06", "p30", "p08", "p15", "p22", "p14", "p29", "p26", "p01"]
    assert len(set(follow_on_media)) == 9
    assert set(follow_on_media).isdisjoint(launch_media)


def test_school_slots_are_interest_reading_not_product_rubric() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    items = wave["items"]
    assert isinstance(items, list)
    school = [item for item in items if item["brand_stream"] == "milovi-school"]

    assert [(item["school_candidate_id"], item["source_slug"]) for item in school] == [
        ("school-read-002", "laduree-1862"),
        ("school-read-006", "paris-brest-race-dessert"),
        ("school-read-003", "careme-first-celebrity-chef"),
    ]
    for item in school:
        assert item["operation"] == "sendMessage"
        assert item["product_cta_allowed"] is False
        caption = str(item["caption"])
        assert "Читать в нашем проекте Milovi School → https://french.milovicake.ru/articles/" in caption
        assert "milovicake.ru/zakazat" not in caption.casefold()
        assert "наш торт" not in caption.casefold()
        assert "мы готовим" not in caption.casefold()


def test_cake_copy_does_not_infer_school_or_french_production() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    items = wave["items"]
    assert isinstance(items, list)
    cake = [item for item in items if item["brand_stream"] == "milovi-cake"]

    forbidden = ("milovi school", "french.milovicake.ru", "француз", "по рецепту school", "технологи school")
    for item in cake:
        caption = str(item["caption"])
        folded = caption.casefold()
        assert item["operation"] == "sendPhoto"
        assert len(caption) <= 1024
        for fragment in forbidden:
            assert fragment not in folded


def test_mutable_customer_guidance_is_marked_for_reverification() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    items = wave["items"]
    assert isinstance(items, list)
    by_position = {item["position"]: item for item in items}

    for position in (2, 4, 6, 9):
        assert by_position[position]["must_reverify_before_operational_promotion"] is True
    for position in (3, 7, 11):
        assert by_position[position]["must_reverify_before_operational_promotion"] is True


def test_review_is_exact_and_explicitly_not_bound_to_photo() -> None:
    wave = _load("follow-on-wave-candidates-2026-08.json")
    reviews = (MILOVI / "follow-on-wave-candidates-2026-08.json").read_text(encoding="utf-8")
    items = wave["items"]
    assert isinstance(items, list)
    review = next(item for item in items if item["position"] == 5)

    exact_quote = "Спасибо за оперативность, внимательный подход, рекомендации по вкусам и вашу работу. Торт получился отличным, именинница довольна."
    assert exact_quote in str(review["caption"])
    assert review["review_author"] == "Жанель"
    assert review["review_date"] == "2026-02-02"
    assert "отзыв не привязан к этой фотографии" in str(review["caption"]).casefold()
    assert exact_quote in reviews


def test_follow_on_source_manifest_binds_all_nine_exact_git_objects() -> None:
    manifest = _load("follow-on-photo-source-manifest-2026-08.json")
    assert manifest["source_repository"] == "FedorMilovanov/Milovi_Cake"
    assert manifest["source_commit"] == "551866f1c34611406fc0a696bec8fc8fb4fd36d8"
    assert manifest["gallery_metadata_blob_sha1"] == "e20e60c07479e8b20c1db700f1a40364b81eb669"
    assert manifest["photo_count"] == 9
    assert manifest["execution_authorized"] is False
    assert manifest["provider_mutation_allowed"] is False

    photos = manifest["photos"]
    assert isinstance(photos, list)
    assert [item["media_id"] for item in photos] == ["p06", "p30", "p08", "p15", "p22", "p14", "p29", "p26", "p01"]
    sha1 = re.compile(r"^[0-9a-f]{40}$")
    sha256 = re.compile(r"^sha256:[0-9a-f]{64}$")
    for item in photos:
        assert sha1.fullmatch(str(item["source_git_blob_sha1"]))
        assert int(item["source_byte_size"]) > 0
        proof_fields = (
            item["source_sha256"],
            item["pixel_width"],
            item["pixel_height"],
            item["transport_byte_size"],
            item["transport_sha256"],
        )
        if manifest["status"] == "provider_inert_exact_transport_verified":
            assert sha256.fullmatch(str(item["source_sha256"]))
            assert int(item["pixel_width"]) > 0
            assert int(item["pixel_height"]) > 0
            assert int(item["transport_byte_size"]) > 0
            assert sha256.fullmatch(str(item["transport_sha256"]))
        else:
            assert manifest["status"] == "provider_inert_exact_source_bound_pending_transport_proof"
            assert proof_fields == (None, None, None, None, None)
