from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.verify_operational_bundle import verify_bundle


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _valid_files() -> dict[str, str]:
    launcher = '$ErrorActionPreference = "Stop"\n$Root = $PSScriptRoot\nWrite-Host $Root\n'
    manifest = {
        "schema_name": "example",
        "schema_version": "1.0",
        "operations": [],
    }
    executor = "print('ok')\n"
    readme = "Run run-operation.ps1\n"
    checksums = (
        f"{hashlib.sha256(executor.encode()).hexdigest()}  executor.py\n"
        f"{hashlib.sha256(json.dumps(manifest).encode()).hexdigest()}  manifest.json\n"
    )
    return {
        "run-operation.ps1": launcher,
        "executor.py": executor,
        "manifest.json": json.dumps(manifest),
        "README.txt": readme,
        "SHA256SUMS.txt": checksums,
    }


def test_valid_flat_bundle(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    _write_zip(archive, _valid_files())

    result = verify_bundle(
        archive,
        entrypoint="run-operation.ps1",
        required=["executor.py", "manifest.json", "README.txt", "SHA256SUMS.txt"],
        require_flat=True,
    )

    assert result.ok
    assert not result.errors


def test_nested_root_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    files = {f"bundle/{name}": content for name, content in _valid_files().items()}
    _write_zip(archive, files)

    result = verify_bundle(
        archive,
        entrypoint="run-operation.ps1",
        require_flat=True,
    )

    assert not result.ok
    assert any("extra nested root" in error for error in result.errors)


def test_missing_entrypoint_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    files = _valid_files()
    files.pop("run-operation.ps1")
    _write_zip(archive, files)

    result = verify_bundle(archive, entrypoint="run-operation.ps1")

    assert not result.ok
    assert any("required archive member is missing" in error for error in result.errors)


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    _write_zip(archive, {"../run.ps1": "$PSScriptRoot\n"})

    result = verify_bundle(archive)

    assert not result.ok
    assert any("unsafe path segments" in error for error in result.errors)


def test_secret_filename_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    files = _valid_files()
    files["secrets/client_secret.json"] = '{"client_secret": "secret"}'
    _write_zip(archive, files)

    result = verify_bundle(archive)

    assert not result.ok
    assert any("possible secret file" in error for error in result.errors)


def test_manifest_secret_value_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    files = _valid_files()
    files["manifest.json"] = json.dumps({"access_token": "secret"})
    _write_zip(archive, files)

    result = verify_bundle(archive)

    assert not result.ok
    assert any("secret-like field" in error for error in result.errors)


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    files = _valid_files()
    files["SHA256SUMS.txt"] = f"{'0' * 64}  executor.py\n"
    _write_zip(archive, files)

    result = verify_bundle(archive)

    assert not result.ok
    assert any("checksum mismatch" in error for error in result.errors)
