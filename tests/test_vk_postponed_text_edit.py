from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from video_channel_manager.platforms.http import HttpFailureKind
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.postponed_text_edit import (
    VK_POSTPONED_TEXT_EDIT_REQUEST_SCHEMA,
    VK_POSTPONED_TEXT_EDIT_REQUEST_VERSION,
    VkPostponedTextEditError,
    VkPostponedTextState,
    build_vk_postponed_text_edit_plan,
    execute_vk_postponed_text_edit_plan,
    reconcile_vk_postponed_text_edit_plan,
    validate_vk_postponed_text_edit_plan,
    validate_vk_postponed_text_edit_request,
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
        data_dir: Path | None = None,
    ) -> None:
        self.published = deepcopy(published or [])
        self.postponed = deepcopy(postponed or [])
        self.token_store = SimpleNamespace(data_dir=data_dir or Path("unused-test-data"))
        self.edit_calls: list[dict[str, Any]] = []
        self.failures: dict[int, list[BaseException]] = {}
        self.mutate_non_target_post_id: int | None = None
        self.reorder_non_target_post_id: int | None = None
        self.fail_next_postponed_read = False
        self.fail_postflight_after_dispatch = False
        self.defer_after_failure_reads: dict[int, int] = {}
        self.deferred_after_text: dict[int, str] = {}
        self.deferred_reads_remaining: dict[int, int] = {}

    def _read_wall_surface(
        self,
        *,
        community_id: int,
        surface: VkWallSurface,
        max_posts: int,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        assert community_id == COMMUNITY_ID
        if surface is VkWallSurface.POSTPONED:
            if self.fail_next_postponed_read:
                self.fail_next_postponed_read = False
                raise VkWriteError("postflight read failed", method="wall.get")
            for post_id, after_text in list(self.deferred_after_text.items()):
                remaining = self.deferred_reads_remaining[post_id]
                if remaining == 0:
                    for post in self.postponed:
                        if post["id"] == post_id:
                            post["text"] = after_text
                            break
                    del self.deferred_after_text[post_id]
                    del self.deferred_reads_remaining[post_id]
                else:
                    self.deferred_reads_remaining[post_id] = remaining - 1
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
            if post_id in self.defer_after_failure_reads:
                self.deferred_after_text[post_id] = str(params["message"])
                self.deferred_reads_remaining[post_id] = self.defer_after_failure_reads[post_id]
            if self.fail_postflight_after_dispatch:
                self.fail_next_postponed_read = True
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
                if self.reorder_non_target_post_id is not None:
                    for other in self.postponed:
                        if other["id"] == self.reorder_non_target_post_id:
                            other["attachments"] = list(reversed(other["attachments"]))
                return {"success": 1}
        raise AssertionError(f"post not found: {post_id}")


def _build_plan(writer: FakeWriter, post_ids: list[int]) -> dict[str, Any]:
    return build_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        _request(post_ids, expected_count=len(writer.postponed)),
        generated_at=NOW,
    )


