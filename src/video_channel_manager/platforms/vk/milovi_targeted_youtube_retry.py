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
from video_channel_manager.platforms.vk import milovi_media_match_probe as media_probe
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence

OUTPUT_SCHEMA = "milovi-cake-targeted-youtube-retry-v1"
MANIFEST_SCHEMA = f"{OUTPUT_SCHEMA}-manifest"

ACCEPTED_MEDIA_PROBE_ZIP_SHA256 = "89aefa40e51450ab3823db1f794ccf262203d8dd14ac5f2543f10b4ec69487ea"
ACCEPTED_MEDIA_PROBE_RESULT_SHA256 = "c3db469e1b4c6d450481b87951db16b13a9ffa93b4d292ceb91553f458a61f36"

RETRY_PAIRS: dict[str, tuple[str, ...]] = {
    "d48QLgOuiTs": (
        "-68859909_456239182",
        "-68859909_456239172",
        "-68859909_456239115",
    ),
    "uA8SbnXzJJc": ("-68859909_456239109",),
}


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


def _read_accepted_probe(input_zip: Path) -> tuple[dict[str, Any], bytes]:
    actual_zip_hash = _sha256_path(input_zip)
    if actual_zip_hash != ACCEPTED_MEDIA_PROBE_ZIP_SHA256:
        raise ValueError(f"unexpected media probe SHA-256: {actual_zip_hash}")

    with zipfile.ZipFile(input_zip) as archive:
        names = set(archive.namelist())
        if "00-manifest.json" not in names or "01-media-match-probe.json" not in names:
            raise ValueError("input ZIP does not contain the Milovi media-match probe contract")
        result_raw = archive.read("01-media-match-probe.json")
        manifest = json.loads(archive.read("00-manifest.json").decode("utf-8-sig"))
        result = json.loads(result_raw.decode("utf-8-sig"))

    if manifest.get("schema") != media_probe.MANIFEST_SCHEMA:
        raise ValueError("unexpected media probe manifest schema")
    if result.get("schema") != media_probe.OUTPUT_SCHEMA:
        raise ValueError("unexpected media probe result schema")
    if _sha256_bytes(result_raw) != ACCEPTED_MEDIA_PROBE_RESULT_SHA256:
        raise ValueError("media probe result is not the accepted live result")
    if manifest.get("result_sha256") != ACCEPTED_MEDIA_PROBE_RESULT_SHA256:
        raise ValueError("media probe manifest/result SHA-256 mismatch")

    safety = result.get("safety") or {}
    browser_probe = result.get("browser_probe") or {}
    if (
        result.get("project_key") != "milovi-cake"
        or result.get("youtube_channel_id") != "UCMDnxfGZiBqcDzgUV1zjFpw"
        or result.get("community_id") != 68859909
        or result.get("owner_id") != -68859909
        or result.get("read_only") is not True
        or result.get("provider_writes") != 0
        or result.get("provider_mutation_authorized") is not False
        or browser_probe.get("youtube_capture_count") != 9
        or browser_probe.get("youtube_expected") != 11
        or browser_probe.get("vk_capture_count") != 16
        or browser_probe.get("vk_expected") != 16
        or safety.get("upload_authorized") is not False
        or safety.get("transfer_queue_created") is not False
        or safety.get("missing_native_clip_claim") is not False
    ):
        raise ValueError("accepted media probe identity/read-only contract is invalid")

    captures_youtube = result.get("captures", {}).get("youtube", {})
    captures_vk = result.get("captures", {}).get("vk", {})
    if set(RETRY_PAIRS) != {
        youtube_id
        for youtube_id, capture in captures_youtube.items()
        if isinstance(capture, dict) and capture.get("status") != "captured"
    }:
        raise ValueError("accepted live probe no longer has exactly the two expected YouTube failures")

    pair_rows = result.get("pair_results") or []
    expected_pair_set = {
        (youtube_id, remote_id)
        for youtube_id, remote_ids in RETRY_PAIRS.items()
        for remote_id in remote_ids
    }
    observed_pair_set = {
        (str(row.get("youtube_id") or ""), str(row.get("vk_remote_id") or ""))
        for row in pair_rows
        if isinstance(row, dict) and str(row.get("youtube_id") or "") in RETRY_PAIRS
    }
    if observed_pair_set != expected_pair_set:
        raise ValueError("accepted retry pair plan does not match the exact four failed pair rows")

    for youtube_id in RETRY_PAIRS:
        capture = captures_youtube.get(youtube_id) or {}
        if capture.get("status") != "capture_error" or capture.get("sample_count") != 0:
            raise ValueError(f"expected accepted YouTube capture_error for {youtube_id}")

    for remote_ids in RETRY_PAIRS.values():
        for remote_id in remote_ids:
            capture = captures_vk.get(remote_id) or {}
            if capture.get("status") != "captured" or capture.get("sample_count") != 12:
                raise ValueError(f"expected accepted exact VK capture for {remote_id}")
            if str(capture.get("final_url") or "").rstrip("/") not in {
                "https://vk.ru/clip_ext.php",
                "https://vk.com/clip_ext.php",
            }:
                raise ValueError(f"accepted VK transport is not exact clip_ext.php for {remote_id}")

    return result, result_raw


def _copy_vk_frames(*, input_zip: Path, output_dir: Path) -> int:
    copied = 0
    wanted_prefixes = {
        f"frames/vk/{remote_id.replace('-', 'neg')}/"
        for remote_ids in RETRY_PAIRS.values()
        for remote_id in remote_ids
    }
    with zipfile.ZipFile(input_zip) as archive:
        for member in archive.namelist():
            if not member.endswith(".jpg"):
                continue
            if not any(member.startswith(prefix) for prefix in wanted_prefixes):
                continue
            destination = output_dir / member
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
            copied += 1
    if copied != 48:
        raise ValueError(f"expected 48 copied exact VK frames, got {copied}")
    return copied


def _capture_error(*, youtube_id: str, page_url: str, exc: Exception) -> dict[str, Any]:
    return sequence._capture_to_json(
        sequence.CaptureResult(
            status="capture_error",
            canonical_url=sequence._youtube_url(youtube_id),
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


def build_targeted_retry(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = True,
    wait_ms: int = 750,
) -> dict[str, Any]:
    if not 250 <= wait_ms <= 5000:
        raise ValueError("wait_ms must be between 250 and 5000")
    if output_dir.exists() or zip_output.exists():
        raise ValueError("output_dir and zip_output must not already exist")

    accepted, accepted_result_raw = _read_accepted_probe(input_zip)
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Playwright is required; install current repo with: pip install -e ".[browser-read,milovi-gap-read]"'
        ) from exc

    executable = clips_ui._resolve_browser_executable(browser_executable)
    output_dir.mkdir(parents=True)
    copied_vk_frame_count = _copy_vk_frames(input_zip=input_zip, output_dir=output_dir)

    captures_youtube: dict[str, dict[str, Any]] = {}
    sync_playwright: Any = vars(sync_api)["sync_playwright"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=headless,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        context = browser.new_context(viewport={"width": 960, "height": 1280})
        try:
            seed_page = context.new_page()
            for youtube_id in sorted(RETRY_PAIRS):
                try:
                    capture = stable_sequence._isolated_capture_page_sequence(
                        page=seed_page,
                        platform="youtube",
                        expected_id=youtube_id,
                        url=sequence._youtube_url(youtube_id),
                        output_dir=output_dir / "frames" / "youtube" / youtube_id,
                        wait_ms=wait_ms,
                    )
                    captures_youtube[youtube_id] = sequence._capture_to_json(capture)
                except Exception as exc:
                    captures_youtube[youtube_id] = _capture_error(
                        youtube_id=youtube_id,
                        page_url=str(seed_page.url),
                        exc=exc,
                    )
        finally:
            context.close()
            browser.close()

    accepted_vk = accepted["captures"]["vk"]
    pair_results: list[dict[str, Any]] = []
    for youtube_id, remote_ids in RETRY_PAIRS.items():
        youtube_capture = captures_youtube[youtube_id]
        for remote_id in remote_ids:
            vk_capture = accepted_vk[remote_id]
            metrics = sequence._sequence_metrics(
                youtube_capture.get("frames") or [],
                vk_capture.get("frames") or [],
            )
            evidence_class = sequence._evidence_class(
                metrics,
                youtube_duration_s=youtube_capture.get("duration_s"),
                vk_duration_s=vk_capture.get("duration_s"),
            )
            pair_results.append(
                {
                    "youtube_id": youtube_id,
                    "vk_remote_id": remote_id,
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

    captured_youtube = sum(capture.get("status") == "captured" for capture in captures_youtube.values())
    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": "completed" if captured_youtube == len(RETRY_PAIRS) else "partial_browser_evidence",
        "project_key": "milovi-cake",
        "youtube_channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw",
        "community_id": 68859909,
        "owner_id": -68859909,
        "content_scope": ["CAKE"],
        "transport": "browser_ui_read_targeted_retry",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            "media_probe_zip_sha256": _sha256_path(input_zip),
            "media_probe_result_sha256": _sha256_bytes(accepted_result_raw),
            "accepted_vk_frames_reused": copied_vk_frame_count,
            "surface_complete_claim": False,
        },
        "retry_scope": {
            "youtube_ids": sorted(RETRY_PAIRS),
            "youtube_count": len(RETRY_PAIRS),
            "pair_count": sum(len(remote_ids) for remote_ids in RETRY_PAIRS.values()),
            "reason": "retry only the two YouTube capture_error rows from the accepted exact-VK media probe",
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
            "youtube_expected": len(RETRY_PAIRS),
            "vk_recapture_count": 0,
            "accepted_vk_capture_count_reused": 4,
            "sample_positions": list(sequence._SAMPLE_POSITIONS),
        },
        "captures": {
            "youtube": captures_youtube,
            "vk": {remote_id: accepted_vk[remote_id] for ids in RETRY_PAIRS.values() for remote_id in ids},
        },
        "pair_results": pair_results,
        "safety": {
            "surface_complete_claim": False,
            "same_media_claim": False,
            "missing_native_clip_claim": False,
            "upload_authorized": False,
            "delete_authorized": False,
            "hide_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "transfer_queue_created": False,
        },
        "known_limitations": [
            "This retry resolves only transient YouTube playback failures from the accepted exact-VK probe.",
            "The four VK sequences are reused byte-for-byte from the pinned accepted probe and are not recaptured.",
            "Sequence metrics remain supporting evidence; manual adjudication is required.",
            "A distinct sequence does not create a provider-surface completeness or missing-Clip claim.",
        ],
    }

    result_path = output_dir / "01-targeted-youtube-retry.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": "milovi-cake",
        "provider_writes": 0,
        "mutation_authority": False,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "accepted_input_zip_sha256": ACCEPTED_MEDIA_PROBE_ZIP_SHA256,
        "accepted_input_result_sha256": ACCEPTED_MEDIA_PROBE_RESULT_SHA256,
        "copied_vk_frame_count": copied_vk_frame_count,
        "youtube_frame_file_count": sum(
            path.is_file() for path in (output_dir / "frames" / "youtube").rglob("*")
        )
        if (output_dir / "frames" / "youtube").exists()
        else 0,
        "surface_complete_claim": False,
        "upload_authorized": False,
    }
    manifest_path = output_dir / "00-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zip_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(output_dir).as_posix())
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Retry only the two failed Milovi YouTube sequence captures from the accepted exact-VK probe."
    )
    root.add_argument("--input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--wait-ms", type=int, default=750)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_targeted_retry(
            input_zip=args.input,
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
                "youtube_captured": result["browser_probe"]["youtube_capture_count"],
                "youtube_expected": result["browser_probe"]["youtube_expected"],
                "pair_count": result["retry_scope"]["pair_count"],
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
