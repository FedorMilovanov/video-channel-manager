from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from urllib.parse import parse_qs

import httpx

from video_channel_manager.platforms.vk.client import VkApiClient
from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.tools.operational_package_acceptance import (
    verify_operational_package,
)


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _manifest(**overrides: object) -> dict[str, object]:
    acceptance: dict[str, object] = {
        "schema_name": "video-manager.operational-package-acceptance",
        "schema_version": "1.0",
        "package_kind": "provider_write_bundle",
        "evidence_level": "self_tested",
        "project_key": "lord-god-strength",
        "target_identity": {"community_id": 60805374, "owner_id": -60805374},
        "supported_entrypoint": "scripts/operator/Invoke-VideoManager.ps1",
        "repository_owned_provider": True,
        "provider_adapter_connected": True,
        "read_only_preflight_required": True,
        "canary_required": True,
        "per_operation_results_required": True,
        "unknown_outcome_requires_reconciliation": True,
        "blind_retry_prohibited": True,
        "separate_review_required": True,
        "provider_writes_authorized": False,
        "automatic_execution": False,
    }
    acceptance.update(overrides)
    return {
        "schema_name": "example",
        "schema_version": "1.0",
        "operational_acceptance": acceptance,
        "operations": [],
    }


def _bundle_files(
    manifest: dict[str, object],
    *,
    standalone_executor: bool = False,
) -> dict[str, str]:
    manifest_text = json.dumps(manifest)
    files = {
        "run-operation.ps1": '$ErrorActionPreference = "Stop"\n$Root = $PSScriptRoot\n',
        "manifest.json": manifest_text,
        "README.txt": "Repository operator handoff\n",
    }
    checksum_lines = [f"{hashlib.sha256(manifest_text.encode()).hexdigest()}  manifest.json"]
    if standalone_executor:
        files["executor.py"] = "print('historical external executor')\n"
        checksum_lines.append(f"{hashlib.sha256(files['executor.py'].encode()).hexdigest()}  executor.py")
    files["SHA256SUMS.txt"] = "\n".join(checksum_lines) + "\n"
    return files


def test_acceptance_gate_never_authorizes_writes(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    _write_zip(archive, _bundle_files(_manifest()))

    result = verify_operational_package(archive)

    assert result.ok
    assert result.structural_ok is True
    assert result.package_kind == "provider_write_bundle"
    assert result.evidence_level == "self_tested"
    assert result.provider_writes_authorized is False
    assert result.as_dict()["provider_writes_authorized"] is False


def test_acceptance_gate_rejects_external_executor_false_binding_and_preview_claim(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "bundle.zip"
    manifest = _manifest(
        supported_entrypoint="executor.py",
        target_identity={"community_id": 235216998, "owner_id": -235216998},
        evidence_level="preview_validated",
    )
    _write_zip(archive, _bundle_files(manifest, standalone_executor=True))

    result = verify_operational_package(archive)

    assert not result.ok
    assert any("registered production operator" in error for error in result.acceptance_errors)
    assert any("standalone executable" in error for error in result.acceptance_errors)
    assert any("identity is inconsistent" in error for error in result.acceptance_errors)
    assert any("evidence_level must be self_tested" in error for error in result.acceptance_errors)


def test_acceptance_gate_rejects_automatic_execution_and_missing_reconciliation(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "bundle.zip"
    _write_zip(
        archive,
        _bundle_files(
            _manifest(
                automatic_execution=True,
                unknown_outcome_requires_reconciliation=False,
            )
        ),
    )

    result = verify_operational_package(archive)

    assert not result.ok
    assert any("automatic_execution must be false" in error for error in result.acceptance_errors)
    assert any("unknown_outcome_requires_reconciliation must be true" in error for error in result.acceptance_errors)


def test_vk_managed_community_preflight_uses_moder_extended_and_bounded_page(
    tmp_path: Path,
) -> None:
    token_store = VkTokenStore(tmp_path)
    token_store.save_token("default", VkAccessToken(access_token="access", user_id=42))

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        assert method == "groups.get"
        assert params["filter"] == "moder"
        assert params["extended"] == "1"
        assert params["count"] == "1000"
        assert params["offset"] == "0"
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [
                        {
                            "id": 60805374,
                            "name": "Lord God Strength",
                            "screen_name": "gospod_bog",
                        }
                    ],
                }
            },
        )

    client = VkApiClient(
        token_store=token_store,
        account_alias="default",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
        max_attempts=1,
    )

    communities = client.list_managed_communities()

    assert [item.community_id for item in communities] == [60805374]
