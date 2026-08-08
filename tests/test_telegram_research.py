from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_research import ResearchQueueV2, load_research_queue, validate_public_copy

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"
REGISTRY = ROOT / "content/telegram/lordchrist/research-queues/historical-preaching-sources-v1.json"


def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_valid_staged_queue_is_not_live_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    queue = load_research_queue(FIXTURE)
    assert queue.schedule.state == "staged"
    assert queue.live_eligible is False
    assert [post.release_offset_days for post in queue.posts] == [0, 2, 4, 6, 8]
    assert queue.digest.startswith("sha256:")


def test_all_five_bodies_are_hash_bound_and_telegram_sized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    queue = load_research_queue(FIXTURE)
    for post in queue.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        assert 600 <= len(body) <= 4096


def test_unknown_claim_source_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    raw = deepcopy(payload())
    raw["posts"][0]["claims"][0]["source_ids"] = ["src-does-not-exist"]
    temp = ROOT / "content/telegram/lordchrist/research-queues/_invalid-test.json"
    temp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="unknown sources"):
            load_research_queue(temp)
    finally:
        temp.unlink(missing_ok=True)


def test_numeric_claim_requires_measurement_scope() -> None:
    raw = deepcopy(payload())
    del raw["posts"][4]["claims"][3]["measurement_scope"]
    with pytest.raises(ValidationError, match="numeric claims require measurement_scope"):
        ResearchQueueV2.model_validate(raw)


def test_calvin_headline_number_cannot_be_upgraded_to_exact() -> None:
    raw = deepcopy(payload())
    raw["posts"][0]["claims"][0]["certainty"] = "exact"
    with pytest.raises(ValidationError, match="Calvin 4–5k must remain an estimate"):
        ResearchQueueV2.model_validate(raw)


def test_spurgeon_3563_cannot_lose_published_scope() -> None:
    raw = deepcopy(payload())
    raw["posts"][0]["claims"][3]["measurement_scope"] = "все произнесённые проповеди"
    with pytest.raises(ValidationError, match="Spurgeon 3,563 must remain an exact published-corpus count"):
        ResearchQueueV2.model_validate(raw)


def test_macarthur_3600_cannot_become_exact_lifetime_total() -> None:
    raw = deepcopy(payload())
    raw["posts"][0]["claims"][5]["certainty"] = "exact"
    with pytest.raises(ValidationError, match=r"MacArthur 3,600\+ must remain a lower-bound archive count"):
        ResearchQueueV2.model_validate(raw)


def test_macarthur_3600_uses_exact_current_gty_archive_source() -> None:
    raw = payload()
    claim = raw["posts"][0]["claims"][5]
    assert claim["claim_id"] == "claim-macarthur-3600"
    assert claim["source_ids"] == ["src-gty-sermon-archive-3600"]

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["source_id"] == "src-gty-sermon-archive-3600")
    assert source["publisher"] == "Grace to You"
    assert source["url"] == "https://www.gty.org/sermons/series/355/john-macarthurs-most-memorable-sermon"
    assert source["checked_on"] == "2026-08-08"


def test_fact_check_date_covers_bound_source_registry_check() -> None:
    raw = payload()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert raw["verification"]["checked_on"] >= registry["checked_on"]


def test_staged_queue_cannot_claim_canary_evidence() -> None:
    raw = deepcopy(payload())
    raw["schedule"]["canary_message_id"] = 1471
    with pytest.raises(ValidationError, match="staged research schedule cannot claim canary"):
        ResearchQueueV2.model_validate(raw)


def test_armed_queue_requires_complete_canary_evidence() -> None:
    raw = deepcopy(payload())
    raw["schedule"]["state"] = "armed"
    with pytest.raises(ValidationError, match="armed research schedule requires"):
        ResearchQueueV2.model_validate(raw)


def test_public_copy_rejects_internal_machine_language_and_markdown() -> None:
    with pytest.raises(ValueError, match="internal editorial or machine language"):
        validate_public_copy(("Нормальный текст. " * 60) + " Fact-check anchors: internal")
    with pytest.raises(ValueError, match="without Markdown"):
        validate_public_copy(("Нормальный текст. " * 60) + " **машинная разметка**")


def test_source_registry_digest_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    raw = deepcopy(payload())
    raw["source_registry_sha256"] = "sha256:" + "0" * 64
    temp = ROOT / "content/telegram/lordchrist/research-queues/_invalid-test.json"
    temp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="source registry digest mismatch"):
            load_research_queue(temp)
    finally:
        temp.unlink(missing_ok=True)
