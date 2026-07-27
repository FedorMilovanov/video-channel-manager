from __future__ import annotations

from pathlib import Path


def test_deferred_review_builder_is_review_only_and_localized() -> None:
    text = Path("scripts/build_vk_deferred_review_bundle.py").read_text(encoding="utf-8")

    assert "verify_bundle(apply_bundle)" in text
    assert '"mode": "review_only"' in text
    assert '"remote_writes": 0' in text
    assert "build_vk_deferred_editorial_findings" in text
    assert "research_units" in text
    assert "description_sha256" in text
    assert "duplicate_description_groups" in text
    assert "trigger_families" in text
    assert "matched_terms" in text
    assert "priority" in text
    assert "review-queue.json" in text
    assert "review-queue.md" in text
    assert "review-queue.html" in text
    assert "review-queue.csv" in text
    assert "video.edit" not in text


def test_deferred_review_builder_groups_only_exact_descriptions() -> None:
    text = Path("scripts/build_vk_deferred_review_bundle.py").read_text(encoding="utf-8")

    assert 'grouped[item["description_sha256"]].append(item)' in text
    assert "similar" not in text.casefold()
    assert "research_unit_id" in text
    assert "P1" in text
    assert "P2" in text
    assert "P3" in text


def test_deferred_review_wrapper_uses_one_verified_apply_zip() -> None:
    text = Path("scripts/Invoke-VkDeferredEditorialReview.ps1").read_text(encoding="utf-8")

    assert "vk-description-wave-apply-*.zip" in text
    assert "build_vk_deferred_review_bundle.py" in text
    assert "vk-deferred-editorial-review-$Stamp.zip" in text
    assert "Записей, удалений или изменений данных VK: 0" in text
    assert "review-queue.html" in text
    assert "vk-description-apply-verification" not in text
    assert "-Execute" not in text
