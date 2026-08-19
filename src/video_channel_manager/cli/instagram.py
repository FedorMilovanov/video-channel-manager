from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError
from rich.console import Console

from video_channel_manager.config import get_settings
from video_channel_manager.editorial._project_profiles import LEGENDARY_POET, PROJECT_CHANNEL_IDS, PROJECT_KEYS
from video_channel_manager.editorial.instagram_video_intake import (
    InstagramVideoIntakeError,
    build_instagram_video_intake,
)
from video_channel_manager.exchange.audit_package import AuditPackage


console = Console()
instagram_app = typer.Typer(no_args_is_help=True, help="Provider-inert Instagram content preparation.")

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_LEGENDARY_POET_MAPPING = _REPOSITORY_ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
_LEGENDARY_POET_REVIEWED = _REPOSITORY_ROOT / "content" / "youtube-comments"


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _load_mapping(path: Path) -> tuple[dict[str, str], str]:
    raw = _read_bytes(path)
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid mapping JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping JSON object: {path}")

    mapping: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError(f"mapping contains an invalid YouTube video ID: {raw_key!r}")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError(f"mapping contains an invalid provider target for {raw_key!r}")
        mapping[raw_key.strip()] = raw_value.strip()
    return mapping, _sha256_bytes(raw)


def _load_reviewed_video_ids(path: Path, *, project_key: str) -> tuple[set[str], str]:
    if not path.is_dir():
        raise ValueError(f"reviewed editorial directory does not exist: {path}")

    expected_channels = PROJECT_CHANNEL_IDS.get(project_key, frozenset())
    ids: set[str] = set()
    digest = hashlib.sha256()
    for source_path in sorted(path.glob("*.json"), key=lambda item: item.name):
        raw = _read_bytes(source_path)
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid reviewed editorial JSON {source_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"expected reviewed editorial JSON object: {source_path}")

        video_id = payload.get("video_id")
        channel_id = payload.get("channel_id")
        if not isinstance(video_id, str) or video_id.strip() != source_path.stem:
            raise ValueError(f"reviewed editorial video_id does not match filename: {source_path}")
        if not isinstance(channel_id, str) or channel_id.strip() not in expected_channels:
            raise ValueError(f"reviewed editorial channel does not match project {project_key}: {source_path}")
        if video_id in ids:
            raise ValueError(f"duplicate reviewed editorial video_id: {video_id}")
        ids.add(video_id)

        digest.update(source_path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")

    return ids, f"sha256:{digest.hexdigest()}"


def _resolve_supporting_sources(
    *,
    project_key: str,
    mapping_path: Path | None,
    reviewed_dir: Path | None,
) -> tuple[dict[str, str], str | None, set[str], str | None]:
    if project_key == LEGENDARY_POET:
        mapping_path = mapping_path or _LEGENDARY_POET_MAPPING
        reviewed_dir = reviewed_dir or _LEGENDARY_POET_REVIEWED

    if mapping_path is None:
        mapping: dict[str, str] = {}
        mapping_sha256 = None
    else:
        mapping, mapping_sha256 = _load_mapping(mapping_path)

    if reviewed_dir is None:
        reviewed_ids: set[str] = set()
        reviewed_sha256 = None
    else:
        reviewed_ids, reviewed_sha256 = _load_reviewed_video_ids(reviewed_dir, project_key=project_key)

    return mapping, mapping_sha256, reviewed_ids, reviewed_sha256


def _read_audit_package(path: Path) -> tuple[AuditPackage, str]:
    raw = _read_bytes(path)
    try:
        audit = AuditPackage.model_validate_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid AuditPackage {path}: {exc}") from exc
    return audit, _sha256_bytes(raw)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


@instagram_app.command("video-intake")
def video_intake(
    audit_package: Annotated[Path, typer.Argument(help="Exact read-only YouTube AuditPackage JSON")],
    project_key: Annotated[str, typer.Option("--project", help="Canonical repository project_key")],
    mapping: Annotated[
        Path | None,
        typer.Option("--mapping", help="Optional exact YouTube→provider identity mapping JSON"),
    ] = None,
    reviewed_dir: Annotated[
        Path | None,
        typer.Option("--reviewed-dir", help="Optional directory of reviewed YouTube editorial records"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Build an immutable-evidence, provider-inert Instagram video intake artifact."""

    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        choices = ", ".join(sorted(PROJECT_KEYS))
        console.print(f"[red]Unknown project:[/red] {project_key}. Registered projects: {choices}")
        raise typer.Exit(code=2)

    try:
        audit, audit_sha256 = _read_audit_package(audit_package)
        mapping_payload, mapping_sha256, reviewed_ids, reviewed_sha256 = _resolve_supporting_sources(
            project_key=normalized_project,
            mapping_path=mapping,
            reviewed_dir=reviewed_dir,
        )
        result = build_instagram_video_intake(
            audit,
            project_key=normalized_project,
            frozen_youtube_vk_mapping=mapping_payload,
            reviewed_video_ids=reviewed_ids,
            source_audit_sha256=audit_sha256,
            frozen_mapping_sha256=mapping_sha256,
            reviewed_corpus_sha256=reviewed_sha256,
        )
    except (InstagramVideoIntakeError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram video intake failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = settings.data_dir / "reports" / f"instagram-{normalized_project}-{audit.snapshot_id}-video-intake.json"
    _write_json(output, result)

    counts = result["counts"]
    console.print(
        f"[green]Built provider-inert Instagram video intake → {output}[/green]\n"
        f"Project: {normalized_project} | Current: {counts['current_videos']} | "
        f"New vs mapping: {counts['new_current_vs_frozen_mapping']} | "
        f"Format unknown: {counts['format_unknown']}"
    )
