from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import clips_ui_inventory as clips_ui
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence

OUTPUT_SCHEMA = "milovi-cake-d48-youtube-overlay-clean-v1"
MANIFEST_SCHEMA = f"{OUTPUT_SCHEMA}-manifest"

ACCEPTED_FALLBACK_ZIP_SHA256 = "5b45553bc792b7eaf7adec5fda3e0fbc7d9aa0c1af76d87d71c878cdb4d6e2f6"
ACCEPTED_FALLBACK_RESULT_SHA256 = "d65b8078a780250481fbbbd99d2b3819c1fdd30c4ad257d4fa3a3b5b412c6007"
ACCEPTED_RETRY_ZIP_SHA256 = "22604bc2329381b563e7243e66bbd548b93fbe770e3b8b23d0a6f9b0b0ca5022"

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
        (
            "nocookie_embed",
            f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=1&mute=1&playsinline=1&rel=0",
        ),
        ("watch_overlay_clean", f"https://www.youtube.com/watch?v={video_id}"),
    )


def _read_accepted_fallback(input_zip: Path) -> tuple[dict[str, Any], bytes]:
    actual_hash = _sha256_path(input_zip)
    if actual_hash != ACCEPTED_FALLBACK_ZIP_SHA256:
        raise ValueError(f"unexpected d48 fallback SHA-256: {actual_hash}")

    with zipfile.ZipFile(input_zip) as archive:
        names = set(archive.namelist())
        if "00-manifest.json" not in names or "01-d48-youtube-fallback.json" not in names:
            raise ValueError("input ZIP does not contain the exact d48 fallback contract")
        manifest = json.loads(archive.read("00-manifest.json").decode("utf-8-sig"))
        result_raw = archive.read("01-d48-youtube-fallback.json")
        result = json.loads(result_raw.decode("utf-8-sig"))

    if manifest.get("schema") != "milovi-cake-d48-youtube-fallback-v1-manifest":
        raise ValueError("unexpected d48 fallback manifest schema")
    if result.get("schema") != "milovi-cake-d48-youtube-fallback-v1":
        raise ValueError("unexpected d48 fallback result schema")
    if _sha256_bytes(result_raw) != ACCEPTED_FALLBACK_RESULT_SHA256:
        raise ValueError("d48 fallback result is not the accepted uploaded result")
    if manifest.get("result_sha256") != ACCEPTED_FALLBACK_RESULT_SHA256:
        raise ValueError("d48 fallback manifest/result SHA-256 mismatch")

    evidence = result.get("input_evidence") or {}
    probe = result.get("browser_probe") or {}
    safety = result.get("safety") or {}
    capture = ((result.get("captures") or {}).get("youtube") or {}).get(YOUTUBE_ID) or {}
    frames = capture.get("frames") or []
    unique_phash = {str(frame.get("phash") or "") for frame in frames}

    if (
        result.get("project_key") != "milovi-cake"
        or result.get("youtube_channel_id") != "UCMDnxfGZiBqcDzgUV1zjFpw"
        or result.get("community_id") != 68859909
        or result.get("owner_id") != -68859909
        or result.get("read_only") is not True
        or result.get("provider_writes") != 0
        or result.get("provider_mutation_authorized") is not False
        or evidence.get("stable_retry_zip_sha256") != ACCEPTED_RETRY_ZIP_SHA256
        or evidence.get("accepted_vk_frames_reused") != 36
        or probe.get("vk_recapture_count") != 0
        or capture.get("status") != "captured"
        or capture.get("sample_count") != 12
        or len(frames) != 12
        or len(unique_phash) != 1
        or safety.get("surface_complete_claim") is not False
        or safety.get("same_media_claim") is not False
        or safety.get("missing_native_clip_claim") is not False
        or safety.get("upload_authorized") is not False
        or safety.get("transfer_queue_created") is not False
    ):
        raise ValueError("accepted d48 fallback does not match the exact consent-overlay failure contract")

    accepted_vk = (result.get("captures") or {}).get("vk") or {}
    for remote_id in VK_REMOTE_IDS:
        vk_capture = accepted_vk.get(remote_id) or {}
        if vk_capture.get("status") != "captured" or vk_capture.get("sample_count") != 12:
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


