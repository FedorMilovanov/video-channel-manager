from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_historical_editorial import (
    HistoricalEditorialQueueV1,
    HistoricalSourceRegistry,
    TheologyProfile,
    load_historical_editorial_queue,
)
from video_channel_manager.telegram_historical_workflow import (
    HistoricalCycleScaffoldV1,
    build_cycle_scaffold,
    next_cadence_dates,
    preflight_historical_bundle,
    write_scaffold,
)


def _source(index: int) -> dict[str, object]:
    if index == 1:
        return {
            "source_id": "src-primary-archive",
            "title": "Primary archive record",
            "publisher": "University Archives",
            "url": "https://archive.example.edu/primary",
            "evidence_type": "primary",
            "grade": "A",
            "evidence_role": "university_archive",
            "checked_on": "2026-09-07",
            "topic_tags": ["fixture", "history"],
            "independence_group": "archive-primary",
        }
    if index == 2:
        return {
            "source_id": "src-peer-review",
            "title": "Independent peer-reviewed study",
            "publisher": "University Press",
            "url": "https://journals.example.edu/article",
            "evidence_type": "scholarly",
            "grade": "B+",
            "evidence_role": "peer_reviewed",
            "checked_on": "2026-09-07",
            "topic_tags": ["fixture", "history"],
            "independence_group": "peer-review-study",
        }
    return {
        "source_id": f"src-corpus-{index:02d}",
        "title": f"Historical corpus source {index}",
        "publisher": f"Academic Publisher {index}",
        "url": f"https://sources.example.edu/item/{index}",
        "evidence_type": "scholarly",
        "grade": "B+",
        "evidence_role": "academic_monograph",
        "checked_on": "2026-09-07",
        "topic_tags": ["fixture", f"topic-{index % 9}"],
        "independence_group": f"academic-group-{index}",
    }


def _registry_payload() -> dict[str, object]:
    return {
        "schema_name": "video-channel-manager.telegram-historical-source-registry",
        "schema_version": 1,
        "checked_on": "2026-09-07",
        "sources": [_source(index) for index in range(1, 51)],
    }


def _theology_payload() -> dict[str, object]:
    return {
        "schema_name": "video-channel-manager.telegram-historical-theology-profile",
        "schema_version": 1,
        "profile_id": "lordchrist-historical-editorial-v1",
        "source_repository": "FedorMilovanov/gb-is-my-strength",
        "source_path": "about/index.html",
        "source_commit": "69c0520bcac095576399cbb9e926f9f1280c7665",
        "checked_on": "2026-09-07",
        "commitments": [
            "Богодухновенность Писания",
            "Достаточность Писания",
            "Спасение благодатью через веру во Христа",
            "Грамматико-историческая герменевтика",
            "Последовательно буквальное толкование",
            "Премилленаризм",
        ],
    }


def _claim(
    claim_id: str,
    *,
    voice: str = "historical_fact",
    side: str = "none",
    proximity: str = "not_applicable",
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "claim_text": "Проверяемое историческое утверждение связано с двумя независимыми источниками высокого качества.",
        "claim_kind": "historical",
        "certainty": "exact",
        "voice": voice,
        "source_ids": ["src-primary-archive", "src-peer-review"],
        "direct_quote": False,
        "testimony_proximity": proximity,
        "controversy_side": side,
    }