def _execute(
    writer: FakeWriter,
    plan: dict[str, Any],
    *,
    output_dir: Path,
    now: Any = lambda: NOW,
    max_transient_retries: int = 1,
) -> dict[str, Any]:
    writer.token_store = SimpleNamespace(data_dir=output_dir.parent / "shared-data")
    return execute_vk_postponed_text_edit_plan(
        writer,  # type: ignore[arg-type]
        plan,
        output_dir=output_dir,
        confirm_plan_sha256=plan["plan_sha256"],
        enable_provider_writes=True,
        minimum_future_seconds=0,
        inter_operation_delay_seconds=0,
        postflight_delay_seconds=0,
        transient_retry_delay_seconds=0,
        max_transient_retries=max_transient_retries,
        sleep=lambda _seconds: None,
        now=now,
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
        assert operation["attachments"] == []
        assert len(operation["removed_lines"]) == 2
    validate_vk_postponed_text_edit_plan(plan)


def test_schema_v1_rejects_attachment_authority_and_attached_targets() -> None:
    request = _request([12513], expected_count=1)
    request["allow_attachments"] = True
    with pytest.raises(ValueError, match="attachment-free"):
        validate_vk_postponed_text_edit_request(request)

    writer = FakeWriter(
        postponed=[
            _post(
                12513,
                quote="A",
                attachments=[{"type": "photo", "photo": {"owner_id": OWNER_ID, "id": 77}}],
            )
        ]
    )
    with pytest.raises(VkPostponedTextEditError, match="attachment-free"):
        _build_plan(writer, [12513])


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

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "succeeded"
    assert result["already_after_before_apply"] == 1
    assert result["newly_verified"] == 1
    assert result["total_verified"] == 2
    assert result["non_target_postponed_unchanged"] == 1
    assert len(writer.edit_calls) == 1
    assert writer.edit_calls[0]["post_id"] == 12514
    assert writer.edit_calls[0]["publish_date"] == plan["operations"][1]["publish_date"]
    assert (tmp_path / "run" / "result.json").is_file()


def test_community_lock_is_shared_across_different_output_directories(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")], data_dir=tmp_path / "shared-data")
    plan = _build_plan(writer, [12513])
    writer.token_store = SimpleNamespace(data_dir=tmp_path / "shared-data")
    lock_path = tmp_path / "shared-data" / "locks" / "vk" / f"legendary-poet-{COMMUNITY_ID}.lock"

    with local_vk_write_lock(
        lock_path,
        account="legendary-poet",
        community_id=COMMUNITY_ID,
        operation="other-output-dir",
    ):
        with pytest.raises(VkWriteError, match="already active"):
            execute_vk_postponed_text_edit_plan(
                writer,  # type: ignore[arg-type]
                plan,
                output_dir=tmp_path / "second-run",
                confirm_plan_sha256=plan["plan_sha256"],
                enable_provider_writes=True,
                minimum_future_seconds=0,
                inter_operation_delay_seconds=0,
                postflight_delay_seconds=0,
                transient_retry_delay_seconds=0,
                sleep=lambda _seconds: None,
                now=lambda: NOW,
            )
    assert writer.edit_calls == []


def test_publication_distance_is_rechecked_before_dispatch(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    observations = iter([NOW, NOW + timedelta(days=20)])

    result = _execute(writer, plan, output_dir=tmp_path / "run", now=lambda: next(observations))

    assert result["status"] == "stopped_too_close_to_publication"
    assert result["stopped_post_id"] == 12513
    assert writer.edit_calls == []


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

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "succeeded"
    assert len(writer.edit_calls) == 2
    assert result["results"][0]["attempts"] == 2


def test_retry_rechecks_publication_distance_before_second_dispatch(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    writer.failures[12513] = [
        VkWriteError("rate limit", method="wall.edit", kind=HttpFailureKind.RATE_LIMIT)
    ]
    observations = iter([NOW, NOW, NOW + timedelta(days=20)])

    result = _execute(writer, plan, output_dir=tmp_path / "run", now=lambda: next(observations))

    assert result["status"] == "stopped_too_close_to_publication"
    assert len(writer.edit_calls) == 1


def test_delayed_reconciliation_rewrites_attempt_journal_to_verified(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    writer.failures[12513] = [
        VkWriteError("rate limit", method="wall.edit", kind=HttpFailureKind.RATE_LIMIT)
    ]
    writer.defer_after_failure_reads[12513] = 1

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "succeeded"
    assert result["results"][0]["state"] == "verified_after_delayed_reconciliation"
    journals = list((tmp_path / "run" / "journal").glob("*.json"))
    assert len(journals) == 1
    journal = json.loads(journals[0].read_text(encoding="utf-8"))
    assert journal["state"] == "verified_after_delayed_reconciliation"
    assert journal["provider_effect"] == "verified"
    assert journal["finished_at"] is not None


def test_post_dispatch_read_failure_stops_unknown_without_retry(tmp_path: Path) -> None:
    writer = FakeWriter(postponed=[_post(12513, quote="A")])
    plan = _build_plan(writer, [12513])
    writer.failures[12513] = [
        VkWriteError("transport lost", method="wall.edit", kind=HttpFailureKind.TRANSPORT)
    ]
    writer.fail_postflight_after_dispatch = True

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "unknown_requires_reconciliation"
    assert len(writer.edit_calls) == 1
    journal = result["results"][-1]
    assert journal["state"] == "unknown_requires_reconciliation"
    assert journal["provider_effect"] == "may_exist"


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

    result = _execute(writer, plan, output_dir=tmp_path / "run")

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

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "non_target_postcondition_failed"


def test_non_target_attachment_order_change_is_detected(tmp_path: Path) -> None:
    attachments = [
        {"type": "photo", "photo": {"owner_id": OWNER_ID, "id": 1, "access_key": "a"}},
        {"type": "doc", "doc": {"owner_id": OWNER_ID, "id": 2, "access_key": "b"}},
    ]
    writer = FakeWriter(
        postponed=[
            _post(12513, quote="A"),
            {"owner_id": OWNER_ID, "id": 900, "date": PUBLISH_DATE, "text": "Article", "attachments": attachments},
        ]
    )
    plan = _build_plan(writer, [12513])
    writer.reorder_non_target_post_id = 900

    result = _execute(writer, plan, output_dir=tmp_path / "run")

    assert result["status"] == "non_target_postcondition_failed"