def _suppress_consent_overlay(page: Any) -> dict[str, Any]:
    try:
        value = page.evaluate(
            """() => {
                const markers = [
                    'прежде чем перейти к youtube',
                    'прежде чем продолжить работу с youtube',
                    'before you continue to youtube',
                    'before you continue to google',
                    'youtube использует файлы cookie'
                ];
                const video = document.querySelector('video');
                const vr = video ? video.getBoundingClientRect() : null;
                const overlap = (a, b) => {
                    if (!a || !b) return 0;
                    const left = Math.max(a.left, b.left);
                    const top = Math.max(a.top, b.top);
                    const right = Math.min(a.right, b.right);
                    const bottom = Math.min(a.bottom, b.bottom);
                    if (right <= left || bottom <= top) return 0;
                    const intersection = (right - left) * (bottom - top);
                    const base = Math.max(1, b.width * b.height);
                    return intersection / base;
                };
                const candidates = new Set();
                document.querySelectorAll(
                    'ytd-consent-bump-v2-lightbox, yt-consent-bump-v2-lightbox, tp-yt-paper-dialog, [role="dialog"], iframe[src*="consent"]'
                ).forEach((node) => candidates.add(node));
                document.querySelectorAll('div, section, form').forEach((node) => {
                    const text = (node.innerText || '').toLowerCase();
                    if (markers.some((marker) => text.includes(marker))) candidates.add(node);
                });

                const hidden = [];
                for (const candidate of candidates) {
                    if (!(candidate instanceof HTMLElement)) continue;
                    if (video && candidate.contains(video)) continue;
                    let chosen = candidate;
                    let cursor = candidate;
                    for (let depth = 0; depth < 6; depth += 1) {
                        const parent = cursor.parentElement;
                        if (!parent || parent === document.body || parent === document.documentElement) break;
                        if (video && parent.contains(video)) break;
                        const style = getComputedStyle(parent);
                        const rect = parent.getBoundingClientRect();
                        if ((style.position === 'fixed' || style.position === 'absolute') && overlap(rect, vr) >= 0.2) {
                            chosen = parent;
                        }
                        cursor = parent;
                    }
                    const rect = chosen.getBoundingClientRect();
                    const text = (chosen.innerText || candidate.innerText || '').toLowerCase();
                    const consentFrame = chosen.tagName === 'IFRAME' && String(chosen.getAttribute('src') || '').includes('consent');
                    if (vr && overlap(rect, vr) < 0.2 && !consentFrame) continue;
                    if (!consentFrame && !markers.some((marker) => text.includes(marker))) continue;
                    chosen.style.setProperty('visibility', 'hidden', 'important');
                    chosen.style.setProperty('pointer-events', 'none', 'important');
                    hidden.push(chosen.tagName.toLowerCase());
                }
                return {hidden_count: hidden.length, hidden_tags: [...new Set(hidden)].sort()};
            }"""
        )
    except Exception as exc:
        return {"hidden_count": 0, "hidden_tags": [], "error": f"{type(exc).__name__}: {exc}"[:500]}
    return value if isinstance(value, dict) else {"hidden_count": 0, "hidden_tags": []}


