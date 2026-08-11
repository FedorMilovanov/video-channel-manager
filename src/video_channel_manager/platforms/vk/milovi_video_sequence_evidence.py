from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import io
import json
import math
import statistics
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qs, urlsplit

from video_channel_manager.platforms.vk import clips_ui_inventory as clips_ui
from video_channel_manager.platforms.vk import milovi_gap_thumbnail_evidence as gap

OUTPUT_SCHEMA = "milovi-cake-video-sequence-evidence-v1"
INPUT_MANIFEST_SCHEMA = f"{gap.OUTPUT_SCHEMA}-manifest"
EXPECTED_CLIP_COUNT = 106
_SAMPLE_POSITIONS = (0.06, 0.14, 0.22, 0.30, 0.38, 0.46, 0.54, 0.62, 0.70, 0.78, 0.86, 0.94)
_DCT_COS: tuple[tuple[float, ...], ...] = tuple(
    tuple(math.cos((2 * position + 1) * frequency * math.pi / 64.0) for position in range(32)) for frequency in range(8)
)
_BLOCK_HINTS = (
    "captcha",
    "робот",
    "авториз",
    "войдите",
    "sign in",
    "access denied",
    "доступ ограничен",
)

# Reviewed pairs after the thumbnail-evidence pass. These are evidence probes, never an upload queue.
# fmt: off
_REVIEWED_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("FQGxV4DRPQw", "-68859909_456239159", "suspected_same_media", "manual_thumbnail_review_strong"),
    ("MdQ0kNBSsa8", "-68859909_456239176", "suspected_same_media", "manual_thumbnail_review_strong"),
    ("cE0ofu6WV3s", "-68859909_456239162", "suspected_same_media", "manual_thumbnail_review_strong"),
    ("CQ29P1F8Hfo", "-68859909_456239100", "suspected_edit_variant", "manual_thumbnail_review_same_shoot"),
    ("R-LknUy9BEs", "-68859909_456239031", "suspected_same_media", "manual_thumbnail_review_possible"),
    ("SiluLt5Bz1c", "-68859909_456239076", "negative_control", "manual_thumbnail_review_distinct"),
    ("BAVKrQQ00XI", "-68859909_456239061", "negative_control", "manual_thumbnail_review_distinct"),
    ("p3xZaajOMvc", "-68859909_456239130", "reference_pair", "wall_proven_shrek_control"),
)
# fmt: on


@dataclass(frozen=True)
class FrameFingerprint:
    sha256: str
    dhash_hex: str
    phash_hex: str
    width: int
    height: int


@dataclass(frozen=True)
class CaptureResult:
    status: str
    canonical_url: str
    final_url: str
    duration_s: float | None
    video_width: int | None
    video_height: int | None
    frames: tuple[dict[str, Any], ...]
    page_title: str
    block_hints: tuple[str, ...]
    error: str | None = None


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
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(raw)


def _youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def _vk_url(remote_id: str) -> str:
    return f"https://vk.com/clip{remote_id}"


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return parsed.path
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _identity_url_matches(*, platform: str, expected_id: str, raw_url: str) -> bool:
    parsed = urlsplit(raw_url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if platform == "youtube":
        allowed = host == "youtube.com" or host.endswith(".youtube.com")
        query_video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        return allowed and (
            path.endswith(f"/shorts/{expected_id}") or (path.endswith("/watch") and query_video_id == expected_id)
        )
    if platform == "vk":
        allowed = (
            host in {"vk.com", "vk.ru", "vkvideo.ru"}
            or host.endswith(".vk.com")
            or host.endswith(".vk.ru")
            or host.endswith(".vkvideo.ru")
        )
        return allowed and (path.endswith(f"/clip{expected_id}") or path.endswith(f"/video{expected_id}"))
    raise ValueError(f"unsupported platform: {platform}")


def _load_pillow() -> Any:
    try:
        from PIL import Image, ImageOps  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Pillow is required; install current repo with: pip install -e ".[browser-read,milovi-gap-read]"'
        ) from exc
    return Image, ImageOps


def _dhash_image(image: Any) -> str:
    Image, _ = _load_pillow()
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (1 if pixels[y * 9 + x] > pixels[y * 9 + x + 1] else 0)
    return f"{value:016x}"


