from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TypeVar, TypedDict

from pydantic import BaseModel, ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.lordchrist_shorts import (
    PROJECT_KEY,
    YOUTUBE_CHANNEL_ID,
    CandidateApprovalManifest,
    HistoricalDurationBaseline,
    LordChristShortsMediaAcceptance,
    OwnerMediaBindingManifest,
    _load_audit,
    _write_model,
    build_backlog_status,
    build_inventory,
    load_bindings,
    load_candidate_approval,
    load_historical_baseline,
    load_inventory,
    load_media_acceptance,
    reconcile_historical_baseline,
)
from video_channel_manager.lordchrist_shorts_snapshot_readiness import require_snapshot_ready

ModelT = TypeVar("ModelT", bound=BaseModel)

_WAVE_FILENAMES = (
    "snapshot-readiness.json",
    "shorts-inventory.json",
    "baseline-reconciliation.json",
    "backlog-status.json",
    "manifest.json",
)


class WaveBuildSummary(TypedDict):
    source_snapshot_id: str
    inventory_item_count: int
    accepted: int
    media_missing: int
    candidate_unconfirmed: int
    output_dir: str
    provider_access_performed: bool
    provider_write_performed: bool
    release_authorized: bool


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_frozen_model(path: Path, model: type[ModelT], *, label: str) -> tuple[ModelT, bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    try:
        value = model.model_validate_json(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid {label} file {path}: {exc}") from exc
    return value, raw, _digest_bytes(raw)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _model_bytes(value: BaseModel) -> bytes:
    return (value.model_dump_json(indent=2) + "\n").encode("utf-8")


def _source_manifest_entry(path: Path, digest: str) -> dict[str, object]:
    return {"path": str(path), "sha256": digest}


def _artifact_manifest_entry(data: bytes) -> dict[str, object]:
    return {"sha256": _digest_bytes(data), "byte_size": len(data)}


def _publish_wave_directory(output_dir: Path, files: dict[str, bytes]) -> None:
    if output_dir.exists():
        raise ValueError(f"wave output directory already exists: {output_dir}")
    if set(files) != set(_WAVE_FILENAMES):
        raise ValueError("wave publication requires the complete fixed artifact set")

    parent = output_dir.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=parent))
    except OSError as exc:
        raise ValueError(f"cannot create wave staging directory beside {output_dir}: {exc}") from exc

    try:
        for filename in _WAVE_FILENAMES:
            (staging / filename).write_bytes(files[filename])
        if output_dir.exists():
            raise ValueError(f"wave output directory appeared during publication: {output_dir}")
        staging.rename(output_dir)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(f"cannot atomically publish wave directory {output_dir}: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def build_wave(
    *,
    audit_path: Path,
    baseline_path: Path,
    output_dir: Path,
    bindings_path: Path | None = None,
    media_path: Path | None = None,
    candidate_approval_path: Path | None = None,
    as_of: datetime | None = None,
    max_age_hours: int = 48,
) -> WaveBuildSummary:
    """Build and publish one provider-inert evidence wave from one frozen source snapshot."""
    if output_dir.exists():
        raise ValueError(f"wave output directory already exists: {output_dir}")

    package, _audit_raw, audit_digest = _load_frozen_model(
        audit_path,
        AuditPackage,
        label="YouTube AuditPackage",
    )
    readiness = require_snapshot_ready(package, as_of=as_of, max_age_hours=max_age_hours)

    baseline, _baseline_raw, baseline_digest = _load_frozen_model(
        baseline_path,
        HistoricalDurationBaseline,
        label="HistoricalDurationBaseline",
    )
    inventory = build_inventory(package)
    reconciliation = reconcile_historical_baseline(
        package,
        baseline,
        source_baseline_sha256=baseline_digest,
        as_of=as_of,
        max_age_hours=max_age_hours,
    )

    sources: dict[str, dict[str, object]] = {
        "audit": _source_manifest_entry(audit_path, audit_digest),
        "baseline": _source_manifest_entry(baseline_path, baseline_digest),
    }

    bindings: OwnerMediaBindingManifest | None = None
    if bindings_path is not None:
        bindings, _raw, digest = _load_frozen_model(
            bindings_path,
            OwnerMediaBindingManifest,
            label="OwnerMediaBindingManifest",
        )
        sources["bindings"] = _source_manifest_entry(bindings_path, digest)

    media: LordChristShortsMediaAcceptance | None = None
    if media_path is not None:
        media, _raw, digest = _load_frozen_model(
            media_path,
            LordChristShortsMediaAcceptance,
            label="LordChristShortsMediaAcceptance",
        )
        sources["media"] = _source_manifest_entry(media_path, digest)

    candidate_approval: CandidateApprovalManifest | None = None
    if candidate_approval_path is not None:
        candidate_approval, _raw, digest = _load_frozen_model(
            candidate_approval_path,
            CandidateApprovalManifest,
            label="CandidateApprovalManifest",
        )
        sources["candidate_approval"] = _source_manifest_entry(candidate_approval_path, digest)

    backlog = build_backlog_status(
        inventory,
        bindings=bindings,
        acceptance=media,
        candidate_approval=candidate_approval,
    )

    readiness_bytes = _json_bytes(readiness)
    inventory_bytes = _model_bytes(inventory)
    reconciliation_bytes = _model_bytes(reconciliation)
    backlog_bytes = _model_bytes(backlog)
    artifact_bytes = {
        "snapshot-readiness.json": readiness_bytes,
        "shorts-inventory.json": inventory_bytes,
        "baseline-reconciliation.json": reconciliation_bytes,
        "backlog-status.json": backlog_bytes,
    }
    manifest = {
        "schema_name": "video-channel-manager.lordchrist-shorts-wave-manifest",
        "schema_version": 1,
        "project_key": PROJECT_KEY,
        "youtube_channel_id": YOUTUBE_CHANNEL_ID,
        "source_snapshot_id": inventory.source_snapshot_id,
        "generated_at": readiness["evaluated_at"],
        "provider_access_performed": False,
        "provider_write_performed": False,
        "release_authorized": False,
        "sources": sources,
        "artifacts": {
            filename: _artifact_manifest_entry(data) for filename, data in artifact_bytes.items()
        },
        "counts": {
            "inventory_item_count": backlog.counts.inventory_item_count,
            "accepted": backlog.counts.accepted,
            "media_missing": backlog.counts.media_missing,
            "candidate_unconfirmed": backlog.counts.candidate_unconfirmed,
            "historical_item_count": reconciliation.counts.historical_item_count,
            "new_shorts_not_in_baseline": reconciliation.counts.new_shorts_not_in_baseline,
            "new_candidates_not_in_baseline": reconciliation.counts.new_candidates_not_in_baseline,
        },
    }
    files = dict(artifact_bytes)
    files["manifest.json"] = _json_bytes(manifest)
    _publish_wave_directory(output_dir, files)

    return WaveBuildSummary(
        source_snapshot_id=inventory.source_snapshot_id,
        inventory_item_count=backlog.counts.inventory_item_count,
        accepted=backlog.counts.accepted,
        media_missing=backlog.counts.media_missing,
        candidate_unconfirmed=backlog.counts.candidate_unconfirmed,
        output_dir=str(output_dir),
        provider_access_performed=False,
        provider_write_performed=False,
        release_authorized=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Provider-inert LordChrist Shorts artifact reconciliation and backlog reporting."
    )
    sub = root.add_subparsers(dest="command", required=True)

    reconcile = sub.add_parser("reconcile-baseline")
    reconcile.add_argument("--audit", type=Path, required=True)
    reconcile.add_argument("--baseline", type=Path, required=True)
    reconcile.add_argument("--output", type=Path, required=True)
    reconcile.add_argument("--max-age-hours", type=int, default=48)

    backlog = sub.add_parser("backlog-status")
    backlog.add_argument("--inventory", type=Path, required=True)
    backlog.add_argument("--output", type=Path, required=True)
    backlog.add_argument("--bindings", type=Path)
    backlog.add_argument("--media", type=Path)
    backlog.add_argument("--candidate-approval", type=Path)

    wave = sub.add_parser("build-wave")
    wave.add_argument("--audit", type=Path, required=True)
    wave.add_argument("--baseline", type=Path, required=True)
    wave.add_argument("--output-dir", type=Path, required=True)
    wave.add_argument("--bindings", type=Path)
    wave.add_argument("--media", type=Path)
    wave.add_argument("--candidate-approval", type=Path)
    wave.add_argument("--max-age-hours", type=int, default=48)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "reconcile-baseline":
            package = _load_audit(args.audit)
            baseline, digest = load_historical_baseline(args.baseline)
            result = reconcile_historical_baseline(
                package,
                baseline,
                source_baseline_sha256=digest,
                max_age_hours=args.max_age_hours,
            )
            _write_model(args.output, result)
            print(
                json.dumps(
                    {
                        "historical_item_count": result.counts.historical_item_count,
                        "present_as_short": result.counts.present_as_short,
                        "present_as_candidate": result.counts.present_as_candidate,
                        "present_as_longform": result.counts.present_as_longform,
                        "present_unresolved": result.counts.present_unresolved,
                        "absent_from_snapshot": result.counts.absent_from_snapshot,
                        "new_shorts_not_in_baseline": result.counts.new_shorts_not_in_baseline,
                        "new_candidates_not_in_baseline": result.counts.new_candidates_not_in_baseline,
                        "compared_snapshot_id": result.compared_snapshot_id,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "backlog-status":
            inventory = load_inventory(args.inventory)
            status = build_backlog_status(
                inventory,
                bindings=load_bindings(args.bindings) if args.bindings else None,
                acceptance=load_media_acceptance(args.media) if args.media else None,
                candidate_approval=(
                    load_candidate_approval(args.candidate_approval) if args.candidate_approval else None
                ),
            )
            _write_model(args.output, status)
            print(
                json.dumps(
                    {
                        "inventory_item_count": status.counts.inventory_item_count,
                        "accepted": status.counts.accepted,
                        "media_missing": status.counts.media_missing,
                        "candidate_unconfirmed": status.counts.candidate_unconfirmed,
                        "release_authorized": status.release_authorized,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "build-wave":
            summary = build_wave(
                audit_path=args.audit,
                baseline_path=args.baseline,
                output_dir=args.output_dir,
                bindings_path=args.bindings,
                media_path=args.media,
                candidate_approval_path=args.candidate_approval,
                max_age_hours=args.max_age_hours,
            )
            print(json.dumps(summary, ensure_ascii=False))
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
