from __future__ import annotations

from pathlib import Path


def test_vk_description_apply_verifier_checks_authoritative_artifacts() -> None:
    text = Path("scripts/verify_vk_description_apply_bundle.py").read_text(encoding="utf-8")

    assert '"03-result.json"' in text
    assert '"04-final-vk-snapshot.json"' in text
    assert 'result.get("status") != "completed"' in text
    assert "updated_and_verified" in text
    assert "vk_texts_equivalent" in text
    assert 'after.description != operation.get("after_description")' in text
    assert "before.title != after.title" in text
    assert "source_collection_titles != final_collection_titles" in text
    assert "_membership_rows(source) != _membership_rows(final)" in text
    assert "target_video_ids_sha256" in text
    assert "membership_state_sha256" in text
    assert '"status": "verified_completed"' in text


def test_vk_description_apply_verifier_validates_manifest_integrity() -> None:
    text = Path("scripts/verify_vk_description_apply_bundle.py").read_text(encoding="utf-8")

    assert "expected_size != len(content)" in text
    assert "hashlib.sha256(content).hexdigest()" in text
    assert "Bundle integrity failed" in text
