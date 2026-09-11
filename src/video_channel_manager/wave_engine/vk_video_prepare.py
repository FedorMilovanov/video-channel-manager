from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.application.cross_platform import compare_audit_packages
from video_channel_manager.domain.enums import PlatformName
from video_channel_manager.editorial._project_profiles import (
    PROJECT_CHANNEL_IDS,
    PROJECT_VK_COMMUNITY_IDS,
)
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.local_media.artifact import (
    MediaSourceIdentity,
    acquisition_from_structured_result,
    load_media_artifact_manifest,
    probe_media_artifact,
    validate_cached_media_artifact,
    write_media_artifact_manifest,
)
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic
from video_channel_manager.wave_engine.models import (
    EvidenceArtifact,
    MutationClass,
    ProjectBinding,
    WaveApplyIntent,
    WaveOperationSpec,
    WavePlan,
    WaveSourceEvidence,
)
from video_channel_manager.wave_engine.vk_video_provider import (
    VK_VIDEO_DEFAULT_ACCOUNT_ALIAS,
    VK_VIDEO_OPERATION_KIND,
    VK_VIDEO_POLICY_VERSION,
)


class VkVideoPreparationError(RuntimeError):
    pass


def _repo_relative(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise VkVideoPreparationError(f"Evidence path must remain inside repository root: {resolved}") from exc
    return relative.as_posix()


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValidationError) as exc:
        raise VkVideoPreparationError(f"Invalid AuditPackage {path}: {exc}") from exc


def _single_project_value(values: Iterable[Any], *, field: str) -> Any:
    selected = tuple(values)
    if len(selected) != 1:
        raise VkVideoPreparationError(f"Project must have exactly one registered {field}")
    return selected[0]


