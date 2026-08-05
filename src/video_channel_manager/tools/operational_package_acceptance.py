from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from scripts.verify_operational_bundle import VerificationResult, verify_bundle
from video_channel_manager.wave_engine.models import PROJECT_IDENTITIES


_ACCEPTANCE_SCHEMA = "video-manager.operational-package-acceptance"
_ACCEPTANCE_VERSION = "1.0"
_EVIDENCE_LEVELS = {
    "editorial_prepared",
    "preview_validated",
    "self_tested",
    "canary_verified",
    "batch_verified",
}
_PACKAGE_KINDS = {
    "editorial_bundle",
    "read_only_evidence_bundle",
    "provider_write_bundle",
}
_WRITE_READY_LEVELS = {"self_tested", "canary_verified", "batch_verified"}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_RETIREMENT_REGISTRY = _REPOSITORY_ROOT / "docs" / "operations" / "retirement-registry-v1.json"


@dataclass
class OperationalPackageAcceptanceResult:
    archive: str
    archive_sha256: str
    structural_ok: bool
    structural_errors: list[str] = field(default_factory=list)
    structural_warnings: list[str] = field(default_factory=list)
    acceptance_errors: list[str] = field(default_factory=list)
    package_kind: str | None = None
    evidence_level: str | None = None
    provider_writes_authorized: Literal[False] = False
    automatic_execution: Literal[False] = False

    @property
    def ok(self) -> bool:
        return self.structural_ok and not self.acceptance_errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_name": "video-manager.operational-package-acceptance-result",
            "schema_version": "1.0",
            "archive": self.archive,
            "archive_sha256": self.archive_sha256,
            "ok": self.ok,
            "structural_ok": self.structural_ok,
            "structural_errors": self.structural_errors,
            "structural_warnings": self.structural_warnings,
            "acceptance_errors": self.acceptance_errors,
            "package_kind": self.package_kind,
            "evidence_level": self.evidence_level,
            "provider_writes_authorized": self.provider_writes_authorized,
            "automatic_execution": self.automatic_execution,
        }


