from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DECISIONS = Path("content/policies/vk-reviewed-corrections-p1-fet-whisper-20260727.json")
_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionFetWave.ps1")
_VERIFIER = Path("scripts/verify_vk_reviewed_correction_fet_dry_run.py")
_BUILDER = Path("src/video_channel_manager/platforms/vk/editorial_correction_wave.py")


def _payload() -> dict[str, Any]:
    payload = json.loads(_DECISIONS.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_fet_decisions_lock_exact_two_video_scope() -> None:
    payload = _payload()
    decisions = payload["decisions"]

    assert payload["decision_set_id"] == "p1-fet-whisper-20260727"
    assert payload["source_review_bundle_sha256"] == (
        "sha256:f38191f18d859ef2bcd445f558204ac76e3c3ebbe4f6414cb3436542df7b4c61"
    )
    assert payload["description_guard_hash_algorithm"] == "video-manager.text-sha256-v1"
    assert {item["target_video_id"] for item in decisions} == {
        "-235216998_456239127",
        "-235216998_456239143",
    }
    canonical_guards = {item["expected_description_sha256"] for item in decisions}
    assert canonical_guards == {
        "sha256:eb10b7f1e529c26c240dada4116d2a9666b33bb4e0e167839ad3f9762e959203",
        "sha256:76c74c96f9aaa93d952531094d42c4b7a168f901566688bd349febd8b7b0c6b9",
    }
    assert "sha256:1b9c99ad52dc29f2df7645ae4c3dbedce20ff0c9da942e8e468709e9e35845e3" not in canonical_guards
    assert "sha256:971c88b8e2aed7273cfcf0115dd957717a0d176c8b4461dcd8259c0346b51a9b" not in canonical_guards


def test_fet_replacements_distinguish_fact_attribution_and_hypothesis() -> None:
    payload = _payload()
    replacements = {item["replacement_id"]: item for item in payload["shared_replacements"]}

    assert set(replacements) == {
        "replace-short-fet-biography-and-attribution",
        "qualify-whisper-biographical-background",
        "attribute-lazich-death-and-cycle",
        "correct-late-love-cycle-and-fet-death",
        "remove-truncated-footer-fragment",
    }
    rendered = "\n".join(str(item["new"]) for item in replacements.values())
    assert "датируется 1850 годом" in rendered
    assert "прямого авторского посвящения" in rendered
    assert "могло скрывать самоубийство" in rendered
    assert "другой поздний цикл 1882–1892 годов" in rendered
    assert "воспоминаниям секретаря Е. В. Кудрявцевой" in rendered
    assert "смерть наступила от сердечного приступа" not in rendered
    assert "Фет всю жизнь писал только ей" not in rendered
    assert "единственной героиней любовной лирики" not in rendered
    assert replacements["remove-truncated-footer-fragment"]["new"] == ""


def test_fet_decisions_have_primary_or_academic_sources_and_owner_stance() -> None:
    payload = _payload()
    sources = {item["source_id"]: item for item in payload["sources"]}

    assert {
        "rvb-fet-bukhshtab-biography",
        "rvb-fet-complete-edition",
        "voplit-fet-verb-free-chernyshevsky",
        "feb-fet-death-kudryavtseva",
        "feb-kle-fet-lazich-cycle",
    } <= set(sources)
    assert any("The Legendary Poet" in item["authority"] for item in sources.values())
    assert any("Research" in item["authority"] for item in sources.values())
    assert payload["editorial_profile"]["judgment_mode"] == "asymmetric_evidence_based"


def test_fet_dry_run_wrapper_is_read_only_and_uses_verified_source_apply() -> None:
    text = _WRAPPER.read_text(encoding="utf-8")

    assert "verify_vk_reviewed_correction_apply_bundle.py" in text
    assert "vk-reviewed-correction-p1-apply-*.zip" in text
    assert "vk-deferred-editorial-review-*.zip" in text
    assert "vk-reviewed-correction-p1-fet-dry-run-$Stamp" in text
    assert "--max-operations 2" in text
    assert "descriptions_to_update -ne 2" in text
    assert "-235216998_456239127" in text
    assert "-235216998_456239143" in text
    assert "remote_writes = 0" in text
    assert "--execute" not in text


def test_fet_wrapper_does_not_label_failed_build_as_ready() -> None:
    text = _WRAPPER.read_text(encoding="utf-8")

    assert "failed diagnostic" in text
    assert "СОЗДАН ДИАГНОСТИЧЕСКИЙ ZIP; DRY-RUN НЕ ПОСТРОЕН" in text
    assert "Подробности сохранены в 00-build.txt" in text
    assert "$RunStatus -eq \"completed\" -and (Test-Path" in text
    assert "Start-Safely" in text
    assert "artifact_kind = $ArtifactKind" in text


def test_fet_builder_explains_raw_vs_canonical_guard_mismatch() -> None:
    text = _BUILDER.read_text(encoding="utf-8")

    assert "VK_DESCRIPTION_GUARD_HASH_ALGORITHM" in text
    assert "video-manager.text-sha256-v1" in text
    assert "raw_text_sha256" in text
    assert "actual_description_sha" in text


def test_fet_verifier_locks_sources_scope_and_forbidden_claims() -> None:
    text = _VERIFIER.read_text(encoding="utf-8")

    assert "verified_dry_run" in text
    assert "source-apply-verification.json" in text
    assert "Nested source review bundle SHA-256 mismatch" in text
    assert "Plan self-digest mismatch" in text
    assert "Fet correction target IDs differ from the reviewed set" in text
    assert "Invalid corrected description length" in text
    assert "прямого авторского посвящения" in text
    assert "другой поздний цикл 1882–1892 годов" in text
    assert "Фет всю жизнь писал только ей" in text
    assert "смерть наступила от сердечного приступа" in text
    assert "No VK mutation method was called" in text
    assert "video.edit" not in text
