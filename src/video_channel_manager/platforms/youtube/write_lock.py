from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from video_channel_manager.platforms.youtube.writer import YouTubeWriteError


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


def _existing_lock_is_stale(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True
    return not _pid_is_running(pid)


@contextmanager
def local_youtube_write_lock(path: Path, *, account: str, channel_id: str) -> Iterator[None]:
    """Prevent two local mutation processes from writing the same channel."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None

    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            if attempt == 0 and _existing_lock_is_stale(path):
                path.unlink(missing_ok=True)
                continue
            try:
                details = path.read_text(encoding="utf-8").strip()
            except OSError:
                details = "unreadable lock metadata"
            raise YouTubeWriteError(
                "Another local YouTube write process is already active for this data directory. "
                f"Lock: {path}. Details: {details}"
            ) from exc
        else:
            payload = {
                "pid": os.getpid(),
                "account": account,
                "channel_id": channel_id,
                "started_at": datetime.now(UTC).isoformat(),
            }
            os.write(descriptor, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            os.fsync(descriptor)
            break

    if descriptor is None:
        raise YouTubeWriteError(f"Cannot acquire local YouTube write lock: {path}")

    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            path.unlink(missing_ok=True)
