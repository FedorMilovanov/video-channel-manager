#!/usr/bin/env python3
"""Build deterministic decisions for the one-command VK P1 megawave."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.editorial_megawave import build_vk_p1_megawave_decisions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Verified final VK AuditPackage JSON")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read AuditPackage {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _load_verified_queue(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    expected_sha = str(policy.get("source_review_bundle_sha256") or "")
    if _sha256(path) != expected_sha:
        raise ValueError("Source review bundle SHA-256 differs from megawave policy")
    try:
        with zipfile.ZipFile(path) as archive:
            names = [entry.filename for entry in archive.infolist()]
            if len(names) != len(set(names)):
                raise ValueError("Source review bundle contains duplicate entries")
            raw_manifest = archive.read("manifest.json")
            raw_queue = archive.read("review-queue.json")
            manifest = json.loads(raw_manifest.decode("utf-8-sig"))
            queue = json.loads(raw_queue.decode("utf-8-sig"))
            records = {
                str(item.get("name")): item
                for item in manifest.get("files", [])
                if isinstance(item, dict) and item.get("name")
            }
            for name, record in records.items():
                content = archive.read(name)
                if len(content) != int(record.get("size_bytes", -1)):
                    raise ValueError(f"Source review size mismatch: {name}")
                digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
                if digest != str(record.get("sha256") or ""):
                    raise ValueError(f"Source review SHA-256 mismatch: {name}")
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Cannot verify source review bundle: {exc}") from exc

    if manifest.get("status") != "review_only_completed" or int(manifest.get("remote_writes", -1)) != 0:
        raise ValueError("Source review handoff is not completed review-only")
    if queue.get("mode") != "review_only" or int(queue.get("remote_writes", -1)) != 0:
        raise ValueError("Source review queue is not review-only")
    if str(queue.get("source_plan_sha256") or "") != str(policy.get("source_plan_sha256") or ""):
        raise ValueError("Source review plan differs from megawave policy")
    return queue


def main() -> int:
    args = _parser().parse_args()
    policy = _load_json(args.policy)
    queue = _load_verified_queue(args.review_bundle, policy)
    decisions = build_vk_p1_megawave_decisions(_load_audit(args.target), queue, policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "megawave_decisions_built",
                "decision_set_id": decisions["decision_set_id"],
                "decisions_sha256": canonical_sha256(decisions),
                "targets": decisions["target_count"],
                "unique_descriptions": decisions["unique_description_count"],
                "remote_writes": 0,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
