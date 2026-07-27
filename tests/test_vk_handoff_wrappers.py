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
