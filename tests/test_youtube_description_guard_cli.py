from __future__ import annotations

import json

import pytest

from video_channel_manager.youtube_description_guard_cli import _load_plan, _plan_digest, _write_new_json


def test_plan_digest_ignores_its_own_field(tmp_path) -> None:
    payload = {
        "schema_name": "video-manager.youtube-description-exact-plan",
        "schema_version": 1,
        "video_id": "video-1",
        "after_description": "text",
    }
    payload["plan_sha256"] = _plan_digest(payload)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = _load_plan(path)

    assert loaded["plan_sha256"] == payload["plan_sha256"]


def test_load_plan_rejects_tampering(tmp_path) -> None:
    payload = {
        "schema_name": "video-manager.youtube-description-exact-plan",
        "schema_version": 1,
        "video_id": "video-1",
        "after_description": "before",
    }
    payload["plan_sha256"] = _plan_digest(payload)
    payload["after_description"] = "tampered"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Plan digest mismatch"):
        _load_plan(path)


def test_write_new_json_refuses_overwrite(tmp_path) -> None:
    path = tmp_path / "evidence.json"
    _write_new_json(path, {"first": True})

    with pytest.raises(ValueError, match="Refusing to overwrite immutable evidence"):
        _write_new_json(path, {"second": True})
