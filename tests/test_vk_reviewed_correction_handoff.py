from __future__ import annotations

import json
from pathlib import Path


def test_reviewed_correction_wrapper_is_dry_run_only() -> None:
    text = Path("scripts/Invoke-VkReviewedCorrectionWave.ps1").read_text(encoding="utf-8")

    assert "build_vk_reviewed_correction_wave.py" in text
    assert "apply_vk_editorial_cleanup_plan.py" in text
    assert "--max-operations 3" in text
    assert "--execute" not in text.casefold()
    assert '$BundleName = "vk-reviewed-correction-p1-dry-run-$Stamp"' in text
    assert '$ZipPath = Join-Path $Handoffs "$BundleName.zip"' in text
    assert "remote_writes = 0" in text
    assert "Expected exactly 3 correction operations" in text
    assert "VK-записей: 0" in text


def test_reviewed_correction_cli_verifies_review_bundle_integrity() -> None:
    text = Path("scripts/build_vk_reviewed_correction_wave.py").read_text(encoding="utf-8")

    assert "Review bundle size mismatch" in text
    assert "Review bundle SHA-256 mismatch" in text
    assert "Review bundle file SHA-256 differs" in text
    assert 'manifest.get("status") != "review_only_completed"' in text
    assert 'queue.get("mode") != "review_only"' in text
    assert "video.edit" not in text


def test_p1_esenin_decisions_are_exactly_scoped() -> None:
    path = Path("content/policies/vk-reviewed-corrections-p1-esenin-confession-20260727.json")
    decisions = json.loads(path.read_text(encoding="utf-8"))

    assert decisions["target_community_id"] == 235216998
    assert decisions["source_review_bundle_sha256"].startswith("sha256:")
    assert len(decisions["decisions"]) == 3
    assert {item["target_video_id"] for item in decisions["decisions"]} == {
        "-235216998_456239046",
        "-235216998_456239047",
        "-235216998_456239050",
    }
    assert {item["replacement_id"] for item in decisions["shared_replacements"]} == {
        "remove-unverifiable-final-faith-judgment",
        "correct-academic-date",
    }
    assert all(len(item["replacement_ids"]) == 2 for item in decisions["decisions"])
    assert all(len(item["source_ids"]) == 2 for item in decisions["decisions"])
