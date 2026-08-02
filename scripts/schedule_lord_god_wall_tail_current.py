#!/usr/bin/env python3
"""Windows-portable entrypoint for the theological VK wall queue.

Python on Windows may not ship the IANA time-zone database. The immutable plan
already stores explicit ``+03:00`` timestamps, so Moscow can be represented by
its fixed UTC+3 offset without downloading or installing ``tzdata``.
"""

from __future__ import annotations

import runpy
import zoneinfo
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

_ORIGINAL_ZONEINFO = zoneinfo.ZoneInfo


def _portable_zoneinfo(key: str, *args: Any, **kwargs: Any) -> timezone | zoneinfo.ZoneInfo:
    if key == "Europe/Moscow":
        return timezone(timedelta(hours=3), name="Europe/Moscow")
    return _ORIGINAL_ZONEINFO(key, *args, **kwargs)


zoneinfo.ZoneInfo = _portable_zoneinfo  # type: ignore[assignment,misc]

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("schedule_lord_god_wall_tail.py")),
        run_name="__main__",
    )
