from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".mts", ".m2ts"})


class LocalMediaRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    filename: str
    extension: str
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    sha256: str | None = None


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def scan_local_media(
    roots: Iterable[Path],
    *,
    include_hash: bool = False,
    extensions: frozenset[str] = VIDEO_EXTENSIONS,
) -> list[LocalMediaRecord]:
    """Read-only recursive media inventory. Files are never moved or modified."""

    records: list[LocalMediaRecord] = []
    for root in roots:
        root = root.expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(root)
        candidates = [root] if root.is_file() else root.rglob("*")
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in extensions:
                continue
            stat = candidate.stat()
            records.append(
                LocalMediaRecord(
                    path=str(candidate),
                    filename=candidate.name,
                    extension=candidate.suffix.lower(),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    sha256=_sha256(candidate) if include_hash else None,
                )
            )
    return sorted(records, key=lambda item: item.path.casefold())
