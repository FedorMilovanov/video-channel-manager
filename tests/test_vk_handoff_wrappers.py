from __future__ import annotations

from pathlib import Path


def _script(name: str) -> str:
    return Path("scripts", name).read_text(encoding="utf-8")


def test_description_wrapper_extracts_snapshot_outside_handoff_bundle() -> None:
    text = _script("Invoke-VkDescriptionWave.ps1")

    assert "$TempRunDir" in text
    assert "$TemporarySnapshot" in text
    assert "[System.IO.Path]::GetTempPath()" in text
    assert "-Destination $TemporarySnapshot" in text
    assert "-Destination $SourceSnapshotCopy" not in text


def test_description_wrapper_skips_copying_a_file_over_itself() -> None:
    text = _script("Invoke-VkDescriptionWave.ps1")

    assert "function Get-NormalizedFullPath" in text
    assert "$SourceFullPath" in text
    assert "$DestinationFullPath" in text
    assert "[System.StringComparison]::OrdinalIgnoreCase" in text
    assert "Copy-Item -LiteralPath $SourceFullPath" in text


def test_description_wrapper_always_packages_and_cleans_temp_files() -> None:
    text = _script("Invoke-VkDescriptionWave.ps1")

    assert "finally {\n    try {\n        Write-Bundle" in text
    assert "Remove-Item -LiteralPath $TempRunDir -Recurse -Force" in text


def test_reviewed_description_wrapper_uses_exact_signed_dry_run_zip() -> None:
    text = _script("Invoke-VkReviewedDescriptionWave.ps1")

    assert "[switch]$Execute" in text
    assert "[string]$ReviewedDryRunBundle" in text
    assert "vk-description-wave-dry-run-*.zip" in text
    assert 'status -ne "dry_run_completed"' in text
    assert 'mode -ne "dry-run"' in text
    assert 'component_scope -ne "descriptions_only"' in text
    assert "Manifest.plan_sha256" in text
    assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in text
    assert 'Assert-ManifestFile -Manifest $Manifest -Name "plan.json"' in text
    assert 'Assert-ManifestFile -Manifest $Manifest -Name "plan-review.md"' in text
    assert 'Assert-ManifestFile -Manifest $Manifest -Name "plan-review.html"' in text
    assert 'Assert-ManifestFile -Manifest $Manifest -Name "00-source-vk-snapshot.json"' in text
    assert 'Assert-ManifestFile -Manifest $Manifest -Name "editorial-policy.json"' in text


def test_reviewed_description_wrapper_fails_closed_on_hidden_changes() -> None:
    text = _script("Invoke-VkReviewedDescriptionWave.ps1")

    assert "[int]$ExpectedCount = 111" in text
    assert "before_title_sha256" in text
    assert "after_title_sha256" in text
    assert "semantic_body_preserved" in text
    assert "semantic_body_sha256" in text
    assert "album_title_operations" in text
    assert "CurrentPolicySha" in text
    assert '"-Execute"' in text
    assert "Invoke-VkDescriptionWave.ps1" in text
    assert "Remove-Item -LiteralPath $TempRunDir -Recurse -Force" in text


def test_cosmetic_title_wrapper_is_exactly_scoped_and_semantic_safe() -> None:
    text = _script("Invoke-VkCosmeticTitlePatch.ps1")

    assert "[int]$ExpectedCount = 3" in text
    assert "-235216998_456239022" in text
    assert "-235216998_456239096" in text
    assert "-235216998_456239101" in text
    assert "semantic_title_labels_preserved" in text
    assert "descriptions_to_update" in text
    assert "albums_to_rename" in text
    assert "Invoke-VkTitleWave.ps1" in text


def test_cosmetic_title_wrapper_executes_only_a_reviewed_dry_run_bundle() -> None:
    text = _script("Invoke-VkCosmeticTitlePatch.ps1")

    assert "[switch]$Execute" in text
    assert "[string]$ReviewedDryRunBundle" in text
    assert 'status -ne "dry_run_completed"' in text
    assert 'mode -ne "dry-run"' in text
    assert "Manifest.plan_sha256" in text
    assert "Get-FileHash -LiteralPath $ReviewedPlan -Algorithm SHA256" in text
    assert '$InvokeArguments += "-Execute"' in text


def test_cosmetic_title_wrapper_uses_one_file_handoffs_and_temp_storage() -> None:
    text = _script("Invoke-VkCosmeticTitlePatch.ps1")

    assert "vk-description-wave-dry-run-*.zip" in text
    assert "vk-title-wave-dry-run-*.zip" in text
    assert "00-source-vk-snapshot.json" in text
    assert "04-final-vk-snapshot.json" in text
    assert "[System.IO.Path]::GetTempPath()" in text
    assert "Remove-Item -LiteralPath $TempRunDir -Recurse -Force" in text
