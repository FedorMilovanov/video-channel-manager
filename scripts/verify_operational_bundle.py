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
from typing import Any, Literal

from video_channel_manager.wave_engine.models import PROJECT_IDENTITIES


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

_ACCEPTANCE_SCHEMA = "video-manager.operational-package-acceptance"
_ACCEPTANCE_VERSION = "1.0"
_EVIDENCE_LEVELS = (
    "editorial_prepared",
    "preview_validated",
    "self_tested",
    "canary_verified",
    "batch_verified",
)
_PACKAGE_KINDS = {
    "editorial_bundle",
    "read_only_evidence_bundle",
    "provider_write_bundle",
}
_WRITE_READY_LEVELS = {"self_tested", "canary_verified", "batch_verified"}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_RETIREMENT_REGISTRY = _REPOSITORY_ROOT / "docs" / "operations" / "retirement-registry-v1.json"


@dataclass
class VerificationResult:
    archive: str
    archive_sha256: str
    entry_count: int
    total_uncompressed_bytes: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    acceptance_checked: bool = False
    package_kind: str | None = None
    evidence_level: str | None = None
    provider_writes_authorized: Literal[False] = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_name": "video-manager.operational-bundle-verification",
            "schema_version": "1.1",
            "archive": self.archive,
            "archive_sha256": self.archive_sha256,
            "entry_count": self.entry_count,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "acceptance_checked": self.acceptance_checked,
            "package_kind": self.package_kind,
            "evidence_level": self.evidence_level,
            "provider_writes_authorized": self.provider_writes_authorized,
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


