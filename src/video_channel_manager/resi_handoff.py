from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

_TIMESTAMP_RE = re.compile(r"^(?P<hours>\d{1,3}):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)(?:\.(?P<millis>\d{1,3}))?$")
_WINDOWS_INVALID_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_ENCODERS = {"auto", "nvenc", "cpu"}


@dataclass(frozen=True)
class ResiHandoffSpec:
    source_url: str
    title: str
    start: str | None = None
    end: str | None = None
    encoder: str = "auto"

    def __post_init__(self) -> None:
        validate_source_url(self.source_url)
        if self.encoder not in _ENCODERS:
            raise ValueError(f"encoder must be one of: {', '.join(sorted(_ENCODERS))}")
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be supplied together")
        if self.start is not None and self.end is not None:
            start_seconds = parse_timestamp(self.start)
            end_seconds = parse_timestamp(self.end)
            if end_seconds <= start_seconds:
                raise ValueError("end must be later than start")

    @property
    def safe_title(self) -> str:
        return windows_safe_name(self.title)

    @property
    def trim_duration_seconds(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return parse_timestamp(self.end) - parse_timestamp(self.start)

    @property
    def trim_duration_ffmpeg(self) -> str | None:
        duration = self.trim_duration_seconds
        return None if duration is None else format_timestamp(duration)


def validate_source_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source URL must be an absolute http(s) URL")
    if not parsed.path.lower().endswith(".mpd"):
        raise ValueError("source URL must point to a DASH .mpd manifest")


def parse_timestamp(value: str) -> float:
    match = _TIMESTAMP_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid timestamp {value!r}; expected HH:MM:SS[.mmm]")
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis_text = match.group("millis") or ""
    millis = int(millis_text.ljust(3, "0")) if millis_text else 0
    return float(hours * 3600 + minutes * 60 + seconds) + millis / 1000.0


def format_timestamp(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("timestamp cannot be negative")
    total_millis = int(round(seconds * 1000))
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    if millis:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"


def windows_safe_name(value: str) -> str:
    cleaned = _WINDOWS_INVALID_RE.sub("-", value).strip().rstrip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = "Resi Download"
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:180].rstrip(". ") or "Resi Download"


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_powershell_handoff(spec: ResiHandoffSpec) -> str:
    source_url = _ps_single_quote(spec.source_url)
    safe_title = _ps_single_quote(spec.safe_title)
    encoder = _ps_single_quote(spec.encoder)
    lines = [
        '$ErrorActionPreference = "Stop"',
        "",
        f"$SourceUrl = {source_url}",
        f"$Title = {safe_title}",
        f"$EncoderPreference = {encoder}",
        '$Repo = "C:\\Users\\Fedor\\Projects\\video-channel-manager"',
        '$OperatorOutput = Join-Path $Repo "operator-output"',
        '$Master = Join-Path $OperatorOutput ($Title + " - FULL.mp4")',
    ]
    if spec.start is not None and spec.end is not None:
        lines.append('$Clip = Join-Path $OperatorOutput ($Title + ".mp4")')
    lines.extend(
        [
            "",
            "New-Item -ItemType Directory -Force -Path $OperatorOutput | Out-Null",
            'foreach ($Tool in @("yt-dlp", "ffmpeg", "ffprobe")) {',
            "    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {",
            '        throw "Required tool not found in PATH: $Tool"',
            "    }",
            "}",
            "",
            'Write-Host "Available DASH formats:"',
            "& yt-dlp -F --no-warnings -- $SourceUrl",
            'if ($LASTEXITCODE -ne 0) { throw "yt-dlp format inspection failed" }',
            "",
            'Write-Host "Downloading best video + best audio..."',
            '& yt-dlp -f "bestvideo+bestaudio/best" --concurrent-fragments 8 --retries infinite --fragment-retries infinite --merge-output-format mp4 --newline -o $Master -- $SourceUrl',
            'if ($LASTEXITCODE -ne 0) { throw "yt-dlp download failed" }',
            'if (-not (Test-Path -LiteralPath $Master -PathType Leaf)) { throw "Expected master was not created: $Master" }',
            "",
            'Write-Host "Master QC:"',
            "& ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels -of default=noprint_wrappers=1 $Master",
            'if ($LASTEXITCODE -ne 0) { throw "ffprobe failed for master" }',
        ]
    )
    if spec.start is None or spec.end is None:
        lines.extend(
            [
                "",
                "$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Master",
                'Write-Host "MASTER READY: $Master"',
                'Write-Host "SHA256: $($Hash.Hash)"',
            ]
        )
        return "\n".join(lines) + "\n"

    expected = spec.trim_duration_seconds
    assert expected is not None
    duration = spec.trim_duration_ffmpeg
    assert duration is not None
    lines.extend(
        [
            "",
            f"$TrimStart = {_ps_single_quote(spec.start)}",
            f"$TrimDuration = {_ps_single_quote(duration)}",
            f"$ExpectedDurationSeconds = {expected:.3f}",
            '$EncoderList = (& ffmpeg -hide_banner -encoders 2>&1 | Out-String)',
            '$HasNvenc = $EncoderList.Contains("h264_nvenc")',
            'if ($EncoderPreference -eq "nvenc" -and -not $HasNvenc) { throw "h264_nvenc was requested but is unavailable" }',
            '$UseNvenc = ($EncoderPreference -eq "nvenc") -or ($EncoderPreference -eq "auto" -and $HasNvenc)',
            "",
            '$CommonArgs = @("-y", "-ss", $TrimStart, "-i", $Master, "-t", $TrimDuration, "-map", "0:v:0", "-map", "0:a:0", "-c:a", "copy", "-movflags", "+faststart")',
            "if ($UseNvenc) {",
            '    $VideoArgs = @("-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-profile:v", "high")',
            '    $SourceVideoBitrateText = (& ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 $Master | Select-Object -First 1)',
            "    $SourceVideoBitrate = [long]0",
            '    if ([long]::TryParse(($SourceVideoBitrateText | Out-String).Trim(), [ref]$SourceVideoBitrate) -and $SourceVideoBitrate -gt 0) {',
            "        $MaxRate = [long][math]::Ceiling($SourceVideoBitrate * 1.5)",
            "        $BufferSize = [long]($MaxRate * 2)",
            '        $VideoArgs += @("-maxrate", [string]$MaxRate, "-bufsize", [string]$BufferSize)',
            "    }",
            '    Write-Host "Exact trim encoder: NVENC P6 HQ, CQ21 with source-aware rate ceiling when available"',
            "} else {",
            '    $VideoArgs = @("-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high")',
            '    Write-Host "Exact trim encoder: libx264 slow CRF18"',
            "}",
            "",
            "$FfmpegArgs = $CommonArgs + $VideoArgs + @($Clip)",
            "& ffmpeg @FfmpegArgs",
            'if ($LASTEXITCODE -ne 0) { throw "ffmpeg trim failed" }',
            'if (-not (Test-Path -LiteralPath $Clip -PathType Leaf)) { throw "Expected clip was not created: $Clip" }',
            "",
            '$ProbeJson = (& ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels -of json $Clip | Out-String)',
            'if ($LASTEXITCODE -ne 0) { throw "ffprobe failed for clip" }',
            "$Probe = $ProbeJson | ConvertFrom-Json",
            '$VideoStreams = @($Probe.streams | Where-Object { $_.codec_type -eq "video" })',
            '$AudioStreams = @($Probe.streams | Where-Object { $_.codec_type -eq "audio" })',
            'if ($VideoStreams.Count -lt 1) { throw "QC failed: no video stream" }',
            'if ($AudioStreams.Count -lt 1) { throw "QC failed: no audio stream" }',
            "$ActualDurationSeconds = [double]$Probe.format.duration",
            'if ([math]::Abs($ActualDurationSeconds - $ExpectedDurationSeconds) -gt 0.25) {',
            '    throw "QC failed: duration $ActualDurationSeconds differs from expected $ExpectedDurationSeconds by more than 0.25 s"',
            "}",
            "$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Clip",
            'Write-Host "CLIP READY: $Clip"',
            'Write-Host ("DURATION: {0:N3} s" -f $ActualDurationSeconds)',
            'Write-Host "SHA256: $($Hash.Hash)"',
            'Write-Host "MASTER KEPT: $Master"',
        ]
    )
    return "\n".join(lines) + "\n"


def default_handoff_path(title: str) -> Path:
    return Path("operator-output") / f"{windows_safe_name(title)} - resi-handoff.ps1"