def _post(sequence: int) -> dict[str, object]:
    topic_kind = "historical_fact"
    opposing_primary_bound = False
    no_opposing_primary_note = None
    claims = [
        _claim(f"claim-post-{sequence}-a"),
        _claim(f"claim-post-{sequence}-b"),
        {
            "claim_id": f"claim-post-{sequence}-eval",
            "claim_text": "Редакционная богословская оценка вынесена из исторического описания и явно обозначена как оценка.",
            "claim_kind": "interpretation",
            "certainty": "interpretation",
            "voice": "editorial_evaluation",
            "source_ids": ["src-peer-review"],
            "direct_quote": False,
            "testimony_proximity": "not_applicable",
            "controversy_side": "none",
        },
    ]
    if sequence == 1:
        topic_kind = "controversy"
        claims[0] = _claim("claim-post-1-side-a", voice="participant_position", side="side_a")
        claims[1] = _claim("claim-post-1-synthesis", side="synthesis")
        no_opposing_primary_note = (
            "В этом цикле отдельный первичный документ противоположной стороны пока не связан; "
            "ограничение явно раскрыто."
        )
    if sequence == 8:
        topic_kind = "martyrdom"
        claims[0] = _claim("claim-post-8-contemporary", proximity="contemporary")

    return {
        "sequence": sequence,
        "publication_id": f"lordchrist-history-fixture-post-{sequence}",
        "topic_kind": topic_kind,
        "title": f"Исторический материал номер {sequence}",
        "lead": (
            "Этот проверочный материал моделирует содержательную историческую публикацию, в которой факты, "
            "границы уверенности и богословская оценка разведены явно."
        ),
        "sections": [
            {
                "section_id": "context",
                "heading": "Исторический контекст",
                "paragraphs": [
                    "Содержательный абзац исторического контекста с ясной редакционной структурой и без "
                    "внутреннего машинного языка."
                ],
            },
            {
                "section_id": "meaning",
                "heading": "Почему это важно",
                "paragraphs": [
                    "Второй содержательный абзац связывает исторический материал с читательским выводом, не "
                    "подменяя документированные факты богословской оценкой."
                ],
            },
        ],
        "evidence_boundary": (
            "Источники подтверждают перечисленные факты; интерпретационные выводы редакции вынесены отдельно "
            "и не выдаются за содержание первичных документов."
        ),
        "claims": claims,
        "theology_review": {
            "historical_description": (
                "Историческое описание ограничено тем, что можно подтвердить источниками и академической "
                "реконструкцией."
            ),
            "participant_position": (
                "Позиция исторического участника передана отдельно от редакционного согласия или несогласия."
            ),
            "editorial_evaluation": (
                "Редакция оценивает материал через достаточность Писания и ясное различение исторического "
                "свидетельства и богословского вывода."
            ),
            "scripture_refs": ["2 Тим 3:16–17", "Еф 2:8–9"],
            "alignment": "mixed",
            "description_separated_from_evaluation": True,
            "review_status": "accepted",
        },
        "images": [],
        "release_offset_days": [0, 2, 5, 7, 9, 12, 14, 16, 19][sequence - 1],
        "opposing_primary_bound": opposing_primary_bound,
        "no_opposing_primary_note": no_opposing_primary_note,
        "editorial_status": "ready",
        "fact_check_status": "accepted",
        "rights_status": "reviewed",
    }


