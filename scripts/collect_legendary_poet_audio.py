#!/usr/bin/env python3
"""Lossless local inventory/copy of MP3/WAV (+optional FLAC), with SHA-256 and CSV.

Never move, delete, transcode or edit any original. Default mode inventories only.
"""

from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import string
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

IGNORED_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "appdata",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".cache",
    "cache",
    "caches",
    ".gradle",
    ".npm",
    ".pnpm-store",
    "recovery",
}
FIELDS = ["status", "format", "bytes", "sha256", "original_path", "collected_path", "original_name"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def within(path: Path, directory: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(directory.resolve(strict=False))
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def safe_stem(text: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    text = re.sub(r"\s+", " ", text)
    return (text[:90] or "audio").rstrip(" .")


def enumerate_audio(roots: list[Path], target: Path, extensions: set[str]):
    seen_dirs: set[str] = set()
    for base in roots:
        if not base.is_dir():
            continue
        for dirname, folders, filenames in os.walk(base, topdown=True, followlinks=False):
            current = Path(dirname)
            if within(current, target):
                folders[:] = []
                continue
            normalized = os.path.normcase(str(current.resolve(strict=False)))
            if normalized in seen_dirs:
                folders[:] = []
                continue
            seen_dirs.add(normalized)
            folders[:] = sorted(
                folder
                for folder in folders
                if folder.casefold() not in IGNORED_DIRS
                and not (current / folder).is_symlink()
                and not within(current / folder, target)
            )
            for filename in sorted(filenames):
                source = current / filename
                if source.suffix.casefold() in extensions and not source.is_symlink() and not within(source, target):
                    yield source


def default_roots() -> list[Path]:
    home = Path.home()
    return [home / name for name in ("Downloads", "Desktop", "Documents", "Music", "Videos")]


def windows_drives() -> list[Path]:
    return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").is_dir()]


def collect(roots: list[Path], target: Path, copy: bool, extensions: set[str]) -> dict:
    target = target.resolve(strict=False)
    target.mkdir(parents=True, exist_ok=True)
    catalog = target / "_АУДИО_КАТАЛОГ.csv"
    unique: dict[str, Path] = {}
    summary = dict(
        mode="copy" if copy else "inventory-only",
        file_count=0,
        unique_count=0,
        exact_duplicates=0,
        copied_count=0,
        bytes_unique=0,
        errors=0,
        scan_roots=[str(p) for p in roots],
        target=str(target),
        originals_modified=False,
    )
    with catalog.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for source in enumerate_audio(roots, target, extensions):
            summary["file_count"] += 1
            try:
                size = source.stat().st_size
                digest = sha256_file(source)
                if digest in unique:
                    destination = unique[digest]
                    summary["exact_duplicates"] += 1
                    status = "duplicate_identical_bytes"
                else:
                    destination = target / (f"{safe_stem(source.stem)}__{digest[:16]}{source.suffix.lower()}")
                    unique[digest] = destination
                    summary["unique_count"] += 1
                    summary["bytes_unique"] += size
                    if destination.exists():
                        if sha256_file(destination) != digest:
                            raise RuntimeError(f"Destination conflict: {destination}")
                        status = "already_collected"
                    elif not copy:
                        status = "planned_copy"
                    else:
                        staging = target / f".{uuid.uuid4().hex}.partial"
                        try:
                            shutil.copy2(source, staging)
                            if sha256_file(staging) != digest:
                                raise RuntimeError("Copied bytes differ from original")
                            if destination.exists():
                                if sha256_file(destination) != digest:
                                    raise RuntimeError(f"Destination conflict: {destination}")
                                status = "already_collected"
                            else:
                                os.replace(staging, destination)
                                summary["copied_count"] += 1
                                status = "copied_verified"
                        finally:
                            staging.unlink(missing_ok=True)
                writer.writerow(
                    dict(
                        status=status,
                        format=source.suffix.lower().lstrip("."),
                        bytes=size,
                        sha256=digest,
                        original_path=str(source),
                        collected_path=str(destination),
                        original_name=source.name,
                    )
                )
            except (OSError, RuntimeError) as error:
                summary["errors"] += 1
                writer.writerow(
                    dict(
                        status=f"ERROR: {error}",
                        format=source.suffix.lower().lstrip("."),
                        bytes="",
                        sha256="",
                        original_path=str(source),
                        collected_path="",
                        original_name=source.name,
                    )
                )
    # Human audition playlist, using only verified files already present in target.
    # Relative paths keep it portable when the collected folder is moved as a unit.
    playlist_entries = sorted(destination.name for destination in unique.values() if destination.is_file())
    (target / "_ВСЕ_НА_ПРОСЛУШИВАНИЕ.m3u8").write_text(
        "#EXTM3U\n" + "\n".join(playlist_entries) + ("\n" if playlist_entries else ""),
        encoding="utf-8-sig",
    )
    summary["playlist_count"] = len(playlist_entries)
    summary["completed_utc"] = datetime.now(timezone.utc).isoformat()
    (target / "_АУДИО_СВОДКА.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory first; optional verified copy to one local audio folder.")
    parser.add_argument(
        "--target", type=Path, required=True, help="Choose a subfolder inside the EXISTING Legendary Poet directory"
    )
    parser.add_argument(
        "--root", type=Path, action="append", default=[], help="Scan this root recursively; repeat for more roots"
    )
    parser.add_argument(
        "--all-drives", action="store_true", help="Scan all accessible Windows drive roots (slow on large disks)"
    )
    parser.add_argument("--include-flac", action="store_true")
    parser.add_argument(
        "--copy", action="store_true", help="Copy unique hashes after validation (default: inventory only)"
    )
    args = parser.parse_args()
    roots = [*args.root, *(windows_drives() if args.all_drives else [])]
    if not roots:
        roots = default_roots()
    roots = list(dict.fromkeys(p.resolve(strict=False) for p in roots if p.is_dir()))
    if not roots:
        parser.error("No readable source roots; specify --root")
    extensions = {".mp3", ".wav"} | ({".flac"} if args.include_flac else set())
    summary = collect(roots, args.target, args.copy, extensions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
