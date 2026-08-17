from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile as anomaly_module
import video_channel_manager.platforms.vk.milovi_issue323_continue as continue_module
import video_channel_manager.platforms.vk.milovi_issue323_status_probe as status_module
from video_channel_manager.platforms.vk.milovi_issue323_continue import run_issue_323_continue_preview
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    initialize_promotion_journal,
    preflight_with_promotion_journal,
    record_promotion_dispatch_started,
    record_promotion_edit_intent,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionFieldObservation,
    PromotionObservationBatch,
    PromotionObservationEvidence,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionPolicy,
    PromotionSpec,
    ReviewedPromotionField,
    promotion_text_sha256,
)
from video_channel_manager.platforms.vk.milovi_promotion import public_clip_description
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SourceAsset,
    build_description,
    build_wall_message,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallPostFingerprint,
    VkWallSurface,
    build_wall_snapshot,
)

OWNER_ID = -68859909
COMMUNITY_ID = 68859909
NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
NOW_EPOCH = int(NOW.timestamp())
CORPUS_PATH = Path(__file__).parent / "fixtures" / "milovi_issue323_historical_stop_corpus.json"

EXPECTED_CASE_IDS = (
    "source1_exact_legacy_copy",
    "provider_added_non_video_wall_projection",
    "aggregate_omission_exact_old_live",
    "tombstoned_old_id_unique_successor",
    "ambiguous_published_successor",
    "future_missing_wall_before_slot",
    "upload_created_immediate_wall_side_effect",
    "verified_clip_processing_projection_no_reupload",
    "manual_clip_copy_drift_blocks_creation",
    "multiple_video_wall_projection_blocks",
    "dispatch_started_before_visible_after_no_replay",
    "dispatch_unknown_exact_after_reconciles_without_replay",
    "processing_projection_never_grants_edit_authority",
    "wall475_tombstone_after_possible_delete_no_second_delete",
)


def _load_corpus() -> list[dict[str, str]]:
    raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert raw["schema_name"] == "video-manager.milovi-issue-323-historical-stop-corpus"
    assert raw["schema_version"] == 1
    assert raw["issue"] == 375
    assert raw["provider_writes_authorized"] is False
    cases = raw["cases"]
    assert isinstance(cases, list)
    return cases


CORPUS = _load_corpus()


def _clip_id(source_id: str) -> int:
    return 456239200 + ROLL_OUT_IDS.index(source_id)


def _wall_id(source_id: str) -> int:
    return 500 + ROLL_OUT_IDS.index(source_id)


def _clip_remote_id(source_id: str) -> str:
    return f"{OWNER_ID}_{_clip_id(source_id)}"


def _wall_remote_id(source_id: str) -> str:
    return f"{OWNER_ID}_{_wall_id(source_id)}"


def _assets() -> list[SourceAsset]:
    result: list[SourceAsset] = []
    for index, source_id in enumerate(ROLL_OUT_IDS, start=1):
        title = f"Milovi source {index}"
        result.append(
            SourceAsset(
                source_id=source_id,
                source_url=f"https://www.youtube.com/shorts/{source_id}",
                title=title,
                duration_seconds=30,
                media_path=f"Z:/historical-fixture/{source_id}.mp4",
                media_sha256="0" * 64,
                width=1080,
                height=1920,
                description=build_description(title, source_id),
                wall_message=build_wall_message(title, source_id),
            )
        )
    return result


def _slots() -> dict[str, datetime]:
    start = NOW - timedelta(days=20)
    return {source_id: start + timedelta(hours=index) for index, source_id in enumerate(ROLL_OUT_IDS)}


def _wall_post(
    source_id: str,
    *,
    publish_date: int,
    text: str,
    post_id: int | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "owner_id": OWNER_ID,
        "id": _wall_id(source_id) if post_id is None else post_id,
        "date": publish_date,
        "text": text,
        "attachments": attachments
        if attachments is not None
        else [
            {
                "type": "video",
                "video": {
                    "owner_id": OWNER_ID,
                    "id": _clip_id(source_id),
                    "type": "short_video",
                },
            }
        ],
    }


