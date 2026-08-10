from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

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
_MAX_SAFE_TITLE_LENGTH = 140


@dataclass(frozen=True)
class ResiHandoffSpec:
    source_url: str
    title: str | None = None
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
        source_title = self.title.strip() if self.title and self.title.strip() else default_title_for_url(self.source_url)
        return windows_safe_name(source_title)

    @property
    def source_identity(self) -> str:
        return canonical_source_identity(self.source_url)

    @property
    def source_fingerprint(self) -> str:
        digest = hashlib.sha256(self.source_identity.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @property
    def normalized_start(self) -> str | None:
        return None if self.start is None else format_timestamp(parse_timestamp(self.start))

    @property
    def normalized_end(self) -> str | None:
        return None if self.end is None else format_timestamp(parse_timestamp(self.end))

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


def canonical_source_identity(value: str) -> str:
    validate_source_url(value)
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    query = "" if host == "resi.media" or host.endswith(".resi.media") else parsed.query
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", query, ""))


def default_title_for_url(value: str) -> str:
    validate_source_url(value)
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2:
        source_component = parts[-2]
    else:
        source_component = hashlib.sha256(canonical_source_identity(value).encode("utf-8")).hexdigest()[:16]
    return f"Resi {source_component}"


def parse_timestamp(value: str) -> float:
    text = value.strip()
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"invalid timestamp {value!r}; expected MM:SS[.mmm] or HH:MM:SS[.mmm]")

    seconds_text = parts[-1]
    if "." in seconds_text:
        whole_seconds_text, millis_text = seconds_text.split(".", 1)
        if not millis_text.isdigit() or not 1 <= len(millis_text) <= 3:
            raise ValueError(f"invalid timestamp {value!r}; milliseconds must contain 1-3 digits")
    else:
        whole_seconds_text = seconds_text
        millis_text = ""

    if not whole_seconds_text.isdigit():
        raise ValueError(f"invalid timestamp {value!r}; seconds must be numeric")
    seconds = int(whole_seconds_text)
    if not 0 <= seconds <= 59:
        raise ValueError(f"invalid timestamp {value!r}; seconds must be between 00 and 59")

    leading = parts[:-1]
    if not all(part.isdigit() for part in leading):
        raise ValueError(f"invalid timestamp {value!r}; hours/minutes must be numeric")

    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
    else:
        hours = int(parts[0])
        minutes = int(parts[1])
        if not 0 <= minutes <= 59:
            raise ValueError(f"invalid timestamp {value!r}; minutes must be between 00 and 59")

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
    reserved_stem = cleaned.split(".", 1)[0].upper()
    if reserved_stem in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:_MAX_SAFE_TITLE_LENGTH].rstrip(". ") or "Resi Download"


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_powershell_handoff(spec: ResiHandoffSpec) -> str:
    source_url = _ps_single_quote(spec.source_url)
    source_fingerprint = _ps_single_quote(spec.source_fingerprint)
    safe_title = _ps_single_quote(spec.safe_title)
    encoder = _ps_single_quote(spec.encoder)
    lines = [
        "param(",
        '    [string]$RepositoryRoot = "C:\\Users\\Fedor\\Projects\\video-channel-manager"',
        ")",
        "",
        '$ErrorActionPreference = "Stop"',
        "",
        f"$SourceUrl = {source_url}",
        f"$SourceFingerprint = {source_fingerprint}",
        f"$Title = {safe_title}",
        f"$EncoderPreference = {encoder}",
        "$Repo = $RepositoryRoot",
        '$OperatorOutput = Join-Path $Repo "operator-output"',
        '$Master = Join-Path $OperatorOutput ($Title + " - FULL.mp4")',
        '$SourceReceipt = Join-Path $OperatorOutput ($Title + " - FULL.source.json")',
        '$Result = Join-Path $OperatorOutput ($Title + " - result.json")',
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
            "$ReuseMaster = $false",
            "if (Test-Path -LiteralPath $Master -PathType Leaf) {",
            "    if (-not (Test-Path -LiteralPath $SourceReceipt -PathType Leaf)) {",
            '        throw "Existing master has no source receipt; refusing unsafe filename-only reuse: $Master"',
            "    }",
            "$ExistingReceipt = Get-Content -Raw -LiteralPath $SourceReceipt | ConvertFrom-Json",
            '    if ($ExistingReceipt.source_fingerprint -ne $SourceFingerprint) {',
            '        throw "Existing master belongs to a different source fingerprint: $Master"',
            "    }",
            "$ExistingMasterHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Master).Hash.ToLowerInvariant()",
            '    if ($ExistingReceipt.master_sha256 -ne ("sha256:" + $ExistingMasterHash)) {',
            '        throw "Existing master hash no longer matches its source receipt: $Master"',
            "    }",
            "$ReuseMaster = $true",
            'Write-Host "Reusing source-bound master: $Master"',
            "}",
            "",
            "if ($ReuseMaster) {",
            '    Write-Host "Verified master is reusable; skipping remote format inspection and download."',
            "} else {",
            '    Write-Host "Available DASH formats:"',
            "    & yt-dlp -F --no-warnings -- $SourceUrl",
            '    if ($LASTEXITCODE -ne 0) { throw "yt-dlp format inspection failed" }',
            '    Write-Host "Downloading best video + best audio..."',
            '    & yt-dlp -f "bestvideo+bestaudio/best" --concurrent-fragments 8 --retries 10 --fragment-retries 10 --merge-output-format mp4 --newline -o $Master -- $SourceUrl',
            '    if ($LASTEXITCODE -ne 0) { throw "yt-dlp download failed after bounded retries" }',
            "}",
            'if (-not (Test-Path -LiteralPath $Master -PathType Leaf)) { throw "Expected master was not created: $Master" }',
            "",
            "$MasterProbeJson = (& ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels,bit_rate -of json $Master | Out-String)",
            'if ($LASTEXITCODE -ne 0) { throw "ffprobe failed for master" }',
            "$MasterProbe = $MasterProbeJson | ConvertFrom-Json",
            '$MasterVideoStreams = @($MasterProbe.streams | Where-Object { $_.codec_type -eq "video" })',
            '$MasterAudioStreams = @($MasterProbe.streams | Where-Object { $_.codec_type -eq "audio" })',
            'if ($MasterVideoStreams.Count -lt 1) { throw "Master QC failed: no video stream" }',
            'if ($MasterAudioStreams.Count -lt 1) { throw "Master QC failed: no audio stream" }',
            "$MasterDurationSeconds = [double]$MasterProbe.format.duration",
            'if ($MasterDurationSeconds -le 0) { throw "Master QC failed: non-positive duration" }',
            "$MasterHashHex = (Get-FileHash -Algorithm SHA256 -LiteralPath $Master).Hash.ToLowerInvariant()",
            '$MasterSha256 = "sha256:" + $MasterHashHex',
            "",
            "$SourceReceiptPayload = [ordered]@{",
            '    schema_name = "video-manager.resi-source-receipt"',
            "    schema_version = 1",
            "    source_fingerprint = $SourceFingerprint",
            "    master_path = $Master",
            "    master_sha256 = $MasterSha256",
            "    duration_seconds = $MasterDurationSeconds",
            "    video_stream_count = $MasterVideoStreams.Count",
            "    audio_stream_count = $MasterAudioStreams.Count",
            "}",
            "$SourceReceiptPayload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SourceReceipt -Encoding UTF8",
            'if (-not (Test-Path -LiteralPath $SourceReceipt -PathType Leaf)) { throw "Source receipt was not created: $SourceReceipt" }',
        ]
    )
    if spec.start is None or spec.end is None:
        lines.extend(
            [
                "",
                "$ResultPayload = [ordered]@{",
                '    schema_name = "video-manager.resi-result"',
                "    schema_version = 1",
                '    mode = "download_only"',
                "    source_fingerprint = $SourceFingerprint",
                "    master_path = $Master",
                "    master_sha256 = $MasterSha256",
                "    master_duration_seconds = $MasterDurationSeconds",
                "    source_receipt_path = $SourceReceipt",
                "}",
                "$ResultPayload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Result -Encoding UTF8",
                'if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) { throw "Result was not created: $Result" }',
                'Write-Host "MASTER READY: $Master"',
                'Write-Host "MASTER SHA256: $MasterSha256"',
                'Write-Host "RESULT READY: $Result"',
            ]
        )
        return "\n".join(lines) + "\n"

    expected = spec.trim_duration_seconds
    assert expected is not None
    duration = spec.trim_duration_ffmpeg
    assert duration is not None
    normalized_start = spec.normalized_start
    normalized_end = spec.normalized_end
    assert normalized_start is not None
    assert normalized_end is not None
    lines.extend(
        [
            "",
            f"$TrimStart = {_ps_single_quote(normalized_start)}",
            f"$TrimEnd = {_ps_single_quote(normalized_end)}",
            f"$TrimDuration = {_ps_single_quote(duration)}",
            f"$ExpectedDurationSeconds = {expected:.3f}",
            "$EncoderList = (& ffmpeg -hide_banner -encoders 2>&1 | Out-String)",
            '$HasNvenc = $EncoderList.Contains("h264_nvenc")',
            "if ($HasNvenc) {",
            '    & ffmpeg -hide_banner -loglevel error -f lavfi -i "color=size=16x16:rate=1" -frames:v 1 -c:v h264_nvenc -f null - *> $null',
            "    $HasNvenc = ($LASTEXITCODE -eq 0)",
            "}",
            'if ($EncoderPreference -eq "nvenc" -and -not $HasNvenc) { throw "h264_nvenc was requested but is unavailable at runtime" }',
            '$UseNvenc = ($EncoderPreference -eq "nvenc") -or ($EncoderPreference -eq "auto" -and $HasNvenc)',
            "",
            '$CommonArgs = @("-y", "-ss", $TrimStart, "-i", $Master, "-t", $TrimDuration, "-map", "0:v:0", "-map", "0:a:0", "-c:a", "copy", "-movflags", "+faststart")',
            "if ($UseNvenc) {",
            '    $SelectedEncoder = "nvenc"',
            '    $VideoArgs = @("-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-profile:v", "high")',
            "    $SourceVideoBitrateText = ($MasterVideoStreams | Select-Object -First 1).bit_rate",
            "    $SourceVideoBitrate = [long]0",
            '    if (-not [long]::TryParse(($SourceVideoBitrateText | Out-String).Trim(), [ref]$SourceVideoBitrate) -or $SourceVideoBitrate -le 0) {',
            "        $SourceFormatBitrateText = $MasterProbe.format.bit_rate",
            "        $SourceVideoBitrate = [long]0",
            "        [void][long]::TryParse(($SourceFormatBitrateText | Out-String).Trim(), [ref]$SourceVideoBitrate)",
            "    }",
            "    if ($SourceVideoBitrate -gt 0) {",
            "        $MaxRate = [long][math]::Ceiling($SourceVideoBitrate * 1.5)",
            "        $BufferSize = [long]($MaxRate * 2)",
            '        $VideoArgs += @("-maxrate", [string]$MaxRate, "-bufsize", [string]$BufferSize)',
            "    }",
            '    Write-Host "Exact trim encoder: NVENC P6 HQ, CQ21 with source-aware rate ceiling when available"',
            "} else {",
            '    $SelectedEncoder = "cpu"',
            '    $VideoArgs = @("-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high")',
            '    Write-Host "Exact trim encoder: libx264 slow CRF18"',
            "}",
            "",
            "$FfmpegArgs = $CommonArgs + $VideoArgs + @($Clip)",
            "& ffmpeg @FfmpegArgs",
            'if ($LASTEXITCODE -ne 0) { throw "ffmpeg trim failed" }',
            'if (-not (Test-Path -LiteralPath $Clip -PathType Leaf)) { throw "Expected clip was not created: $Clip" }',
            "",
            "$ProbeJson = (& ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels -of json $Clip | Out-String)",
            'if ($LASTEXITCODE -ne 0) { throw "ffprobe failed for clip" }',
            "$Probe = $ProbeJson | ConvertFrom-Json",
            '$VideoStreams = @($Probe.streams | Where-Object { $_.codec_type -eq "video" })',
            '$AudioStreams = @($Probe.streams | Where-Object { $_.codec_type -eq "audio" })',
            'if ($VideoStreams.Count -lt 1) { throw "Clip QC failed: no video stream" }',
            'if ($AudioStreams.Count -lt 1) { throw "Clip QC failed: no audio stream" }',
            "$ActualDurationSeconds = [double]$Probe.format.duration",
            "if ([math]::Abs($ActualDurationSeconds - $ExpectedDurationSeconds) -gt 0.25) {",
            '    throw "Clip QC failed: duration $ActualDurationSeconds differs from expected $ExpectedDurationSeconds by more than 0.25 s"',
            "}",
            "$ClipHashHex = (Get-FileHash -Algorithm SHA256 -LiteralPath $Clip).Hash.ToLowerInvariant()",
            '$ClipSha256 = "sha256:" + $ClipHashHex',
            "",
            "$ResultPayload = [ordered]@{",
            '    schema_name = "video-manager.resi-result"',
            "    schema_version = 1",
            '    mode = "exact_trim"',
            "    source_fingerprint = $SourceFingerprint",
            "    master_path = $Master",
            "    master_sha256 = $MasterSha256",
            "    master_duration_seconds = $MasterDurationSeconds",
            "    source_receipt_path = $SourceReceipt",
            "    clip_path = $Clip",
            "    clip_sha256 = $ClipSha256",
            "    trim_start = $TrimStart",
            "    trim_end = $TrimEnd",
            "    expected_duration_seconds = $ExpectedDurationSeconds",
            "    actual_duration_seconds = $ActualDurationSeconds",
            "    encoder = $SelectedEncoder",
            "}",
            "$ResultPayload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Result -Encoding UTF8",
            'if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) { throw "Result was not created: $Result" }',
            'Write-Host "CLIP READY: $Clip"',
            'Write-Host ("DURATION: {0:N3} s" -f $ActualDurationSeconds)',
            'Write-Host "CLIP SHA256: $ClipSha256"',
            'Write-Host "MASTER SHA256: $MasterSha256"',
            'Write-Host "MASTER KEPT: $Master"',
            'Write-Host "RESULT READY: $Result"',
        ]
    )
    return "\n".join(lines) + "\n"


def default_handoff_path(title: str) -> Path:
    return Path("operator-output") / f"{windows_safe_name(title)} - resi-handoff.ps1"
