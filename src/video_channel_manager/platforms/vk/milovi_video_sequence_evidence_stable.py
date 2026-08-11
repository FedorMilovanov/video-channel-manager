from __future__ import annotations

import argparse
import html
import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as base

_ORIGINAL_CAPTURE = base._capture_page_sequence
_ORIGINAL_IDENTITY = base._identity_url_matches
_LOCAL_YOUTUBE_ORIGIN = "http://127.0.0.1:8765"


def _youtube_capture_url(video_id: str) -> str:
    return f"{_LOCAL_YOUTUBE_ORIGIN}/youtube/{video_id}"


def _youtube_embed_url(video_id: str) -> str:
    origin = quote(_LOCAL_YOUTUBE_ORIGIN, safe="")
    return (
        f"https://www.youtube-nocookie.com/embed/{video_id}"
        f"?autoplay=1&mute=1&playsinline=1&rel=0&enablejsapi=1&origin={origin}"
    )


def _youtube_embed_document(video_id: str) -> str:
    embed_url = html.escape(_youtube_embed_url(video_id), quote=True)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>Milovi read-only YouTube evidence</title>
<style>
html,body{{margin:0;width:100%;height:100%;background:#111;overflow:hidden}}
iframe{{border:0;width:100vw;height:100vh;display:block}}
</style>
</head>
<body>
<iframe
  id="milovi-youtube-player"
  src="{embed_url}"
  allow="autoplay; encrypted-media; picture-in-picture"
  referrerpolicy="strict-origin-when-cross-origin"
  allowfullscreen
></iframe>
</body>
</html>"""


def _split_vk_remote_id(remote_id: str) -> tuple[str, str]:
    owner_id, video_id = remote_id.rsplit("_", 1)
    if not owner_id.startswith("-") or not owner_id[1:].isdigit() or not video_id.isdigit():
        raise ValueError(f"invalid VK Clip remote id: {remote_id}")
    return owner_id, video_id


def _vk_capture_url(remote_id: str) -> str:
    owner_id, video_id = _split_vk_remote_id(remote_id)
    return f"https://vk.com/clip_ext.php?oid={owner_id}&id={video_id}&autoplay=1"


def _stable_identity_url_matches(*, platform: str, expected_id: str, raw_url: str) -> bool:
    parsed = urlsplit(raw_url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if platform == "youtube":
        local_origin = urlsplit(_LOCAL_YOUTUBE_ORIGIN)
        if (
            host == (local_origin.hostname or "").lower()
            and parsed.port == local_origin.port
            and path == f"/youtube/{expected_id}"
        ):
            return True
        allowed_embed_host = (
            host == "youtube-nocookie.com"
            or host.endswith(".youtube-nocookie.com")
            or host == "youtube.com"
            or host.endswith(".youtube.com")
        )
        if allowed_embed_host and path.endswith(f"/embed/{expected_id}"):
            return True
    if platform == "vk":
        allowed_vk_host = host in {"vk.com", "vk.ru"} or host.endswith(".vk.com") or host.endswith(".vk.ru")
        if allowed_vk_host and path.endswith("/clip_ext.php"):
            owner_id, video_id = _split_vk_remote_id(expected_id)
            query = parse_qs(parsed.query)
            return (query.get("oid") or [""])[0] == owner_id and (query.get("id") or [""])[0] == video_id
    return _ORIGINAL_IDENTITY(platform=platform, expected_id=expected_id, raw_url=raw_url)


def _capture_error(*, canonical_url: str, page: Any, exc: Exception) -> base.CaptureResult:
    try:
        final_url = base._safe_url(str(page.url))
    except Exception:
        final_url = ""
    return base.CaptureResult(
        status="capture_error",
        canonical_url=canonical_url,
        final_url=final_url,
        duration_s=None,
        video_width=None,
        video_height=None,
        frames=(),
        page_title="",
        block_hints=(),
        error=f"{type(exc).__name__}: {exc}"[:1000],
    )


def _temporal_diversity_gate(result: base.CaptureResult) -> base.CaptureResult:
    if result.status != "captured" or len(result.frames) < 6:
        return result
    unique_sha_count = len({str(frame.get("sha256") or "") for frame in result.frames})
    minimum_unique = max(4, len(result.frames) // 3)
    if unique_sha_count >= minimum_unique:
        return result
    return replace(
        result,
        status="temporal_capture_unreliable",
        frames=(),
        error=(
            f"timeline capture collapsed to {unique_sha_count} unique rendered frames "
            f"across {len(result.frames)} samples; sequence evidence suppressed"
        ),
    )


def _install_youtube_referrer_page(page: Any, *, video_id: str, capture_url: str) -> None:
    document = _youtube_embed_document(video_id)

    def fulfill(route: Any) -> None:
        route.fulfill(
            status=200,
            body=document,
            content_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )

    page.route(capture_url, fulfill)


def _isolated_capture_page_sequence(
    *,
    page: Any,
    platform: str,
    expected_id: str,
    url: str,
    output_dir: Path,
    wait_ms: int,
) -> base.CaptureResult:
    capture_url = (
        _youtube_capture_url(expected_id)
        if platform == "youtube"
        else _vk_capture_url(expected_id)
        if platform == "vk"
        else url
    )

    # A fresh page per media identity prevents delayed navigation from one item interrupting
    # the next. YouTube is embedded under a local HTTP parent to supply a valid referrer.
    # VK uses its exact clip_ext player instead of the recommendation/feed Clip surface, so
    # the sampled <video> is bound to owner_id + video_id rather than whichever feed item is visible.
    # All transports are read-only; no clicks, forms, uploads, deletes, or wall actions occur.
    last_result: base.CaptureResult | None = None
    last_error: Exception | None = None
    for _attempt in range(2):
        isolated_page = page.context.new_page()
        try:
            if platform == "youtube":
                _install_youtube_referrer_page(
                    isolated_page,
                    video_id=expected_id,
                    capture_url=capture_url,
                )
            try:
                result = _ORIGINAL_CAPTURE(
                    page=isolated_page,
                    platform=platform,
                    expected_id=expected_id,
                    url=capture_url,
                    output_dir=output_dir,
                    wait_ms=wait_ms,
                )
            except Exception as exc:
                last_error = exc
                result = _capture_error(canonical_url=url, page=isolated_page, exc=exc)
            result = _temporal_diversity_gate(replace(result, canonical_url=url))
            last_result = result
            if result.status == "captured":
                return result
        finally:
            try:
                isolated_page.close()
            except Exception:
                pass

    if last_result is not None:
        return last_result
    if last_error is not None:
        raise last_error
    raise RuntimeError("isolated media capture produced no result")


def build_video_sequence_evidence(
    *,
    input_zip: Path,
    output_dir: Path,
    zip_output: Path,
    browser_executable: Path | None = None,
    headless: bool = False,
    wait_ms: int = 500,
) -> dict[str, Any]:
    previous_capture = base._capture_page_sequence
    previous_identity = base._identity_url_matches
    base._capture_page_sequence = _isolated_capture_page_sequence
    base._identity_url_matches = _stable_identity_url_matches
    try:
        result = base.build_video_sequence_evidence(
            input_zip=input_zip,
            output_dir=output_dir,
            zip_output=zip_output,
            browser_executable=browser_executable,
            headless=headless,
            wait_ms=wait_ms,
        )
    finally:
        base._capture_page_sequence = previous_capture
        base._identity_url_matches = previous_identity
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=("Build stable read-only browser video-sequence evidence for reviewed Milovi confectionery pairs.")
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
