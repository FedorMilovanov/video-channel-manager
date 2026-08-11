from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import clips_ui_inventory as clips_ui
from video_channel_manager.platforms.vk import milovi_final_review_queue as final_queue
from video_channel_manager.platforms.vk import milovi_gap_thumbnail_evidence as gap
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence

OUTPUT_SCHEMA = "milovi-cake-media-match-probe-v1"
MANIFEST_SCHEMA = f"{OUTPUT_SCHEMA}-manifest"
ACCEPTED_FINAL_QUEUE_ZIP_SHA256 = "8d47a14f130aa3bd892eceb309a29c9c2ca8bcceae206cba86f5cb71a28d9e7d"
ACCEPTED_FINAL_QUEUE_RESULT_SHA256 = "ed9363ee664342205333523b3768ff81392ce1d4583f24567683771bec2202d8"
ACCEPTED_GAP_ZIP_SHA256 = final_queue.ACCEPTED_GAP_ZIP_SHA256
EXPECTED_PUBLIC_VK_CLIP_COUNT = 106
EXPECTED_MEDIA_CANDIDATE_COUNT = 13

# The accepted final queue contains exactly these 13 low-risk cake/dessert rows.
# The manual review notes below come from an exhaustive 13 x 106 pass over the accepted
# VK thumbnail evidence plus the exact published-wall Clip descriptions. Probe IDs are only
# plausible representations worth sequence capture; an empty probe list is not an absence claim.
EXHAUSTIVE_REVIEW: dict[str, dict[str, Any]] = {
    "d48QLgOuiTs": {
        "scope": "CAKE",
        "probe_remote_ids": (
            "-68859909_456239182",
            "-68859909_456239172",
            "-68859909_456239115",
        ),
        "review_note": "silver bow plus red-heart cake; bow and heart Clip variants are the only plausible 106-item visual/metadata neighbors",
    },
    "Oix9s6l9vNg": {
        "scope": "CAKE",
        "probe_remote_ids": (),
        "review_note": "classic crumb-coated medovik; no plausible same-product representation observed across the accepted 106 thumbnails/descriptions",
    },
    "uA8SbnXzJJc": {
        "scope": "CAKE",
        "probe_remote_ids": ("-68859909_456239109",),
        "review_note": "marbled medovik with marshmallow coating; marshmallow-coated VK cake is semantically plausible despite a distinct thumbnail",
    },
    "u-PuqjWuhKk": {
        "scope": "CAKE",
        "probe_remote_ids": (
            "-68859909_456239177",
            "-68859909_456239143",
            "-68859909_456239190",
        ),
        "review_note": "dark-blue birthday cake with blue spheres; blue/ball birthday variants are retained as bounded probes",
    },
    "L6XG2_zzrPU": {
        "scope": "DESSERT",
        "probe_remote_ids": ("-68859909_456239060",),
        "review_note": "picnic eclairs and marshmallows; the accepted eclair Clip is the only direct dessert-family probe",
    },
    "pCARxxaVjTw": {
        "scope": "DESSERT",
        "probe_remote_ids": ("-68859909_456239141",),
        "review_note": "chocolate flower bouquet; tulip-themed confectionery Clip is retained only as a negative-or-shared-source probe",
    },
    "OWV-KGsLdA8": {
        "scope": "CAKE",
        "probe_remote_ids": (
            "-68859909_456239068",
            "-68859909_456239163",
        ),
        "review_note": "black heart-shaped cake with cherries; two heart-cake VK variants are the only plausible semantic neighbors",
    },
    "SiluLt5Bz1c": {
        "scope": "CAKE",
        "probe_remote_ids": (
            "-68859909_456239082",
            "-68859909_456239096",
        ),
        "review_note": "gold-and-white birthday cake visibly corresponds to both accepted VK gold-cake thumbnails; sequence confirmation required",
    },
    "o1WXIMupuws": {
        "scope": "CAKE",
        "probe_remote_ids": ("-68859909_456239076",),
        "review_note": "money-themed birthday cake; money-inside VK cake is retained as the only plausible money-cake probe",
    },
    "1_SuzeQD_1g": {
        "scope": "CAKE",
        "probe_remote_ids": ("-68859909_456239139",),
        "review_note": "New Year snowflake bento; New Year bento VK Clip is the direct semantic probe even though its accepted first frame is non-diagnostic",
    },
    "5B9OuXbdGKc": {
        "scope": "CAKE",
        "probe_remote_ids": (),
        "review_note": "blood-pressure-monitor cake; no corresponding medical-device cake is observed in the accepted 106 thumbnails/descriptions",
    },
    "BAVKrQQ00XI": {
        "scope": "CAKE",
        "probe_remote_ids": (
            "-68859909_456239082",
            "-68859909_456239096",
        ),
        "review_note": "gold-and-white Happy Birthday cake visibly corresponds to the same two accepted VK gold-cake thumbnails",
    },
    "R0KjJvbxS8s": {
        "scope": "DESSERT",
        "probe_remote_ids": ("-68859909_456239065",),
        "review_note": "trifle/cup dessert montage; the exact VK Trifles description is the direct semantic probe",
    },
}