def _phash_image(image: Any) -> str:
    Image, ImageOps = _load_pillow()
    normalized = ImageOps.fit(image.convert("L"), (32, 32), method=Image.Resampling.LANCZOS)
    pixels = list(normalized.getdata())
    coeffs: list[float] = []
    for u in range(8):
        cos_x = _DCT_COS[u]
        for v in range(8):
            cos_y = _DCT_COS[v]
            total = 0.0
            for y in range(32):
                row = y * 32
                y_factor = cos_y[y]
                for x in range(32):
                    total += pixels[row + x] * cos_x[x] * y_factor
            coeffs.append(total)
    median = statistics.median(coeffs[1:])
    value = 0
    for coeff in coeffs:
        value = (value << 1) | (1 if coeff > median else 0)
    return f"{value:016x}"


def _frame_fingerprint(data: bytes) -> tuple[FrameFingerprint, bytes]:
    Image, _ = _load_pillow()
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        image = source.convert("RGB")
        width, height = image.size
        longest = max(width, height)
        if longest > 720:
            scale = 720.0 / longest
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90, optimize=True)
        normalized_bytes = buffer.getvalue()
        fingerprint = FrameFingerprint(
            sha256=_sha256_bytes(normalized_bytes),
            dhash_hex=_dhash_image(image),
            phash_hex=_phash_image(image),
            width=width,
            height=height,
        )
    return fingerprint, normalized_bytes


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _combined_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    dhash_distance = _hamming(str(left["dhash"]), str(right["dhash"]))
    phash_distance = _hamming(str(left["phash"]), str(right["phash"]))
    return round(0.4 * dhash_distance + 0.6 * phash_distance, 3)


def _distance_matrix(
    left_frames: Sequence[dict[str, Any]],
    right_frames: Sequence[dict[str, Any]],
) -> list[list[float]]:
    return [[_combined_distance(left, right) for right in right_frames] for left in left_frames]


def _monotonic_matches(
    matrix: Sequence[Sequence[float]],
    *,
    threshold: float,
) -> list[tuple[int, int, float]]:
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    dp: list[list[tuple[int, float, tuple[tuple[int, int, float], ...]]]] = [
        [(0, 0.0, ()) for _ in range(cols + 1)] for _ in range(rows + 1)
    ]

    def better(
        left: tuple[int, float, tuple[tuple[int, int, float], ...]],
        right: tuple[int, float, tuple[tuple[int, int, float], ...]],
    ) -> tuple[int, float, tuple[tuple[int, int, float], ...]]:
        if left[0] != right[0]:
            return left if left[0] > right[0] else right
        if left[1] != right[1]:
            return left if left[1] < right[1] else right
        return left if left[2] <= right[2] else right

    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            best = better(dp[i - 1][j], dp[i][j - 1])
            distance = float(matrix[i - 1][j - 1])
            if distance <= threshold:
                count, cost, path = dp[i - 1][j - 1]
                matched = (count + 1, cost + distance, path + ((i - 1, j - 1, distance),))
                best = better(best, matched)
            dp[i][j] = best
    return list(dp[rows][cols][2])


