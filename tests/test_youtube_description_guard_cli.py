from __future__ import annotations

import argparse
import json

import pytest

import video_channel_manager.youtube_description_guard_cli as guard


def _valid_plan() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_name": guard.SCHEMA_NAME,
        "schema_version": guard.SCHEMA_VERSION,
        "created_at": "2026-08-09T00:00:00+00:00",
        "project_key": "legendary-poet",
        "account_alias": "legendary-poet",
        "target_channel_id": "UC-78ys2S3cQ3lpqgXfo-SvQ",
        "video_id": "x-puy27S2qs",
        "title_at_plan": "Black Man",
        "source_description_path": "/tmp/description.txt",
        "source_description_sha256": "sha256:" + "1" * 64,
        "before_revision": "sha256:" + "2" * 64,
        "before_description": "before",
        "before_description_sha256": "sha256:" + "3" * 64,
        "after_description": "after",
        "after_description_sha256": "sha256:" + "4" * 64,
        "writes": ["snippet.description"],
        "preserve": ["snippet.title"],
        "provider_write_authorized": False,
    }
    payload["plan_sha256"] = guard._plan_digest(payload)
    return payload


def test_plan_digest_ignores_its_own_field() -> None:
    payload = _valid_plan()
    first = guard._plan_digest(payload)
    payload["plan_sha256"] = "sha256:" + "f" * 64
    assert guard._plan_digest(payload) == first


def test_load_plan_rejects_tampering(tmp_path) -> None:
    payload = _valid_plan()
    payload["after_description"] = "tampered"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Plan digest mismatch"):
        guard._load_plan(path)


def test_load_plan_rejects_legacy_schema_fail_closed(tmp_path) -> None:
    payload = _valid_plan()
    payload["schema_version"] = 1
    payload["plan_sha256"] = guard._plan_digest(payload)
    path = tmp_path / "legacy-plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported exact-description plan schema"):
        guard._load_plan(path)


def test_load_plan_rejects_cross_project_identity(tmp_path) -> None:
    payload = _valid_plan()
    payload["account_alias"] = "fedor-milovanov"
    payload["plan_sha256"] = guard._plan_digest(payload)
    path = tmp_path / "wrong-project.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="OAuth alias differs from canonical project identity"):
        guard._load_plan(path)


def test_writer_identity_gate_runs_before_credentials(monkeypatch) -> None:
    calls: list[str] = []

    def reject_identity(*, project_key: str, account: str, channel: str) -> None:
        calls.append(f"identity:{project_key}:{account}:{channel}")
        raise ValueError("identity-stop")

    monkeypatch.setattr(guard, "_require_identity", reject_identity)
    monkeypatch.setattr(guard, "get_settings", lambda: pytest.fail("credentials/config accessed before identity gate"))

    with pytest.raises(ValueError, match="identity-stop"):
        guard._writer_for_identity(
            project_key="legendary-poet",
            account="legendary-poet",
            channel="UC-78ys2S3cQ3lpqgXfo-SvQ",
        )

    assert calls == ["identity:legendary-poet:legendary-poet:UC-78ys2S3cQ3lpqgXfo-SvQ"]


def test_unresolved_chapter_marker_is_not_publishable_copy() -> None:
    with pytest.raises(ValueError, match="unresolved exact-timing chapter marker"):
        guard._validate_description("Body\n\n[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]\n\nFooter")


def test_markdown_emphasis_is_not_publishable_description_copy() -> None:
    with pytest.raises(ValueError, match="Description lint failed"):
        guard._validate_description("Лишь в **1833 году** роман появился единым изданием.")


def test_angle_bracket_placeholder_is_not_publishable_description_copy() -> None:
    with pytest.raises(ValueError, match="Description lint failed"):
        guard._validate_description("Плейлист: <PLAYLIST_URL>")


def test_execute_review_only_plan_stops_before_credentials(monkeypatch, tmp_path) -> None:
    payload = _valid_plan()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(guard, "_writer_for_identity", lambda **_: pytest.fail("writer must not be constructed"))
    args = argparse.Namespace(
        repo=tmp_path,
        plan=plan_path,
        confirm=f"YTDESC:{payload['plan_sha256']}",
        result=tmp_path / "result.json",
    )

    with pytest.raises(ValueError, match="review-only"):
        guard.execute(args)


def test_write_new_json_refuses_overwrite(tmp_path) -> None:
    path = tmp_path / "evidence.json"
    guard._write_new_json(path, {"first": True})

    with pytest.raises(ValueError, match="Refusing to overwrite immutable evidence"):
        guard._write_new_json(path, {"second": True})
