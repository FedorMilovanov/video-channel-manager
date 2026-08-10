from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from video_channel_manager.youtube_upload_plan import UploadPlanError


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadPlanError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UploadPlanError(f"Expected JSON object: {path}")
    return payload


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise UploadPlanError(f"Refusing to overwrite immutable evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def stable_key_mutation_lock(stable_journal: Path) -> Iterator[Path]:
    lock_path = stable_journal.with_suffix(stable_journal.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("x", encoding="utf-8") as handle:
            handle.write("stable YouTube identity mutation in progress\n")
    except FileExistsError as exc:
        raise UploadPlanError(
            f"Stable upload identity is already locked: {lock_path}. "
            "Inspect the existing journal/lock; do not bypass concurrent or interrupted mutation."
        ) from exc
    try:
        yield lock_path
    finally:
        lock_path.unlink(missing_ok=True)
