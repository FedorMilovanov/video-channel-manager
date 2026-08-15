from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from video_channel_manager.platforms.vk.writer import VkWriteError

_INVALID_LOCK_GRACE_SECONDS = 30.0
_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_STILL_ACTIVE = 259
_WINDOWS_ERROR_INVALID_PARAMETER = 87
_ISSUE323_COMMUNITY_ID = 68859909
_ISSUE323_OPERATION_PREFIX = "milovi-issue-323"
_ISSUE323_APPROVED_MAIN_SHA_ENV = "VCM_ISSUE323_APPROVED_MAIN_SHA"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _windows_pid_is_running(pid: int, *, kernel32: Any | None = None) -> bool:
    """Check a Windows PID without using ``os.kill``.

    Python implements ``os.kill`` on Windows through ``TerminateProcess`` for
    ordinary numeric signals, including zero. A Unix-style ``kill(pid, 0)``
    probe would therefore be destructive on the operator's Windows machine.
    """

    if pid <= 0:
        return False

    import ctypes
    from ctypes import wintypes

    if kernel32 is None:
        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            # This function is dispatched only on Windows. A missing loader is
            # therefore an uncertain state and must keep the lock active.
            return True
        api: Any = win_dll("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
    else:
        api = kernel32

    handle = api.OpenProcess(_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        if kernel32 is None:
            get_last_error = getattr(ctypes, "get_last_error", None)
            error = int(get_last_error()) if callable(get_last_error) else 0
        else:
            raw_error = getattr(api, "last_error", 0)
            error = int(raw_error) if isinstance(raw_error, int | str) else 0
        if error == _WINDOWS_ERROR_INVALID_PARAMETER:
            return False
        # Access denied and unknown failures are handled fail-closed: never
        # delete a lock merely because process liveness could not be proved.
        return True

    try:
        exit_code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == _WINDOWS_STILL_ACTIVE
    finally:
        api.CloseHandle(handle)


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_age_seconds(path: Path) -> float:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return 0.0


def _read_lock_payload(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _stale(path: Path, *, invalid_grace_seconds: float = _INVALID_LOCK_GRACE_SECONDS) -> bool:
    payload = _read_lock_payload(path)
    if payload is None:
        # A second process can observe the file in the tiny interval between
        # O_EXCL creation and metadata fsync. Treat fresh malformed/empty files
        # as active instead of deleting the first writer's lock.
        return _lock_age_seconds(path) >= max(0.0, invalid_grace_seconds)

    hostname = str(payload.get("hostname") or "").strip()
    if hostname and hostname != socket.gethostname():
        return False
    raw_pid = payload.get("pid")
    if not isinstance(raw_pid, int | str):
        return _lock_age_seconds(path) >= max(0.0, invalid_grace_seconds)
    try:
        pid = int(raw_pid)
    except ValueError:
        return _lock_age_seconds(path) >= max(0.0, invalid_grace_seconds)
    return not _pid_is_running(pid)


def _remove_stale_lock(path: Path) -> bool:
    """Atomically quarantine a stale lock before deleting it."""

    if not _stale(path):
        return False
    quarantine = path.with_name(f"{path.name}.stale-{uuid.uuid4().hex}")
    try:
        os.replace(path, quarantine)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    quarantine.unlink(missing_ok=True)
    return True


def _release_owned_lock(path: Path, nonce: str) -> None:
    payload = _read_lock_payload(path)
    if payload is None or str(payload.get("nonce") or "") != nonce:
        # The path was removed or replaced while the writer was running. Never
        # unlink a lock that may now belong to another process.
        return
    path.unlink(missing_ok=True)


def community_vk_write_lock_path(data_dir: Path, *, community_id: int) -> Path:
    """Return the one canonical local writer lock path for a VK community."""

    if community_id <= 0:
        raise ValueError("community_id must be positive")
    return Path(data_dir) / "locks" / f"vk-community-{community_id}.lock"


def _canonicalize_requested_lock_path(path: Path, *, community_id: int) -> Path:
    """Collapse operation-specific filenames into one community mutex.

    Existing callers historically supplied names such as ``...-finalizer.lock``
    and ``...-live-resume.lock``. Keeping those names as independent mutexes can
    allow concurrent writes to the same remote community. The caller still
    chooses the lock directory, but the filename is canonical and derived only
    from the exact community identity.
    """

    if community_id <= 0:
        raise ValueError("community_id must be positive")
    return Path(path).parent / f"vk-community-{community_id}.lock"


def _git_output(args: tuple[str, ...], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise VkWriteError(
            f"Cannot verify Issue #323 repository execution identity: git unavailable: {exc}",
            method="local.execution_identity",
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise VkWriteError(
            f"Cannot verify Issue #323 repository execution identity: git {' '.join(args)} failed: {detail}",
            method="local.execution_identity",
        )
    return completed.stdout.strip()


def _require_issue323_execution_identity(*, community_id: int, operation: str) -> dict[str, str] | None:
    """Fail closed unless an Issue #323 writer runs from the exact approved main checkout."""

    if community_id != _ISSUE323_COMMUNITY_ID or not operation.startswith(_ISSUE323_OPERATION_PREFIX):
        return None

    approved_sha = os.environ.get(_ISSUE323_APPROVED_MAIN_SHA_ENV, "").strip().lower()
    if not _GIT_SHA_RE.fullmatch(approved_sha):
        raise VkWriteError(
            f"Issue #323 requires {_ISSUE323_APPROVED_MAIN_SHA_ENV}=<exact 40-char approved main SHA>",
            method="local.execution_identity",
        )

    start = Path.cwd()
    root_text = _git_output(("rev-parse", "--show-toplevel"), cwd=start)
    repo_root = Path(root_text).resolve()
    branch = _git_output(("branch", "--show-current"), cwd=repo_root)
    head_sha = _git_output(("rev-parse", "HEAD"), cwd=repo_root).lower()
    origin_main_sha = _git_output(("rev-parse", "--verify", "origin/main"), cwd=repo_root).lower()
    worktree = _git_output(("status", "--porcelain=v1", "--untracked-files=normal"), cwd=repo_root)

    mismatches: list[str] = []
    if branch != "main":
        mismatches.append(f"branch={branch or '<detached>'}")
    if head_sha != approved_sha:
        mismatches.append(f"HEAD={head_sha}")
    if origin_main_sha != approved_sha:
        mismatches.append(f"origin/main={origin_main_sha}")
    if worktree:
        mismatches.append("worktree=dirty")
    if mismatches:
        raise VkWriteError(
            "Issue #323 execution identity mismatch; provider access is blocked: " + ", ".join(mismatches),
            method="local.execution_identity",
        )

    return {
        "approved_main_sha": approved_sha,
        "head_sha": head_sha,
        "origin_main_sha": origin_main_sha,
        "branch": branch,
        "repo_root": str(repo_root),
        "worktree": "clean",
    }


@contextmanager
def local_vk_write_lock(path: Path, *, account: str, community_id: int, operation: str) -> Iterator[None]:
    """Prevent two local processes from mutating the same VK community.

    The supplied path is treated as a lock-directory hint for backward
    compatibility. Its filename is never an authority boundary: all operations
    for one community converge on the same canonical filename.
    """

    if community_id <= 0:
        raise ValueError("community_id must be positive")
    account = account.strip()
    operation = operation.strip()
    if not account or not operation:
        raise ValueError("account and operation cannot be blank")

    execution_identity = _require_issue323_execution_identity(community_id=community_id, operation=operation)
    path = _canonicalize_requested_lock_path(path, community_id=community_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    nonce = uuid.uuid4().hex
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            if attempt == 0 and _remove_stale_lock(path):
                continue
            try:
                details = path.read_text(encoding="utf-8").strip()
            except OSError:
                details = "unreadable lock metadata"
            raise VkWriteError(
                "Another local VK write process is already active for this community. "
                f"Lock: {path}. Details: {details}",
                method="local.lock",
            ) from exc
        else:
            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "nonce": nonce,
                "account": account,
                "community_id": community_id,
                "operation": operation,
                "started_at": datetime.now(UTC).isoformat(),
            }
            if execution_identity is not None:
                payload["execution_identity"] = execution_identity
            encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            try:
                written = 0
                while written < len(encoded):
                    count = os.write(descriptor, encoded[written:])
                    if count <= 0:
                        raise OSError("os.write returned no progress while writing VK lock metadata")
                    written += count
                os.fsync(descriptor)
            except BaseException:
                os.close(descriptor)
                descriptor = None
                _release_owned_lock(path, nonce)
                raise
            break

    if descriptor is None:
        raise VkWriteError(f"Cannot acquire local VK write lock: {path}", method="local.lock")

    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            _release_owned_lock(path, nonce)


__all__ = ["community_vk_write_lock_path", "local_vk_write_lock"]
