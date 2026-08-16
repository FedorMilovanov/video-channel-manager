from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (
    ROOT
    / "content/telegram/milovi-cake/school-interest-reading-candidates-2026-08.json"
)
BOUNDARY = ROOT / "content/telegram/milovi-cake/editorial-brand-boundary-2026-08.md"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_school_candidate_pool_is_provider_inert_and_separate_from_product_brand() -> None:
    data = _load_json(CANDIDATES)
    school = data["school_project"]

    assert data["status"] == "provider_inert_editorial_candidate_pool"
    assert data["provider_mutation_allowed"] is False
    assert data["execution_authorized"] is False
    assert school["name"] == "Milovi School"
    assert school["positioning"] == "our separate editorial project for interesting reading"
    assert school["not_product_rubric"] is True
    assert school["not_evidence_of_milovi_cake_production"] is True


def test_first_school_wave_has_twelve_distinct_story_led_candidates() -> None:
    data = _load_json(CANDIDATES)
    candidates = data["candidates"]

    assert len(candidates) == 12
    assert len({item["candidate_id"] for item in candidates}) == 12
    assert len({item["source_slug"] for item in candidates}) == 12
    assert all(item["hook"].strip() for item in candidates)
    assert all(item["preview"].strip() for item in candidates)
    assert all(item["open_loop"].strip() for item in candidates)
    assert all("Milovi School" in item["cta"] for item in candidates)
    assert all("[verified article URL before scheduling]" in item["cta"] for item in candidates)


def test_school_previews_do_not_claim_milovi_cake_product_or_production_link() -> None:
    data = _load_json(CANDIDATES)
    combined = "\n".join(
        "\n".join(
            [
                str(item["hook"]),
                str(item["preview"]),
                str(item["open_loop"]),
                str(item["cta"]),
            ]
        )
        for item in data["candidates"]
    ).casefold()

    forbidden = [
        "наши торты делают",
        "наши торты готовят",
        "в milovi cake мы готовим",
        "в milovi cake мы используем",
        "рецепт milovi cake",
        "технология milovi cake",
        "французская кухня milovi cake",
        "французская кондитерская milovi cake",
        "заказать такой торт",
        "закажите такой торт",
    ]
    assert all(phrase not in combined for phrase in forbidden)


def test_school_policy_is_interest_reading_not_product_rubric() -> None:
    data = _load_json(CANDIDATES)
    policy = data["editorial_policy"]
    boundary = BOUNDARY.read_text(encoding="utf-8")

    assert policy["first_screen_school_items"] == 0
    assert policy["eligible_only_after_bootstrap_first_screen"] is True
    assert policy["school_posts_may_not_be_consecutive"] is True
    assert policy["product_cta_required"] is False
    assert policy["product_cta_default"] == "forbidden"
    assert "our separate editorial project for interesting reading" in boundary
    assert "not as a product rubric" in boundary
    assert "Do **not** force a Milovi Cake product CTA into a School preview" in boundary
