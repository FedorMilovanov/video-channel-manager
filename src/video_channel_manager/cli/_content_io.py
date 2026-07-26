from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from video_channel_manager.editorial.content import (
    EditorialContentRecord,
    parse_content_record,
    validate_content_collection,
)

console = Console()


def json_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("*.json"))
    raise ValueError(f"Input path does not exist: {input_path}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_records(input_path: Path) -> tuple[list[EditorialContentRecord], list[str]]:
    records: list[EditorialContentRecord] = []
    errors: list[str] = []
    for path in json_paths(input_path):
        try:
            records.append(parse_content_record(read_json(path)))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
    errors.extend(validate_content_collection(records))
    return records, errors


def print_failures(failures: list[str]) -> None:
    for failure in failures:
        console.print(f"[red]ERROR:[/red] {failure}")


__all__ = [
    "console",
    "json_paths",
    "load_records",
    "print_failures",
    "read_json",
    "write_json",
]
