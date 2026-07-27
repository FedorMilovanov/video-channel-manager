from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_DECISIONS = Path("content/policies/vk-reviewed-corrections-p1-blok-night-20260728.json")
_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionBlokWave.ps1")
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
        "трёх документированных версиях",
        "литературной интерпретацией",
        "разрешение для него было получено лишь 23 июля",
        "художественным и человеческим завещанием",
        "одно из самых узнаваемых и мрачных восьмистиший",
    ):
        assert required in rendered
    for forbidden in (
        "точный момент рождения стихотворения",
        "аптекой самоубийц",
        "всё прекрасное и духовное уничтожено",
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