def _sequence_metrics(
    left_frames: Sequence[dict[str, Any]],
    right_frames: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if not left_frames or not right_frames:
        return {
            "comparable": False,
            "strong_match_count": 0,
            "support_match_count": 0,
            "loose_match_count": 0,
            "support_coverage": 0.0,
            "loose_coverage": 0.0,
            "median_support_distance": None,
            "median_row_best_distance": None,
            "exact_normalized_frame_sha_matches": 0,
            "support_matches": [],
        }

    matrix = _distance_matrix(left_frames, right_frames)
    strong_matches = _monotonic_matches(matrix, threshold=8.0)
    support_matches = _monotonic_matches(matrix, threshold=12.0)
    loose_matches = _monotonic_matches(matrix, threshold=16.0)
    denominator = min(len(left_frames), len(right_frames))
    row_best = [min(row) for row in matrix if row]
    exact_sha = len({str(left["sha256"]) for left in left_frames} & {str(right["sha256"]) for right in right_frames})
    return {
        "comparable": True,
        "strong_match_count": len(strong_matches),
        "support_match_count": len(support_matches),
        "loose_match_count": len(loose_matches),
        "support_coverage": round(len(support_matches) / denominator, 6),
        "loose_coverage": round(len(loose_matches) / denominator, 6),
        "median_support_distance": (
            round(statistics.median(match[2] for match in support_matches), 3) if support_matches else None
        ),
        "median_row_best_distance": round(statistics.median(row_best), 3) if row_best else None,
        "exact_normalized_frame_sha_matches": exact_sha,
        "support_matches": [
            {
                "youtube_frame_index": i,
                "vk_frame_index": j,
                "distance": round(distance, 3),
            }
            for i, j, distance in support_matches
        ],
    }


def _evidence_class(
    metrics: dict[str, Any],
    *,
    youtube_duration_s: float | None,
    vk_duration_s: float | None,
) -> str:
    if metrics.get("comparable") is not True:
        return "INSUFFICIENT_VIDEO_EVIDENCE"

    support_coverage = float(metrics.get("support_coverage") or 0.0)
    loose_coverage = float(metrics.get("loose_coverage") or 0.0)
    strong_count = int(metrics.get("strong_match_count") or 0)
    median_support = metrics.get("median_support_distance")
    row_best = metrics.get("median_row_best_distance")
    duration_ratio = None
    if youtube_duration_s is not None and vk_duration_s is not None and youtube_duration_s > 0 and vk_duration_s > 0:
        duration_ratio = min(youtube_duration_s, vk_duration_s) / max(youtube_duration_s, vk_duration_s)

    if support_coverage >= 0.75 and strong_count >= 5 and isinstance(median_support, (int, float)):
        if median_support <= 9.0 and duration_ratio is not None and duration_ratio >= 0.94:
            return "STRONG_SAME_EDIT_SEQUENCE_SUPPORT"
        if median_support <= 10.5:
            return "STRONG_SHARED_SEQUENCE_EDIT_VARIANT_SUPPORT"

    if loose_coverage >= 0.58 and isinstance(row_best, (int, float)) and row_best <= 14.0:
        return "SHARED_SOURCE_SEQUENCE_SUPPORT"

    if loose_coverage <= 0.25 and isinstance(row_best, (int, float)) and row_best >= 18.0:
        return "DISTINCT_SEQUENCE_SUPPORT"

    return "INCONCLUSIVE_VIDEO_SEQUENCE"


def _operational_disposition(evidence_class: str) -> str:
    if evidence_class in {
        "STRONG_SAME_EDIT_SEQUENCE_SUPPORT",
        "STRONG_SHARED_SEQUENCE_EDIT_VARIANT_SUPPORT",
        "SHARED_SOURCE_SEQUENCE_SUPPORT",
    }:
        return "BLOCK_DUPLICATE_UPLOAD_PENDING_REVIEW"
    if evidence_class == "DISTINCT_SEQUENCE_SUPPORT":
        return "NO_ABSENCE_CLAIM_DISTINCT_FROM_THIS_VK_CLIP"
    return "REVIEW_REQUIRED_NO_UPLOAD"


def _read_input(input_zip: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    if not input_zip.is_file():
        raise ValueError(f"input evidence ZIP does not exist: {input_zip}")

    with zipfile.ZipFile(input_zip) as archive:
        names = set(archive.namelist())
        if "00-manifest.json" not in names or "01-gap-thumbnail-reconciliation.json" not in names:
            raise ValueError("input ZIP does not contain the exact Milovi thumbnail-evidence contract")
        manifest_bytes = archive.read("00-manifest.json")
        result_bytes = archive.read("01-gap-thumbnail-reconciliation.json")

    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    result = json.loads(result_bytes.decode("utf-8-sig"))
    if manifest.get("schema") != INPUT_MANIFEST_SCHEMA:
        raise ValueError(f"unexpected input manifest schema: {manifest.get('schema')}")
    if result.get("schema") != gap.OUTPUT_SCHEMA:
        raise ValueError(f"unexpected input result schema: {result.get('schema')}")
    if manifest.get("result_sha256") != _sha256_bytes(result_bytes):
        raise ValueError("input result SHA-256 does not match manifest")

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
        or input_evidence.get("exact_public_ui_clip_count") != EXPECTED_CLIP_COUNT
        or input_evidence.get("exact_wall_native_clip_count") != EXPECTED_CLIP_COUNT
        or input_evidence.get("exact_ui_wall_intersection_count") != EXPECTED_CLIP_COUNT
        or input_evidence.get("ui_only_count") != 0
        or input_evidence.get("wall_only_count") != 0
        or input_evidence.get("surface_complete_claim") is not False
        or safety.get("upload_authorized") is not False
    ):
        raise ValueError("input Milovi identity/read-only/coverage contract is invalid")

    candidates = result.get("candidates") or []
    candidate_ids = {str(candidate.get("youtube_id") or "") for candidate in candidates if isinstance(candidate, dict)}
    expected_candidate_ids = {str(row["youtube_id"]) for row in gap._GAP_CANDIDATES}
    if candidate_ids != expected_candidate_ids:
        raise ValueError("input candidate manifest does not match the exact reviewed 25-item scope")

    with zipfile.ZipFile(input_zip) as archive:
        for youtube_id, remote_id, role, _prior in _REVIEWED_PAIRS:
            if role != "reference_pair" and youtube_id not in candidate_ids:
                raise ValueError(f"reviewed YouTube pair is outside candidate scope: {youtube_id}")
            vk_member = f"media/vk/neg{abs(gap.MILOVI_OWNER_ID)}_{remote_id.rsplit('_', 1)[1]}.jpg"
            if vk_member not in archive.namelist():
                raise ValueError(f"reviewed VK Clip is not present in accepted 106-item media evidence: {remote_id}")

    return (
        manifest,
        result,
        {
            "input_zip_sha256": _sha256_path(input_zip),
            "input_manifest_sha256": _sha256_bytes(manifest_bytes),
            "input_result_sha256": _sha256_bytes(result_bytes),
        },
    )


def _playwright_version() -> str | None:
    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        return None


def _find_video_handle(page: Any, *, wait_ms: int) -> tuple[Any, dict[str, Any]]:
    deadline_rounds = max(4, round(30_000 / max(wait_ms, 250)))
    for _ in range(deadline_rounds):
        best: tuple[int, Any, dict[str, Any]] | None = None
        for frame in page.frames:
            try:
                handles = frame.query_selector_all("video")
            except Exception:
                continue
            for handle in handles:
                try:
                    metadata = handle.evaluate(
                        """(v) => {
                            const rect = v.getBoundingClientRect();
                            const style = getComputedStyle(v);
                            return {
                                duration: Number.isFinite(v.duration) ? v.duration : null,
                                videoWidth: v.videoWidth || 0,
                                videoHeight: v.videoHeight || 0,
                                readyState: v.readyState || 0,
                                clientWidth: rect.width || 0,
                                clientHeight: rect.height || 0,
                                visible: style.visibility !== "hidden"
                                    && style.display !== "none"
                                    && rect.width >= 40
                                    && rect.height >= 40
                            };
                        }"""
                    )
                except Exception:
                    continue
                if not isinstance(metadata, dict):
                    continue
                duration = metadata.get("duration")
                width = int(metadata.get("videoWidth") or 0)
                height = int(metadata.get("videoHeight") or 0)
                ready_state = int(metadata.get("readyState") or 0)
                client_width = int(float(metadata.get("clientWidth") or 0))
                client_height = int(float(metadata.get("clientHeight") or 0))
                if (
                    not isinstance(duration, (int, float))
                    or duration <= 0
                    or width <= 0
                    or height <= 0
                    or metadata.get("visible") is not True
                    or client_width <= 0
                    or client_height <= 0
                ):
                    continue
                area = client_width * client_height
                if ready_state >= 1 and (best is None or area > best[0]):
                    best = (area, handle, metadata)
        if best is not None:
            return best[1], best[2]
        page.wait_for_timeout(wait_ms)
    raise RuntimeError("no playable <video> element with finite duration was observed")


def _seek_video(handle: Any, target_seconds: float) -> dict[str, Any]:
    result = handle.evaluate(
        """(v, target) => new Promise((resolve) => {
            const finish = (ok, reason) => resolve({
                ok,
                reason,
                currentTime: Number.isFinite(v.currentTime) ? v.currentTime : null,
                readyState: v.readyState || 0
            });
            let finished = false;
            const done = (ok, reason) => {
                if (finished) return;
                finished = true;
                clearTimeout(timer);
                finish(ok, reason);
            };
            const timer = setTimeout(() => done(false, "seek_timeout"), 12000);
            const onSeeked = () => {
                if (v.readyState >= 2) done(true, "seeked");
            };
            v.addEventListener("seeked", onSeeked, {once: true});
            try {
                v.muted = true;
                v.pause();
                v.currentTime = target;
                if (Math.abs(v.currentTime - target) < 0.08 && v.readyState >= 2) {
                    setTimeout(() => done(true, "already_at_target"), 50);
                }
            } catch (error) {
                done(false, String(error));
            }
        })""",
        target_seconds,
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        reason = result.get("reason") if isinstance(result, dict) else "unknown_seek_failure"
        raise RuntimeError(f"video seek failed: {reason}")
    return result


def _capture_page_sequence(
    *,
    page: Any,
    platform: str,
    expected_id: str,
    url: str,
    output_dir: Path,
    wait_ms: int,
) -> CaptureResult:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(max(wait_ms, 1200))
    raw_final_url = str(page.url)
    final_url = _safe_url(raw_final_url)
    page_title = str(page.title())[:500]
    try:
        body_text = str(page.evaluate("() => document.body ? document.body.innerText.slice(0, 12000) : ''"))
    except Exception:
        body_text = ""
    block_hints = tuple(sorted({hint for hint in _BLOCK_HINTS if hint in body_text.lower()}))
    if not _identity_url_matches(platform=platform, expected_id=expected_id, raw_url=raw_final_url):
        return CaptureResult(
            status="identity_not_observed",
            canonical_url=url,
            final_url=final_url,
            duration_s=None,
            video_width=None,
            video_height=None,
            frames=(),
            page_title=page_title,
            block_hints=block_hints,
            error="final browser URL did not retain the exact expected media identity",
        )

    handle, metadata = _find_video_handle(page, wait_ms=wait_ms)
    duration = float(metadata["duration"])
    video_width = int(metadata.get("videoWidth") or 0)
    video_height = int(metadata.get("videoHeight") or 0)
    frames: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, position in enumerate(_SAMPLE_POSITIONS):
        target = max(0.15, min(duration - 0.15, duration * position))
        try:
            seek = _seek_video(handle, target)
        except Exception:
            handle, metadata = _find_video_handle(page, wait_ms=wait_ms)
            seek = _seek_video(handle, target)
        page.wait_for_timeout(120)
        screenshot = handle.screenshot(type="png")
        fingerprint, normalized = _frame_fingerprint(screenshot)
        filename = f"{index:02d}-{position:.2f}.jpg"
        (output_dir / filename).write_bytes(normalized)
        frames.append(
            {
                "index": index,
                "position": position,
                "target_time_s": round(target, 3),
                "observed_time_s": round(float(seek.get("currentTime") or target), 3),
                "filename": filename,
                "sha256": fingerprint.sha256,
                "dhash": fingerprint.dhash_hex,
                "phash": fingerprint.phash_hex,
                "source_width": fingerprint.width,
                "source_height": fingerprint.height,
            }
        )

    return CaptureResult(
        status="captured",
        canonical_url=url,
        final_url=final_url,
        duration_s=round(duration, 3),
        video_width=video_width,
        video_height=video_height,
        frames=tuple(frames),
        page_title=page_title,
        block_hints=block_hints,
    )


def _capture_to_json(capture: CaptureResult) -> dict[str, Any]:
    return {
        "status": capture.status,
        "canonical_url": capture.canonical_url,
        "final_url": capture.final_url,
        "duration_s": capture.duration_s,
        "video_width": capture.video_width,
        "video_height": capture.video_height,
        "sample_count": len(capture.frames),
        "sample_positions": list(_SAMPLE_POSITIONS),
        "frames": list(capture.frames),
        "page_title": capture.page_title,
        "block_hints": list(capture.block_hints),
        "error": capture.error,
    }


def build_video_sequence_evidence(
    *,
    input_zip: Path,
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

    _manifest, input_result, input_hashes = _read_input(input_zip)
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Playwright is required; install current repo with: pip install -e ".[browser-read,milovi-gap-read]"'
        ) from exc

    executable = clips_ui._resolve_browser_executable(browser_executable)
    sync_playwright: Any = vars(sync_api)["sync_playwright"]
    output_dir.mkdir(parents=True)
    frame_root = output_dir / "frames"
    captures_youtube: dict[str, dict[str, Any]] = {}
    captures_vk: dict[str, dict[str, Any]] = {}

    youtube_ids = sorted({row[0] for row in _REVIEWED_PAIRS})
    vk_ids = sorted({row[1] for row in _REVIEWED_PAIRS})
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
                    capture = _capture_page_sequence(
                        page=page,
                        platform="youtube",
                        expected_id=youtube_id,
                        url=_youtube_url(youtube_id),
                        output_dir=frame_root / "youtube" / youtube_id,
                        wait_ms=wait_ms,
                    )
                except Exception as exc:
                    capture = CaptureResult(
                        status="capture_error",
                        canonical_url=_youtube_url(youtube_id),
                        final_url=_safe_url(str(page.url)),
                        duration_s=None,
                        video_width=None,
                        video_height=None,
                        frames=(),
                        page_title="",
                        block_hints=(),
                        error=f"{type(exc).__name__}: {exc}"[:1000],
                    )
                captures_youtube[youtube_id] = _capture_to_json(capture)

            for remote_id in vk_ids:
                try:
                    capture = _capture_page_sequence(
                        page=page,
                        platform="vk",
                        expected_id=remote_id,
                        url=_vk_url(remote_id),
                        output_dir=frame_root / "vk" / remote_id.replace("-", "neg"),
                        wait_ms=wait_ms,
                    )
                except Exception as exc:
                    capture = CaptureResult(
                        status="capture_error",
                        canonical_url=_vk_url(remote_id),
                        final_url=_safe_url(str(page.url)),
                        duration_s=None,
                        video_width=None,
                        video_height=None,
                        frames=(),
                        page_title="",
                        block_hints=(),
                        error=f"{type(exc).__name__}: {exc}"[:1000],
                    )
                captures_vk[remote_id] = _capture_to_json(capture)
        finally:
            context.close()
            browser.close()

    input_candidates = {
        str(candidate.get("youtube_id") or ""): candidate
        for candidate in input_result.get("candidates") or []
        if isinstance(candidate, dict)
    }
    pair_results: list[dict[str, Any]] = []
    for youtube_id, remote_id, review_role, prior_review in _REVIEWED_PAIRS:
        youtube_capture = captures_youtube[youtube_id]
        vk_capture = captures_vk[remote_id]
        metrics = _sequence_metrics(
            youtube_capture.get("frames") or [],
            vk_capture.get("frames") or [],
        )
        evidence_class = _evidence_class(
            metrics,
            youtube_duration_s=youtube_capture.get("duration_s"),
            vk_duration_s=vk_capture.get("duration_s"),
        )
        candidate = input_candidates.get(youtube_id)
        pair_results.append(
            {
                "pair_key": f"{youtube_id}__{remote_id}",
                "youtube_id": youtube_id,
                "youtube_title": str(candidate.get("title") or "") if candidate else "",
                "youtube_scope": str(candidate.get("scope") or "control") if candidate else "control",
                "youtube_url": _youtube_url(youtube_id),
                "vk_remote_id": remote_id,
                "vk_clip_url": _vk_url(remote_id),
                "review_role": review_role,
                "prior_review": prior_review,
                "youtube_capture_status": youtube_capture.get("status"),
                "vk_capture_status": vk_capture.get("status"),
                "youtube_duration_s": youtube_capture.get("duration_s"),
                "vk_duration_s": vk_capture.get("duration_s"),
                "sequence_metrics": metrics,
                "evidence_class": evidence_class,
                "operational_disposition": _operational_disposition(evidence_class),
                "same_media_claim": False,
                "same_final_edit_claim": False,
                "missing_native_clip_claim": False,
                "upload_authorized": False,
            }
        )

    captured_youtube = sum(row.get("status") == "captured" for row in captures_youtube.values())
    captured_vk = sum(row.get("status") == "captured" for row in captures_vk.values())
    complete_capture = captured_youtube == len(youtube_ids) and captured_vk == len(vk_ids)
    result = {
        "schema": OUTPUT_SCHEMA,
        "generated_at": _utc_iso(),
        "status": "completed" if complete_capture else "partial_browser_evidence",
        "project_key": gap.MILOVI_PROJECT_KEY,
        "youtube_channel_id": gap.MILOVI_YOUTUBE_CHANNEL_ID,
        "community_id": gap.MILOVI_COMMUNITY_ID,
        "owner_id": gap.MILOVI_OWNER_ID,
        "transport": "browser_ui_read",
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            **input_hashes,
            "thumbnail_evidence_schema": input_result.get("schema"),
            "exact_public_ui_clip_count": EXPECTED_CLIP_COUNT,
            "exact_wall_native_clip_count": EXPECTED_CLIP_COUNT,
            "exact_ui_wall_intersection_count": EXPECTED_CLIP_COUNT,
            "surface_complete_claim": False,
        },
        "pair_manifest": {
            "count": len(_REVIEWED_PAIRS),
            "canonical_sha256": _canonical_json_sha256(_REVIEWED_PAIRS),
            "suspected_pairs": sum(row[2].startswith("suspected") for row in _REVIEWED_PAIRS),
            "negative_controls": sum(row[2] == "negative_control" for row in _REVIEWED_PAIRS),
            "reference_pairs": sum(row[2] == "reference_pair" for row in _REVIEWED_PAIRS),
            "source_role": "reviewed video-sequence evidence probes; not an upload queue",
        },
        "browser_probe": {
            "browser_executable_name": executable.name,
            "playwright_version": _playwright_version(),
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
            "sample_positions": list(_SAMPLE_POSITIONS),
        },
        "captures": {
            "youtube": captures_youtube,
            "vk": captures_vk,
        },
        "pair_results": pair_results,
        "safety": {
            "same_media_claim_from_browser_frames": False,
            "same_final_edit_claim_from_browser_frames": False,
            "missing_native_clip_claim_from_non_match": False,
            "upload_authorized": False,
            "delete_authorized": False,
            "hide_authorized": False,
            "wall_post_authorized": False,
            "schedule_authorized": False,
            "transfer_queue_created": False,
        },
        "known_limitations": [
            "Browser-rendered frame sequences are supporting evidence, not byte identity or source-master proof.",
            "A strong shared sequence can block duplicate upload pending review; it does not authorize any provider mutation.",
            "A distinct or missing frame sequence does not prove the YouTube item is absent from the full VK Clips owner surface.",
            "The public UI and published-wall Clip sets remain a bounded 106-item observation with surface_complete_claim=false.",
            "Only reviewed cake/pastry/dessert pairs and one cake reference pair are probed; no personal/family/non-confectionery content is included.",
        ],
    }

    result_path = output_dir / "01-video-sequence-reconciliation.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": f"{OUTPUT_SCHEMA}-manifest",
        "generated_at": _utc_iso(),
        "project_key": gap.MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "result_file": result_path.name,
        "result_sha256": _sha256_path(result_path),
        "frame_file_count": sum(path.is_file() for path in frame_root.rglob("*")),
        "input_evidence": input_hashes,
        "pair_manifest_sha256": _canonical_json_sha256(_REVIEWED_PAIRS),
        "surface_complete_claim": False,
        "mutation_authority": False,
    }
    manifest_path = output_dir / "00-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    zip_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build read-only browser video-sequence evidence for reviewed Milovi confectionery pairs."
    )
    root.add_argument("--input", type=Path, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--zip-output", type=Path, required=True)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--wait-ms", type=int, default=500)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = build_video_sequence_evidence(
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
                {
                    "status": "failed",
                    "provider_writes": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": result["status"],
                "pairs": result["pair_manifest"]["count"],
                "youtube_captured": result["browser_probe"]["youtube_capture_count"],
                "vk_captured": result["browser_probe"]["vk_capture_count"],
                "provider_writes": 0,
                "output_dir": str(args.output_dir.resolve()),
                "zip_output": str(args.zip_output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
