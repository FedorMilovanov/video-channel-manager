from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from video_channel_manager.platforms.vk.lock import (
    _pid_is_running,
    _stale,
    _windows_pid_is_running,
    community_vk_write_lock_path,
    local_vk_write_lock,
)
from video_channel_manager.platforms.vk.writer import VkWriteError


class _FakeKernel32:
    def __init__(self, *, handle: int = 1, exit_code: int = 259, last_error: int = 0) -> None:
        self.handle = handle
        self.exit_code = exit_code
        self.last_error = last_error
        self.closed: list[int] = []

    def OpenProcess(self, access: int, inherit_handle: bool, pid: int) -> int:  # noqa: N802
        assert access == 0x1000
        assert inherit_handle is False
        assert pid > 0
        return self.handle

    def GetExitCodeProcess(self, handle: int, exit_code: object) -> int:  # noqa: N802
        assert handle == self.handle
        exit_code._obj.value = self.exit_code  # type: ignore[attr-defined]
        return 1

    def CloseHandle(self, handle: int) -> int:  # noqa: N802
        self.closed.append(handle)
        return 1


def _canonical(tmp_path: Path, community_id: int) -> Path:
    return community_vk_write_lock_path(tmp_path, community_id=community_id)


def test_windows_pid_probe_reports_active_without_terminating_process() -> None:
    kernel32 = _FakeKernel32(exit_code=259)

    assert _windows_pid_is_running(42, kernel32=kernel32) is True
    assert kernel32.closed == [1]


def test_windows_pid_probe_reports_finished_process() -> None:
    kernel32 = _FakeKernel32(exit_code=0)

    assert _windows_pid_is_running(42, kernel32=kernel32) is False
    assert kernel32.closed == [1]


def test_windows_pid_probe_treats_invalid_pid_as_finished() -> None:
    kernel32 = _FakeKernel32(handle=0, last_error=87)

    assert _windows_pid_is_running(42, kernel32=kernel32) is False


def test_windows_pid_probe_fails_closed_on_access_denied() -> None:
    kernel32 = _FakeKernel32(handle=0, last_error=5)

    assert _windows_pid_is_running(42, kernel32=kernel32) is True


def test_pid_dispatch_never_calls_os_kill_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("video_channel_manager.platforms.vk.lock.os.name", "nt")
    monkeypatch.setattr("video_channel_manager.platforms.vk.lock._windows_pid_is_running", lambda pid: pid == 42)

    def destructive_probe(pid: int, signal: int) -> None:
        raise AssertionError(f"os.kill({pid}, {signal}) must not be used on Windows")

    monkeypatch.setattr("video_channel_manager.platforms.vk.lock.os.kill", destructive_probe)

    assert _pid_is_running(42) is True


def test_community_lock_path_is_deterministic_and_identity_scoped(tmp_path: Path) -> None:
    assert _canonical(tmp_path, 7) == tmp_path / "locks" / "vk-community-7.lock"
    assert _canonical(tmp_path, 8) == tmp_path / "locks" / "vk-community-8.lock"


def test_nested_lock_is_rejected_and_owner_lock_survives(tmp_path: Path) -> None:
    requested_path = tmp_path / "locks" / "outer-operation.lock"
    lock_path = _canonical(tmp_path, 7)

    with local_vk_write_lock(requested_path, account="legendary-poet", community_id=7, operation="outer"):
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["nonce"]
        with pytest.raises(VkWriteError, match="Another local VK write process"):
            with local_vk_write_lock(
                tmp_path / "locks" / "different-operation.lock",
                account="legendary-poet",
                community_id=7,
                operation="inner",
            ):
                pass
        assert lock_path.exists()
        assert not requested_path.exists()

    assert not lock_path.exists()


def test_different_operation_names_cannot_bypass_same_community_mutex(tmp_path: Path) -> None:
    first = tmp_path / "locks" / "issue-323-live-resume.lock"
    second = tmp_path / "locks" / "issue-323-finalizer.lock"

    with local_vk_write_lock(first, account="shared", community_id=68859909, operation="resume"):
        with pytest.raises(VkWriteError, match="Another local VK write process"):
            with local_vk_write_lock(second, account="shared", community_id=68859909, operation="finalizer"):
                pass


def test_different_communities_use_independent_mutexes(tmp_path: Path) -> None:
    with local_vk_write_lock(
        tmp_path / "locks" / "same-name.lock",
        account="shared",
        community_id=7,
        operation="first",
    ):
        with local_vk_write_lock(
            tmp_path / "locks" / "same-name.lock",
            account="shared",
            community_id=8,
            operation="second",
        ):
            assert _canonical(tmp_path, 7).exists()
            assert _canonical(tmp_path, 8).exists()


def test_fresh_incomplete_lock_is_not_deleted(tmp_path: Path) -> None:
    lock_path = tmp_path / "vk.lock"
    lock_path.write_text("", encoding="utf-8")

    assert _stale(lock_path, invalid_grace_seconds=30.0) is False


def test_old_incomplete_lock_is_stale(tmp_path: Path) -> None:
    lock_path = tmp_path / "vk.lock"
    lock_path.write_text("", encoding="utf-8")
    old = time.time() - 120
    os.utime(lock_path, (old, old))

    assert _stale(lock_path, invalid_grace_seconds=30.0) is True


def test_release_does_not_remove_replacement_lock(tmp_path: Path) -> None:
    requested_path = tmp_path / "locks" / "owner-operation.lock"
    lock_path = _canonical(tmp_path, 7)

    with local_vk_write_lock(requested_path, account="legendary-poet", community_id=7, operation="owner"):
        lock_path.unlink()
        lock_path.write_text(
            json.dumps({"pid": os.getpid(), "nonce": "replacement", "hostname": "replacement-host"}),
            encoding="utf-8",
        )

    assert lock_path.exists()
    lock_path.unlink()
