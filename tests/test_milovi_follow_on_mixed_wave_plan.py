from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "content/telegram/milovi-cake/follow-on-mixed-wave-plan-2026-08.json"
SCHOOL = ROOT / "content/telegram/milovi-cake/school-interest-reading-candidates-2026-08.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_follow_on_plan_is_provider_inert_and_waits_for_bootstrap_completion() -> None:
    plan = _load(PLAN)
    prerequisites = plan["prerequisites"]

    assert plan["status"] == "provider_inert_editorial_plan_only"
    assert plan["execution_authorized"] is False
    assert plan["provider_mutation_allowed"] is False
    assert plan["becomes_operational_queue"] is False
    assert prerequisites["bootstrap_final_publication_id"] == "milovi-bootstrap-010"
    assert prerequisites["bootstrap_must_be_terminally_verified_before_this_wave"] is True
    assert prerequisites["school_candidates_must_be_reverified_before_operational_promotion"] is True


def test_mixed_wave_is_nine_cake_three_school_with_no_consecutive_school_posts() -> None:
    plan = _load(PLAN)
    items = plan["items"]
    pacing = plan["pacing"]

    assert len(items) == 12
    assert [item["position"] for item in items] == list(range(1, 13))
    cake = [item for item in items if item["brand_stream"] == "milovi-cake"]
    school = [item for item in items if item["brand_stream"] == "milovi-school"]
    assert len(cake) == pacing["planned_cake_items"] == 9
    assert len(school) == pacing["planned_school_items"] == 3
    assert [item["position"] for item in school] == pacing["school_positions"] == [3, 7, 11]
    assert all(
        not (items[index]["brand_stream"] == items[index + 1]["brand_stream"] == "milovi-school")
        for index in range(len(items) - 1)
    )
    assert items[-1]["brand_stream"] == "milovi-cake"


def test_selected_school_items_are_exact_history_candidates_and_have_no_product_cta() -> None:
    plan = _load(PLAN)
    pool = _load(SCHOOL)
    pool_by_id = {item["candidate_id"]: item for item in pool["candidates"]}
    school_items = [item for item in plan["items"] if item["brand_stream"] == "milovi-school"]

    assert [item["school_candidate_id"] for item in school_items] == [
        "school-read-002",
        "school-read-006",
        "school-read-003",
    ]
    for item in school_items:
        candidate = pool_by_id[item["school_candidate_id"]]
        assert item["source_slug"] == candidate["source_slug"]
        assert candidate["source_category"] == "histoire-culinaire"
        assert not candidate["source_slug"].startswith("recipe-")
        assert item["product_cta_allowed"] is False


def test_cross_brand_boundary_forbids_school_product_and_production_linkage() -> None:
    plan = _load(PLAN)
    boundary = plan["cross_brand_boundary"]

    assert boundary["school_is_product_rubric"] is False
    assert boundary["school_is_our_separate_interest_reading_project"] is True
    assert boundary["school_article_may_describe_milovi_cake_production"] is False
    assert boundary["school_article_may_be_used_as_evidence_of_milovi_cake_recipe_or_technique"] is False
    assert boundary["forced_product_cta_in_school_post"] is False
    assert boundary["adjacent_cake_post_may_imply_school_article_explains_its_production"] is False
