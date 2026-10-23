"""`video-manager-vk-postponed-text` must be executable, not merely documented.

The console entry point, its PowerShell wrapper and its runbook were all shipped while the CLI
module itself had 0% coverage: the Pester suite asserted that the module *name* appeared in the
argument list, and the Python suite tested the planning library underneath. Nothing proved that
`plan`, `reconcile` and `apply` parse their arguments, refuse a bad request and refuse to write
when the write gate is not explicitly opened.

These tests invoke the real Typer application. Provider access is replaced at the single point
the CLI builds a writer (`_writer`), so every branch below runs without a token and without a
network call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from video_channel_manager.cli import vk_postponed_text as cli
from video_channel_manager.platforms.vk.postponed_text_edit import (
    VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
    VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
    VkPostponedTextEditError,
    calculate_vk_postponed_text_plan_sha256,
)

COMMUNITY_ID = 60805374
OWNER_ID = -COMMUNITY_ID
RUNNER = CliRunner()


class _FakeWallWriter:
    """Minimal reviewer-visible surface: two pages of postponed posts, no published posts."""

    def __init__(self, posts: list[dict[str, Any]]) -> None:
        self.posts = posts
        self.closed = False

    def __enter__(self) -> "_FakeWallWriter":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.closed = True

    def _read_wall_surface(
        self, *, community_id: int, surface: object, max_posts: int
    ) -> tuple[list[dict[str, Any]], int, bool]:
        assert community_id == COMMUNITY_ID
        assert max_posts == 10000
        if getattr(surface, "value", surface) == "published":
            return [], 1, True
        return list(self.posts), 1, True


def _request(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_name": VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
        "project_key": "lord-god-strength",
        "community_id": COMMUNITY_ID,
        "owner_id": OWNER_ID,
        "expected_postponed_count": 2,
        "target_post_ids": [501, 502],
        "rules": [{"match": "exact", "value": "Источник: legendy.org", "expected_per_post": 1}],
    }
    payload.update(overrides)
    return payload


def _post(post_id: int) -> dict[str, Any]:
    return {
        "id": post_id,
        "owner_id": OWNER_ID,
        "date": 1790000000 + post_id,
        "text": f"Строка {post_id}\nИсточник: legendy.org\nПодпись",
        "attachments": [],
    }


def _patch_writer(monkeypatch: pytest.MonkeyPatch, writer: _FakeWallWriter) -> None:
    monkeypatch.setattr(cli, "_writer", lambda account: writer)


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _reviewed_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, Any]]:
    """Produce a real plan document through the CLI, so later stages validate a real artifact."""

    _patch_writer(monkeypatch, _FakeWallWriter([_post(501), _post(502)]))
    request_path = _write(tmp_path / "request.json", _request())
    plan_path = tmp_path / "plan.json"
    produced = RUNNER.invoke(cli.app, ["plan", str(request_path), "--output", str(plan_path)])
    assert produced.exit_code == 0, produced.stdout
    return plan_path, json.loads(plan_path.read_text(encoding="utf-8"))


def test_help_lists_the_three_supported_commands() -> None:
    result = RUNNER.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    for command in ("plan", "reconcile", "apply"):
        assert command in result.stdout


def test_plan_writes_an_immutable_plan_from_a_complete_wall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _FakeWallWriter([_post(501), _post(502)])
    _patch_writer(monkeypatch, writer)
    request_path = _write(tmp_path / "request.json", _request())
    output_path = tmp_path / "plan.json"

    result = RUNNER.invoke(cli.app, ["plan", str(request_path), "--output", str(output_path)])

    assert result.exit_code == 0, result.stdout
    assert writer.closed is True
    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["operation_count"] == 2
    assert plan["expected_postponed_count"] == 2
    assert plan["plan_sha256"] == calculate_vk_postponed_text_plan_sha256(plan)
    assert all(operation["post_id"] in {501, 502} for operation in plan["operations"])


def test_plan_refuses_a_request_whose_schema_is_not_the_supported_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_writer(monkeypatch, _FakeWallWriter([_post(501)]))
    request_path = _write(tmp_path / "request.json", _request(schema_version=2))

    result = RUNNER.invoke(
        cli.app,
        ["plan", str(request_path), "--output", str(tmp_path / "plan.json")],
    )

    assert result.exit_code == 2
    assert "plan failed" in result.stdout
    assert not (tmp_path / "plan.json").exists()


def test_plan_refuses_a_postponed_surface_that_changed_since_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The request was reviewed against two postponed posts; the wall now has three.
    writer = _FakeWallWriter([_post(501), _post(502), _post(503)])
    _patch_writer(monkeypatch, writer)
    request_path = _write(tmp_path / "request.json", _request())

    result = RUNNER.invoke(
        cli.app,
        ["plan", str(request_path), "--output", str(tmp_path / "plan.json")],
    )

    assert result.exit_code == 2
    assert "postponed count changed" in result.stdout
    assert not (tmp_path / "plan.json").exists()


def test_plan_refuses_a_target_post_with_no_exact_publish_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    posts = [_post(501), _post(502)]
    posts[1]["date"] = None
    _patch_writer(monkeypatch, _FakeWallWriter(posts))
    request_path = _write(tmp_path / "request.json", _request())

    result = RUNNER.invoke(
        cli.app,
        ["plan", str(request_path), "--output", str(tmp_path / "plan.json")],
    )

    assert result.exit_code == 2
    assert "publish_date" in result.stdout


def test_plan_surfaces_a_missing_credential_as_a_clean_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from video_channel_manager.platforms.vk.store import VkAccountNotFoundError

    def _raise(account: str) -> object:
        raise VkAccountNotFoundError(f"no local credential for {account}")

    monkeypatch.setattr(cli, "_writer", _raise)
    request_path = _write(tmp_path / "request.json", _request())

    result = RUNNER.invoke(
        cli.app,
        ["plan", str(request_path), "--output", str(tmp_path / "plan.json")],
    )

    assert result.exit_code == 2
    assert "plan failed" in result.stdout


def test_reconcile_requires_a_plan_that_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_writer(monkeypatch, _FakeWallWriter([_post(501)]))

    result = RUNNER.invoke(
        cli.app,
        ["reconcile", str(tmp_path / "absent.json"), "--output", str(tmp_path / "reconciliation.json")],
    )

    assert result.exit_code == 2
    assert "reconciliation failed" in result.stdout


def test_apply_refuses_to_run_without_explicit_write_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate is `--enable-provider-writes`; its absence must stop before any wall.edit."""

    plan_path, plan = _reviewed_plan(tmp_path, monkeypatch)

    monkeypatch.setattr(cli, "_writer", lambda account: _FakeWallWriter([_post(501), _post(502)]))

    result = RUNNER.invoke(
        cli.app,
        [
            "apply",
            str(plan_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--confirm-plan-sha256",
            plan["plan_sha256"],
        ],
    )

    assert result.exit_code == 2
    assert "provider writes require explicit" in result.stdout
    assert not (tmp_path / "out" / "result.json").exists()


def test_apply_requires_the_reviewed_plan_digest_as_an_explicit_option(tmp_path: Path) -> None:
    result = RUNNER.invoke(
        cli.app,
        ["apply", str(tmp_path / "plan.json"), "--output-dir", str(tmp_path / "out")],
    )

    assert result.exit_code == 2
    assert "confirm-plan-sha256" in result.output


def test_apply_reports_a_stopped_run_as_a_non_success_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, plan = _reviewed_plan(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "execute_vk_postponed_text_edit_plan",
        lambda *args, **kwargs: {
            "status": "stopped_conflict",
            "operation_count": 1,
            "plan_sha256": plan["plan_sha256"],
        },
    )

    result = RUNNER.invoke(
        cli.app,
        [
            "apply",
            str(plan_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--confirm-plan-sha256",
            plan["plan_sha256"],
        ],
    )

    assert result.exit_code == 4
    assert "stopped_conflict" in result.stdout


def test_reconcile_marks_a_non_ready_surface_as_a_non_success_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path, plan = _reviewed_plan(tmp_path, monkeypatch)
    payload = {
        "status": "conflict",
        "postponed_count": 2,
        "operation_count": 2,
        "plan_sha256": plan["plan_sha256"],
    }
    monkeypatch.setattr(cli, "reconcile_vk_postponed_text_edit_plan", lambda *args, **kwargs: payload)

    result = RUNNER.invoke(
        cli.app,
        ["reconcile", str(plan_path), "--output", str(tmp_path / "reconciliation.json")],
    )

    assert result.exit_code == 4
    assert "conflict" in result.stdout
    assert json.loads((tmp_path / "reconciliation.json").read_text(encoding="utf-8")) == payload


def test_library_error_surfaces_as_exit_two_not_a_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, _plan = _reviewed_plan(tmp_path, monkeypatch)

    def _raise(*args: object, **kwargs: object) -> dict[str, Any]:
        raise VkPostponedTextEditError("plan digest mismatch")

    monkeypatch.setattr(cli, "reconcile_vk_postponed_text_edit_plan", _raise)
    output = tmp_path / "reconciliation.json"

    result = RUNNER.invoke(cli.app, ["reconcile", str(plan_path), "--output", str(output)])

    assert result.exit_code == 2
    assert "plan digest mismatch" in result.stdout
    assert not output.exists()