VK_INTERNAL_DUPLICATE_PROBES: tuple[tuple[str, str, str], ...] = (
    (
        "-68859909_456239082",
        "-68859909_456239096",
        "accepted thumbnails are near-identical views of the same gold-and-white cake; test whether the Clip sequences are duplicate/repost variants",
    ),
)


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(raw)


def _read_json_member(path: Path, member: str) -> tuple[bytes, dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(member)
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{member} must contain a JSON object")
    return raw, value


def _validate_inputs(*, final_input: Path, gap_input: Path) -> tuple[dict[str, Any], dict[str, str]]:
    final_hash = _sha256_path(final_input)
    gap_hash = _sha256_path(gap_input)
    if final_hash != ACCEPTED_FINAL_QUEUE_ZIP_SHA256:
        raise ValueError(f"unexpected final queue SHA-256: {final_hash}")
    if gap_hash != ACCEPTED_GAP_ZIP_SHA256:
        raise ValueError(f"unexpected gap evidence SHA-256: {gap_hash}")

    final_manifest_raw, final_manifest = _read_json_member(final_input, "00-manifest.json")
    final_result_raw, final_result = _read_json_member(final_input, "01-final-review-queue.json")
    if final_manifest.get("schema") != final_queue.MANIFEST_SCHEMA:
        raise ValueError("unexpected final queue manifest schema")
    if final_result.get("schema") != final_queue.OUTPUT_SCHEMA:
        raise ValueError("unexpected final queue result schema")
    if _sha256_bytes(final_result_raw) != ACCEPTED_FINAL_QUEUE_RESULT_SHA256:
        raise ValueError("final queue result is not the accepted live result")
    if final_manifest.get("result_sha256") != ACCEPTED_FINAL_QUEUE_RESULT_SHA256:
        raise ValueError("final queue manifest/result SHA-256 mismatch")

    _, gap_result = _read_json_member(gap_input, "01-gap-thumbnail-reconciliation.json")
    if gap_result.get("schema") != gap.OUTPUT_SCHEMA:
        raise ValueError("unexpected gap evidence schema")

    safety = final_result.get("safety") or {}
    summary = final_result.get("summary") or {}
    if (
        final_result.get("project_key") != gap.MILOVI_PROJECT_KEY
        or final_result.get("youtube_channel_id") != gap.MILOVI_YOUTUBE_CHANNEL_ID
        or final_result.get("community_id") != gap.MILOVI_COMMUNITY_ID
        or final_result.get("owner_id") != gap.MILOVI_OWNER_ID
        or final_result.get("read_only") is not True
        or final_result.get("provider_writes") != 0
        or final_result.get("provider_mutation_authorized") is not False
        or summary.get("media_reconciliation_count") != EXPECTED_MEDIA_CANDIDATE_COUNT
        or summary.get("transfer_ready_count") != 0
        or safety.get("upload_authorized") is not False
        or safety.get("surface_complete_claim") is not False
    ):
        raise ValueError("final queue identity/read-only contract is invalid")

    media_rows = [
        row
        for row in final_result.get("remaining_candidates") or []
        if isinstance(row, dict) and row.get("transfer_gate") == "MEDIA_RECONCILIATION_REQUIRED"
    ]
    media_ids = {str(row.get("youtube_id") or "") for row in media_rows}
    if media_ids != set(EXHAUSTIVE_REVIEW):
        raise ValueError("accepted 13-item media-reconciliation scope does not match the exhaustive review manifest")
    if any(str(row.get("scope") or "") not in {"CAKE", "DESSERT"} for row in media_rows):
        raise ValueError("non-confectionery row entered the 13-item media-reconciliation scope")

    with zipfile.ZipFile(gap_input) as archive:
        vk_media = [name for name in archive.namelist() if name.startswith("media/vk/") and name.endswith(".jpg")]
    if len(vk_media) != EXPECTED_PUBLIC_VK_CLIP_COUNT:
        raise ValueError(f"expected exactly 106 accepted VK Clip thumbnails, got {len(vk_media)}")

    return final_result, {
        "final_queue_zip_sha256": final_hash,
        "final_queue_manifest_sha256": _sha256_bytes(final_manifest_raw),
        "final_queue_result_sha256": _sha256_bytes(final_result_raw),
        "gap_zip_sha256": gap_hash,
    }


def _probe_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(
        (youtube_id, remote_id)
        for youtube_id, review in EXHAUSTIVE_REVIEW.items()
        for remote_id in review["probe_remote_ids"]
    )


def _capture_error(*, platform: str, expected_id: str, page_url: str, exc: Exception) -> dict[str, Any]:
    canonical_url = sequence._youtube_url(expected_id) if platform == "youtube" else sequence._vk_url(expected_id)
    return sequence._capture_to_json(
        sequence.CaptureResult(
            status="capture_error",
            canonical_url=canonical_url,
            final_url=sequence._safe_url(page_url),
            duration_s=None,
            video_width=None,
            video_height=None,
            frames=(),
            page_title="",
            block_hints=(),
            error=f"{type(exc).__name__}: {exc}"[:1000],
        )
    )


def build_media_match_probe(
    *,
    final_input: Path,
    gap_input: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = False,
    wait_ms: int = 500,
) -> dict[str, Any]:
    if not 250 <= wait_ms <= 5000:
        raise ValueError("wait_ms must be between 250 and 5000")
    if output_dir.exists() or zip_output.exists():
        raise ValueError("output_dir and zip_output must not already exist")

    final_result, input_hashes = _validate_inputs(final_input=final_input, gap_input=gap_input)
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise RuntimeError('Playwright is required; install current repo with: pip install -e ".[browser-read,milovi-gap-read]"') from exc

    executable = clips_ui._resolve_browser_executable(browser_executable)
    pair_plan = _probe_pairs()
    youtube_ids = sorted({youtube_id for youtube_id, _ in pair_plan})
    vk_ids = sorted(
        {remote_id for _, remote_id in pair_plan}
        | {remote_id for pair in VK_INTERNAL_DUPLICATE_PROBES for remote_id in pair[:2]}
    )

    output_dir.mkdir(parents=True)
    frame_root = output_dir / "frames"
    captures_youtube: dict[str, dict[str, Any]] = {}
    captures_vk: dict[str, dict[str, Any]] = {}
    sync_playwright: Any = vars(sync_api)["sync_playwright"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=headless,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        context = browser.new_context(viewport={"width": 960, "height": 1280})
        try:
            page = context.new_page()
            for youtube_id in youtube_ids:
                try:
                    capture = sequence._capture_page_sequence(
                        page=page,
                        platform="youtube",
                        expected_id=youtube_id,
                        url=sequence._youtube_url(youtube_id),
                        output_dir=frame_root / "youtube" / youtube_id,
                        wait_ms=wait_ms,
                    )
                    captures_youtube[youtube_id] = sequence._capture_to_json(capture)
                except Exception as exc:
                    captures_youtube[youtube_id] = _capture_error(
                        platform="youtube",
                        expected_id=youtube_id,
                        page_url=str(page.url),
                        exc=exc,
                    )

            for remote_id in vk_ids:
                try:
                    capture = sequence._capture_page_sequence(
                        page=page,
                        platform="vk",
                        expected_id=remote_id,
                        url=sequence._vk_url(remote_id),
                        output_dir=frame_root / "vk" / remote_id.replace("-", "neg"),
                        wait_ms=wait_ms,
                    )
                    captures_vk[remote_id] = sequence._capture_to_json(capture)
                except Exception as exc:
                    captures_vk[remote_id] = _capture_error(
                        platform="vk",
                        expected_id=remote_id,
                        page_url=str(page.url),
                        exc=exc,
                    )
        finally:
            context.close()
            browser.close()

    media_rows = {
        str(row.get("youtube_id") or ""): row
        for row in final_result.get("remaining_candidates") or []
        if isinstance(row, dict) and row.get("transfer_gate") == "MEDIA_RECONCILIATION_REQUIRED"
    }
    pair_results: list[dict[str, Any]] = []
    for youtube_id, remote_id in pair_plan:
        youtube_capture = captures_youtube[youtube_id]
        vk_capture = captures_vk[remote_id]
        metrics = sequence._sequence_metrics(youtube_capture.get("frames") or [], vk_capture.get("frames") or [])
        evidence_class = sequence._evidence_class(
            metrics,
            youtube_duration_s=youtube_capture.get("duration_s"),
            vk_duration_s=vk_capture.get("duration_s"),
        )
        row = media_rows[youtube_id]
        pair_results.append(
            {
                "youtube_id": youtube_id,
                "youtube_title": str(row.get("title") or ""),
                "youtube_scope": str(row.get("scope") or ""),
                "vk_remote_id": remote_id,
                "youtube_url": sequence._youtube_url(youtube_id),
                "vk_clip_url": sequence._vk_url(remote_id),
                "review_note": EXHAUSTIVE_REVIEW[youtube_id]["review_note"],
                "youtube_capture_status": youtube_capture.get("status"),
                "vk_capture_status": vk_capture.get("status"),
                "youtube_duration_s": youtube_capture.get("duration_s"),
                "vk_duration_s": vk_capture.get("duration_s"),
                "sequence_metrics": metrics,
                "collector_evidence_class": evidence_class,
                "manual_adjudication_required": True,
                "same_media_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    vk_duplicate_results: list[dict[str, Any]] = []
    for left_id, right_id, note in VK_INTERNAL_DUPLICATE_PROBES:
        left_capture = captures_vk[left_id]
        right_capture = captures_vk[right_id]
        metrics = sequence._sequence_metrics(left_capture.get("frames") or [], right_capture.get("frames") or [])
        evidence_class = sequence._evidence_class(
            metrics,
            youtube_duration_s=left_capture.get("duration_s"),
            vk_duration_s=right_capture.get("duration_s"),
        )
        vk_duplicate_results.append(
            {
                "left_remote_id": left_id,
                "right_remote_id": right_id,
                "review_note": note,
                "left_capture_status": left_capture.get("status"),
                "right_capture_status": right_capture.get("status"),
                "left_duration_s": left_capture.get("duration_s"),
                "right_duration_s": right_capture.get("duration_s"),
                "sequence_metrics": metrics,
                "collector_evidence_class": evidence_class,
                "duplicate_media_claim": False,
                "manual_adjudication_required": True,
            }
        )

    captured_youtube = sum(row.get("status") == "captured" for row in captures_youtube.values())
    captured_vk = sum(row.get("status") == "captured" for row in captures_vk.values())
    complete_capture = captured_youtube == len(youtube_ids) and captured_vk == len(vk_ids)

    exhaustive_rows = [
        {
            "youtube_id": youtube_id,
            "title": str(media_rows[youtube_id].get("title") or ""),
            "scope": review["scope"],
            "review_note": review["review_note"],
            "probe_remote_ids": list(review["probe_remote_ids"]),
            "plausible_probe_count": len(review["probe_remote_ids"]),
            "no_probe_is_not_absence_claim": True,
        }
        for youtube_id, review in EXHAUSTIVE_REVIEW.items()
    ]

    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": "completed" if complete_capture else "partial_browser_evidence",
        "project_key": gap.MILOVI_PROJECT_KEY,
        "youtube_channel_id": gap.MILOVI_YOUTUBE_CHANNEL_ID,
        "community_id": gap.MILOVI_COMMUNITY_ID,
        "owner_id": gap.MILOVI_OWNER_ID,
        "content_scope": ["CAKE", "DESSERT"],
        "transport": "browser_ui_read",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            **input_hashes,
            "exact_public_ui_clip_count": EXPECTED_PUBLIC_VK_CLIP_COUNT,
            "surface_complete_claim": False,
        },
        "exhaustive_thumbnail_review": {
            "candidate_count": EXPECTED_MEDIA_CANDIDATE_COUNT,
            "vk_clip_count": EXPECTED_PUBLIC_VK_CLIP_COUNT,
            "pair_space_reviewed": EXPECTED_MEDIA_CANDIDATE_COUNT * EXPECTED_PUBLIC_VK_CLIP_COUNT,
            "method": "manual visual review of all accepted VK Clip thumbnails plus exact published-wall Clip descriptions",
            "selected_sequence_probe_pair_count": len(pair_plan),
            "rows": exhaustive_rows,
            "absence_claim_from_thumbnail_review": False,
        },
        "browser_probe": {
            "browser_executable_name": executable.name,
            "playwright_version": sequence._playwright_version(),
            "headless": headless,
            "persistent_profile_used": False,
            "cookies_persisted": False,
            "clicks_performed": 0,
            "forms_submitted": 0,
            "provider_writes": 0,
            "youtube_capture_count": captured_youtube,
            "youtube_expected": len(youtube_ids),
            "vk_capture_count": captured_vk,
            "vk_expected": len(vk_ids),
            "sample_positions": list(sequence._SAMPLE_POSITIONS),
        },
        "captures": {"youtube": captures_youtube, "vk": captures_vk},
        "pair_results": pair_results,
        "vk_internal_duplicate_probes": vk_duplicate_results,
        "safety": {
            "surface_complete_claim": False,
            "same_media_claim": False,
            "duplicate_media_claim": False,
            "missing_native_clip_claim": False,
            "upload_authorized": False,
            "delete_authorized": False,
            "hide_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "transfer_queue_created": False,
        },
        "known_limitations": [
            "The accepted public VK UI/wall observation contains 106 unique remote IDs, but unique IDs do not imply unique media.",
            "The 13 x 106 thumbnail/metadata pass is exhaustive over the accepted 106-item observation, not proof that the provider owner surface is complete.",
            "Browser frame metrics are supporting evidence only and previously false-negatived known corresponding media; manual adjudication remains required.",
            "A non-match or empty shortlist must never be converted into a missing-native-Clip claim or upload authority.",
            "Only cake/dessert rows are in scope; IP/trademark holds and non-confectionery content are excluded from this probe.",
        ],
    }

    result_path = output_dir / "01-media-match-probe.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": gap.MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "mutation_authority": False,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "frame_file_count": sum(path.is_file() for path in frame_root.rglob("*")),
        "pair_plan_sha256": _canonical_json_sha256(pair_plan),
        "exhaustive_review_sha256": _canonical_json_sha256(EXHAUSTIVE_REVIEW),
        "surface_complete_claim": False,
        "upload_authorized": False,
    }
    manifest_path = output_dir / "00-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zip_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build read-only Milovi 13 x 106 confectionery reconciliation sequence probes."
    )
    root.add_argument("--final-input", type=Path, required=True)
    root.add_argument("--gap-input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--wait-ms", type=int, default=500)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_media_match_probe(
            final_input=args.final_input,
            gap_input=args.gap_input,
            output_dir=args.output_dir,
            zip_output=args.zip_output,
            browser_executable=args.browser_executable,
            headless=args.headless,
            wait_ms=args.wait_ms,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "provider_writes": 0, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": result["status"],
                "candidate_count": result["exhaustive_thumbnail_review"]["candidate_count"],
                "pair_space_reviewed": result["exhaustive_thumbnail_review"]["pair_space_reviewed"],
                "sequence_probe_pairs": result["exhaustive_thumbnail_review"]["selected_sequence_probe_pair_count"],
                "youtube_captured": result["browser_probe"]["youtube_capture_count"],
                "vk_captured": result["browser_probe"]["vk_capture_count"],
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
