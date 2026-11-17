"""Offline, provider-inert preflight for the selected Manrope 01 Russian Shorts style.

Checks saved ASS centisecond events, local raw Large-v3 ASR provenance and MP4
streams. Passing does NOT establish listening, theological accuracy or rights.
No network access, no mutation, and no font files in outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_ASS_STAMP = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)\.(\d{2})$")
_EXPECTED_ACTIVE_ASS = "&H007DE1FF&"  # #FFE17D in libass BGR notation
_EXPECTED_PAPER_ASS = "&H00F1FAFF&"   # #FFFAF1
_INTERNAL_ONLY = re.compile(r"(?i)\bвопрос\s*0?\d+\s*(?:из|/)\s*\d+\b")


def ass_centiseconds(value: str) -> int:
    match = _ASS_STAMP.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid ASS centisecond timestamp: {value!r}")
    h, m, s, cs = (int(v) for v in match.groups())
    return h * 360_000 + m * 6_000 + s * 100 + cs


def check_ass(ass_content: str) -> list[str]:
    """Check the SAVED ASS text, not unrounded float timestamps or generator state."""
    errors: list[str] = []
    styles: dict[str, str] = {}
    events: list[tuple[int, int, str, str]] = []
    for lineno, line in enumerate(ass_content.lstrip("\ufeff").splitlines(), 1):
        if line.startswith("Style: "):
            fields = line[7:].split(",")
            if len(fields) < 3:
                errors.append(f"Malformed ASS style at line {lineno}")
            else:
                styles[fields[0].strip()] = fields[1].strip()
        if not line.startswith("Dialogue: "):
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            errors.append(f"Malformed Dialogue at line {lineno}")
            continue
        try:
            start = ass_centiseconds(fields[1])
            end = ass_centiseconds(fields[2])
        except ValueError as exc:
            errors.append(f"Line {lineno}: {exc}")
            continue
        kind = fields[3].strip()
        if start >= end:
            errors.append(f"Non-positive subtitle interval at line {lineno}")
        events.append((start, end, kind, fields[-1]))
    if not any("Manrope" in font for font in styles.values()):
        errors.append("Manrope font style missing")
    if "Body" not in styles or "Manrope" not in styles["Body"]:
        errors.append("Body must use selected Manrope font")
    bodies = sorted((e for e in events if e[2] == "Body"), key=lambda x: (x[0], x[1]))
    if not bodies:
        errors.append("No Body subtitle events")
    for previous, following in zip(bodies, bodies[1:], strict=False):
        if previous[1] > following[0]:
            errors.append(
                f"Overlapping Body subtitles at {previous[0] / 100:.2f}s:"
                f" previous ends {previous[1] / 100:.2f}s,"
                f" next begins {following[0] / 100:.2f}s"
            )
    if not any(e[2] == "Kicker" for e in events):
        errors.append("Missing source attribution Kicker")
    if not any(e[2] == "Title" for e in events):
        errors.append("Missing understandable topic Title")
    if _INTERNAL_ONLY.search(ass_content):
        errors.append("An internal question index must not replace source identification")
    body_payload = "\n".join(e[3] for e in bodies)
    if _EXPECTED_ACTIVE_ASS.lower() not in body_payload.lower():
        errors.append("Selected amber active-word highlighting missing")
    if _EXPECTED_PAPER_ASS.lower() not in body_payload.lower():
        errors.append("Selected pale inactive-word highlighting missing")
    for start, end, _, payload in bodies:
        if payload.count(r"\N") > 1:
            errors.append(f"More than two lines at {start / 100:.2f}s")
        if r"\pos(540,1426)" not in payload:
            errors.append(f"Manrope 01 Body anchor missing at {start / 100:.2f}s")
        if end - start > 300:  # a hold longer than 3 seconds is stale karaoke
            errors.append(f"Suspiciously long active-word event at {start / 100:.2f}s")
    return errors


def check_asr_provenance(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    model = str(record.get("model", "")).strip().lower()
    if model not in ("faster-whisper-large-v3", "large-v3"):
        errors.append(f"Selected large-v3 required; got {model!r}")
    if str(record.get("device", "")).lower() != "cpu":
        errors.append("CPU explicitly required on the affected workstation; CUDA forbidden")
    if str(record.get("compute_type", "")).lower() != "int8":
        errors.append("CPU INT8 required; float16/CUDA forbidden")
    if record.get("segments") is None:
        errors.append("Raw timestamped ASR segments missing")
    if not record.get("source_id") and not record.get("source"):
        errors.append("Raw ASR source identity missing")
    return errors


def check_mp4_streams(payload: dict[str, Any]) -> list[str]:
    streams = payload.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    errors: list[str] = []
    if len(videos) != 1 or (videos and (videos[0].get("codec_name"), videos[0].get("width"), videos[0].get("height")) != ("h264", 1080, 1920)):
        errors.append("One H.264 1080x1920 video stream required")
    if not audios or audios[0].get("codec_name") != "aac":
        errors.append("AAC audio stream required")
    try:
        duration = float(payload.get("format", {}).get("duration", 0))
        if not (0 < duration <= 180.0):
            errors.append(f"Short duration must be (0, 180.0] seconds; got {duration}")
    except (TypeError, ValueError):
        errors.append("Media duration is missing or invalid")
    return errors


def verify(
    ass: Path,
    asr: Path,
    mp4: Path,
    *,
    ffprobe: str = "ffprobe",
    receipt: Path | None = None,
) -> list[str]:
    issues: list[str] = []
    for path in (ass, asr, mp4, *([receipt] if receipt is not None else [])):
        if not path.is_file():
            issues.append(f"Required file missing: {path}")
    if issues:
        return issues
    try:
        issues.extend(check_ass(ass.read_text(encoding="utf-8-sig")))
        raw = json.loads(asr.read_text(encoding="utf-8"))
        issues.extend(check_asr_provenance(raw))
    except (ValueError, UnicodeError, OSError) as exc:
        issues.append(f"Text/ASR load failed: {exc}")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height:format=duration",
             "-of", "json", str(mp4)],
            check=True, capture_output=True, text=True, timeout=30
        )
        issues.extend(check_mp4_streams(json.loads(result.stdout)))
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
        issues.append(f"Unusable MP4 (possible missing moov): {exc}")
    if receipt is not None:
        try:
            record = json.loads(receipt.read_text(encoding="utf-8"))
            expected = str(record.get("sha256") or "")
            digest = hashlib.sha256()
            with mp4.open("rb") as source:
                for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                    digest.update(block)
            if expected != digest.hexdigest():
                issues.append("Exact MP4 SHA-256 differs from review receipt")
            for key in ("subtitle_overlap_count", "overlapping_body_states"):
                if key in record and record[key] != 0:
                    issues.append(f"Receipt reports {key}={record[key]!r}; expected zero")
        except (ValueError, UnicodeError, OSError, AttributeError) as exc:
            issues.append(f"Invalid or corrupted review receipt: {exc}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ass", type=Path, required=True, help="Saved, burned-in ASS file")
    parser.add_argument("--asr-json", type=Path, required=True, help="Raw Large-v3 JSON with device/provenance")
    parser.add_argument("--mp4", type=Path, required=True, help="Exact rendered review MP4")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--receipt-json", type=Path, help="Exact SHA-256 review receipt, recommended")
    args = parser.parse_args()
    problems = verify(args.ass, args.asr_json, args.mp4, ffprobe=args.ffprobe, receipt=args.receipt_json)
    if problems:
        for problem in problems:
            print(f"REJECT: {problem}")
        return 1
    print("MANROPE01_TECH_PREFLIGHT_PASS (not listening, theology, rights or publication)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
