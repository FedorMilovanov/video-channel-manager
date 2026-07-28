from __future__ import annotations

from pathlib import Path


def test_correction_dry_run_verifier_locks_exact_scope() -> None:
    text = Path("scripts/verify_vk_reviewed_correction_dry_run.py").read_text(encoding="utf-8")

    assert "verified_dry_run" in text
    assert "source-review-bundle.zip" in text
    assert "Plan self-digest mismatch" in text
    assert "Nested source review bundle SHA-256 mismatch" in text
    assert "asymmetric_evidence_based" in text
    assert "do_not_balance_documented_unbelief_with_bare_possibility" in text
    assert "По доступным историческим свидетельствам Есенин умер неверующим" in text
    assert "вечная погибель под Божьим судом" in text
    assert "1913–1915 гг." in text
    assert "1912 г." in text
    assert "remote_writes" in text
    assert "video.edit" not in text


def test_correction_apply_verifier_checks_targets_and_non_targets() -> None:
    text = Path("scripts/verify_vk_reviewed_correction_apply_bundle.py").read_text(encoding="utf-8")

    assert "verify_dry_run_bundle" in text
    assert "previous-reviewed-dry-run.zip" in text
    assert "updated_and_verified" in text
    assert "already_applied" in text
    assert "non-target title changed" in text
    assert "non-target description changed" in text
    assert "VK album inventory or titles changed" in text
    assert "VK album memberships changed" in text
    assert "non_target_videos_verified_unchanged" in text
    assert "05-independent-verification.json" in text
    assert "verified_completed" in text


def test_correction_apply_wrapper_is_explicit_and_double_verified() -> None:
    text = Path("scripts/Invoke-VkReviewedCorrectionApply.ps1").read_text(encoding="utf-8")

    assert "if (-not $Execute)" in text
    assert "vk-reviewed-correction-p1-dry-run-*.zip" in text
    assert "verify_vk_reviewed_correction_dry_run.py" in text
    assert text.count("verify_vk_reviewed_correction_apply_bundle.py") == 2
    assert "--execute" in text
    assert "--confirm-community" in text
    assert "--confirm-ready" in text
    assert "--confirm-plan-sha256" in text
    assert "--confirm-video-coverage" in text
    assert "--confirm-memberships" in text
    assert "--max-operations $ExpectedCount" in text
    assert "video-manager vk scan" in text
    assert "05-independent-verification.json" in text
    assert "remaining 108 descriptions" not in text
    assert "остальные 108 описаний" in text


def test_correction_dry_run_readme_matches_owner_stance() -> None:
    text = Path("scripts/Invoke-VkReviewedCorrectionWave.ps1").read_text(encoding="utf-8")

    assert "духовный вывод, согласованный с PROJECT_CHARTER" in text
    assert "удаление недоказуемого утверждения" not in text
    assert "DRY-RUN НЕ ВЫЗЫВАЕТ VK MUTATION API" in text
