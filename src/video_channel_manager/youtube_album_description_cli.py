from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from video_channel_manager.youtube_album_description import (
    AlbumDescriptionError,
    render_album_description,
    render_evidence,
)


def _read_package(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlbumDescriptionError(f"Cannot read album package {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AlbumDescriptionError("Album package JSON must be an object.")
    return payload


def _write_new_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise AlbumDescriptionError(f"Refusing to overwrite immutable rendered description: {path}") from exc


def _write_new_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise AlbumDescriptionError(f"Refusing to overwrite immutable render evidence: {path}") from exc


def render(args: argparse.Namespace) -> int:
    body_path = Path(args.body).resolve()
    package_path = Path(args.package).resolve()
    output_path = Path(args.output).resolve()
    evidence_path = Path(args.evidence).resolve()
    if output_path == evidence_path:
        raise AlbumDescriptionError("Rendered text and evidence paths must differ.")
    body = body_path.read_text(encoding="utf-8")
    package = _read_package(package_path)
    rendered = render_album_description(body, package, project_key=args.project)
    evidence = render_evidence(
        body_path=body_path,
        package_path=package_path,
        rendered=rendered,
        package=package,
    )

    _write_new_text(output_path, rendered)
    try:
        _write_new_json(evidence_path, evidence)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    print("YOUTUBE ALBUM DESCRIPTION RENDERED — LOCAL ONLY; NO PROVIDER ACCESS.")
    print(f"Description: {output_path}")
    print(f"Evidence: {evidence_path}")
    print(f"Media SHA: {evidence['final_media_sha256']}")
    print(f"Timing SHA: {evidence['timing_sha256']}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Render a YouTube album description from a verified album package.")
    root.add_argument("--project", required=True)
    root.add_argument("--body", required=True)
    root.add_argument("--package", required=True)
    root.add_argument("--output", required=True)
    root.add_argument("--evidence", required=True)
    root.set_defaults(func=render)
    return root


def run() -> None:
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (OSError, ValueError, AlbumDescriptionError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    run()
