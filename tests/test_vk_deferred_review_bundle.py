from __future__ import annotations

from pathlib import Path


def test_deferred_review_builder_is_review_only() -> None:
    text = Path("scripts/build_vk_deferred_review_bundle.py").read_text(encoding="utf-8")

    assert "verify_bundle(apply_bundle)" in text
    assert '"mode": "review_only"' in text
    assert '"remote_writes": 0' in text
    assert "deferred_editorial_review" in text
    assert "review-queue.json" in text
    assert "review-queue.md" in text
    assert "review-queue.html" in text
    assert "video.edit" not in text


def test_deferred_review_wrapper_uses_one_verified_apply_zip() -> None:
    text = Path("scripts/Invoke-VkDeferredEditorialReview.ps1").read_text(encoding="utf-8")

    assert "vk-description-wave-apply-*.zip" in text
    assert "verify_vk_description_apply_bundle.py" in text
    assert "build_vk_deferred_review_bundle.py" in text
    assert "vk-deferred-editorial-review-$Stamp.zip" in text
    assert "Удалённых или изменённых данных VK: 0" in text
    assert "-Execute" not in text
