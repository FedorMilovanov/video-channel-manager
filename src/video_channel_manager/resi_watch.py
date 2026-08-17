from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import parse_qs, urlparse, urlunparse

from video_channel_manager.resi_handoff import (
    ResiHandoffSpec,
    canonical_source_identity,
    default_title_for_url,
    format_timestamp,
    parse_timestamp,
)


class ResiWatchTimeout(RuntimeError):
    pass


class ResiWatchAmbiguous(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestObservation:
    page_url: str
    final_page_url: str
    manifest_url: str
    source_identity: str
    source_fingerprint: str
    frame_url: str | None
    player_id: str | None


@dataclass(frozen=True)
class PageProbeResult:
    page_url: str
    final_page_url: str
    observations: tuple[ManifestObservation, ...]


ProbePage = Callable[[str, float], PageProbeResult]


def source_fingerprint(url: str) -> str:
    identity = canonical_source_identity(url)
    return "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def canonical_page_identity(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("page URL must be an absolute http(s) URL")
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def is_resi_manifest_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        return False
    if host != "resi.media" and not host.endswith(".resi.media"):
        return False
    return parsed.path.lower().endswith("/manifest.mpd")


def extract_resi_player_id(frame_url: str | None) -> str | None:
    if not frame_url:
        return None
    parsed = urlparse(frame_url)
    if (parsed.hostname or "").lower() != "control.resi.io":
        return None
    if parsed.path.lower() != "/webplayer/video.html":
        return None
    values = parse_qs(parsed.query).get("id", [])
    return values[0] if values else None


def _observation(page_url: str, final_page_url: str, manifest_url: str, frame_url: str | None) -> ManifestObservation:
    return ManifestObservation(
        page_url=page_url,
        final_page_url=final_page_url,
        manifest_url=manifest_url,
        source_identity=canonical_source_identity(manifest_url),
        source_fingerprint=source_fingerprint(manifest_url),
        frame_url=frame_url,
        player_id=extract_resi_player_id(frame_url),
    )


def probe_page(page_url: str, wait_seconds: float) -> PageProbeResult:
    canonical_page_identity(page_url)
    if wait_seconds <= 0:
        raise ValueError("wait_seconds must be positive")
    try:
        sync_playwright = import_module("playwright.sync_api").sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is required for resi watch; install the browser-read extra and Chromium: "
            "python -m pip install -e '.[browser-read]' && python -m playwright install chromium"
        ) from exc

    found: dict[str, tuple[str, str | None]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def inspect(request: Any) -> None:
            manifest_url = str(request.url)
            if not is_resi_manifest_url(manifest_url):
                return
            frame_url: str | None
            try:
                frame_url = str(request.frame.url)
            except Exception:
                frame_url = None
            identity = canonical_source_identity(manifest_url)
            existing = found.get(identity)
            if existing is None or (existing[1] is None and frame_url is not None):
                found[identity] = (manifest_url, frame_url)

        context.on("request", inspect)
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(round(wait_seconds * 1000))
            final_page_url = page.url
        finally:
            browser.close()

    observations = tuple(
        _observation(page_url, final_page_url, manifest_url, frame_url) for manifest_url, frame_url in found.values()
    )
    return PageProbeResult(page_url=page_url, final_page_url=final_page_url, observations=observations)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _read_last_identity(state_path: Path, *, expected_page_url: str) -> str | None:
    if not state_path.is_file():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Watcher state is unreadable; refusing duplicate-prone restart: {state_path}") from exc

    state_page_identity = payload.get("target_page_identity")
    if not isinstance(state_page_identity, str) or not state_page_identity:
        raise RuntimeError(
            f"Watcher state is legacy/unscoped and cannot be safely reused across pages: {state_path}. "
            "Preserve the last manifest as --known-manifest, then remove or replace this state file."
        )
    expected_identity = canonical_page_identity(expected_page_url)
    if state_page_identity != expected_identity:
        raise RuntimeError(
            "Watcher state belongs to a different target page; refusing cross-page baseline reuse. "
            f"state={state_page_identity!r}, requested={expected_identity!r}, path={state_path}"
        )

    value = payload.get("last_source_identity")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Watcher state is missing last_source_identity: {state_path}")
    return value


def _single_observation(result: PageProbeResult, *, label: str) -> ManifestObservation | None:
    by_identity = {item.source_identity: item for item in result.observations}
    if len(by_identity) > 1:
        identities = ", ".join(sorted(by_identity))
        raise ResiWatchAmbiguous(f"{label} exposed multiple distinct Resi manifests: {identities}")
    return next(iter(by_identity.values()), None)


def watch_for_new_manifest(
    page_url: str,
    *,
    known_manifest: str | None,
    compare_page: str | None,
    timeout_seconds: float,
    poll_seconds: float,
    probe_wait_seconds: float,
    max_consecutive_probe_errors: int = 10,
    latest_txt: Path,
    latest_json: Path,
    state_path: Path,
    probe: ProbePage = probe_page,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    target_page_identity = canonical_page_identity(page_url)
    if compare_page is not None:
        canonical_page_identity(compare_page)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    if probe_wait_seconds <= 0:
        raise ValueError("probe_wait_seconds must be positive")
    if max_consecutive_probe_errors <= 0:
        raise ValueError("max_consecutive_probe_errors must be positive")

    ignored: set[str] = set()
    if known_manifest is not None:
        if not is_resi_manifest_url(known_manifest):
            raise ValueError("known_manifest must be an HTTPS resi.media Manifest.mpd URL")
        ignored.add(canonical_source_identity(known_manifest))
    persisted_identity = _read_last_identity(state_path, expected_page_url=page_url)
    if persisted_identity:
        ignored.add(persisted_identity)

    deadline = monotonic() + timeout_seconds
    last_error: str | None = None
    consecutive_probe_errors = 0
    while True:
        try:
            target_result = probe(page_url, probe_wait_seconds)
            target = _single_observation(target_result, label="target page")
            last_error = None
            consecutive_probe_errors = 0
        except ResiWatchAmbiguous:
            raise
        except Exception as exc:
            target = None
            consecutive_probe_errors += 1
            last_error = f"{type(exc).__name__}: {exc}"
            if consecutive_probe_errors >= max_consecutive_probe_errors:
                raise RuntimeError(
                    f"{consecutive_probe_errors} consecutive Resi page probes failed. Last error: {last_error}"
                ) from exc

        if target is not None and target.source_identity not in ignored:
            compare_payload: dict[str, Any] | None = None
            if compare_page:
                try:
                    compare_result = probe(compare_page, probe_wait_seconds)
                    compare = _single_observation(compare_result, label="compare page")
                    compare_payload = {
                        "page_url": compare_page,
                        "final_page_url": compare_result.final_page_url,
                        "observation": asdict(compare) if compare else None,
                    }
                except Exception as exc:
                    compare_payload = {
                        "page_url": compare_page,
                        "error": f"{type(exc).__name__}: {exc}",
                    }

            captured_at = datetime.now(UTC).isoformat()
            payload: dict[str, Any] = {
                "schema_name": "video-manager.resi-watch-capture",
                "schema_version": 2,
                "captured_at": captured_at,
                "target_page_identity": target_page_identity,
                "target": asdict(target),
                "compare": compare_payload,
                "language_claim": "unverified",
                "full_download_dispatched": False,
            }
            state_payload = {
                "schema_name": "video-manager.resi-watch-state",
                "schema_version": 2,
                "updated_at": captured_at,
                "target_page_url": page_url,
                "target_page_identity": target_page_identity,
                "last_source_identity": target.source_identity,
                "last_manifest_url": target.manifest_url,
                "last_capture_path": str(latest_json),
            }

            _atomic_write_text(latest_json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            _atomic_write_text(state_path, json.dumps(state_payload, ensure_ascii=False, indent=2) + "\n")
            _atomic_write_text(latest_txt, target.manifest_url + "\n")
            return payload

        remaining = deadline - monotonic()
        if remaining <= 0:
            suffix = f" Last probe error: {last_error}" if last_error else ""
            raise ResiWatchTimeout(f"No new Resi Manifest.mpd detected before timeout.{suffix}")
        sleeper(min(poll_seconds, remaining))


@contextmanager
def keep_system_awake() -> Iterator[None]:
    if os.name != "nt":
        yield
        return

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    set_execution_state = kernel32.SetThreadExecutionState
    set_execution_state.argtypes = [ctypes.c_uint32]
    set_execution_state.restype = ctypes.c_uint32

    es_continuous = 0x80000000
    es_system_required = 0x00000001
    if set_execution_state(es_continuous | es_system_required) == 0:
        raise OSError("SetThreadExecutionState failed")
    try:
        yield
    finally:
        set_execution_state(es_continuous)


def build_audio_probe_command(manifest_url: str) -> list[str]:
    ResiHandoffSpec(manifest_url)
    return [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "json",
        manifest_url,
    ]


def probe_audio_stream_count(manifest_url: str) -> int:
    command = build_audio_probe_command(manifest_url)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffprobe audio-stream preflight timed out after 90 seconds") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"ffprobe audio-stream preflight failed with exit code {completed.returncode}{suffix}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe audio-stream preflight returned invalid JSON") from exc
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise RuntimeError("ffprobe audio-stream preflight did not return a streams list")
    return len(streams)


def build_audio_sample_command(
    manifest_url: str,
    *,
    at: str,
    duration_seconds: int,
    output_path: Path,
) -> list[str]:
    ResiHandoffSpec(manifest_url)
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    start_seconds = parse_timestamp(at)
    normalized = format_timestamp(start_seconds)
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-y",
        "-ss",
        normalized,
        "-i",
        manifest_url,
        "-t",
        str(duration_seconds),
        "-map",
        "0:a:0",
        "-vn",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]


def create_audio_samples(
    manifest_url: str,
    *,
    points: list[str],
    duration_seconds: int,
    output_dir: Path,
) -> list[Path]:
    spec = ResiHandoffSpec(manifest_url)
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for resi sample")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required for resi sample")
    if not points:
        raise ValueError("at least one sample point is required")

    audio_stream_count = probe_audio_stream_count(manifest_url)
    if audio_stream_count != 1:
        raise RuntimeError(
            "Language preflight requires exactly one audio stream so the sampled speech is bound to the FULL "
            f"download's audio selection; found {audio_stream_count}. Stop and add explicit audio selection before FULL."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    index_samples: list[dict[str, Any]] = []
    for point in points:
        start_seconds = parse_timestamp(point)
        normalized = format_timestamp(start_seconds)
        safe_point = normalized.replace(":", "-").replace(".", "-")
        output_path = output_dir / f"{spec.safe_title} - sample {safe_point}.m4a"
        command = build_audio_sample_command(
            manifest_url,
            at=point,
            duration_seconds=duration_seconds,
            output_path=output_path,
        )
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg sample failed at {point} with exit code {completed.returncode}")
        if not output_path.is_file():
            raise RuntimeError(f"ffmpeg reported success but sample is missing: {output_path}")
        if output_path.stat().st_size < 4096:
            raise RuntimeError(
                f"ffmpeg sample is empty or too small at {point}; the requested position may not exist yet: {output_path}"
            )
        outputs.append(output_path)
        index_samples.append(
            {
                "requested_at": point,
                "normalized_at": normalized,
                "duration_seconds": duration_seconds,
                "path": str(output_path),
            }
        )

    index = {
        "schema_name": "video-manager.resi-language-samples",
        "schema_version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "manifest_url": manifest_url,
        "source_identity": canonical_source_identity(manifest_url),
        "source_fingerprint": spec.source_fingerprint,
        "audio_stream_count": audio_stream_count,
        "audio_selection_contract": "single_audio_stream_only",
        "language_claim": "unverified_operator_listen_required",
        "samples": index_samples,
    }
    _atomic_write_text(output_dir / "samples.json", json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return outputs


def default_sample_dir(repository_root: Path, manifest_url: str) -> Path:
    title = default_title_for_url(manifest_url)
    return repository_root / "operator-output" / "resi-language-samples" / title
