from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.clips_candidate_triage import build_owner_only_risk_triage
from video_channel_manager.platforms.vk.clips_owner_probe import (
    VK_OWNER_CLIPS_PROBE_API_VERSION,
    build_vk_owner_clips_probe_snapshot,
)
from video_channel_manager.platforms.vk.clips_owner_reconciliation import build_owner_clips_wall_reconciliation
from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.store import VkTokenStore

VK_OWNER_CLIPS_EVIDENCE_PIPELINE_SCHEMA = "vk-owner-clips-evidence-pipeline-v1"
_OWNER_PROBE_FILENAME = "01-owner-clips-probe.json"
_RECONCILIATION_FILENAME = "02-owner-clips-wall-reconciliation.json"
_TRIAGE_FILENAME = "03-owner-only-risk-triage.json"
_MANIFEST_FILENAME = "00-evidence-manifest.json"


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Any) -> tuple[str, str]:
    data = _json_bytes(payload)
    path.write_bytes(data)
    return "sha256:" + hashlib.sha256(data).hexdigest(), canonical_sha256(payload)


def run_owner_clips_evidence_pipeline(
    client: VkApiClient,
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    published_posts: list[dict[str, Any]],
    output_dir: Path,
    required_remote_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Collect one owner probe and derive all downstream evidence from that exact object.

    This function performs only the read-only provider calls already encapsulated
    by ``build_vk_owner_clips_probe_snapshot``. Reconciliation and triage are
    pure local transformations. No upload, hide, delete, wall, or scheduling
    method is reachable from this module.
    """

    owner_probe = build_vk_owner_clips_probe_snapshot(
        client,
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
        required_remote_ids=required_remote_ids,
    )
    reconciliation = build_owner_clips_wall_reconciliation(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
        published_posts=published_posts,
        owner_probe=owner_probe,
    )
    triage = build_owner_only_risk_triage(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
        reconciliation=reconciliation,
        owner_probe=owner_probe,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    owner_path = output_dir / _OWNER_PROBE_FILENAME
    reconciliation_path = output_dir / _RECONCILIATION_FILENAME
    triage_path = output_dir / _TRIAGE_FILENAME

    owner_file_sha, owner_canonical_sha = _write_json(owner_path, owner_probe)
    reconciliation_file_sha, reconciliation_canonical_sha = _write_json(reconciliation_path, reconciliation)
    triage_file_sha, triage_canonical_sha = _write_json(triage_path, triage)

    provider_probe = owner_probe.get("provider_probe")
    reconciliation_summary = reconciliation.get("reconciliation")
    triage_summary = triage.get("summary")
    if not isinstance(provider_probe, dict):
        raise ValueError("owner probe has no provider_probe summary")
    if not isinstance(reconciliation_summary, dict):
        raise ValueError("reconciliation has no exact comparison summary")
    if not isinstance(triage_summary, dict):
        raise ValueError("triage has no exact summary")

    manifest: dict[str, Any] = {
        "schema": VK_OWNER_CLIPS_EVIDENCE_PIPELINE_SCHEMA,
        "project_key": project_key,
        "community_id": community_id,
        "owner_id": owner_id,
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "owner_surface_complete_claim": False,
        "source_wall_snapshot": {
            "published_post_count": len(published_posts),
            "canonical_sha256": canonical_sha256(published_posts),
        },
        "artifacts": {
            "owner_probe": {
                "path": _OWNER_PROBE_FILENAME,
                "file_sha256": owner_file_sha,
                "canonical_sha256": owner_canonical_sha,
                "provider_status": provider_probe.get("status"),
            },
            "reconciliation": {
                "path": _RECONCILIATION_FILENAME,
                "file_sha256": reconciliation_file_sha,
                "canonical_sha256": reconciliation_canonical_sha,
                "status": reconciliation.get("status"),
                "both_count": reconciliation_summary.get("both_count"),
                "wall_only_count": reconciliation_summary.get("wall_only_count"),
                "owner_only_count": reconciliation_summary.get("owner_only_count"),
            },
            "triage": {
                "path": _TRIAGE_FILENAME,
                "file_sha256": triage_file_sha,
                "canonical_sha256": triage_canonical_sha,
                "owner_only_candidate_count": triage_summary.get("owner_only_candidate_count"),
                "risk_disposition_counts": triage_summary.get("risk_disposition_counts"),
            },
        },
        "safety": {
            "provider_methods": ["groups.get", "shortVideo.getOwnerVideos"],
            "provider_methods_read_only": True,
            "upload_authorized": False,
            "hide_authorized": False,
            "delete_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "surface_complete_claim": False,
        },
    }
    manifest["manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    _write_json(output_dir / _MANIFEST_FILENAME, manifest)
    return manifest


def _load_published_posts(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("published wall evidence must be a JSON list of objects")
    return payload


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Collect one read-only VK owner Clips probe and derive a hash-bound evidence bundle."
    )
    root.add_argument("--project", required=True)
    root.add_argument("--community", type=int, required=True)
    root.add_argument("--owner-id", type=int, required=True)
    root.add_argument("--account", default="default")
    root.add_argument("--published-wall-posts", type=Path, required=True)
    root.add_argument("--require-remote-id", action="append", default=[])
    root.add_argument("--output-dir", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    client = VkApiClient(
        token_store=store,
        account_alias=args.account,
        api_version=VK_OWNER_CLIPS_PROBE_API_VERSION,
    )
    published_posts = _load_published_posts(args.published_wall_posts)
    manifest = run_owner_clips_evidence_pipeline(
        client,
        project_key=args.project,
        community_id=args.community,
        owner_id=args.owner_id,
        published_posts=published_posts,
        output_dir=args.output_dir,
        required_remote_ids=args.require_remote_id,
    )
    artifacts = manifest["artifacts"]
    print(
        json.dumps(
            {
                "provider_status": artifacts["owner_probe"]["provider_status"],
                "both": artifacts["reconciliation"]["both_count"],
                "wall_only": artifacts["reconciliation"]["wall_only_count"],
                "owner_only": artifacts["reconciliation"]["owner_only_count"],
                "owner_only_triaged": artifacts["triage"]["owner_only_candidate_count"],
                "provider_writes": 0,
                "provider_mutation_authorized": False,
                "surface_complete_claim": False,
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "VK_OWNER_CLIPS_EVIDENCE_PIPELINE_SCHEMA",
    "run_owner_clips_evidence_pipeline",
]
