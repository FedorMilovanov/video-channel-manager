from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path, local_vk_write_lock
from video_channel_manager.platforms.vk.writer import VkWriteError


_READONLY_OPERATION = "milovi-issue-323-readonly-status-probe"
_WRITER_OPERATION = "milovi-issue-323-finalize-internal-promotion"


def test_issue323_readonly_status_probe_does_not_require_write_execution_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("VCM_ISSUE323_APPROVED_MAIN_SHA", raising=False)
    requested = tmp_path / "locks" / "issue-323-readonly-status.lock"
    canonical = community_vk_write_lock_path(tmp_path, community_id=68859909)

    with local_vk_write_lock(
        requested,
        account="legendary-poet",
        community_id=68859909,
        operation=_READONLY_OPERATION,
    ):
        payload = json.loads(canonical.read_text(encoding="utf-8"))
        assert payload["operation"] == _READONLY_OPERATION
        assert "execution_identity" not in payload

    assert not canonical.exists()


def test_issue323_writer_still_requires_exact_write_execution_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("VCM_ISSUE323_APPROVED_MAIN_SHA", raising=False)

    with pytest.raises(VkWriteError, match="VCM_ISSUE323_APPROVED_MAIN_SHA"):
        with local_vk_write_lock(
            tmp_path / "locks" / "issue-323-writer.lock",
            account="legendary-poet",
            community_id=68859909,
            operation=_WRITER_OPERATION,
        ):
            pass


def test_similarly_named_issue323_operation_cannot_bypass_write_identity_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("VCM_ISSUE323_APPROVED_MAIN_SHA", raising=False)

    with pytest.raises(VkWriteError, match="VCM_ISSUE323_APPROVED_MAIN_SHA"):
        with local_vk_write_lock(
            tmp_path / "locks" / "issue-323-lookalike.lock",
            account="legendary-poet",
            community_id=68859909,
            operation=f"{_READONLY_OPERATION}-extra",
        ):
            pass


def test_readonly_probe_uses_same_community_mutex_as_other_provider_inert_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("VCM_ISSUE323_APPROVED_MAIN_SHA", raising=False)

    with local_vk_write_lock(
        tmp_path / "locks" / "issue-323-readonly-status.lock",
        account="legendary-poet",
        community_id=68859909,
        operation=_READONLY_OPERATION,
    ):
        with pytest.raises(VkWriteError, match="Another local VK write process"):
            with local_vk_write_lock(
                tmp_path / "locks" / "other-readonly.lock",
                account="legendary-poet",
                community_id=68859909,
                operation="read-only-observer",
            ):
                pass