class _FakeVkDelegate:
    def __init__(
        self,
        *,
        videos: dict[str, dict[str, Any]],
        published: list[dict[str, Any]],
        postponed: list[dict[str, Any]] | None = None,
        exact_posts: dict[int, dict[str, Any] | None] | None = None,
    ) -> None:
        self.videos = videos
        self.published = published
        self.postponed = postponed or []
        self.exact_posts = exact_posts or {}
        self.read_video_calls: list[str] = []
        self.read_post_calls: list[int] = []

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int):
        assert community_id == COMMUNITY_ID
        assert max_posts_per_surface == 10000
        return build_wall_snapshot(
            community_id=community_id,
            published_items=self.published,
            postponed_items=self.postponed,
            published_pages=1,
            postponed_pages=1,
            complete=True,
            captured_at=NOW,
        )

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        remote_id = f"{owner_id}_{video_id}"
        self.read_video_calls.append(remote_id)
        raw = self.videos.get(remote_id)
        return dict(raw) if raw is not None else None

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == COMMUNITY_ID
        self.read_post_calls.append(post_id)
        if post_id in self.exact_posts:
            raw = self.exact_posts[post_id]
            return dict(raw) if raw is not None else None
        for raw in [*self.published, *self.postponed]:
            if raw.get("id") == post_id:
                return dict(raw)
        return None


@dataclass
class _StatusScenario:
    journal: dict[str, Any]
    slots: dict[str, datetime]
    provider: _FakeVkDelegate
    target_source_id: str
    expected_status: str
    expected_action: str
    expected_resolution_mode: str | None = None
    expected_current_wall_remote_id: str | None = None
    expected_stop_contains: str | None = None
    expected_clip_copy_state: str | None = None
    exact_post_must_not_be_read: int | None = None


def _base_status_state() -> tuple[list[SourceAsset], dict[str, datetime], dict[str, Any], _FakeVkDelegate]:
    assets = _assets()
    slots = _slots()
    journal: dict[str, Any] = {"items": {}}
    videos: dict[str, dict[str, Any]] = {}
    published: list[dict[str, Any]] = []

    for asset in assets:
        source_id = asset.source_id
        publish_date = int(slots[source_id].timestamp())
        journal["items"][source_id] = {
            "status": "wall_verified",
            "clip_remote_id": _clip_remote_id(source_id),
            "wall_remote_id": _wall_remote_id(source_id),
            "publish_date": publish_date,
        }
        videos[_clip_remote_id(source_id)] = {
            "owner_id": OWNER_ID,
            "id": _clip_id(source_id),
            "type": "short_video",
            "description": asset.description,
        }
        published.append(
            _wall_post(
                source_id,
                publish_date=publish_date,
                text=asset.wall_message,
            )
        )

    return assets, slots, journal, _FakeVkDelegate(videos=videos, published=published)


def _remove_published_post(provider: _FakeVkDelegate, post_id: int) -> dict[str, Any]:
    raw = next(post for post in provider.published if post["id"] == post_id)
    provider.published = [post for post in provider.published if post["id"] != post_id]
    return raw


