from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


_SECRET_NAME_PATTERNS = (
    re.compile(r"(^|/)(client_secret|oauth_client|access_token|refresh_token)(\.|/|$)", re.IGNORECASE),
    re.compile(r"(^|/)(token|tokens|secrets?)(\.json|\.txt|/)", re.IGNORECASE),
)
_SECRET_JSON_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "private_key",
}
_SHA_LINE_RE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64})[ *](?P<path>.+)$")


@dataclass
class VerificationResult:
    archive: str
    archive_sha256: str
    entry_count: int
    total_uncompressed_bytes: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_name": "video-manager.operational-bundle-verification",
            "schema_version": "1.0",
            "archive": self.archive,
            "archive_sha256": self.archive_sha256,
            "entry_count": self.entry_count,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_member_name(raw_name: str) -> str:
    if "\\" in raw_name:
        raise ValueError(f"archive member uses backslashes: {raw_name!r}")
    path = PurePosixPath(raw_name)
    if path.is_absolute():
        raise ValueError(f"archive member is absolute: {raw_name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"archive member has unsafe path segments: {raw_name!r}")
    return path.as_posix()


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _contains_secret_filename(name: str) -> bool:
    return any(pattern.search(name) for pattern in _SECRET_NAME_PATTERNS)


def _find_secret_json_values(value: Any, *, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}"
            if key_text.casefold() in _SECRET_JSON_KEYS and child not in (None, "", [], {}):
                findings.append(child_prefix)
            findings.extend(_find_secret_json_values(child, prefix=child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_secret_json_values(child, prefix=f"{prefix}[{index}]"))
    return findings


def _parse_sha256sums(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SHA_LINE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"SHA256SUMS.txt line {line_number} is invalid")
        member = match.group("path").strip()
        if member.startswith("*"):
            member = member[1:]
        rows.append((match.group("digest").lower(), _normalize_member_name(member)))
    return rows


def verify_bundle(
    archive_path: Path,
    *,
    entrypoint: str | None = None,
    required: list[str] | None = None,
    require_flat: bool = False,
    max_uncompressed_bytes: int = 20 * 1024 * 1024 * 1024,
) -> VerificationResult:
    required = list(required or [])
    archive_path = archive_path.resolve()
    result = VerificationResult(
        archive=str(archive_path),
        archive_sha256=_sha256_file(archive_path),
        entry_count=0,
        total_uncompressed_bytes=0,
    )

    if not zipfile.is_zipfile(archive_path):
        result.errors.append("file is not a valid ZIP archive")
        return result

    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        result.entry_count = len(infos)
        result.total_uncompressed_bytes = sum(info.file_size for info in infos)

        if not infos:
            result.errors.append("archive is empty")
            return result

        if result.total_uncompressed_bytes > max_uncompressed_bytes:
            result.errors.append(
                f"archive uncompressed size exceeds limit: {result.total_uncompressed_bytes} > {max_uncompressed_bytes}"
            )

        normalized_to_info: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            try:
                normalized = _normalize_member_name(info.filename.rstrip("/"))
            except ValueError as exc:
                result.errors.append(str(exc))
                continue

            if normalized in normalized_to_info:
                result.errors.append(f"duplicate normalized member: {normalized}")
                continue
            normalized_to_info[normalized] = info

            if info.flag_bits & 0x1:
                result.errors.append(f"encrypted archive member is not allowed: {normalized}")
            if _is_symlink(info):
                result.errors.append(f"symbolic link is not allowed: {normalized}")
            if not info.is_dir() and _contains_secret_filename(normalized):
                result.errors.append(f"possible secret file is not allowed: {normalized}")

        names = {name for name, info in normalized_to_info.items() if not info.is_dir()}

        expected = []
        if entrypoint is not None:
            expected.append(entrypoint)
        expected.extend(required)

        for raw_expected in expected:
            try:
                normalized_expected = _normalize_member_name(raw_expected)
            except ValueError as exc:
                result.errors.append(f"invalid expected path: {exc}")
                continue
            if normalized_expected not in names:
                result.errors.append(f"required archive member is missing: {normalized_expected}")
            if require_flat and len(PurePosixPath(normalized_expected).parts) != 1:
                result.errors.append(f"required flat member is not at archive root: {normalized_expected}")

        file_top_levels = {PurePosixPath(name).parts[0] for name in names}
        if require_flat and len(file_top_levels) == 1:
            only_top = next(iter(file_top_levels))
            if all(len(PurePosixPath(name).parts) > 1 for name in names):
                result.errors.append(f"archive has an extra nested root directory: {only_top}/")

        bad_crc = archive.testzip()
        if bad_crc is not None:
            result.errors.append(f"ZIP CRC verification failed for: {bad_crc}")

        if entrypoint is not None:
            normalized_entrypoint = PurePosixPath(entrypoint).as_posix()
            if normalized_entrypoint in names and normalized_entrypoint.casefold().endswith(".ps1"):
                try:
                    launcher_text = archive.read(normalized_entrypoint).decode("utf-8-sig")
                except UnicodeDecodeError:
                    result.errors.append(f"PowerShell entrypoint is not UTF-8 text: {normalized_entrypoint}")
                else:
                    if "$PSScriptRoot" not in launcher_text:
                        result.errors.append(
                            f"PowerShell entrypoint is not self-locating with $PSScriptRoot: {normalized_entrypoint}"
                        )
                    if "$ErrorActionPreference" not in launcher_text:
                        result.warnings.append(
                            f"PowerShell entrypoint does not set $ErrorActionPreference: {normalized_entrypoint}"
                        )

        manifest_names = sorted(name for name in names if PurePosixPath(name).name.casefold() == "manifest.json")
        for manifest_name in manifest_names:
            try:
                payload = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                result.errors.append(f"invalid manifest JSON {manifest_name}: {exc}")
                continue
            secret_paths = _find_secret_json_values(payload)
            for secret_path in secret_paths:
                result.errors.append(f"manifest contains a non-empty secret-like field: {manifest_name}:{secret_path}")

        checksum_names = sorted(name for name in names if PurePosixPath(name).name == "SHA256SUMS.txt")
        for checksum_name in checksum_names:
            try:
                checksum_rows = _parse_sha256sums(archive.read(checksum_name).decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError) as exc:
                result.errors.append(f"invalid checksum file {checksum_name}: {exc}")
                continue
            checksum_dir = PurePosixPath(checksum_name).parent
            for expected_digest, listed_path in checksum_rows:
                candidate = (
                    PurePosixPath(listed_path) if checksum_dir == PurePosixPath(".") else checksum_dir / listed_path
                ).as_posix()
                if candidate not in names:
                    result.errors.append(f"checksum references missing member: {checksum_name} -> {candidate}")
                    continue
                actual_digest = hashlib.sha256(archive.read(candidate)).hexdigest()
                if actual_digest != expected_digest:
                    result.errors.append(
                        f"checksum mismatch for {candidate}: expected {expected_digest}, actual {actual_digest}"
                    )

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a user-facing operational ZIP before handoff.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--entrypoint")
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--require-flat", action="store_true")
    parser.add_argument(
        "--max-uncompressed-bytes",
        type=int,
        default=20 * 1024 * 1024 * 1024,
    )
    parser.add_argument("--json-output", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        result = verify_bundle(
            args.archive,
            entrypoint=args.entrypoint,
            required=args.require,
            require_flat=args.require_flat,
            max_uncompressed_bytes=args.max_uncompressed_bytes,
        )
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = result.as_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
