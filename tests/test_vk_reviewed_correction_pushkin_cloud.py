from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_DECISIONS = Path("content/policies/vk-reviewed-corrections-p1-pushkin-cloud-20260728.json")
_WRAPPER = Path("scripts/Invoke-VkReviewedCorrectionPushkinCloudWave.ps1")
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


def test_pushkin_cloud_decision_locks_exact_one_video_scope() -> None:
    payload = _payload()
    decisions = payload["decisions"]

    assert payload["decision_set_id"] == "p1-pushkin-cloud-20260728"
    assert payload["description_guard_hash_algorithm"] == "video-manager.text-sha256-v1"
    assert _canonical_sha(payload) == "sha256:eaddbce693498a87cd888642642073bb0198c85087659543756ae61763e80a75"
    assert len(decisions) == 1
    assert decisions[0]["target_video_id"] == "-235216998_456239106"
    assert decisions[0]["expected_description_sha256"] == (
        "sha256:c06815c12dc652d793823bd1c65d7b34edbdfd1e614c0bc7bfaffca77a555eeb"
    )


def test_pushkin_cloud_replacements_correct_fact_and_qualify_interpretation() -> None:
    payload = _payload()
    replacements = {item["replacement_id"]: item for item in payload["shared_replacements"]}

    assert set(replacements) == {
        "remove-unsupported-personal-superlative",
        "qualify-cloud-psychological-autobiography",
        "correct-pushkin-1835-biography-and-context",
        "correct-duel-death-and-limit-prophecy",
        "attribute-interpretation-and-document-publication",
    }
    rendered = "\n".join(str(item["new"]) for item in replacements.values())
    for required in (
        "Пушкину было тридцать пять лет",
        "у Пушкиных было двое детей",
        "Григорий, родился 14 мая",
        "попытка выйти в отставку относится к лету 1834-го",
        "смертельно ранен на дуэли с Дантесом и умер 29 января",
        "Н. В. Измайлов позднее предполагал скрытый политический смысл",
        "18 июня 1835 года просил А. А. Краевского исправить",
        "литературная интерпретация, а не установленный биографический факт",
    ):
        assert required in rendered
    for forbidden in (
        "Пушкину тридцать шесть лет",
        "У него четверо детей",
        "Я здесь как в тюрьме",
        "Я не могу дышать в этом воздухе рабства",
        "Белинский назвал «Тучу»",
        "Набоков включил её",
        "27 января 1837 года, он погибнет",
    ):
        assert forbidden not in rendered


def test_pushkin_cloud_replacements_preserve_urls_and_hashtags() -> None:
    payload = _payload()

    for replacement in payload["shared_replacements"]:
        old = str(replacement["old"])
        new = str(replacement["new"])
        assert replacement["expected_count"] == 1
        assert _URL_RE.findall(old) == _URL_RE.findall(new)
        assert _HASHTAG_RE.findall(old) == _HASHTAG_RE.findall(new)


def test_pushkin_cloud_sources_are_academic_primary_and_owner_governance() -> None:
    payload = _payload()
    sources = {item["source_id"] for item in payload["sources"]}

    assert sources == {
        "rvb-pushkin-tucha-text",
        "feb-pushkin-tucha-comment",
        "bigenc-pushkin",
        "rvb-pushkin-diary-1834",
        "feb-pushkin-resignation-comment",
        "pushkinmuseum-grigory-birth",
        "pushkinmuseum-duel-death",
        "rvb-pushkin-kraevsky-letter",
        "feb-izmailov-pushkin-cycles",
        "site-project-charter",
        "site-editorial-judgment-policy",
        "research-knowledge-base",
    }
    assert payload["editorial_profile"]["judgment_mode"] == "asymmetric_evidence_based"


def test_pushkin_cloud_wrapper_is_read_only_and_uses_verified_blok_apply() -> None:
    text = _WRAPPER.read_text(encoding="utf-8")

    assert "verify_vk_reviewed_correction_blok_apply_bundle.py" in text
    assert "vk-reviewed-correction-p1-blok-apply-*.zip" in text
    assert "vk-reviewed-correction-p1-pushkin-cloud-dry-run-$Stamp" in text
    assert '"p1-pushkin-cloud-20260728"' in text
    assert '"-235216998_456239106"' in text
    assert "$ExpectedCount = 1" in text
    assert "$SourceExpectedCount = 2" in text
    assert "--max-operations $ExpectedCount" in text
    assert "remote_writes = 0" in text
    assert "--execute" not in text
    assert "СОЗДАН ДИАГНОСТИЧЕСКИЙ ZIP; DRY-RUN НЕ ПОСТРОЕН" in text