def _build_status_scenario(case_id: str) -> tuple[list[SourceAsset], _StatusScenario]:
    assets, slots, journal, provider = _base_status_state()
    target = ROLL_OUT_IDS[0]
    item = journal["items"][target]
    target_asset = assets[0]

    scenario = _StatusScenario(
        journal=journal,
        slots=slots,
        provider=provider,
        target_source_id=target,
        expected_status="verified_read_only",
        expected_action="phase_a_complete_promotion_pending",
        expected_resolution_mode="journaled_id",
        expected_current_wall_remote_id=_wall_remote_id(target),
        expected_clip_copy_state="legacy",
    )

    if case_id == "source1_exact_legacy_copy":
        return assets, scenario

    if case_id == "provider_added_non_video_wall_projection":
        raw = next(post for post in provider.published if post["id"] == _wall_id(target))
        raw["attachments"].append(
            {
                "type": "link",
                "link": {
                    "url": "https://milovicake.ru/",
                    "title": "provider projection",
                },
            }
        )
        return assets, scenario

    if case_id == "aggregate_omission_exact_old_live":
        old = _remove_published_post(provider, _wall_id(target))
        provider.exact_posts[_wall_id(target)] = old
        scenario.expected_resolution_mode = "exact_old_id"
        return assets, scenario

    if case_id in {"tombstoned_old_id_unique_successor", "ambiguous_published_successor"}:
        old = _remove_published_post(provider, _wall_id(target))
        provider.exact_posts[_wall_id(target)] = {
            "owner_id": OWNER_ID,
            "id": _wall_id(target),
            "date": old["date"],
            "is_deleted": True,
        }
        provider.published.append(
            _wall_post(
                target,
                publish_date=old["date"],
                text=target_asset.wall_message,
                post_id=900,
            )
        )
        if case_id == "ambiguous_published_successor":
            provider.published.append(
                _wall_post(
                    target,
                    publish_date=old["date"],
                    text=target_asset.wall_message,
                    post_id=901,
                )
            )
            scenario.expected_status = "blocked"
            scenario.expected_action = "stop_conflict"
            scenario.expected_resolution_mode = None
            scenario.expected_current_wall_remote_id = None
            scenario.expected_stop_contains = "successor is ambiguous"
        else:
            scenario.expected_resolution_mode = "published_successor"
            scenario.expected_current_wall_remote_id = f"{OWNER_ID}_900"
        return assets, scenario

    if case_id == "future_missing_wall_before_slot":
        _remove_published_post(provider, _wall_id(target))
        future_slot = NOW + timedelta(hours=1)
        slots[target] = future_slot
        item["publish_date"] = int(future_slot.timestamp())
        scenario.expected_status = "blocked"
        scenario.expected_action = "stop_conflict"
        scenario.expected_resolution_mode = None
        scenario.expected_current_wall_remote_id = None
        scenario.expected_stop_contains = "before its frozen slot"
        scenario.exact_post_must_not_be_read = _wall_id(target)
        return assets, scenario

    if case_id == "upload_created_immediate_wall_side_effect":
        item["status"] = "clip_verified"
        item.pop("wall_remote_id")
        scenario.expected_action = "reconcile_existing_wall_without_repost"
        scenario.expected_resolution_mode = "unjournaled_exact_mapping"
        return assets, scenario

    if case_id in {
        "verified_clip_processing_projection_no_reupload",
        "manual_clip_copy_drift_blocks_creation",
    }:
        target = ROLL_OUT_IDS[8]
        target_asset = assets[8]
        item = journal["items"][target]
        item.clear()
        item.update(
            {
                "status": "upload_in_progress",
                "upload_record": {
                    "stage": UploadStage.VERIFIED.value,
                    "reservation": {"remote_id": _clip_remote_id(target)},
                },
            }
        )
        _remove_published_post(provider, _wall_id(target))
        video = provider.videos[_clip_remote_id(target)]
        if case_id == "verified_clip_processing_projection_no_reupload":
            promoted = public_clip_description(target_asset.title).strip()
            assert len(promoted) > 140
            video.update(
                {
                    "processing": 1,
                    "converting": 1,
                    "title": None,
                    "player": None,
                    "description": promoted[:140].rstrip() + "..",
                }
            )
            return assets, _StatusScenario(
                journal=journal,
                slots=slots,
                provider=provider,
                target_source_id=target,
                expected_status="verified_read_only",
                expected_action="resume_from_verified_clip_without_reupload_then_wall",
                expected_clip_copy_state="provider_processing_promoted_projection",
            )

        video["description"] = "operator-edited third-state copy"
        return assets, _StatusScenario(
            journal=journal,
            slots=slots,
            provider=provider,
            target_source_id=target,
            expected_status="blocked",
            expected_action="stop_conflict",
            expected_stop_contains="observation-only",
            expected_clip_copy_state="unreviewed_exact",
        )

    if case_id == "multiple_video_wall_projection_blocks":
        raw = next(post for post in provider.published if post["id"] == _wall_id(target))
        raw["attachments"].append(
            {
                "type": "video",
                "video": {
                    "owner_id": OWNER_ID,
                    "id": 456239999,
                    "type": "short_video",
                },
            }
        )
        scenario.expected_status = "blocked"
        scenario.expected_action = "stop_conflict"
        scenario.expected_resolution_mode = None
        scenario.expected_current_wall_remote_id = None
        scenario.expected_stop_contains = "exactly one video attachment; observed 2"
        return assets, scenario

    raise AssertionError(f"Unknown status corpus case: {case_id}")