def _write_bundle(tmp_path: Path) -> Path:
    registry_payload = _registry_payload()
    registry = HistoricalSourceRegistry.model_validate(registry_payload)
    theology = TheologyProfile.model_validate(_theology_payload())

    data_dir = tmp_path / "content" / "telegram" / "lordchrist" / "historical-editorial" / "v1"
    data_dir.mkdir(parents=True)
    registry_rel = "content/telegram/lordchrist/historical-editorial/v1/source-registry.json"
    theology_rel = "content/telegram/lordchrist/historical-editorial/v1/theology-profile.json"
    queue_rel = "content/telegram/lordchrist/historical-editorial/v1/cycle-fixture.json"
    (tmp_path / registry_rel).write_text(
        json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (tmp_path / theology_rel).write_text(
        json.dumps(_theology_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    queue_payload = {
        "schema_name": "video-channel-manager.telegram-historical-editorial-queue",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "series_id": "series-history-fixture-cycle",
        "purpose": "evidence_backed_historical_edification",
        "state": "provider_inert",
        "verification": {
            "reviewed_urls": 50,
            "checked_on": "2026-09-07",
            "method": "a_bplus_primary_archive_scholarly_crosscheck",
            "production_threshold": "A_or_B_plus_only",
            "editorial_language": "ru",
            "anti_ranking": True,
        },
        "schedule": {
            "state": "staged",
            "provider_writes_authorized": False,
            "activation_policy": "manual_after_verified_historical_rich_canary",
            "timezone": "Europe/Moscow",
            "local_time": "19:17",
            "iso_weekdays": [1, 3, 6],
            "posts_per_week": 3,
            "max_verified_per_day": 2,
            "backfill_policy": "none",
        },
        "source_binding_kind": "registry",
        "source_binding_path": registry_rel,
        "source_binding_sha256": registry.digest,
        "source_registry_sha256": registry.digest,
        "theology_profile_path": theology_rel,
        "theology_profile_sha256": theology.digest,
        "posts": [_post(index) for index in range(1, 10)],
    }
    HistoricalEditorialQueueV1.model_validate(queue_payload)
    queue_path = tmp_path / queue_rel
    queue_path.write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return queue_path


def _registry_scaffold(
    registry: HistoricalSourceRegistry,
    theology: TheologyProfile,
    cycle_id: str,
) -> HistoricalCycleScaffoldV1:
    return build_cycle_scaffold(
        cycle_id=cycle_id,
        start_on=date(2026, 10, 1),
        source_binding_kind="registry",
        source_binding_path="content/telegram/lordchrist/historical-editorial/v1/source-registry.json",
        source_binding_sha256=registry.digest,
        source_registry_sha256=registry.digest,
        theology_profile_path="content/telegram/lordchrist/historical-editorial/v1/theology-profile.json",
        theology_profile_sha256=theology.digest,
    )


def test_next_cadence_dates_are_deterministic_monday_wednesday_saturday() -> None:
    assert next_cadence_dates(date(2026, 9, 7), count=9) == tuple(
        date(2026, 9, day) for day in (7, 9, 12, 14, 16, 19, 21, 23, 26)
    )


def test_scaffold_can_start_between_slots_without_backfill() -> None:
    dates = next_cadence_dates(date(2026, 9, 8), count=3)
    assert dates == (date(2026, 9, 9), date(2026, 9, 12), date(2026, 9, 14))


def test_scaffold_is_provider_inert_and_digest_stable() -> None:
    registry = HistoricalSourceRegistry.model_validate(_registry_payload())
    theology = TheologyProfile.model_validate(_theology_payload())
    scaffold = _registry_scaffold(registry, theology, "history-cycle-2026-10-a")

    assert scaffold.state == "draft_scaffold"
    assert scaffold.provider_writes_authorized is False
    assert scaffold.local_time == "19:17"
    assert scaffold.source_binding_kind == "registry"
    assert scaffold.source_binding_sha256 == registry.digest
    assert scaffold.source_registry_sha256 == registry.digest
    assert scaffold.digest == HistoricalCycleScaffoldV1.model_validate(scaffold.model_dump()).digest


def test_scaffold_preserves_distinct_catalog_and_registry_digests() -> None:
    registry = HistoricalSourceRegistry.model_validate(_registry_payload())
    theology = TheologyProfile.model_validate(_theology_payload())
    catalog_sha = "sha256:" + "1" * 64
    scaffold = build_cycle_scaffold(
        cycle_id="history-cycle-2026-10-catalog",
        start_on=date(2026, 10, 1),
        source_binding_kind="catalog",
        source_binding_path="content/telegram/lordchrist/historical-editorial/v1/source-catalog.json",
        source_binding_sha256=catalog_sha,
        source_registry_sha256=registry.digest,
        theology_profile_path="content/telegram/lordchrist/historical-editorial/v1/theology-profile.json",
        theology_profile_sha256=theology.digest,
    )

    assert scaffold.source_binding_sha256 == catalog_sha
    assert scaffold.source_registry_sha256 == registry.digest
    assert scaffold.source_binding_sha256 != scaffold.source_registry_sha256


def test_scaffold_writer_refuses_overwrite(tmp_path: Path) -> None:
    registry = HistoricalSourceRegistry.model_validate(_registry_payload())
    theology = TheologyProfile.model_validate(_theology_payload())
    scaffold = _registry_scaffold(registry, theology, "history-cycle-2026-10-b")
    target = tmp_path / "cycle.json"
    write_scaffold(target, scaffold)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_scaffold(target, scaffold)


def test_direct_queue_loader_uses_repo_root_and_verified_registry_binding(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    queue = load_historical_editorial_queue(queue_path, repo_root=tmp_path)

    assert queue.source_binding_kind == "registry"
    assert queue.live_eligible is False


def test_preflight_returns_machine_readable_proof_and_never_live_authorizes(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    report = preflight_historical_bundle(queue_path, repo_root=tmp_path)
    assert report.status == "PASS"
    assert report.source_count == 50
    assert report.grade_a_count == 1
    assert report.grade_bplus_count == 49
    assert report.claim_count == 27
    assert report.controversy_post_count == 1
    assert report.martyrdom_post_count == 1
    assert report.provider_writes_authorized is False
    assert report.live_eligible is False
    assert report.backfill_policy == "none"


def test_preflight_rejects_semantic_registry_digest_drift(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    raw["source_registry_sha256"] = "sha256:" + "0" * 64
    queue_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="source registry digest mismatch"):
        preflight_historical_bundle(queue_path, repo_root=tmp_path)


def test_preflight_rejects_registry_artifact_drift(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    registry_path = tmp_path / "content/telegram/lordchrist/historical-editorial/v1/source-registry.json"
    registry_raw = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_raw["sources"][2]["title"] = "Changed after sealing"
    registry_path.write_text(json.dumps(registry_raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="source binding digest mismatch"):
        preflight_historical_bundle(queue_path, repo_root=tmp_path)


def test_preflight_rejects_fake_independence(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    registry_path = tmp_path / "content/telegram/lordchrist/historical-editorial/v1/source-registry.json"
    registry_raw = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_raw["sources"][1]["independence_group"] = "archive-primary"
    changed_registry = HistoricalSourceRegistry.model_validate(registry_raw)
    registry_path.write_text(json.dumps(registry_raw, ensure_ascii=False), encoding="utf-8")

    queue_raw = json.loads(queue_path.read_text(encoding="utf-8"))
    queue_raw["source_binding_sha256"] = changed_registry.digest
    queue_raw["source_registry_sha256"] = changed_registry.digest
    queue_path.write_text(json.dumps(queue_raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="two independent evidence groups"):
        preflight_historical_bundle(queue_path, repo_root=tmp_path)


def test_direct_preflight_rejects_catalog_bound_queue(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    raw["source_binding_kind"] = "catalog"
    queue_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="require manifest preflight"):
        preflight_historical_bundle(queue_path, repo_root=tmp_path)


def test_registry_requires_fifty_sources() -> None:
    raw = _registry_payload()
    raw["sources"] = raw["sources"][:49]
    with pytest.raises(ValidationError):
        HistoricalSourceRegistry.model_validate(raw)


def test_scaffold_rejects_noncanonical_cadence() -> None:
    registry = HistoricalSourceRegistry.model_validate(_registry_payload())
    theology = TheologyProfile.model_validate(_theology_payload())
    raw = _registry_scaffold(registry, theology, "history-cycle-2026-10-c").model_dump(mode="json")
    raw["iso_weekdays"] = [1, 4, 6]
    with pytest.raises(ValidationError, match="Monday/Wednesday/Saturday"):
        HistoricalCycleScaffoldV1.model_validate(raw)


def test_preflight_rejects_repo_escape_path(tmp_path: Path) -> None:
    queue_path = _write_bundle(tmp_path)
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    raw["source_binding_path"] = "../outside.json"
    queue_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes repository root"):
        preflight_historical_bundle(queue_path, repo_root=tmp_path)