def _copy_exact(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if file_sha256(source) != file_sha256(destination):
        raise VkVideoPreparationError(f"Copied evidence SHA-256 mismatch: {destination}")
    return destination


def _yt_dlp_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise VkVideoPreparationError("yt-dlp --version failed")
    return completed.stdout.strip().splitlines()[0].strip()


def _acquire_media(
    *,
    project_key: str,
    source_channel_id: str,
    video: Any,
    media_directory: Path,
    manifests_directory: Path,
    acquisition_directory: Path,
    yt_dlp: str,
    tool_version: str,
) -> tuple[Path, Path, Path]:
    source_id = video.ref.remote_id
    requested_output = media_directory / f"{source_id}.mp4"
    proof_path = acquisition_directory / f"{source_id}.final-path.txt"
    result_path = acquisition_directory / f"{source_id}.json"
    output_template = str(media_directory / f"{source_id}.%(ext)s")

    completed = subprocess.run(
        [
            yt_dlp,
            "--no-playlist",
            "--no-progress",
            "--newline",
            "--format",
            "bv*+ba/b",
            "--format-sort",
            "vcodec:h264,acodec:aac",
            "--merge-output-format",
            "mp4",
            "--remux-video",
            "mp4",
            "--output",
            output_template,
            "--print-to-file",
            "after_move:filepath",
            str(proof_path),
            f"https://www.youtube.com/watch?v={source_id}",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()[-2000:]
        raise VkVideoPreparationError(f"yt-dlp failed for {source_id}: {stderr}")
    if not proof_path.is_file():
        raise VkVideoPreparationError(f"yt-dlp produced no exact final-path proof for {source_id}")
    proof_lines = [line.strip() for line in proof_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(proof_lines) != 1:
        raise VkVideoPreparationError(
            f"yt-dlp final-path proof for {source_id} must contain exactly one path, got {len(proof_lines)}"
        )
    final_path = Path(proof_lines[0]).expanduser().resolve()
    if not final_path.is_file():
        raise VkVideoPreparationError(f"yt-dlp reported missing final file for {source_id}: {final_path}")
    try:
        final_path.relative_to(media_directory.resolve())
    except ValueError as exc:
        raise VkVideoPreparationError(f"yt-dlp final path escaped media directory for {source_id}") from exc
    if final_path.suffix.lower() != ".mp4":
        raise VkVideoPreparationError(f"yt-dlp final media is not MP4 for {source_id}: {final_path}")

    result = {
        "schema_name": "video-manager.yt-dlp-acquisition-result",
        "schema_version": 1,
        "project_key": project_key,
        "source_channel_id": source_channel_id,
        "source_video_id": source_id,
        "source_url": f"https://www.youtube.com/watch?v={source_id}",
        "final_path": str(final_path),
        "tool_name": "yt-dlp",
        "tool_version": tool_version,
    }
    write_json_atomic(result_path, result)
    structured = acquisition_from_structured_result(
        result,
        method="yt_dlp",
        result_path=("final_path",),
        requested_output_path=requested_output,
        tool_name="yt-dlp",
        tool_version=tool_version,
    )
    identity = MediaSourceIdentity(
        project_key=project_key,
        platform=PlatformName.YOUTUBE,
        source_channel_id=source_channel_id,
        source_id=source_id,
        source_url=f"https://www.youtube.com/watch?v={source_id}",
        source_revision=video.revision,
        expected_duration_seconds=float(video.duration_seconds),
    )
    artifact = probe_media_artifact(
        source=identity,
        acquisition=structured.acquisition,
    )
    manifest_path = manifests_directory / f"{source_id}.json"
    write_media_artifact_manifest(artifact, manifest_path)
    return final_path, manifest_path, result_path


def _reuse_media_manifest(
    *,
    manifest_path: Path,
    repository_root: Path,
    project_key: str,
    source_channel_id: str,
    source_id: str,
    source_duration_seconds: int,
) -> tuple[Path, Path]:
    try:
        manifest_path = manifest_path.resolve()
        manifest_path.relative_to(repository_root)
    except ValueError as exc:
        raise VkVideoPreparationError(
            f"Reusable media manifest must already be inside repository root: {manifest_path}"
        ) from exc
    artifact = load_media_artifact_manifest(manifest_path)
    media_path = Path(artifact.acquisition.authoritative_final_path).resolve()
    try:
        media_path.relative_to(repository_root)
    except ValueError as exc:
        raise VkVideoPreparationError(
            f"Reusable authoritative media must be inside repository root: {media_path}"
        ) from exc
    validate_cached_media_artifact(
        artifact,
        expected_project_key=project_key,
        expected_source_platform=PlatformName.YOUTUBE,
        expected_source_channel_id=source_channel_id,
        expected_source_id=source_id,
        expected_source_duration_seconds=float(source_duration_seconds),
        expected_path=media_path,
    )
    return media_path, manifest_path


def _build_scope(
    *,
    repository_root: Path,
    scope_directory: Path,
    project: ProjectBinding,
    artifact_paths: Sequence[Path],
    specs: Sequence[WaveOperationSpec],
    account_alias: str,
) -> dict[str, Any]:
    scope_directory.mkdir(parents=True, exist_ok=False)
    operations_path = scope_directory / "operations.json"
    write_json_atomic(
        operations_path,
        [spec.model_dump(mode="json") for spec in specs],
    )
    source_artifacts = tuple(
        EvidenceArtifact(
            path=_repo_relative(repository_root, path),
            sha256=file_sha256(path),
        )
        for path in sorted(set(artifact_paths), key=lambda item: _repo_relative(repository_root, item))
    )
    source = WaveSourceEvidence.build(
        project=project,
        policy_version=VK_VIDEO_POLICY_VERSION,
        artifacts=source_artifacts,
    )
    source_path = scope_directory / "source.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
    plan = WavePlan.build(source=source, specs=tuple(specs))
    plan_path = scope_directory / "plan.json"
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path=_repo_relative(repository_root, source_path),
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path=_repo_relative(repository_root, plan_path),
        plan_file_sha256=file_sha256(plan_path),
        enable_provider_writes=True,
    )
    intent_path = scope_directory / "intent.json"
    write_json_atomic(intent_path, intent.model_dump(mode="json"))

    journal_directory = scope_directory / "journal"
    manifest_path = scope_directory / "operator-manifest.json"
    manifest = {
        "schema_name": "video-manager.operator-manifest",
        "schema_version": 1,
        "project_key": project.project_key,
        "community_id": project.community_id,
        "owner_id": project.owner_id,
        "source_snapshot_id": source.source_snapshot_id,
        "operation_count": len(plan.operations),
        "operation_class": "ambiguous_mutation",
        "provider_mutation": True,
        "entrypoint_id": "video-manager-cli",
        "arguments": [
            "wave",
            "apply",
            "--source",
            _repo_relative(repository_root, source_path),
            "--plan",
            _repo_relative(repository_root, plan_path),
            "--intent",
            _repo_relative(repository_root, intent_path),
            "--repository-root",
            str(repository_root.resolve()),
            "--journal-directory",
            _repo_relative(repository_root, journal_directory),
            "--vk-account",
            account_alias,
            "--enable-provider-writes",
        ],
    }
    write_json_atomic(manifest_path, manifest)
    manifest_sha256 = file_sha256(manifest_path)
    request_path = scope_directory / "operator-request.json"
    request = {
        "schema_name": "video-manager.operator-request",
        "schema_version": 1,
        "mode": "apply",
        "manifest_path": _repo_relative(repository_root, manifest_path),
        "manifest_sha256": manifest_sha256,
        "confirm_manifest_sha256": manifest_sha256,
        "confirm_project_key": project.project_key,
        "confirm_community_id": project.community_id,
        "confirm_owner_id": project.owner_id,
        "confirm_source_snapshot_id": source.source_snapshot_id,
        "confirm_operation_count": len(plan.operations),
    }
    write_json_atomic(request_path, request)
    return {
        "scope": scope_directory.name,
        "operation_count": len(plan.operations),
        "source_snapshot_id": source.source_snapshot_id,
        "source_self_digest": source.self_digest,
        "plan_self_digest": plan.self_digest,
        "operation_set_digest": plan.operation_set_digest,
        "intent_self_digest": intent.self_digest,
        "request_path": _repo_relative(repository_root, request_path),
        "request_sha256": file_sha256(request_path),
        "manifest_path": _repo_relative(repository_root, manifest_path),
        "manifest_sha256": manifest_sha256,
        "journal_path": _repo_relative(repository_root, journal_directory),
    }


def prepare_vk_video_wave(
    *,
    project_key: str,
    source_audit_path: Path,
    target_audit_path: Path,
    candidate_ids: Sequence[str],
    canary_id: str,
    repository_root: Path,
    output_root: Path,
    account_alias: str = VK_VIDEO_DEFAULT_ACCOUNT_ALIAS,
    yt_dlp: str = "yt-dlp",
    reuse_media_manifests: Sequence[Path] = (),
    processing_timeout_seconds: int = 3600,
) -> dict[str, Any]:
    root = repository_root.resolve()
    output = output_root.resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise VkVideoPreparationError("Video wave output root must remain inside repository root") from exc
    if output.exists():
        raise VkVideoPreparationError(f"Video wave output root already exists; overwrite is prohibited: {output}")
    if processing_timeout_seconds <= 0:
        raise VkVideoPreparationError("processing_timeout_seconds must be positive")

    source = _load_audit(source_audit_path.resolve())
    target = _load_audit(target_audit_path.resolve())

    expected_channel = str(_single_project_value(PROJECT_CHANNEL_IDS.get(project_key, ()), field="YouTube channel"))
    expected_community = int(_single_project_value(PROJECT_VK_COMMUNITY_IDS.get(project_key, ()), field="VK community"))
    if source.channel.ref.platform is not PlatformName.YOUTUBE:
        raise VkVideoPreparationError("Source AuditPackage must be YouTube")
    if source.channel.ref.channel_id != expected_channel:
        raise VkVideoPreparationError(
            f"Source channel mismatch: expected {expected_channel}, got {source.channel.ref.channel_id}"
        )
    if target.channel.ref.platform is not PlatformName.VK:
        raise VkVideoPreparationError("Target AuditPackage must be VK")
    if int(target.channel.ref.channel_id) != expected_community:
        raise VkVideoPreparationError(
            f"Target community mismatch: expected {expected_community}, got {target.channel.ref.channel_id}"
        )

    normalized_candidates = tuple(dict.fromkeys(value.strip() for value in candidate_ids if value.strip()))
    if not normalized_candidates:
        raise VkVideoPreparationError("At least one exact candidate ID is required")
    if len(normalized_candidates) != len(candidate_ids):
        raise VkVideoPreparationError("Candidate IDs must be nonblank and unique")
    if canary_id not in normalized_candidates:
        raise VkVideoPreparationError("Canary ID must be one of the exact candidate IDs")

    comparison = compare_audit_packages(source, target, project_key=project_key)
    missing_ids = {item.ref.remote_id for item in comparison.missing_on_target}
    source_by_id = {item.ref.remote_id: item for item in source.videos}
    conflict_source_ids = {ref.remote_id for conflict in comparison.conflicts for ref in conflict.source_refs}
    for source_id in normalized_candidates:
        video = source_by_id.get(source_id)
        if video is None:
            raise VkVideoPreparationError(f"Candidate is absent from YouTube snapshot: {source_id}")
        if source_id not in missing_ids:
            raise VkVideoPreparationError(f"Candidate is not proof-backed missing on target: {source_id}")
        if source_id in conflict_source_ids:
            raise VkVideoPreparationError(f"Candidate participates in an ambiguous/conflicting match: {source_id}")
        if video.privacy_status != "public":
            raise VkVideoPreparationError(f"Candidate is not public: {source_id}")
        if video.duration_seconds is None or video.duration_seconds <= 180:
            raise VkVideoPreparationError(f"Candidate is not long-form (>180s): {source_id}")

    output.mkdir(parents=True, exist_ok=False)
    evidence_directory = output / "evidence"
    media_directory = output / "media"
    manifests_directory = output / "media-manifests"
    acquisition_directory = output / "acquisition"
    for directory in (evidence_directory, media_directory, manifests_directory, acquisition_directory):
        directory.mkdir(parents=True, exist_ok=True)

    source_copy = _copy_exact(source_audit_path.resolve(), evidence_directory / "youtube-source.json")
    target_copy = _copy_exact(target_audit_path.resolve(), evidence_directory / "vk-target.json")
    comparison_path = evidence_directory / "comparison.json"
    write_json_atomic(comparison_path, comparison.model_dump(mode="json"))

    reuse_by_id: dict[str, Path] = {}
    for raw_manifest in reuse_media_manifests:
        artifact = load_media_artifact_manifest(raw_manifest.resolve())
        source_id = artifact.source.source_id
        if source_id in reuse_by_id:
            raise VkVideoPreparationError(f"Duplicate reusable media manifest for {source_id}")
        reuse_by_id[source_id] = raw_manifest.resolve()

    executable = shutil.which(yt_dlp) or (str(Path(yt_dlp).resolve()) if Path(yt_dlp).is_file() else None)
    need_download = any(source_id not in reuse_by_id for source_id in normalized_candidates)
    if need_download and executable is None:
        raise VkVideoPreparationError(f"yt-dlp executable not found: {yt_dlp}")
    tool_version = _yt_dlp_version(executable) if need_download and executable is not None else ""

    shared_artifacts: list[Path] = [source_copy, target_copy, comparison_path]
    specs_by_id: dict[str, WaveOperationSpec] = {}
    media_summary: list[dict[str, Any]] = []

    for source_id in normalized_candidates:
        video = source_by_id[source_id]
        duration_seconds = video.duration_seconds
        if duration_seconds is None:
            raise VkVideoPreparationError(f"Validated candidate lost duration evidence: {source_id}")
        if source_id in reuse_by_id:
            media_path, media_manifest_path = _reuse_media_manifest(
                manifest_path=reuse_by_id[source_id],
                repository_root=root,
                project_key=project_key,
                source_channel_id=expected_channel,
                source_id=source_id,
                source_duration_seconds=duration_seconds,
            )
            acquisition_result_path = None
        else:
            assert executable is not None
            media_path, media_manifest_path, acquisition_result_path = _acquire_media(
                project_key=project_key,
                source_channel_id=expected_channel,
                video=video,
                media_directory=media_directory,
                manifests_directory=manifests_directory,
                acquisition_directory=acquisition_directory,
                yt_dlp=executable,
                tool_version=tool_version,
            )

        artifact = load_media_artifact_manifest(media_manifest_path)
        rendered = render_vk_video_description(video.description, source_video_id=source_id)
        if rendered.has_errors:
            raise VkVideoPreparationError(
                f"VK description has blocking issues for {source_id}: "
                + ", ".join(item.code for item in rendered.issues)
            )
        title = video.title.strip()
        if not title:
            raise VkVideoPreparationError(f"VK title is blank for {source_id}")

        payload = {
            "source_video_id": source_id,
            "source_channel_id": expected_channel,
            "youtube_snapshot_id": str(source.snapshot_id),
            "target_snapshot_id": str(target.snapshot_id),
            "source_title": video.title,
            "source_duration_seconds": duration_seconds,
            "privacy_status": video.privacy_status,
            "published_title": title,
            "published_description": rendered.text,
            "media_manifest_path": _repo_relative(root, media_manifest_path),
            "media_manifest_sha256": file_sha256(media_manifest_path),
            "media_artifact_manifest_sha256": artifact.manifest_sha256,
            "processing_timeout_seconds": processing_timeout_seconds,
            "wallpost": False,
            "auto_publish": False,
            "repeat": False,
        }
        specs_by_id[source_id] = WaveOperationSpec(
            order_key=f"{video.published_at.isoformat() if video.published_at else '0000'}-{source_id}",
            operation_kind=VK_VIDEO_OPERATION_KIND,
            mutation_class=MutationClass.AMBIGUOUS_MUTATION,
            payload=payload,
        )
        shared_artifacts.extend((media_path, media_manifest_path))
        if acquisition_result_path is not None:
            shared_artifacts.extend((acquisition_result_path, acquisition_directory / f"{source_id}.final-path.txt"))
        media_summary.append(
            {
                "source_video_id": source_id,
                "title": title,
                "duration_seconds": duration_seconds,
                "published_at": video.published_at.isoformat() if video.published_at else None,
                "media_path": _repo_relative(root, media_path),
                "media_sha256": file_sha256(media_path),
                "media_manifest_path": _repo_relative(root, media_manifest_path),
                "media_manifest_sha256": file_sha256(media_manifest_path),
                "media_artifact_manifest_sha256": artifact.manifest_sha256,
                "reused": source_id in reuse_by_id,
            }
        )

    selection_path = evidence_directory / "selection.json"
    write_json_atomic(
        selection_path,
        {
            "schema_name": "video-manager.vk-video-wave-selection",
            "schema_version": 1,
            "project_key": project_key,
            "youtube_snapshot_id": str(source.snapshot_id),
            "vk_snapshot_id": str(target.snapshot_id),
            "comparison_conflict_count": comparison.conflict_count,
            "selected_candidate_ids": list(normalized_candidates),
            "canary_id": canary_id,
            "media": media_summary,
            "provider_writes_during_preparation": 0,
        },
    )
    shared_artifacts.append(selection_path)

    project = ProjectBinding(
        project_key=project_key,
        community_id=expected_community,
        owner_id=-expected_community,
    )
    canary_specs = (specs_by_id[canary_id],)
    batch_ids = tuple(source_id for source_id in normalized_candidates if source_id != canary_id)
    batch_specs = tuple(specs_by_id[source_id] for source_id in batch_ids)

    canary = _build_scope(
        repository_root=root,
        scope_directory=output / "canary",
        project=project,
        artifact_paths=shared_artifacts,
        specs=canary_specs,
        account_alias=account_alias,
    )
    batch = (
        _build_scope(
            repository_root=root,
            scope_directory=output / "batch",
            project=project,
            artifact_paths=shared_artifacts,
            specs=batch_specs,
            account_alias=account_alias,
        )
        if batch_specs
        else None
    )
    summary = {
        "schema_name": "video-manager.vk-video-wave-preparation",
        "schema_version": 1,
        "project_key": project_key,
        "community_id": expected_community,
        "owner_id": -expected_community,
        "youtube_snapshot_id": str(source.snapshot_id),
        "vk_snapshot_id": str(target.snapshot_id),
        "candidate_ids": list(normalized_candidates),
        "canary_id": canary_id,
        "batch_ids": list(batch_ids),
        "provider_writes": 0,
        "canary": canary,
        "batch": batch,
    }
    write_json_atomic(output / "summary.json", summary)
    return summary


__all__ = [
    "VkVideoPreparationError",
    "prepare_vk_video_wave",
]