def _run_status_public_surface(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assets: list[SourceAsset],
    scenario: _StatusScenario,
) -> dict[str, Any]:
    journal_path = tmp_path / "rollout-journal.json"
    journal_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(status_module, "_load_journal", lambda _path: scenario.journal)
    monkeypatch.setattr(status_module, "_load_prepared_assets", lambda _path: assets)
    monkeypatch.setattr(status_module, "_load_schedule_read_only", lambda _path: scenario.slots)
    monkeypatch.setattr(
        status_module,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"),
    )
    monkeypatch.setattr(status_module, "VkTokenStore", lambda _data_dir: object())
    monkeypatch.setattr(status_module, "_resolve_account", lambda _store, _version: ("fixture", object()))
    monkeypatch.setattr(status_module, "VkWallWriter", lambda **_kwargs: scenario.provider)
    monkeypatch.setattr(status_module, "local_vk_write_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(status_module, "_prove_target", lambda _client: None)
    monkeypatch.setattr(status_module.time, "time", lambda: NOW_EPOCH)

    return status_module.run_issue_323_status_probe(
        output_path=tmp_path / "status.json",
        journal_path=journal_path,
        schedule_path=tmp_path / "schedule.json",
        prepared_manifest_path=tmp_path / "prepared.json",
    )


def _assert_status_case(result: dict[str, Any], scenario: _StatusScenario) -> None:
    row = next(item for item in result["items"] if item["source_id"] == scenario.target_source_id)
    assert result["provider_mutation_authorized"] is False
    assert result["journal_mutation_authorized"] is False
    assert result["status"] == scenario.expected_status
    assert row["safe_next_action"] == scenario.expected_action
    assert row["reupload_authorized_by_probe"] is False
    assert row["repost_authorized_by_probe"] is False

    if scenario.expected_resolution_mode is not None:
        assert row["wall_resolution_mode"] == scenario.expected_resolution_mode
    if scenario.expected_current_wall_remote_id is not None:
        assert row["current_wall_remote_id"] == scenario.expected_current_wall_remote_id
    if scenario.expected_clip_copy_state is not None:
        assert row["clip_copy_state"] == scenario.expected_clip_copy_state
    if scenario.expected_stop_contains is not None:
        assert scenario.expected_stop_contains in row["stop_reason"]
    if scenario.exact_post_must_not_be_read is not None:
        assert scenario.exact_post_must_not_be_read not in scenario.provider.read_post_calls

    if scenario.expected_action == "resume_from_verified_clip_without_reupload_then_wall":
        assert row["provider_effect_durable"] is True
        assert row["upload_stage"] == UploadStage.VERIFIED.value
        assert row["plan"]["forbids_reupload"] is True
        assert "create_clip" not in row["plan"]["required_capabilities"]

    if scenario.expected_action == "reconcile_existing_wall_without_repost":
        assert row["plan"]["forbids_reupload"] is True
        assert row["plan"]["forbids_repost"] is True


def _promotion_text(source_id: str, field: PromotionField) -> str:
    return f"reviewed current {source_id} {field.value}"


def _promotion_remote_id(source_id: str, field: PromotionField) -> str:
    index = ROLL_OUT_IDS.index(source_id)
    if field is PromotionField.CLIP_DESCRIPTION:
        return f"{OWNER_ID}_{456239200 + index}"
    return f"{OWNER_ID}_{500 + index}"


def _promotion_wall_incarnation(source_id: str, text: str) -> VkWallPostFingerprint:
    index = ROLL_OUT_IDS.index(source_id)
    return VkWallPostFingerprint(
        owner_id=OWNER_ID,
        post_id=500 + index,
        surface=VkWallSurface.PUBLISHED,
        publish_date=1_700_000_000 + index,
        text_sha256=promotion_text_sha256(text),
        attachments=(f"video{OWNER_ID}_{456239200 + index}",),
    )


def _promotion_observation(
    *,
    override: tuple[str, PromotionField, str, bool] | None = None,
    captured_at: str = "2026-08-16T10:00:00+00:00",
) -> PromotionObservationBatch:
    fields: list[PromotionFieldObservation] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            text = _promotion_text(source_id, field)
            processing_projection = False
            if override is not None and override[:2] == (source_id, field):
                text = override[2]
                processing_projection = override[3]
            fields.append(
                PromotionFieldObservation(
                    source_id=source_id,
                    field=field,
                    text=text,
                    sha256=promotion_text_sha256(text),
                    remote_id=_promotion_remote_id(source_id, field),
                    evidence=(
                        PromotionObservationEvidence.EXACT_CLIP_READ
                        if field is PromotionField.CLIP_DESCRIPTION
                        else PromotionObservationEvidence.EXACT_WALL_INCARNATION
                    ),
                    processing_projection=processing_projection,
                    wall_incarnation=(
                        None
                        if field is PromotionField.CLIP_DESCRIPTION
                        else _promotion_wall_incarnation(source_id, text)
                    ),
                )
            )
    return PromotionObservationBatch(
        source_snapshot_id="issue323-historical-corpus",
        wall_snapshot_sha256="sha256:historical-corpus-wall-snapshot",
        captured_at=captured_at,
        fields=tuple(fields),
    )


def _promotion_spec(key: tuple[str, PromotionField]) -> PromotionSpec:
    fields: list[ReviewedPromotionField] = []
    for source_id in ROLL_OUT_IDS:
        for field in PromotionField:
            before = _promotion_text(source_id, field)
            if (source_id, field) == key:
                after = f"reviewed target {source_id} {field.value}"
                fields.append(
                    ReviewedPromotionField(
                        source_id=source_id,
                        field=field,
                        policy=PromotionPolicy.MANAGED_EXACT,
                        before_text=before,
                        before_sha256=promotion_text_sha256(before),
                        after_text=after,
                        after_sha256=promotion_text_sha256(after),
                    )
                )
            else:
                fields.append(
                    ReviewedPromotionField(
                        source_id=source_id,
                        field=field,
                        policy=PromotionPolicy.ADOPT_REVIEWED_EXACT,
                        before_text=before,
                        before_sha256=promotion_text_sha256(before),
                    )
                )
    return PromotionSpec(review_id="historical-corpus-review", fields=tuple(fields))


def _status_payload(observation: PromotionObservationBatch) -> dict[str, Any]:
    raw = observation.as_dict()
    raw["observation_digest"] = observation.digest
    return {
        "status": "verified_read_only",
        "provider_mutation_authorized": False,
        "promotion_observation": raw,
    }


def _continue_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "output_path": tmp_path / "continue.json",
        "status_output_path": tmp_path / "status.json",
        "rollout_journal_path": tmp_path / "rollout.json",
        "schedule_path": tmp_path / "schedule.json",
        "prepared_manifest_path": tmp_path / "prepared.json",
        "promotion_spec_path": tmp_path / "promotion-spec.json",
        "promotion_journal_path": tmp_path / "promotion-journal.json",
    }


