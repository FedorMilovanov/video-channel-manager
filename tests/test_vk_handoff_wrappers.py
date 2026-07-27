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


def test_cosmetic_title_wrapper_is_dry_run_only_and_exactly_scoped() -> None:
    text = _script("Invoke-VkCosmeticTitlePatch.ps1")

    assert "[int]$ExpectedCount = 3" in text
    assert "-235216998_456239022" in text
    assert "-235216998_456239096" in text
    assert "-235216998_456239101" in text
    assert "semantic_title_labels_preserved" in text
    assert "descriptions_to_update" in text
    assert "albums_to_rename" in text
    assert "Invoke-VkTitleWave.ps1" in text
    assert "-Execute" not in text


def test_cosmetic_title_wrapper_uses_snapshot_from_one_file_handoff() -> None:
    text = _script("Invoke-VkCosmeticTitlePatch.ps1")

    assert "vk-description-wave-dry-run-*.zip" in text
    assert "00-source-vk-snapshot.json" in text
    assert "04-final-vk-snapshot.json" in text
    assert "[System.IO.Path]::GetTempPath()" in text
    assert "Remove-Item -LiteralPath $TempRunDir -Recurse -Force" in text
