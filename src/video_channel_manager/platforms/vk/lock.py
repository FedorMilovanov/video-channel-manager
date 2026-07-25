from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from video_channel_manager.platforms.vk.writer import VkWriteError


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _stale(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True
    return not _pid_is_running(pid)


@contextmanager
def local_vk_write_lock(path: Path, *, account: str, community_id: int, operation: str) -> Iterator[None]:
    """Prevent two local processes from mutating the same VK community."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            if attempt == 0 and _stale(path):
                path.unlink(missing_ok=True)
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
                "account": account,
                "community_id": community_id,
                "operation": operation,
                "started_at": datetime.now(UTC).isoformat(),
            }
            os.write(descriptor, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            os.fsync(descriptor)
            break

    if descriptor is None:
        raise VkWriteError(f"Cannot acquire local VK write lock: {path}", method="local.lock")

    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            path.unlink(missing_ok=True)


__all__ = ["local_vk_write_lock"]
