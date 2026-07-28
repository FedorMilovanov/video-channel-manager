from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_DECISIONS = Path("content/policies/vk-reviewed-corrections-p1-blok-night-20260728.json")
_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionBlokWave.ps1")
_DRY_VERIFIER = Path("scripts/verify_vk_reviewed_correction_blok_dry_run.py")
_APPLY_VERIFIER = Path("scripts/verify_vk_reviewed_correction_blok_apply_bundle.py")
_APPLY_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionBlokApply.ps1")
_URL_RE = re.compile(r"https?://[^\s]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё]+")


def _payload() -> dict[str, Any]:
    payload = json.loads(_DECISIONS.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _canonical_sha(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def test_blok_decisions_lock_exact_two_video_scope() -> None:
    payload = _payload()
    decisions = payload["decisions"]

    assert payload["decision_set_id"] == "p1-blok-night-20260728"
    assert payload["description_guard_hash_algorithm"] == "video-manager.text-sha256-v1"
    assert _canonical_sha(payload) == "sha256:3b8e3f661d317a03483e568b90ef361de8bc325abe19d9d049076dd24b7f103e"
    assert {item["target_video_id"] for item in decisions} == {
        "-235216998_456239120",
        "-235216998_456239126",
    }
    assert {item["expected_description_sha256"] for item in decisions} == {
        "sha256:252ec08971ddaa0b2fbffee2fc428cdd0641879abd10dc09bf7c44504eae15f1",
        "sha256:dd321580877a2be9dec0109e2f875204973c2471e9790d9d4d8c145ffe82e9b0",
    }


def test_blok_replacements_distinguish_fact_source_and_interpretation() -> None:
    payload = _payload()
    replacements = {item["replacement_id"]: item for item in payload["shared_replacements"]}

    assert set(replacements) == {
        "correct-gippius-memory-and-limit-inference",
        "attribute-competing-pharmacy-prototypes",
        "separate-cycle-fact-from-interpretation",
        "correct-blok-final-illness-and-exit-timeline",
        "remove-unsupported-silver-age-superlative",
    }
    rendered = "\n".join(str(item["new"]) for item in replacements.values())
    for required in (
        "датированным 10 октября",
        "Около каждого дома есть аптека",
        "спор о прототипе продолжается",
        "нескольких документированных версиях",
        "литературной интерпретацией",
        "разрешение для него было получено лишь 23 июля",
        "художественным и человеческим завещанием",
        "одно из самых узнаваемых и мрачных восьмистиший",
    ):
        assert required in rendered
    for forbidden in (
        "точный момент рождения стихотворения",
        "аптекой самоубийц",
        "В «Страшном мире» всё прекрасное и духовное уничтожено:",
        "почти не приходил в сознание",
        "самое безысходное стихотворение Серебряного века",
    ):
        assert forbidden not in rendered


def test_blok_replacements_preserve_urls_and_hashtags() -> None:
    payload = _payload()

    for replacement in payload["shared_replacements"]:
        old = str(replacement["old"])
        new = str(replacement["new"])
        assert replacement["expected_count"] == 1
        assert _URL_RE.findall(old) == _URL_RE.findall(new)
        assert _HASHTAG_RE.findall(old) == _HASHTAG_RE.findall(new)


def test_blok_decisions_have_primary_academic_and_owner_sources() -> None:
    payload = _payload()
    sources = {item["source_id"]: item for item in payload["sources"]}

    assert {
        "rvb-blok-complete-edition",
        "feb-gippius-meetings",
        "culture-blok-pharmacy-exhibition",
        "likhachev-blok-pharmacy-commentary",
        "russian-thought-first-publication",
        "culture-blok-biography",
        "bigenc-blok",
        "site-project-charter",
        "site-editorial-judgment-policy",
        "research-knowledge-base",
    } == set(sources)
    assert payload["editorial_profile"]["judgment_mode"] == "asymmetric_evidence_based"


def test_blok_dry_run_wrapper_is_read_only_and_uses_verified_fet_apply() -> None:
    text = _WRAPPER.read_text(encoding="utf-8")

    assert "verify_vk_reviewed_correction_fet_apply_bundle.py" in text
    assert "vk-reviewed-correction-p1-fet-apply-*.zip" in text
    assert "vk-reviewed-correction-p1-blok-dry-run-$Stamp" in text
    assert '"p1-blok-night-20260728"' in text
    assert '"-235216998_456239120"' in text
    assert '"-235216998_456239126"' in text
    assert "$ExpectedCount = 2" in text
    assert "--max-operations $ExpectedCount" in text
    assert "remote_writes = 0" in text
    assert "--execute" not in text
    assert "СОЗДАН ДИАГНОСТИЧЕСКИЙ ZIP; DRY-RUN НЕ ПОСТРОЕН" in text


def test_blok_exact_dry_run_verifier_pins_reviewed_contents() -> None:
    text = _DRY_VERIFIER.read_text(encoding="utf-8")

    for required in (
        "sha256:53bed1c056868731dcb1f9c04b8d3188fd4295baa5d14364b1f8b72187cea4fb",
        "sha256:3b8e3f661d317a03483e568b90ef361de8bc325abe19d9d049076dd24b7f103e",
        "sha256:ac95b72a59b03e7fc8ef07ecf906fbb05ef3534e7ad0757d2c65db60b893f407",
        "sha256:753e2bc4f2bb41e37ce9285b4f6cd02a0013a9a0296f4a36dba63d97ee94cf27",
        "exact_independently_reviewed_contents",
        "reviewed_replacements_reconstructed",
        "urls_and_hashtags_unchanged",
        "exact_member_hashes_verified",
    ):
        assert required in text
    assert '"-235216998_456239120"' in text
    assert '"-235216998_456239126"' in text
    assert "Bundle contains duplicate ZIP entries" in text
    assert "No VK mutation method was called" in text


def test_blok_apply_wrapper_executes_only_verified_plan() -> None:
    text = _APPLY_WRAPPER.read_text(encoding="utf-8")

    assert "[switch]$Execute" in text
    assert "if (-not $Execute)" in text
    assert "verify_vk_reviewed_correction_blok_dry_run.py" in text
    assert "verify_vk_reviewed_correction_blok_apply_bundle.py" in text
    assert "vk-reviewed-correction-p1-blok-dry-run-*.zip" in text
    assert "$ExpectedCount = 2" in text
    assert '"p1-blok-night-20260728"' in text
    assert "--confirm-plan-sha256" in text
    assert "--confirm-video-coverage" in text
    assert "--confirm-memberships" in text
    assert "--max-operations $ExpectedCount" in text
    assert "--result-output" in text
    assert "build_vk_reviewed_correction_wave.py" not in text


def test_blok_apply_verifier_locks_postflight_scope() -> None:
    text = _APPLY_VERIFIER.read_text(encoding="utf-8")

    assert "verify_vk_reviewed_correction_blok_dry_run" in text
    assert "sha256:53bed1c056868731dcb1f9c04b8d3188fd4295baa5d14364b1f8b72187cea4fb" in text
    assert "sha256:3b8e3f661d317a03483e568b90ef361de8bc325abe19d9d049076dd24b7f103e" in text
    assert '"-235216998_456239120"' in text
    assert '"-235216998_456239126"' in text
    assert '"non_target_videos_verified_unchanged": 109' in text
    assert "VK album memberships changed during Blok correction" in text
    assert "05-independent-verification.json" in text
