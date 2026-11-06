from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TextIO

# Reserve enough room for the before-description backup, the result journal,
# and repeated postflight updates. A zero-space disk is a pre-dispatch stop.
COPY_JOURNAL_MIN_FREE_BYTES = 16 * 1024 * 1024


def make_console_text_safe(stream: TextIO) -> None:
    """Avoid UnicodeEncodeError on Windows terminals using cp1252 or cp866."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors="backslashreplace")
        except (OSError, ValueError):
            # Some embedding/redirected streams do not support reconfigure.
            pass


def prepare_windows_youtube_console() -> None:
    """Do not let presentation encoding failures trigger provider rollback."""

    if os.name == "nt":
        make_console_text_safe(sys.stdout)
        make_console_text_safe(sys.stderr)


def reserve_youtube_copy_journals(
    *,
    plan_path: Path,
    backup_output: Path,
    result_output: Path,
    min_free_bytes: int = COPY_JOURNAL_MIN_FREE_BYTES,
) -> None:
    """Fail closed before videos.update, and prevent replacing old receipts.

    This reserves both journal paths exclusively under the caller's YouTube
    single-writer lock. The CLI atomically replaces these placeholders with a
    full backup and a durable started-result before dispatching any mutation.
    A leftover reservation is intentionally evidence of an interrupted run,
    never permission to replay that run.
    """

    plan = plan_path.resolve()
    backup = backup_output.resolve()
    result = result_output.resolve()
    if len({plan, backup, result}) != 3:
        raise ValueError("YouTube plan, backup, and result paths must be three different files.")
    if min_free_bytes < 0:
        raise ValueError("min_free_bytes must be nonnegative")

    for output in (backup, result):
        output.parent.mkdir(parents=True, exist_ok=True)

    # Check all paths/volumes before reserving the first path.
    for output in (backup, result):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite an existing YouTube output: {output}")
        available = shutil.disk_usage(output.parent).free
        if available < min_free_bytes:
            raise OSError(
                f"Insufficient free space for YouTube recovery journals at {output.parent}: "
                f"{available} available, {min_free_bytes} required."
            )

    reserved: list[Path] = []
    try:
        for output in (backup, result):
            with output.open("x", encoding="utf-8") as file:
                reserved.append(output)
                file.write(
                    '{"schema_name":"video-manager.youtube-copy-output-reservation",'
                    '"schema_version":1,"provider_dispatch":"not_started"}\n'
                )
                file.flush()
                os.fsync(file.fileno())
    except BaseException:
        # No provider mutation has occurred. Clean only paths reserved by this
        # invocation; an already-existing output is never touched.
        for output in reversed(reserved):
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
        raise