def _perceptual_diversity_gate(result: sequence.CaptureResult) -> sequence.CaptureResult:
    if result.status != "captured" or len(result.frames) < 6:
        return result
    unique_phash = len({str(frame.get("phash") or "") for frame in result.frames})
    minimum_unique = max(3, len(result.frames) // 4)
    if unique_phash >= minimum_unique:
        return result
    return replace(
        result,
        status="visual_capture_obscured",
        frames=(),
        error=(
            f"perceptual diversity collapsed to {unique_phash} unique pHash values across "
            f"{len(result.frames)} samples; consent/overlay-dominated evidence suppressed"
        ),
    )


def _capture_one(
    *,
    page: Any,
    url: str,
    output_dir: Path,
    wait_ms: int,
) -> tuple[sequence.CaptureResult, list[dict[str, Any]]]:
    original_find = sequence._find_video_handle
    original_seek = sequence._seek_video
    suppressions: list[dict[str, Any]] = []

    def clean_find(current_page: Any, *, wait_ms: int) -> tuple[Any, dict[str, Any]]:
        suppressions.append(_suppress_consent_overlay(current_page))
        return original_find(current_page, wait_ms=wait_ms)

    def clean_seek(handle: Any, target_seconds: float) -> dict[str, Any]:
        seek = original_seek(handle, target_seconds)
        suppressions.append(_suppress_consent_overlay(page))
        return seek

    sequence._find_video_handle = clean_find
    sequence._seek_video = clean_seek
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
    finally:
        sequence._find_video_handle = original_find
        sequence._seek_video = original_seek

    capture = stable_sequence._temporal_diversity_gate(capture)
    capture = _perceptual_diversity_gate(capture)
    return capture, suppressions


def _capture_with_clean_transports(
    *,
    seed_page: Any,
    output_dir: Path,
    wait_ms: int,
) -> tuple[sequence.CaptureResult, list[dict[str, Any]], str | None, int]:
    attempts: list[dict[str, Any]] = []
    last: sequence.CaptureResult | None = None
    selected: str | None = None
    local_dom_style_mutations = 0

    for transport, url in _transport_urls(YOUTUBE_ID):
        for attempt_number in (1, 2):
            if output_dir.exists():
                shutil.rmtree(output_dir)
            page = seed_page.context.new_page()
            try:
                capture, suppressions = _capture_one(
                    page=page,
                    url=url,
                    output_dir=output_dir,
                    wait_ms=wait_ms,
                )
                hidden_count = sum(int(item.get("hidden_count") or 0) for item in suppressions)
                local_dom_style_mutations += hidden_count
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
                        "unique_phash_count": len({str(frame.get("phash") or "") for frame in capture.frames}),
                        "consent_overlay_hidden_count": hidden_count,
                        "error": capture.error,
                    }
                )
                if capture.status == "captured":
                    selected = transport
                    return capture, attempts, selected, local_dom_style_mutations
            finally:
                try:
                    page.close()
                except Exception:
                    pass

    if output_dir.exists():
        shutil.rmtree(output_dir)
    if last is None:
        raise RuntimeError("overlay-clean d48 capture produced no result")
    return last, attempts, selected, local_dom_style_mutations


def build_overlay_clean_evidence(
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

    accepted, accepted_result_raw = _read_accepted_fallback(input_zip)
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
                capture, attempts, selected_transport, local_dom_style_mutations = _capture_with_clean_transports(
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
        "transport": "browser_ui_read_d48_overlay_clean",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            "d48_fallback_zip_sha256": _sha256_path(input_zip),
            "d48_fallback_result_sha256": _sha256_bytes(accepted_result_raw),
            "accepted_vk_frames_reused": copied_vk_frame_count,
            "prior_capture_unique_phash_count": 1,
            "surface_complete_claim": False,
        },
        "capture_scope": {
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
            "local_dom_style_mutations": local_dom_style_mutations,
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
            "This collector retries only d48QLgOuiTs after the accepted watch capture was visually obscured by YouTube consent UI.",
            "Consent UI is hidden only by ephemeral local DOM style changes; no consent button is clicked and no cookie/profile state is persisted.",
            "The three VK sequences are reused byte-for-byte from the pinned accepted fallback and are not recaptured.",
            "A perceptual-diversity gate suppresses captures with fewer than three unique pHash values across twelve samples.",
            "Sequence metrics remain supporting evidence; manual visual adjudication is required.",
            "A distinct sequence does not create a provider-surface completeness or missing-Clip claim.",
        ],
    }

    result_path = output_dir / "01-d48-youtube-overlay-clean.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": "milovi-cake",
        "provider_writes": 0,
        "mutation_authority": False,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "accepted_input_zip_sha256": ACCEPTED_FALLBACK_ZIP_SHA256,
        "accepted_input_result_sha256": ACCEPTED_FALLBACK_RESULT_SHA256,
        "copied_vk_frame_count": copied_vk_frame_count,
        "youtube_frame_file_count": (
            sum(path.is_file() for path in (output_dir / "frames" / "youtube").rglob("*"))
            if (output_dir / "frames" / "youtube").exists()
            else 0
        ),
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
    root = argparse.ArgumentParser(description="Capture only d48 after suppressing local YouTube consent overlays.")
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
        result = build_overlay_clean_evidence(
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
                "provider_writes": 0,
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
