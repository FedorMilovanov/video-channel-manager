from __future__ import annotations

from pathlib import Path


_APPLY = Path("scripts/Invoke-VkReviewedCorrectionFetApply.ps1")
_VERIFIER = Path("scripts/verify_vk_reviewed_correction_fet_apply_bundle.py")


def test_fet_execute_helper_requires_exact_reviewed_dry_run() -> None:
    text = _APPLY.read_text(encoding="utf-8")

    assert "if (-not $Execute)" in text
    assert "vk-reviewed-correction-p1-fet-dry-run-*.zip" in text
    assert "verify_vk_reviewed_correction_fet_dry_run.py" in text
    assert '"p1-fet-whisper-20260727"' in text
    assert '"-235216998_456239127"' in text
    assert '"-235216998_456239143"' in text
    assert "$ExpectedCount = 2" in text
    assert "--max-operations $ExpectedCount" in text
    assert "build_vk_reviewed_correction_wave.py" not in text


def test_fet_execute_helper_repeats_all_live_guards_and_postflight() -> None:
    text = _APPLY.read_text(encoding="utf-8")

    assert "--confirm-community $Community" in text
    assert "--confirm-ready $Ready" in text
    assert '--confirm-plan-sha256 "$($PlanJson.plan_sha256)"' in text
    assert '--confirm-video-coverage "$($PlanJson.target_video_ids_sha256)"' in text
    assert '--confirm-memberships "$($PlanJson.initial_memberships_sha256)"' in text
    assert '--result-output "$ResultPath"' in text
    assert "video-manager vk scan" in text
    assert text.count("verify_vk_reviewed_correction_fet_apply_bundle.py") == 2
    assert "05-independent-verification.json" in text
    assert "Создан диагностический Fet apply ZIP" in text


def test_fet_apply_verifier_locks_scope_and_all_non_targets() -> None:
    text = _VERIFIER.read_text(encoding="utf-8")

    assert "verify_vk_reviewed_correction_fet_dry_run" in text
    assert "p1-fet-whisper-20260727" in text
    assert "Plan must contain exactly two Fet description corrections" in text
    assert "Fet apply target IDs differ from the reviewed set" in text
    assert '"operations": 2' in text
    assert "len(_video_map(final)) - len(_TARGET_IDS)" in text
    assert "VK album memberships changed during Fet correction" in text
    assert "membership_position_changes" in text
    assert "updated_and_verified" in text
    assert "already_applied" in text


def test_fet_apply_verifier_checks_reviewed_meaning() -> None:
    text = _VERIFIER.read_text(encoding="utf-8")

    for required in (
        "датируется 1850 годом",
        "прямого авторского посвящения",
        "могло скрывать самоубийство",
        "другой поздний цикл 1882–1892 годов",
        "воспоминаниям секретаря Е. В. Кудрявцевой",
    ):
        assert required in text
    for forbidden in (
        "Фет посвятил его Марии Лазич",
        "Фет всю жизнь писал только ей",
        "смерть наступила от сердечного приступа",
    ):
        assert forbidden in text