def _load_supported_entrypoints() -> dict[str, str]:
    try:
        payload = json.loads(_RETIREMENT_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load retirement registry: {exc}") from exc
    entries = payload.get("supported_entrypoints")
    if not isinstance(entries, list):
        raise ValueError("retirement registry supported_entrypoints must be a list")
    supported: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("retirement registry entry must be an object")
        entry_id = item.get("id")
        entrypoint = item.get("entrypoint")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("retirement registry entry id must be a non-empty string")
        if not isinstance(entrypoint, str) or not entrypoint:
            raise ValueError("retirement registry entrypoint must be a non-empty string")
        supported[entry_id] = entrypoint
    return supported


def _require_bool(
    acceptance: dict[str, Any],
    field_name: str,
    expected: bool,
    errors: list[str],
) -> None:
    value = acceptance.get(field_name)
    if value is not expected:
        errors.append(f"operational acceptance field {field_name} must be {str(expected).lower()}")


def _validate_operational_acceptance(
    payload: Any,
    *,
    manifest_name: str,
    archive_names: set[str],
    result: VerificationResult,
) -> None:
    result.acceptance_checked = True
    if not isinstance(payload, dict):
        result.errors.append(f"manifest root must be an object for acceptance: {manifest_name}")
        return
    acceptance = payload.get("operational_acceptance")
    if not isinstance(acceptance, dict):
        result.errors.append(f"manifest is missing operational_acceptance object: {manifest_name}")
        return

    if acceptance.get("schema_name") != _ACCEPTANCE_SCHEMA:
        result.errors.append(
            f"operational acceptance schema_name must be {_ACCEPTANCE_SCHEMA}: {manifest_name}"
        )
    if acceptance.get("schema_version") != _ACCEPTANCE_VERSION:
        result.errors.append(
            f"operational acceptance schema_version must be {_ACCEPTANCE_VERSION}: {manifest_name}"
        )

    package_kind = acceptance.get("package_kind")
    evidence_level = acceptance.get("evidence_level")
    if not isinstance(package_kind, str) or package_kind not in _PACKAGE_KINDS:
        result.errors.append(f"unsupported operational package_kind: {package_kind!r}")
    else:
        result.package_kind = package_kind
    if not isinstance(evidence_level, str) or evidence_level not in _EVIDENCE_LEVELS:
        result.errors.append(f"unsupported operational evidence_level: {evidence_level!r}")
    else:
        result.evidence_level = evidence_level

    _require_bool(acceptance, "provider_writes_authorized", False, result.errors)
    _require_bool(acceptance, "automatic_execution", False, result.errors)

    if package_kind in {"editorial_bundle", "read_only_evidence_bundle"}:
        _require_bool(acceptance, "provider_adapter_connected", False, result.errors)
        return

    if package_kind != "provider_write_bundle":
        return

    standalone_executors = sorted(
        name
        for name in archive_names
        if PurePosixPath(name).suffix.casefold() in {".py", ".pyw", ".bat", ".cmd", ".exe"}
    )
    for name in standalone_executors:
        result.errors.append(
            f"provider_write_bundle contains a standalone executable outside the registered operator: {name}"
        )
    powershell_launchers = sorted(
        name for name in archive_names if PurePosixPath(name).suffix.casefold() == ".ps1"
    )
    if len(powershell_launchers) > 1:
        result.errors.append(
            "provider_write_bundle may contain at most one PowerShell orchestration launcher "
            f"(found {len(powershell_launchers)})"
        )

    if evidence_level not in _WRITE_READY_LEVELS:
        result.errors.append(
            "provider_write_bundle evidence_level must be self_tested, canary_verified, or batch_verified"
        )

    project_key = acceptance.get("project_key")
    target_identity = acceptance.get("target_identity")
    if not isinstance(project_key, str) or project_key not in PROJECT_IDENTITIES:
        result.errors.append(f"provider_write_bundle has unknown project_key: {project_key!r}")
    elif not isinstance(target_identity, dict):
        result.errors.append("provider_write_bundle target_identity must be an object")
    else:
        expected_community, expected_owner = PROJECT_IDENTITIES[project_key]
        if (target_identity.get("community_id"), target_identity.get("owner_id")) != (
            expected_community,
            expected_owner,
        ):
            result.errors.append("provider_write_bundle project/community/owner identity is inconsistent")

    try:
        supported = _load_supported_entrypoints()
    except ValueError as exc:
        result.errors.append(str(exc))
    else:
        expected_entrypoint = supported.get("production-operator")
        if acceptance.get("supported_entrypoint") != expected_entrypoint:
            result.errors.append(
                "provider_write_bundle supported_entrypoint must equal the registered production operator"
            )

    required_true_fields = (
        "repository_owned_provider",
        "provider_adapter_connected",
        "read_only_preflight_required",
        "canary_required",
        "per_operation_results_required",
        "unknown_outcome_requires_reconciliation",
        "blind_retry_prohibited",
        "separate_review_required",
    )
    for field_name in required_true_fields:
        _require_bool(acceptance, field_name, True, result.errors)


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
    require_acceptance: bool = False,
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
        parsed_manifests: dict[str, Any] = {}
        for manifest_name in manifest_names:
            try:
                payload = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                result.errors.append(f"invalid manifest JSON {manifest_name}: {exc}")
                continue
            parsed_manifests[manifest_name] = payload
            secret_paths = _find_secret_json_values(payload)
            for secret_path in secret_paths:
                result.errors.append(f"manifest contains a non-empty secret-like field: {manifest_name}:{secret_path}")

        if require_acceptance:
            if len(manifest_names) != 1:
                result.acceptance_checked = True
                result.errors.append(
                    "acceptance verification requires exactly one manifest.json "
                    f"(found {len(manifest_names)})"
                )
            elif manifest_names[0] in parsed_manifests:
                _validate_operational_acceptance(
                    parsed_manifests[manifest_names[0]],
                    manifest_name=manifest_names[0],
                    archive_names=names,
                    result=result,
                )

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
        "--require-acceptance",
        action="store_true",
        help="Require and validate the operational_acceptance manifest contract.",
    )
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
            require_acceptance=args.require_acceptance,
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
