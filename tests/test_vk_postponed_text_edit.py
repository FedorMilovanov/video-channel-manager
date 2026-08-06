from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.http import HttpFailureKind
from video_channel_manager.platforms.vk.postponed_text_edit import (
    VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
    VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
    VkPostponedTextState,
    build_vk_postponed_text_edit_plan,
    execute_vk_postponed_text_edit_plan,
    reconcile_vk_postponed_text_edit_plan,
    validate_vk_postponed_text_edit_plan,
)
from video_channel_manager.platforms.vk.wall_safety import VkWallSurface
from video_channel_manager.platforms.vk.writer import VkWriteError

COMMUNITY_ID = 60805374
OWNER_ID = -COMMUNITY_ID
NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
PUBLISH_DATE = int((NOW + timedelta(days=10)).timestamp())
TRANSLATION_LINE = "Авторский литературно-буквальный перевод с английского."


def _post(post_id: int, *, quote: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "owner_id": OWNER_ID,
        "id": post_id,
        "date": PUBLISH_DATE + post_id,
        "text": (
            f"«{quote}»\n\n"
            "— Чарльз Хэддон Сперджен\n"
            "Проповедь №1\n\n"
            f"{TRANSLATION_LINE}\n"
            f"Источник: https://ccel.org/example/{post_id}"
        ),
        "attachments": attachments or [],
    }


def _request(post_ids: list[int], *, expected_count: int) -> dict[str, Any]:
    return {
        "schema_name": VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
        "schema_version": VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
        "project_key": "lord-god-strength",
        "community_id": COMMUNITY_ID,
        "owner_id": OWNER_ID,
        "expected_postponed_count": expected_count,
        "target_post_ids": post_ids,
        "rules": [
            {
                "match": "exact",
                "value": TRANSLATION_LINE,
                "expected_per_post": 1,
            },
            {
                "match": "prefix",
                "value": "Источник: https://",
                "expected_per_post": 1,
            },
        ],
        "allow_attachments": False,
    }


class FakeWriter:
    account_alias = "legendary-poet"

    def __init__(
        self,
        *,
        published: list[dict[str, Any]] | None = None,
        postponed: list[dict[str, Any]] | None = None,
    ) -> None:
        self.published = deepcopy(published or [])
        self.postponed = deepcopy(postponed or [])
        self.edit_calls: list[dict[str, Any]] = []
        self.failures: dict[int, list[BaseException]] = {}
        self.mutate_non_target_post_id: int | None = None

    def _read_wall_surface(
        self,
        *,
        community_id: int,
        surface: VkWallSurface,
        max_posts: int,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        assert community_id == COMMUNITY_ID
        items = self.published if surface is VkWallSurface.PUBLISHED else self.postponed
        return deepcopy(items[:max_posts]), 1, len(items) <= max_posts

    def _call(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        retry_transient: bool = False,
    ) -> object:
        assert method == "wall.edit"
        assert retry_transient is False
        assert params is not None
        post_id = int(params["post_id"])
        self.edit_calls.append(dict(params))
        queued = self.failures.get(post_id) or []
        if queued:
            error = queued.pop(0)
            raise error
        for post in self.postponed:
            if post["id"] == post_id:
                post["text"] = params["message"]
                post["date"] = int(params["publish_date"])
                assert params["attachments"] == ""
                if self.mutate_non_target_post_id is not None:
                    for other in self.postponed:
                        if other["id"] == self.mutate_non_target_post_id:
                            other["text"] = "unexpected external mutation"
                return {"success": 1}
        raise AssertionError(f"post not found: {post_id}")


def _build_plan(writer: FakeWriter, post_ids: list[int]) -> dict[str, Any]:
    return build_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        _request(post_ids, expected_count=len(writer.postponed)),
        generated_at=NOW,
    )


def test_build_plan_removes_only_declared_lines_and_is_self_validating() -> None:
    writer = FakeWriter(
        postponed=[
            _post(12513, quote="Первая цитата"),
            _post(12514, quote="Вторая цитата"),
            {"owner_id": OWNER_ID, "id": 900, "date": PUBLISH_DATE, "text": "Видео", "attachments": []},
        ]
    )

    plan = _build_plan(writer, [12513, 12514])

    assert plan["operation_count"] == 2
    assert plan["expected_postponed_count"] == 3
    assert plan["target_post_ids"] == [12513, 12514]
    assert plan["source_snapshot"]["complete"] is True
    for operation in plan["operations"]:
        assert TRANSLATION_LINE not in operation["after_text"]
        assert "Источник: https://" not in operation["after_text"]
        assert "— Чарльз Хэддон Сперджен" in operation["after_text"]
        assert len(operation["removed_lines"]) == 2
    validate_vk_postponed_text_edit_plan(plan)


