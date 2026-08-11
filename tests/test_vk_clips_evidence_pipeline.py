from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.platforms.vk import clips_evidence_pipeline
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.clips_evidence_pipeline import run_owner_clips_evidence_pipeline

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
KNOWN_SHREK_CLIP = "-68859909_456239130"


def _clip(video_id: int, title: str) -> dict[str, Any]:
    return {
        "remote_id": f"{MILOVI_OWNER_ID}_{video_id}",
        "owner_id": MILOVI_OWNER_ID,
        "video_id": video_id,
        "type": "short_video",
        "is_native_clip": True,
        "title": title,
        "description": "",
        "duration_seconds": 30,
        "width": 1080,
        "height": 1920,
    }


def _owner_probe(*, status: str = "ok") -> dict[str, Any]:
    clips = [
        _clip(456239131, "Клубничный торт"),
        _clip(456239130, "Торт Шрек"),
    ]
    return {
        "schema": "vk-owner-clips-experimental-probe-v2",
        "generated_at": "2026-08-11T03:00:00Z",
        "project_key": "milovi-cake",
        "account_alias": "legendary-poet",
        "api_version": "5.253",
        "read_only": True,
        "provider_effect": "safe_read_only",
        "community": {
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "title": "Milovi Cake",
            "url": "https://vk.com/milovi_cake",
            "managed_by_token": True,
        },
        "provider_probe": {
            "status": status,
            "error": None if status == "ok" else {"code": 3},
            "provider_reported_total": 2 if status == "ok" else None,
            "provider_reported_offsets": [0],
            "retrieved_raw_item_count": 2,
            "pagination_complete": status == "ok",
        },
        "coverage": {
            "candidate_count": 2,
            "clip_count": 2,
            "shape_noise_count": 0,
            "returned_type_counts": {"short_video": 2},
            "all_normalized_items_exact_owner": True,
            "native_clip_identity_rule": "type=short_video",
            "required_remote_ids": [KNOWN_SHREK_CLIP],
            "required_remote_ids_found_as_clips": [KNOWN_SHREK_CLIP],
            "required_remote_ids_returned_non_clip": [],
            "required_remote_ids_missing_from_probe": [],
            "surface_complete_claim": False,
        },
        "clips": clips,
        "endpoint_candidates": clips,
        "shape_noise": [],
    }


def _wall_posts() -> list[dict[str, Any]]:
    return [
        {
            "id": 1001,
            "owner_id": MILOVI_OWNER_ID,
            "attachments": [
                {
                    "type": "video",
                    "video": {
                        "id": 456239131,
                        "owner_id": MILOVI_OWNER_ID,
                        "type": "short_video",
                        "title": "Клубничный торт",
                        "description": "",
                        "duration": 30,
                        "width": 1080,
                        "height": 1920,
                    },
                }
            ],
        }
    ]


def _file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_pipeline_uses_one_owner_probe_for_reconciliation_and_triage(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    probe = _owner_probe()

    def fake_probe(client: object, **kwargs: Any) -> dict[str, Any]:
        calls.append({"client": client, **kwargs})
        return probe

    monkeypatch.setattr(clips_evidence_pipeline, "build_vk_owner_clips_probe_snapshot", fake_probe)
    client = object()

    manifest = run_owner_clips_evidence_pipeline(  # type: ignore[arg-type]
        client,
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=_wall_posts(),
        output_dir=tmp_path,
        required_remote_ids=[KNOWN_SHREK_CLIP],
    )

    assert len(calls) == 1
    assert calls[0]["required_remote_ids"] == [KNOWN_SHREK_CLIP]
    assert manifest["schema"] == "vk-owner-clips-evidence-pipeline-v1"
    assert manifest["read_only"] is True
    assert manifest["provider_writes"] == 0
    assert manifest["provider_mutation_authorized"] is False
    assert manifest["owner_surface_complete_claim"] is False
    assert manifest["artifacts"]["owner_probe"]["provider_status"] == "ok"
    assert manifest["artifacts"]["reconciliation"]["both_count"] == 1
    assert manifest["artifacts"]["reconciliation"]["wall_only_count"] == 0
    assert manifest["artifacts"]["reconciliation"]["owner_only_count"] == 1
    assert manifest["artifacts"]["triage"]["owner_only_candidate_count"] == 1
    assert manifest["artifacts"]["triage"]["risk_disposition_counts"] == {"IP_HOLD_HIDE": 1}
    assert manifest["safety"]["provider_methods"] == ["groups.get", "shortVideo.getOwnerVideos"]
    assert manifest["safety"]["upload_authorized"] is False
    assert manifest["safety"]["delete_authorized"] is False

    owner_path = tmp_path / "01-owner-clips-probe.json"
    reconciliation_path = tmp_path / "02-owner-clips-wall-reconciliation.json"
    triage_path = tmp_path / "03-owner-only-risk-triage.json"
    manifest_path = tmp_path / "00-evidence-manifest.json"
    assert all(path.exists() for path in (owner_path, reconciliation_path, triage_path, manifest_path))
    assert manifest["artifacts"]["owner_probe"]["file_sha256"] == _file_sha(owner_path)
    assert manifest["artifacts"]["reconciliation"]["file_sha256"] == _file_sha(reconciliation_path)
    assert manifest["artifacts"]["triage"]["file_sha256"] == _file_sha(triage_path)
    assert manifest["artifacts"]["owner_probe"]["canonical_sha256"] == canonical_sha256(probe)

    stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert stored_manifest == manifest
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == canonical_sha256(unsigned)


def test_pipeline_preserves_read_error_evidence_without_creating_mutation_authority(
    monkeypatch, tmp_path: Path
) -> None:
    probe = _owner_probe(status="error")
    monkeypatch.setattr(
        clips_evidence_pipeline,
        "build_vk_owner_clips_probe_snapshot",
        lambda client, **kwargs: probe,
    )

    manifest = run_owner_clips_evidence_pipeline(  # type: ignore[arg-type]
        object(),
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=_wall_posts(),
        output_dir=tmp_path,
    )

    assert manifest["artifacts"]["owner_probe"]["provider_status"] == "error"
    assert manifest["artifacts"]["reconciliation"]["status"] == "probe_error"
    assert manifest["provider_mutation_authorized"] is False
    assert manifest["safety"]["hide_authorized"] is False
    assert manifest["safety"]["wall_post_authorized"] is False
    assert manifest["safety"]["schedule_authorized"] is False


def test_pipeline_writes_nothing_when_exact_identity_chain_fails(monkeypatch, tmp_path: Path) -> None:
    foreign_probe = _owner_probe()
    foreign_probe["community"]["community_id"] = 235216998
    monkeypatch.setattr(
        clips_evidence_pipeline,
        "build_vk_owner_clips_probe_snapshot",
        lambda client, **kwargs: foreign_probe,
    )

    with pytest.raises(ValueError, match="exact community/owner"):
        run_owner_clips_evidence_pipeline(  # type: ignore[arg-type]
            object(),
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            published_posts=_wall_posts(),
            output_dir=tmp_path,
        )

    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []
