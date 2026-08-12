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
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence

OUTPUT_SCHEMA = "milovi-cake-d48-youtube-fallback-v1"
MANIFEST_SCHEMA = f"{OUTPUT_SCHEMA}-manifest"

ACCEPTED_RETRY_ZIP_SHA256 = "22604bc2329381b563e7243e66bbd548b93fbe770e3b8b23d0a6f9b0b0ca5022"
ACCEPTED_RETRY_RESULT_SHA256 = "76f46a7ac7b8183a8033f6d859ac8cd96c2f426dea105771892f2563594053e6"
ACCEPTED_MEDIA_PROBE_ZIP_SHA256 = "89aefa40e51450ab3823db1f794ccf262203d8dd14ac5f2543f10b4ec69487ea"
ACCEPTED_MEDIA_PROBE_RESULT_SHA256 = "c3db469e1b4c6d450481b87951db16b13a9ffa93b4d292ceb91553f458a61f36"

YOUTUBE_ID = "d48QLgOuiTs"
VK_REMOTE_IDS = (
    "-68859909_456239182",
    "-68859909_456239172",
    "-68859909_456239115",
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


def _transport_urls(video_id: str) -> tuple[tuple[str, str], ...]:
    return (
        ("shorts", f"https://www.youtube.com/shorts/{video_id}"),
        ("watch", f"https://www.youtube.com/watch?v={video_id}"),
    )


def _read_accepted_retry(input_zip: Path) -> tuple[dict[str, Any], bytes]:
    actual_zip_hash = _sha256_path(input_zip)
    if actual_zip_hash != ACCEPTED_RETRY_ZIP_SHA256:
        raise ValueError(f"unexpected stable retry SHA-256: {actual_zip_hash}")

    with zipfile.ZipFile(input_zip) as archive:
        names = set(archive.namelist())
        if "00-manifest.json" not in names or "01-targeted-youtube-retry.json" not in names:
            raise ValueError("input ZIP does not contain the stable targeted retry contract")
        manifest = json.loads(archive.read("00-manifest.json").decode("utf-8-sig"))
        result_raw = archive.read("01-targeted-youtube-retry.json")
        result = json.loads(result_raw.decode("utf-8-sig"))

    if manifest.get("schema") != "milovi-cake-targeted-youtube-retry-v1-manifest":
        raise ValueError("unexpected stable retry manifest schema")
    if result.get("schema") != "milovi-cake-targeted-youtube-retry-v1":
        raise ValueError("unexpected stable retry result schema")
    if _sha256_bytes(result_raw) != ACCEPTED_RETRY_RESULT_SHA256:
        raise ValueError("stable retry result is not the accepted uploaded result")
    if manifest.get("result_sha256") != ACCEPTED_RETRY_RESULT_SHA256:
        raise ValueError("stable retry manifest/result SHA-256 mismatch")

    input_evidence = result.get("input_evidence") or {}
    browser_probe = result.get("browser_probe") or {}
    safety = result.get("safety") or {}
    if (
        result.get("project_key") != "milovi-cake"
        or result.get("youtube_channel_id") != "UCMDnxfGZiBqcDzgUV1zjFpw"
        or result.get("community_id") != 68859909
        or result.get("owner_id") != -68859909
        or result.get("read_only") is not True
        or result.get("provider_writes") != 0
        or result.get("provider_mutation_authorized") is not False
        or input_evidence.get("media_probe_zip_sha256") != ACCEPTED_MEDIA_PROBE_ZIP_SHA256
        or input_evidence.get("media_probe_result_sha256") != ACCEPTED_MEDIA_PROBE_RESULT_SHA256
        or input_evidence.get("accepted_vk_frames_reused") != 48
        or browser_probe.get("youtube_capture_count") != 1
        or browser_probe.get("youtube_expected") != 2
        or browser_probe.get("vk_recapture_count") != 0
        or safety.get("surface_complete_claim") is not False
        or safety.get("same_media_claim") is not False
        or safety.get("missing_native_clip_claim") is not False
        or safety.get("upload_authorized") is not False
        or safety.get("transfer_queue_created") is not False
    ):
        raise ValueError("accepted stable retry identity/read-only contract is invalid")

    captures_youtube = (result.get("captures") or {}).get("youtube") or {}
    d48 = captures_youtube.get(YOUTUBE_ID) or {}
    ua8 = captures_youtube.get("uA8SbnXzJJc") or {}
    if (
        d48.get("status") != "capture_error"
        or d48.get("sample_count") != 0
        or "no playable <video> element" not in str(d48.get("error") or "")
        or ua8.get("status") != "captured"
        or ua8.get("sample_count") != 12
    ):
        raise ValueError("accepted stable retry no longer has the exact expected d48-only failure")

    captures_vk = (result.get("captures") or {}).get("vk") or {}
    for remote_id in VK_REMOTE_IDS:
        capture = captures_vk.get(remote_id) or {}
        if capture.get("status") != "captured" or capture.get("sample_count") != 12:
            raise ValueError(f"accepted VK sequence is invalid for {remote_id}")

    return result, result_raw


def _copy_vk_frames(*, input_zip: Path, output_dir: Path) -> int:
    prefixes = {f"frames/vk/{remote_id.replace('-', 'neg')}/" for remote_id in VK_REMOTE_IDS}
    copied = 0
    with zipfile.ZipFile(input_zip) as archive:
        for member in archive.namelist():
            if not member.endswith(".jpg") or not any(member.startswith(prefix) for prefix in prefixes):
                continue
            destination = output_dir / member
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
            copied += 1
    if copied != 36:
        raise ValueError(f"expected 36 reused VK frames, got {copied}")
    return copied


def _capture_with_direct_transports(
    *,
    seed_page: Any,
    output_dir: Path,
    wait_ms: int,
) -> tuple[sequence.CaptureResult, list[dict[str, Any]], str | None]:
    attempts: list[dict[str, Any]] = []
    last: sequence.CaptureResult | None = None
    selected_transport: str | None = None

    for transport, url in _transport_urls(YOUTUBE_ID):
        for attempt_number in (1, 2):
            page = seed_page.context.new_page()
            try:
                try:
                    capture = sequence._capture_page_sequence(
                        page=page,
                        platform="youtube",
                        expected_id=YOUTUBE_ID,
                        url=url,
                        output_dir=output_dir,
                        wait_ms=wait_ms,
                    )
                except Exception as exc:
                    capture = sequence.CaptureResult(
                        status="capture_error",
                        canonical_url=url,
                        final_url=sequence._safe_url(str(page.url)),
                        duration_s=None,
                        video_width=None,
                        video_height=None,
                        frames=(),
                        page_title="",
                        block_hints=(),
                        error=f"{type(exc).__name__}: {exc}"[:1000],
                    )
                capture = stable_sequence._temporal_diversity_gate(capture)
                last = capture
                attempts.append(
                    {
                        "transport": transport,
                        "attempt": attempt_number,
                        "url": url,
                        "status": capture.status,
                        "final_url": capture.final_url,
                        "duration_s": capture.duration_s,
                        "sample_count": len(capture.frames),
                        "error": capture.error,
                    }
                )
                if capture.status == "captured":
                    selected_transport = transport
                    return capture, attempts, selected_transport
            finally:
                try:
                    page.close()
                except Exception:
                    pass

    if last is None:
        raise RuntimeError("d48 fallback produced no capture result")
    return last, attempts, selected_transport


def build_d48_fallback(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = True,
    wait_ms: int = 1000,
) -> dict[str, Any]:
    if not 250 <= wait_ms <= 5000:
        raise ValueError("wait_ms must be between 250 and 5000")
    if output_dir.exists() or zip_output.exists():
        raise ValueError("output_dir and zip_output must not already exist")

    accepted, accepted_result_raw = _read_accepted_retry(input_zip)
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Playwright is required; install current repo with: pip install -e ".[browser-read,milovi-gap-read]"'
        ) from exc

    executable = clips_ui._resolve_browser_executable(browser_executable)
    output_dir.mkdir(parents=True)
    copied_vk_frame_count = _copy_vk_frames(input_zip=input_zip, output_dir=output_dir)

    previous_identity = sequence._identity_url_matches
    sequence._identity_url_matches = stable_sequence._stable_identity_url_matches
    try:
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
                capture, attempts, selected_transport = _capture_with_direct_transports(
                    seed_page=seed_page,
                    output_dir=output_dir / "frames" / "youtube" / YOUTUBE_ID,
                    wait_ms=wait_ms,
                )
            finally:
                context.close()
                browser.close()
    finally:
        sequence._identity_url_matches = previous_identity

    youtube_capture = sequence._capture_to_json(capture)
    accepted_vk = accepted["captures"]["vk"]
    pair_results: list[dict[str, Any]] = []
    for remote_id in VK_REMOTE_IDS:
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
                "youtube_id": YOUTUBE_ID,
                "vk_remote_id": remote_id,
                "youtube_capture_status": youtube_capture.get("status"),
                "vk_capture_status": vk_capture.get("status"),
                "sequence_metrics": metrics,
                "collector_evidence_class": evidence_class,
                "manual_adjudication_required": True,
                "same_media_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    captured = youtube_capture.get("status") == "captured"
    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": "completed" if captured else "partial_browser_evidence",
        "project_key": "milovi-cake",
        "youtube_channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw",
        "community_id": 68859909,
        "owner_id": -68859909,
        "content_scope": ["CAKE"],
        "transport": "browser_ui_read_d48_direct_fallback",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            "stable_retry_zip_sha256": _sha256_path(input_zip),
            "stable_retry_result_sha256": _sha256_bytes(accepted_result_raw),
            "accepted_media_probe_zip_sha256": ACCEPTED_MEDIA_PROBE_ZIP_SHA256,
            "accepted_media_probe_result_sha256": ACCEPTED_MEDIA_PROBE_RESULT_SHA256,
            "accepted_vk_frames_reused": copied_vk_frame_count,
            "surface_complete_claim": False,
        },
        "fallback_scope": {
            "youtube_id": YOUTUBE_ID,
            "pair_count": len(VK_REMOTE_IDS),
            "transport_order": [name for name, _url in _transport_urls(YOUTUBE_ID)],
            "attempts": attempts,
            "selected_transport": selected_transport,
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
            "youtube_capture_count": 1 if captured else 0,
            "youtube_expected": 1,
            "vk_recapture_count": 0,
            "accepted_vk_capture_count_reused": 3,
            "sample_positions": list(sequence._SAMPLE_POSITIONS),
        },
        "captures": {
            "youtube": {YOUTUBE_ID: youtube_capture},
            "vk": {remote_id: accepted_vk[remote_id] for remote_id in VK_REMOTE_IDS},
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
            "This fallback retries only d48QLgOuiTs after the accepted stable retry captured uA8SbnXzJJc.",
            "The three VK sequences are reused byte-for-byte from the pinned accepted stable retry and are not recaptured.",
            "Only exact YouTube Shorts/watch URLs for d48QLgOuiTs are accepted by the identity gate.",
            "Sequence metrics remain supporting evidence; manual visual adjudication is required.",
            "A distinct sequence does not create a provider-surface completeness or missing-Clip claim.",
        ],
    }

    result_path = output_dir / "01-d48-youtube-fallback.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": "milovi-cake",
        "provider_writes": 0,
        "mutation_authority": False,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "accepted_input_zip_sha256": ACCEPTED_RETRY_ZIP_SHA256,
        "accepted_input_result_sha256": ACCEPTED_RETRY_RESULT_SHA256,
        "copied_vk_frame_count": copied_vk_frame_count,
        "youtube_frame_file_count": sum(path.is_file() for path in (output_dir / "frames" / "youtube").rglob("*"))
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
    root = argparse.ArgumentParser(description="Retry only Milovi d48QLgOuiTs via exact direct YouTube transports.")
    root.add_argument("--input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--wait-ms", type=int, default=1000)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_d48_fallback(
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
                "selected_transport": result["fallback_scope"]["selected_transport"],
                "pair_count": result["fallback_scope"]["pair_count"],
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
