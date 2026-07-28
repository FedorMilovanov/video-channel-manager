from __future__ import annotations

from pathlib import Path


_DRY_VERIFIER = Path("scripts/verify_vk_reviewed_correction_pushkin_cloud_dry_run.py")
_APPLY_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionPushkinCloudApply.ps1")
_APPLY_VERIFIER = Path("scripts/verify_vk_reviewed_correction_pushkin_cloud_apply_bundle.py")


def test_pushkin_cloud_dry_run_verifier_pins_exact_reviewed_bundle() -> None:
    text = _DRY_VERIFIER.read_text(encoding="utf-8")

    assert "sha256:8131a1a5845547eb1fc78b313e3de50d22a433a8dc7c559329bafd58cc6521a5" in text
    assert "sha256:207ee6e5622692b504254c7d7aa3579fd2907614eaf88d1b6e0ac7c1eacf517c" in text
    assert "sha256:eaddbce693498a87cd888642642073bb0198c85087659543756ae61763e80a75" in text
    assert '"-235216998_456239106"' in text
    assert '"ready: 1"' in text
    assert '"already applied: 0"' in text
    assert '"conflicts: 0"' in text
    assert "reviewed_replacements_reconstructed" in text
    assert "urls_and_hashtags_unchanged" in text
    assert "exact_member_hashes_verified" in text


def test_pushkin_cloud_apply_wrapper_is_explicit_and_exact() -> None:
    text = _APPLY_WRAPPER.read_text(encoding="utf-8")

    assert "[switch]$Execute" in text
    assert "if (-not $Execute)" in text
    assert "$ExpectedCount = 1" in text
    assert '$ExpectedDecisionSet = "p1-pushkin-cloud-20260728"' in text
    assert '$ExpectedIds = @("-235216998_456239106")' in text
    assert "verify_vk_reviewed_correction_pushkin_cloud_dry_run.py" in text
    assert "verify_vk_reviewed_correction_pushkin_cloud_apply_bundle.py" in text
    assert "--confirm-community $Community" in text
    assert "--confirm-ready $Ready" in text
    assert '--confirm-plan-sha256 "$($PlanJson.plan_sha256)"' in text
    assert '--confirm-video-coverage "$($PlanJson.target_video_ids_sha256)"' in text
    assert '--confirm-memberships "$($PlanJson.initial_memberships_sha256)"' in text
    assert "--max-operations $ExpectedCount" in text
    assert "--execute" in text
    assert "04-final-vk-snapshot.json" in text
    assert "05-independent-verification.json" in text


def test_pushkin_cloud_apply_verifier_freezes_full_inventory() -> None:
    text = _APPLY_VERIFIER.read_text(encoding="utf-8")

    assert "len(final_videos) != 111" in text
    assert 'len(source.get("collections", [])) != 17' in text
    assert 'len(source.get("memberships", [])) != 294' in text
    assert "non-target description changed" in text
    assert "VK collection identities or titles changed" in text
    assert "VK membership identity changed" in text
    assert '"non_target_videos_verified_unchanged": 110' in text
    assert '"membership_identity_unchanged": True' in text