def _supported_production_entrypoint() -> str:
    try:
        payload = json.loads(_RETIREMENT_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load retirement registry: {exc}") from exc
    entries = payload.get("supported_entrypoints")
    if not isinstance(entries, list):
        raise ValueError("retirement registry supported_entrypoints must be a list")
    for item in entries:
        if isinstance(item, dict) and item.get("id") == "production-operator":
            entrypoint = item.get("entrypoint")
            if isinstance(entrypoint, str) and entrypoint:
                return entrypoint
    raise ValueError("retirement registry has no production-operator entrypoint")


def _require_bool(
    acceptance: dict[str, Any],
    field_name: str,
    expected: bool,
    errors: list[str],
) -> None:
    if acceptance.get(field_name) is not expected:
        errors.append(f"operational acceptance field {field_name} must be {str(expected).lower()}")


def _load_manifest(archive_path: Path) -> tuple[dict[str, Any] | None, set[str], list[str]]:
    errors: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        names = {
            PurePosixPath(info.filename.rstrip("/")).as_posix()
            for info in archive.infolist()
            if not info.is_dir()
        }
        manifests = sorted(name for name in names if PurePosixPath(name).name.casefold() == "manifest.json")
        if len(manifests) != 1:
            return None, names, [
                "acceptance verification requires exactly one manifest.json "
                f"(found {len(manifests)})"
            ]
        manifest_name = manifests[0]
        try:
            payload = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, names, [f"invalid manifest JSON {manifest_name}: {exc}"]
        if not isinstance(payload, dict):
            errors.append(f"manifest root must be an object: {manifest_name}")
            return None, names, errors
        return payload, names, errors


def _validate_acceptance(
    payload: dict[str, Any],
    names: set[str],
    result: OperationalPackageAcceptanceResult,
) -> None:
    acceptance = payload.get("operational_acceptance")
    if not isinstance(acceptance, dict):
        result.acceptance_errors.append("manifest is missing operational_acceptance object")
        return

    if acceptance.get("schema_name") != _ACCEPTANCE_SCHEMA:
        result.acceptance_errors.append(
            f"operational acceptance schema_name must be {_ACCEPTANCE_SCHEMA}"
        )
    if acceptance.get("schema_version") != _ACCEPTANCE_VERSION:
        result.acceptance_errors.append(
            f"operational acceptance schema_version must be {_ACCEPTANCE_VERSION}"
        )

    package_kind = acceptance.get("package_kind")
    evidence_level = acceptance.get("evidence_level")
    if isinstance(package_kind, str) and package_kind in _PACKAGE_KINDS:
        result.package_kind = package_kind
    else:
        result.acceptance_errors.append(f"unsupported operational package_kind: {package_kind!r}")
    if isinstance(evidence_level, str) and evidence_level in _EVIDENCE_LEVELS:
        result.evidence_level = evidence_level
    else:
        result.acceptance_errors.append(f"unsupported operational evidence_level: {evidence_level!r}")

    _require_bool(acceptance, "provider_writes_authorized", False, result.acceptance_errors)
    _require_bool(acceptance, "automatic_execution", False, result.acceptance_errors)

    if package_kind in {"editorial_bundle", "read_only_evidence_bundle"}:
        _require_bool(acceptance, "provider_adapter_connected", False, result.acceptance_errors)
        return
    if package_kind != "provider_write_bundle":
        return

    if evidence_level not in _WRITE_READY_LEVELS:
        result.acceptance_errors.append(
            "provider_write_bundle evidence_level must be self_tested, canary_verified, or batch_verified"
        )

    forbidden_executables = sorted(
        name
        for name in names
        if PurePosixPath(name).suffix.casefold() in {".py", ".pyw", ".bat", ".cmd", ".exe"}
    )
    for name in forbidden_executables:
        result.acceptance_errors.append(
            f"provider_write_bundle contains a standalone executable outside the registered operator: {name}"
        )
    powershell_launchers = sorted(
        name for name in names if PurePosixPath(name).suffix.casefold() == ".ps1"
    )
    if len(powershell_launchers) > 1:
        result.acceptance_errors.append(
            "provider_write_bundle may contain at most one PowerShell orchestration launcher "
            f"(found {len(powershell_launchers)})"
        )

    project_key = acceptance.get("project_key")
    target_identity = acceptance.get("target_identity")
    if not isinstance(project_key, str) or project_key not in PROJECT_IDENTITIES:
        result.acceptance_errors.append(f"provider_write_bundle has unknown project_key: {project_key!r}")
    elif not isinstance(target_identity, dict):
        result.acceptance_errors.append("provider_write_bundle target_identity must be an object")
    else:
        expected_community, expected_owner = PROJECT_IDENTITIES[project_key]
        observed = (target_identity.get("community_id"), target_identity.get("owner_id"))
        if observed != (expected_community, expected_owner):
            result.acceptance_errors.append(
                "provider_write_bundle project/community/owner identity is inconsistent"
            )

    try:
        production_entrypoint = _supported_production_entrypoint()
    except ValueError as exc:
        result.acceptance_errors.append(str(exc))
    else:
        if acceptance.get("supported_entrypoint") != production_entrypoint:
            result.acceptance_errors.append(
                "provider_write_bundle supported_entrypoint must equal the registered production operator"
            )

    for field_name in (
        "repository_owned_provider",
        "provider_adapter_connected",
        "read_only_preflight_required",
        "canary_required",
        "per_operation_results_required",
        "unknown_outcome_requires_reconciliation",
        "blind_retry_prohibited",
        "separate_review_required",
    ):
        _require_bool(acceptance, field_name, True, result.acceptance_errors)


def verify_operational_package(
    archive_path: Path,
    *,
    entrypoint: str | None = None,
    required: list[str] | None = None,
    require_flat: bool = False,
    max_uncompressed_bytes: int = 20 * 1024 * 1024 * 1024,
) -> OperationalPackageAcceptanceResult:
    structural: VerificationResult = verify_bundle(
        archive_path,
        entrypoint=entrypoint,
        required=required,
        require_flat=require_flat,
        max_uncompressed_bytes=max_uncompressed_bytes,
    )
    result = OperationalPackageAcceptanceResult(
        archive=structural.archive,
        archive_sha256=structural.archive_sha256,
        structural_ok=structural.ok,
        structural_errors=list(structural.errors),
        structural_warnings=list(structural.warnings),
    )
    if not zipfile.is_zipfile(archive_path):
        result.acceptance_errors.append("file is not a valid ZIP archive")
        return result
    payload, names, manifest_errors = _load_manifest(archive_path)
    result.acceptance_errors.extend(manifest_errors)
    if payload is not None:
        _validate_acceptance(payload, names, result)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify operational ZIP structure and fail-closed readiness claims."
    )
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
        result = verify_operational_package(
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
