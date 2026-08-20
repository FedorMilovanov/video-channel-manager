from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
WORKFLOWS = ROOT / ".github" / "workflows"
MARATHON = CONTENT / "marathon-wave-2026-08.json"
FROZEN = CONTENT / "follow-on-wave-candidates-2026-08.json"
PHOTOS = CONTENT / "follow-on-photo-source-manifest-2026-08.json"
SCHOOL = CONTENT / "school-interest-reading-candidates-2026-08.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marathon_reuses_exact_merged_follow_on_work_without_reauthoring() -> None:
    marathon = _json(MARATHON)
    frozen = _json(FROZEN)

    assert marathon["status"] == "provider_inert_editorially_fresh_marathon"
    assert marathon["source_contract"]["frozen_copy_git_blob_sha1"] == "5f9ef57b80df664348da25705cfe93606fdcecbf"
    assert marathon["wave_contract"]["total_items"] == len(frozen["items"]) == 12
    assert [item["legacy_position"] for item in marathon["items"]] == [item["position"] for item in frozen["items"]]

    for item in marathon["items"]:
        source = frozen["items"][item["legacy_position"] - 1]
        assert item["brand_stream"] == source["brand_stream"]
        assert item["content_role"] == source["content_role"]
        assert item["operation"] == source["operation"]
        if item["operation"] == "sendPhoto":
            assert item["media_id"] == source["media_id"]
        else:
            assert item["school_candidate_id"] == source["school_candidate_id"]
            assert item["source_slug"] == source["source_slug"]


def test_marathon_is_exact_nine_cake_three_school_nonconsecutive_mix() -> None:
    marathon = _json(MARATHON)
    items = marathon["items"]

    assert len(items) == 12
    assert [item["position"] for item in items] == list(range(1, 13))
    cake = [item for item in items if item["brand_stream"] == "milovi-cake"]
    school = [item for item in items if item["brand_stream"] == "milovi-school"]
    assert len(cake) == 9
    assert len(school) == 3
    assert [item["position"] for item in school] == [3, 7, 11]
    assert items[-1]["brand_stream"] == "milovi-cake"
    assert all(b["position"] - a["position"] > 1 for a, b in zip(school, school[1:], strict=True))


def test_every_photo_slot_has_existing_exact_transport_evidence() -> None:
    marathon = _json(MARATHON)
    manifest = _json(PHOTOS)
    by_id = {photo["media_id"]: photo for photo in manifest["photos"]}
    photo_items = [item for item in marathon["items"] if item["operation"] == "sendPhoto"]

    assert manifest["status"] == "provider_inert_exact_transport_verified"
    assert manifest["photo_count"] == manifest["transport_ready_count"] == 9
    assert len(photo_items) == 9
    assert set(item["media_id"] for item in photo_items) == set(by_id)
    for item in photo_items:
        proof = by_id[item["media_id"]]
        assert proof["source_sha256"].startswith("sha256:")
        assert proof["transport_sha256"].startswith("sha256:")
        assert proof["transport_byte_size"] > 0


def test_every_school_slot_is_in_existing_reviewed_interest_reading_pool() -> None:
    marathon = _json(MARATHON)
    school_pool = _json(SCHOOL)
    by_id = {candidate["candidate_id"]: candidate for candidate in school_pool["candidates"]}
    school_items = [item for item in marathon["items"] if item["operation"] == "sendMessage"]

    assert school_pool["status"] == "provider_inert_editorial_candidate_pool"
    assert school_pool["school_project"]["source_repository_head_reviewed"] == "aa82176012b93a50ccfcfb90293d496618e50b61"
    assert len(school_items) == 3
    for item in school_items:
        candidate = by_id[item["school_candidate_id"]]
        assert candidate["source_slug"] == item["source_slug"]
        assert candidate["expected_article_url"].endswith(f"/articles/{item['source_slug']}")
        assert item["product_cta_allowed"] is False


def test_marathon_never_creates_standing_authority_or_stale_schedule() -> None:
    marathon = _json(MARATHON)

    assert marathon["publication_authorized"] is False
    assert marathon["execution_authorized"] is False
    assert marathon["provider_mutation_allowed"] is False
    assert marathon["provider_access_performed"] is False
    assert marathon["provider_write_performed"] is False
    assert marathon["dates_frozen"] is False
    assert marathon["publication_ids_frozen"] is False
    assert marathon["wave_contract"]["standing_execution_authority"] is False
    assert marathon["wave_contract"]["no_catch_up"] is True
    assert marathon["wave_contract"]["strict_next_only"] is True


def test_marathon_preserves_one_permanent_writer_and_does_not_revive_follow_on_executor() -> None:
    marathon = _json(MARATHON)
    publisher = WORKFLOWS / "milovi-telegram-feed-publisher.yml"

    assert marathon["wave_contract"]["permanent_writer_only"] == ".github/workflows/milovi-telegram-feed-publisher.yml"
    assert publisher.exists()
    assert not (WORKFLOWS / "milovi-telegram-follow-on-readiness.yml").exists()
    assert not (WORKFLOWS / "milovi-telegram-follow-on-media-proof.yml").exists()


def test_reserve_keeps_completed_video_artifacts_and_unverified_life_content_separate() -> None:
    marathon = _json(MARATHON)
    reserve = marathon["reserve"]

    assert reserve["school_candidate_pool_total"] == 12
    assert reserve["school_candidates_used_in_this_wave"] == 3
    assert reserve["school_candidates_remaining"] == 9
    assert reserve["native_video_artifacts"]["status"] == "accepted_16_of_16"
    assert reserve["native_video_artifacts"]["accepted_output_count"] == 16
    assert reserve["native_video_artifacts"]["included_in_this_wave"] is False
    assert reserve["life_or_bts"]["included"] is False
