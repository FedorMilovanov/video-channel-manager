from __future__ import annotations

import json
import os
import socket
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from video_channel_manager.platforms.youtube.writer import YouTubeWriteError

_INVALID_LOCK_GRACE_SECONDS = 30.0
_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_STILL_ACTIVE = 259
_WINDOWS_ERROR_INVALID_PARAMETER = 87


def _windows_pid_is_running(pid: int, *, kernel32: Any | None = None) -> bool:
    """Check a Windows PID without destructive ``os.kill`` semantics."""

    if pid <= 0:
        return False

    import ctypes
    from ctypes import wintypes

    api = kernel32 if kernel32 is not None else ctypes.WinDLL("kernel32", use_last_error=True)
    if kernel32 is None:
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL

    handle = api.OpenProcess(_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        error = ctypes.get_last_error() if kernel32 is None else int(getattr(api, "last_error", 0))
        if error == _WINDOWS_ERROR_INVALID_PARAMETER:
            return False
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


def _existing_lock_is_stale(
    path: Path,
    *,
    invalid_grace_seconds: float = _INVALID_LOCK_GRACE_SECONDS,
) -> bool:
    payload = _read_lock_payload(path)
    if payload is None:
        return _lock_age_seconds(path) >= max(0.0, invalid_grace_seconds)

    hostname = str(payload.get("hostname") or "").strip()
    if hostname and hostname != socket.gethostname():
        return False
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        return _lock_age_seconds(path) >= max(0.0, invalid_grace_seconds)
    return not _pid_is_running(pid)


def _remove_stale_lock(path: Path) -> bool:
    if not _existing_lock_is_stale(path):
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
        return
    path.unlink(missing_ok=True)


@contextmanager
def local_youtube_write_lock(path: Path, *, account: str, channel_id: str) -> Iterator[None]:
    """Prevent two local mutation processes from writing the same channel."""

    account = account.strip()
    channel_id = channel_id.strip()
    if not account or not channel_id:
        raise ValueError("account and channel_id cannot be blank")

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
            raise YouTubeWriteError(
                "Another local YouTube write process is already active for this channel. "
                f"Lock: {path}. Details: {details}"
            ) from exc
        else:
            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "nonce": nonce,
                "account": account,
                "channel_id": channel_id,
                "started_at": datetime.now(UTC).isoformat(),
            }
            encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            try:
                written = 0
                while written < len(encoded):
                    count = os.write(descriptor, encoded[written:])
                    if count <= 0:
                        raise OSError("os.write returned no progress while writing YouTube lock metadata")
                    written += count
                os.fsync(descriptor)
            except BaseException:
                os.close(descriptor)
                descriptor = None
                _release_owned_lock(path, nonce)
                raise
            break

    if descriptor is None:
        raise YouTubeWriteError(f"Cannot acquire local YouTube write lock: {path}")

    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            _release_owned_lock(path, nonce)


__all__ = ["local_youtube_write_lock"]