def test_reconcile_reports_exact_before_after_and_conflict() -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A"), _post(12514, quote="B")])
    plan = _build_plan(writer, [12513, 12514])
    writer.postponed[0]["text"] = plan["operations"][0]["after_text"]

    ready = reconcile_vk_postponed_text_edit_plan(writer, plan)  # type: ignore[arg-type]

    assert ready["status"] == "ready"
    assert ready["after"] == 1
    assert ready["before"] == 1
    assert ready["conflict"] == 0

    writer.postponed[1]["text"] = "manual conflicting text"
    blocked = reconcile_vk_postponed_text_edit_plan(writer, plan)  # type: ignore[arg-type]
    assert blocked["status"] == "blocked"
    assert blocked["conflict"] == 1
    assert blocked["states"][1]["state"] == VkPostponedTextState.CONFLICT.value


def test_execute_skips_after_edits_before_and_preserves_non_targets(tmp_path: Path) -> None:
    writer = FakeWriter(
        published=[{"owner_id": OWNER_ID, "id": 10, "date": PUBLISH_DATE, "text": "Published", "attachments": []}],
        postponed=[
            _post(12513, quote="A"),
            _post(12514, quote="B"),
            {"owner_id": OWNER_ID, "id": 900, "date": PUBLISH_DATE, "text": "Video", "attachments": []},
        ],
    )
    plan = _build_plan(writer, [12513, 12514])
    writer.postponed[0]["text"] = plan["operations"][0]["after_text"]

    result = execute_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        plan,
        output_dir=tmp_path,
        confirm_plan_sha256=plan["plan_sha256"],
        enable_provider_writes=True,
        minimum_future_seconds=0,
        inter_operation_delay_seconds=0,
        postflight_delay_seconds=0,
        transient_retry_delay_seconds=0,
        sleep=lambda _seconds: None,
        now=lambda: NOW,
    )

    assert result["status"] == "succeeded"
    assert result["already_after_before_apply"] == 1
    assert result["newly_verified"] == 1
    assert result["total_verified"] == 2
    assert result["non_target_postponed_unchanged"] == 1
    assert len(writer.edit_calls) == 1
    assert writer.edit_calls[0]["post_id"] == 12514
    assert writer.edit_calls[0]["publish_date"] == plan["operations"][1]["publish_date"]
    assert (tmp_path / "result.json").is_file()


def test_rate_limit_retries_only_after_exact_before_readback(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    writer.failures[12513] = [
        VkWriteError(
            "VK API HTTP 429 while calling wall.edit",
            method="wall.edit",
            kind=HttpFailureKind.RATE_LIMIT,
        )
    ]

    result = execute_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        plan,
        output_dir=tmp_path,
        confirm_plan_sha256=plan["plan_sha256"],
        enable_provider_writes=True,
        minimum_future_seconds=0,
        inter_operation_delay_seconds=0,
        postflight_delay_seconds=0,
        transient_retry_delay_seconds=0,
        max_transient_retries=1,
        sleep=lambda _seconds: None,
        now=lambda: NOW,
    )

    assert result["status"] == "succeeded"
    assert len(writer.edit_calls) == 2
    assert result["results"][0]["attempts"] == 2


def test_captcha_stops_with_confirmed_absent_and_is_resumable(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    writer.failures[12513] = [
        VkWriteError(
            "VK API 14 in wall.edit: Captcha needed",
            method="wall.edit",
            code=14,
            kind=HttpFailureKind.PROVIDER_ERROR,
        )
    ]

    result = execute_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        plan,
        output_dir=tmp_path,
        confirm_plan_sha256=plan["plan_sha256"],
        enable_provider_writes=True,
        minimum_future_seconds=0,
        inter_operation_delay_seconds=0,
        postflight_delay_seconds=0,
        transient_retry_delay_seconds=0,
        sleep=lambda _seconds: None,
        now=lambda: NOW,
    )

    assert result["status"] == "stopped_captcha_required"
    assert result["stopped_post_id"] == 12513
    assert len(writer.edit_calls) == 1
    reconciliation = reconcile_vk_postponed_text_edit_plan(writer, plan)  # type: ignore[arg-type]
    assert reconciliation["before"] == 1
    assert reconciliation["after"] == 0


def test_non_target_mutation_fails_final_postcondition(tmp_path: Path) -> None:
    writer = FakeWriter(
        postponed=[
            _post(12513, quote="A"),
            {"owner_id": OWNER_ID, "id": 900, "date": PUBLISH_DATE, "text": "Video", "attachments": []},
        ]
    )
    plan = _build_plan(writer, [12513])
    writer.mutate_non_target_post_id = 900

    result = execute_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        plan,
        output_dir=tmp_path,
        confirm_plan_sha256=plan["plan_sha256"],
        enable_provider_writes=True,
        minimum_future_seconds=0,
        inter_operation_delay_seconds=0,
        postflight_delay_seconds=0,
        transient_retry_delay_seconds=0,
        sleep=lambda _seconds: None,
        now=lambda: NOW,
    )

    assert result["status"] == "non_target_postcondition_failed"
