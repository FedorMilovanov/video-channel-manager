from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import milovi_gap_thumbnail_evidence as gap
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence

OUTPUT_SCHEMA = "milovi-cake-final-review-queue-v1"
MANIFEST_SCHEMA = f"{OUTPUT_SCHEMA}-manifest"
ACCEPTED_GAP_ZIP_SHA256 = "f33b119d660fef85f11ae3d85f7f6649ff70e566594e26fff785cded5c5481a3"
ACCEPTED_SEQUENCE_ZIP_SHA256 = "23a6238bf61e8e67cf21fe768a58947a39b514c4d6dd192fddc08d3b9584c616"
ACCEPTED_SEQUENCE_RESULT_SHA256 = "0ea7c8c8654e8f99a3252b5b629013e5fa21bbadae369a50682661a3a1f25de2"

# Human adjudication of the exact accepted live 12-frame evidence bundle. These labels are
# intentionally conservative: they block duplicate upload when repeated corresponding scenes
# are visibly present, but they do not claim byte-identical files or identical final edits.
_MANUAL_ADJUDICATIONS: dict[str, dict[str, Any]] = {
    "FQGxV4DRPQw": {
        "vk_remote_id": "-68859909_456239159",
        "role": "suspected_same_media",
        "decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "multiple corresponding pig-cake scenes align across the sampled timelines",
    },
    "MdQ0kNBSsa8": {
        "vk_remote_id": "-68859909_456239176",
        "role": "suspected_same_media",
        "decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "mouse-and-cheese cake scenes, filmstrip sequence, and outdoor packaged-cake scenes recur in both",
    },
    "cE0ofu6WV3s": {
        "vk_remote_id": "-68859909_456239162",
        "role": "suspected_same_media",
        "decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "the same blue cardiology cake, anatomical heart, stethoscope details, and packaging scenes recur in both",
    },
    "CQ29P1F8Hfo": {
        "vk_remote_id": "-68859909_456239100",
        "role": "suspected_edit_variant",
        "decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "the same meringue-roll shots and packaging sequence recur; the YouTube edit has additional tail material",
    },
    "R-LknUy9BEs": {
        "vk_remote_id": "-68859909_456239031",
        "role": "suspected_same_media",
        "decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "the same white-and-gold birthday cake and matching camera angles recur across both timelines",
    },
    "SiluLt5Bz1c": {
        "vk_remote_id": "-68859909_456239076",
        "role": "negative_control",
        "decision": "DISTINCT_FROM_PROBED_VK_CLIP",
        "confidence": "high",
        "basis": "the YouTube gold birthday cake and VK blue cake are visibly different products",
    },
    "BAVKrQQ00XI": {
        "vk_remote_id": "-68859909_456239061",
        "role": "negative_control",
        "decision": "DISTINCT_FROM_PROBED_VK_CLIP",
        "confidence": "high",
        "basis": "the YouTube white-and-gold cake and VK pink cherry cake are visibly different products",
    },
    "p3xZaajOMvc": {
        "vk_remote_id": "-68859909_456239130",
        "role": "reference_pair",
        "decision": "REFERENCE_NATIVE_REPRESENTATION_OBSERVED",
        "confidence": "high",
        "basis": "corresponding Shrek-cake scenes align across the sampled timelines",
    },
}


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json_member(path: Path, member: str) -> tuple[bytes, dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(member)
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{member} must contain a JSON object")
    return raw, value


def _validate_gap_input(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    actual_hash = _sha256_path(path)
    if actual_hash != ACCEPTED_GAP_ZIP_SHA256:
        raise ValueError(f"unexpected gap evidence SHA-256: {actual_hash}")

    manifest_raw, manifest = _read_json_member(path, "00-manifest.json")
    result_raw, result = _read_json_member(path, "01-gap-thumbnail-reconciliation.json")
    if manifest.get("schema") != f"{gap.OUTPUT_SCHEMA}-manifest":
        raise ValueError("unexpected gap manifest schema")
    if result.get("schema") != gap.OUTPUT_SCHEMA:
        raise ValueError("unexpected gap result schema")
    if manifest.get("result_sha256") != _sha256_bytes(result_raw):
        raise ValueError("gap result SHA-256 does not match manifest")
    input_evidence = result.get("input_evidence") or {}
    safety = result.get("safety") or {}
    if (
        result.get("project_key") != gap.MILOVI_PROJECT_KEY
        or result.get("youtube_channel_id") != gap.MILOVI_YOUTUBE_CHANNEL_ID
        or result.get("community_id") != gap.MILOVI_COMMUNITY_ID
        or result.get("owner_id") != gap.MILOVI_OWNER_ID
        or result.get("read_only") is not True
        or result.get("provider_writes") != 0
        or result.get("provider_mutation_authorized") is not False
        or input_evidence.get("exact_public_ui_clip_count") != 106
        or input_evidence.get("exact_wall_native_clip_count") != 106
        or input_evidence.get("exact_ui_wall_intersection_count") != 106
        or input_evidence.get("ui_only_count") != 0
        or input_evidence.get("wall_only_count") != 0
        or input_evidence.get("surface_complete_claim") is not False
        or safety.get("upload_authorized") is not False
    ):
        raise ValueError("gap evidence identity/read-only contract is invalid")
    candidates = result.get("candidates") or []
    if len(candidates) != 25:
        raise ValueError("expected exact reviewed 25-item confectionery gap scope")
    return result, {
        "gap_zip_sha256": actual_hash,
        "gap_manifest_sha256": _sha256_bytes(manifest_raw),
        "gap_result_sha256": _sha256_bytes(result_raw),
    }


def _validate_sequence_input(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    actual_hash = _sha256_path(path)
    if actual_hash != ACCEPTED_SEQUENCE_ZIP_SHA256:
        raise ValueError(f"unexpected exact-VK sequence evidence SHA-256: {actual_hash}")

    manifest_raw, manifest = _read_json_member(path, "00-manifest.json")
    result_raw, result = _read_json_member(path, "01-video-sequence-reconciliation.json")
    if manifest.get("schema") != f"{sequence.OUTPUT_SCHEMA}-manifest":
        raise ValueError("unexpected sequence manifest schema")
    if result.get("schema") != sequence.OUTPUT_SCHEMA:
        raise ValueError("unexpected sequence result schema")
    if _sha256_bytes(result_raw) != ACCEPTED_SEQUENCE_RESULT_SHA256:
        raise ValueError("sequence result SHA-256 is not the accepted live result")
    if manifest.get("result_sha256") != _sha256_bytes(result_raw):
        raise ValueError("sequence result SHA-256 does not match manifest")
    if (
        result.get("status") != "completed"
        or result.get("project_key") != gap.MILOVI_PROJECT_KEY
        or result.get("youtube_channel_id") != gap.MILOVI_YOUTUBE_CHANNEL_ID
        or result.get("community_id") != gap.MILOVI_COMMUNITY_ID
        or result.get("owner_id") != gap.MILOVI_OWNER_ID
        or result.get("read_only") is not True
        or result.get("provider_writes") != 0
        or result.get("provider_mutation_authorized") is not False
        or (result.get("browser_probe") or {}).get("youtube_capture_count") != 8
        or (result.get("browser_probe") or {}).get("vk_capture_count") != 8
        or (result.get("safety") or {}).get("upload_authorized") is not False
        or (result.get("safety") or {}).get("transfer_queue_created") is not False
    ):
        raise ValueError("sequence evidence identity/read-only contract is invalid")

    pair_results = result.get("pair_results") or []
    observed_pairs = {
        (str(row.get("youtube_id") or ""), str(row.get("vk_remote_id") or ""))
        for row in pair_results
        if isinstance(row, dict)
    }
    expected_pairs = {(youtube_id, str(spec["vk_remote_id"])) for youtube_id, spec in _MANUAL_ADJUDICATIONS.items()}
    if observed_pairs != expected_pairs:
        raise ValueError("sequence evidence pair manifest is not the accepted eight-pair scope")
    return result, {
        "sequence_zip_sha256": actual_hash,
        "sequence_manifest_sha256": _sha256_bytes(manifest_raw),
        "sequence_result_sha256": _sha256_bytes(result_raw),
    }


def _derive_candidate_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved_ids = {
        youtube_id
        for youtube_id, spec in _MANUAL_ADJUDICATIONS.items()
        if spec["decision"] == "EXISTING_NATIVE_REPRESENTATION_OBSERVED"
    }
    blocked_existing: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for candidate in candidates:
        youtube_id = str(candidate.get("youtube_id") or "")
        if youtube_id in resolved_ids:
            spec = _MANUAL_ADJUDICATIONS[youtube_id]
            blocked_existing.append(
                {
                    "youtube_id": youtube_id,
                    "title": str(candidate.get("title") or ""),
                    "scope": str(candidate.get("scope") or ""),
                    "vk_remote_id": spec["vk_remote_id"],
                    "decision": spec["decision"],
                    "confidence": spec["confidence"],
                    "basis": spec["basis"],
                    "operational_disposition": "BLOCK_DUPLICATE_UPLOAD_EXISTING_NATIVE_REPRESENTATION",
                    "upload_authorized": False,
                }
            )
        else:
            remaining.append(
                {
                    "youtube_id": youtube_id,
                    "title": str(candidate.get("title") or ""),
                    "scope": str(candidate.get("scope") or ""),
                    "transfer_gate": str(candidate.get("transfer_gate") or ""),
                    "status": "NOT_PROVEN_MISSING_REVIEW_REQUIRED",
                    "upload_authorized": False,
                }
            )
    return blocked_existing, remaining


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Milovi Cake final confectionery review queue",
        "",
        "Read-only adjudication. No provider writes and no upload authority.",
        "",
        f"- Existing native representations blocked as duplicates: {result['summary']['blocked_existing_count']}",
        f"- Remaining not-proven-missing candidates: {result['summary']['remaining_candidate_count']}",
        f"- Media reconciliation review queue: {result['summary']['media_reconciliation_count']}",
        f"- IP hold: {result['summary']['ip_hold_count']}",
        f"- Trademark review: {result['summary']['trademark_review_count']}",
        "",
        "## Existing native representations — do not upload",
        "",
    ]
    for row in result["blocked_existing"]:
        lines.append(f"- `{row['youtube_id']}` → `{row['vk_remote_id']}` — {row['title']}")
    lines.extend(["", "## Remaining review candidates", ""])
    for row in result["remaining_candidates"]:
        lines.append(f"- `{row['youtube_id']}` — {row['title']} — `{row['transfer_gate']}`")
    lines.extend(
        [
            "",
            "No row in this document is an authorized transfer. `surface_complete_claim` remains false.",
            "",
        ]
    )
    return "\n".join(lines)


def build_final_review_queue(*, gap_input: Path, sequence_input: Path) -> dict[str, Any]:
    gap_result, gap_hashes = _validate_gap_input(gap_input)
    sequence_result, sequence_hashes = _validate_sequence_input(sequence_input)
    candidates = [row for row in gap_result.get("candidates") or [] if isinstance(row, dict)]
    blocked_existing, remaining = _derive_candidate_rows(candidates)
    gate_counts: dict[str, int] = {}
    for row in remaining:
        gate = str(row["transfer_gate"])
        gate_counts[gate] = gate_counts.get(gate, 0) + 1

    reviewed_pairs: list[dict[str, Any]] = []
    by_pair = {
        (str(row.get("youtube_id") or ""), str(row.get("vk_remote_id") or "")): row
        for row in sequence_result.get("pair_results") or []
        if isinstance(row, dict)
    }
    for youtube_id, spec in _MANUAL_ADJUDICATIONS.items():
        pair = by_pair[(youtube_id, str(spec["vk_remote_id"]))]
        reviewed_pairs.append(
            {
                "youtube_id": youtube_id,
                "vk_remote_id": spec["vk_remote_id"],
                "review_role": spec["role"],
                "manual_decision": spec["decision"],
                "manual_confidence": spec["confidence"],
                "manual_basis": spec["basis"],
                "collector_evidence_class": pair.get("evidence_class"),
                "collector_metric_overridden": True,
                "override_reason": (
                    "accepted exact-VK live contact-sheet review shows the collector full-frame hash metric "
                    "false-negatives on the known Shrek reference and visibly corresponding confectionery sequences"
                ),
                "same_final_edit_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    return {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": "completed_manual_sequence_adjudication",
        "project_key": gap.MILOVI_PROJECT_KEY,
        "youtube_channel_id": gap.MILOVI_YOUTUBE_CHANNEL_ID,
        "community_id": gap.MILOVI_COMMUNITY_ID,
        "owner_id": gap.MILOVI_OWNER_ID,
        "content_scope": ["CAKE", "DESSERT"],
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {**gap_hashes, **sequence_hashes, "surface_complete_claim": False},
        "summary": {
            "reviewed_gap_candidate_count": len(candidates),
            "blocked_existing_count": len(blocked_existing),
            "remaining_candidate_count": len(remaining),
            "media_reconciliation_count": gate_counts.get("MEDIA_RECONCILIATION_REQUIRED", 0),
            "ip_hold_count": gate_counts.get("IP_HOLD_DO_NOT_TRANSFER", 0),
            "trademark_review_count": gate_counts.get("TRADEMARK_REVIEW_REQUIRED", 0),
            "transfer_ready_count": 0,
        },
        "reviewed_sequence_pairs": reviewed_pairs,
        "blocked_existing": blocked_existing,
        "remaining_candidates": remaining,
        "safety": {
            "surface_complete_claim": False,
            "missing_native_clip_claim": False,
            "upload_authorized": False,
            "delete_authorized": False,
            "hide_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "transfer_queue_created": False,
        },
        "known_limitations": [
            "manual sequence adjudication blocks duplicate uploads but does not claim byte-identical media or identical final edits",
            "the accepted public VK UI observation is bounded and still does not carry an authoritative owner-surface completeness claim",
            "remaining candidates are review candidates only; non-observation is not proof of missing native Clip",
            "IP and trademark gates remain independent of duplicate reconciliation",
        ],
    }


def write_bundle(*, result: dict[str, Any], output_dir: Path, zip_output: Path) -> None:
    if output_dir.exists() or zip_output.exists():
        raise ValueError("output_dir and zip_output must not already exist")
    output_dir.mkdir(parents=True)
    result_path = output_dir / "01-final-review-queue.json"
    markdown_path = output_dir / "02-final-review-queue.md"
    result_raw = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    markdown_raw = _markdown(result).encode("utf-8")
    result_path.write_bytes(result_raw)
    markdown_path.write_bytes(markdown_raw)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": gap.MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "mutation_authority": False,
        "result_file": result_path.name,
        "result_sha256": _sha256_bytes(result_raw),
        "markdown_file": markdown_path.name,
        "markdown_sha256": _sha256_bytes(markdown_raw),
        "surface_complete_claim": False,
        "upload_authorized": False,
    }
    manifest_path = output_dir / "00-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.iterdir()):
            archive.write(path, arcname=path.name)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build provider-free Milovi confectionery final review queue evidence.")
    root.add_argument("--gap-input", type=Path, required=True)
    root.add_argument("--sequence-input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_final_review_queue(gap_input=args.gap_input, sequence_input=args.sequence_input)
        write_bundle(result=result, output_dir=args.output_dir, zip_output=args.zip_output)
    except Exception as exc:
        print(json.dumps({"status": "failed", "provider_writes": 0, "error": f"{type(exc).__name__}: {exc}"}))
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "blocked_existing": result["summary"]["blocked_existing_count"],
                "remaining": result["summary"]["remaining_candidate_count"],
                "media_reconciliation": result["summary"]["media_reconciliation_count"],
                "ip_hold": result["summary"]["ip_hold_count"],
                "trademark_review": result["summary"]["trademark_review_count"],
                "transfer_ready": 0,
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