def _write_started_promotion(
    *,
    paths: dict[str, Path],
    key: tuple[str, PromotionField],
    baseline: PromotionObservationBatch,
    spec: PromotionSpec,
) -> None:
    paths["promotion_spec_path"].write_text(
        json.dumps(spec.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    journal = initialize_promotion_journal(
        spec=spec,
        observation=baseline,
        created_at="2026-08-16T10:05:00+00:00",
    )
    preflight = preflight_with_promotion_journal(spec=spec, observation=baseline, journal=journal)
    journal = record_promotion_edit_intent(
        journal=journal,
        preflight=preflight,
        source_id=key[0],
        field=key[1],
    )
    journal = record_promotion_dispatch_started(
        journal=journal,
        source_id=key[0],
        field=key[1],
        preflight_digest=preflight.digest,
    )
    paths["promotion_journal_path"].write_text(
        json.dumps(journal.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _provider_dispatch_must_not_run(**_kwargs: Any) -> None:
    raise AssertionError("historical replay attempted provider dispatch")


def _run_continuation_case(
    *,
    case_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = (ROLL_OUT_IDS[0], PromotionField.CLIP_DESCRIPTION)
    baseline = _promotion_observation()
    spec = _promotion_spec(key)
    paths = _continue_paths(tmp_path)
    _write_started_promotion(paths=paths, key=key, baseline=baseline, spec=spec)

    if case_id == "dispatch_started_before_visible_after_no_replay":
        fresh = _promotion_observation(captured_at="2026-08-16T10:01:00+00:00")
        expected_status = "dispatch_unknown_requires_reconciliation"
        expected_operation_status = "unknown_requires_reconciliation"
    elif case_id == "dispatch_unknown_exact_after_reconciles_without_replay":
        managed = next(item for item in spec.fields if (item.source_id, item.field) == key)
        assert managed.after_text is not None
        fresh = _promotion_observation(
            override=(key[0], key[1], managed.after_text, False),
            captured_at="2026-08-16T10:01:00+00:00",
        )
        expected_status = "dispatch_reconciled_verified_ready_for_next_plan"
        expected_operation_status = "verified"
    elif case_id == "processing_projection_never_grants_edit_authority":
        managed = next(item for item in spec.fields if (item.source_id, item.field) == key)
        assert managed.after_text is not None
        projected = (managed.after_text * 6)[:100].rstrip() + ".."
        fresh = _promotion_observation(
            override=(key[0], key[1], projected, True),
            captured_at="2026-08-16T10:01:00+00:00",
        )
        expected_status = "dispatch_unknown_requires_reconciliation"
        expected_operation_status = "unknown_requires_reconciliation"
    else:
        raise AssertionError(f"Unknown continuation corpus case: {case_id}")

    monkeypatch.setattr(
        continue_module,
        "run_issue_323_status_probe",
        lambda **_kwargs: _status_payload(fresh),
    )
    monkeypatch.setattr(continue_module, "_dispatch_existing_intent", _provider_dispatch_must_not_run)

    result = run_issue_323_continue_preview(**paths)

    assert result["continuation_status"] == expected_status
    assert result["provider_mutation_authorized"] is False
    assert result["provider_writes_executed"] == 0
    raw_journal = json.loads(paths["promotion_journal_path"].read_text(encoding="utf-8"))
    operation = next(
        item for item in raw_journal["operations"] if (item["source_id"], item["field"]) == (key[0], key[1].value)
    )
    assert operation["status"] == expected_operation_status
    assert operation["dispatch_started"] is True

    if case_id == "dispatch_started_before_visible_after_no_replay":
        assert result["promotion_dispatch_unknown"] is True
        assert "do not retry" in result["blockers"][0]
    if case_id == "processing_projection_never_grants_edit_authority":
        assert result["promotion_dispatch_unknown"] is True
        assert "processing projection" in result["blockers"][0]
    if case_id == "dispatch_unknown_exact_after_reconciles_without_replay":
        assert result["promotion_dispatch_reconciled"] is True


class _AnomalyReader:
    def __init__(self) -> None:
        self.read_post_calls = 0
        self.read_video_calls = 0

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any]:
        assert community_id == COMMUNITY_ID
        assert post_id == anomaly_module.ANOMALY_POST_ID
        self.read_post_calls += 1
        return {
            "owner_id": OWNER_ID,
            "id": anomaly_module.ANOMALY_POST_ID,
            "is_deleted": True,
        }

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any]:
        expected_owner, expected_video = map(int, anomaly_module.ANOMALY_CLIP_REMOTE_ID.split("_", maxsplit=1))
        assert (owner_id, video_id) == (expected_owner, expected_video)
        self.read_video_calls += 1
        return {
            "owner_id": owner_id,
            "id": video_id,
            "type": "short_video",
            "description": "historical protected clip",
        }


def _run_anomaly_case(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asset = next(item for item in _assets() if item.source_id == anomaly_module.ANOMALY_SOURCE_ID)
    state: dict[str, Any] = {
        "cleanup_475": {
            "status": "unknown_requires_reconciliation",
            "delete_dispatch_started": True,
            "delete_authority": False,
        }
    }
    reader = _AnomalyReader()

    monkeypatch.setattr(anomaly_module, "prepare_sources", lambda _work_dir: [asset])
    monkeypatch.setattr(anomaly_module, "load_anomaly_cleanup_state", lambda _path: state)
    monkeypatch.setattr(anomaly_module, "save_anomaly_cleanup_state", lambda _path, _state: None)
    monkeypatch.setattr(
        anomaly_module,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"),
    )
    monkeypatch.setattr(anomaly_module, "VkTokenStore", lambda _data_dir: object())
    monkeypatch.setattr(anomaly_module, "_resolve_account", lambda _store, _version: ("fixture", object()))
    monkeypatch.setattr(anomaly_module, "VkWallWriter", lambda **_kwargs: reader)
    monkeypatch.setattr(anomaly_module, "local_vk_write_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(anomaly_module, "_prove_target", lambda _client: None)

    result = anomaly_module.run_reconcile(
        confirmation=anomaly_module.EXECUTION_CONFIRMATION,
        output_path=tmp_path / "anomaly-result.json",
        finalizer_journal_path=tmp_path / "anomaly-state.json",
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "verified_absent"
    assert state["cleanup_475"]["status"] == "verified_absent"
    assert state["cleanup_475"]["delete_authority"] is False
    assert "resume" in state["cleanup_475"]["absence_evidence"]
    assert reader.read_post_calls == 2
    assert reader.read_video_calls == 1
    assert not hasattr(reader, "delete_post")


def test_historical_stop_corpus_manifest_is_exact_and_public() -> None:
    case_ids = tuple(case["case_id"] for case in CORPUS)
    assert case_ids == EXPECTED_CASE_IDS
    assert len(case_ids) == len(set(case_ids))
    allowed_surfaces = {"run_issue_323_status_probe", "run_issue_323_continue_preview", "run_reconcile"}
    assert all(case["public_surface"] in allowed_surfaces for case in CORPUS)
    assert all(case["incident_class"].strip() for case in CORPUS)
    assert all(case["invariant"].strip() for case in CORPUS)


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case["case_id"])
def test_historical_stop_replay_corpus(
    case: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = case["case_id"]
    if case["public_surface"] == "run_issue_323_status_probe":
        assets, scenario = _build_status_scenario(case_id)
        result = _run_status_public_surface(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            assets=assets,
            scenario=scenario,
        )
        _assert_status_case(result, scenario)
        return

    if case["public_surface"] == "run_issue_323_continue_preview":
        _run_continuation_case(case_id=case_id, tmp_path=tmp_path, monkeypatch=monkeypatch)
        return

    if case["public_surface"] == "run_reconcile":
        assert case_id == "wall475_tombstone_after_possible_delete_no_second_delete"
        _run_anomaly_case(tmp_path=tmp_path, monkeypatch=monkeypatch)
        return

    raise AssertionError(f"Unknown public corpus surface: {case['public_surface']}")
