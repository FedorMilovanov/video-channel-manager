from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from video_channel_manager.cli.instagram_production import (
    _enforce_local_reel_size,
    _open_reconciliation_service,
    instagram_production_app,
)
from video_channel_manager.config import get_settings
from video_channel_manager.instagram.local_resumable import (
    InstagramLocalPublishManifest,
    InstagramLocalResumableService,
    InstagramResumableProviderClient,
    InstagramResumableUploadLedger,
    ResumableUploadState,
)
from video_channel_manager.instagram.production import (
    InstagramProductionError,
    InstagramProductionService,
    InstagramProviderError,
    InstagramPublicationLedger,
    PublicationStatus,
)
from video_channel_manager.persistence import Database


_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(output: str) -> str:
    return _ANSI_CSI.sub("", output)


def test_publish_local_is_exposed_in_production_help() -> None:
    result = CliRunner().invoke(instagram_production_app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "publish-local" in _plain(result.output)


def test_publish_local_exposes_explicit_write_gate() -> None:
    command = get_command(instagram_production_app)
    publish_local = command.commands["publish-local"]
    options = {option for parameter in publish_local.params for option in getattr(parameter, "opts", ())}
    assert "--publication-key" in options
    assert "--execute" in options
    assert "--share-to-feed" in options


def test_publish_local_rejects_file_above_meta_one_gigabyte_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "too-large.mp4"
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=1_000_000_001))

    with pytest.raises(InstagramProductionError, match="at most 1000000000 bytes"):
        _enforce_local_reel_size(video_path)


_ACCOUNT_ID = "17841435926122104"
_USERNAME = "the.legendary.poet"
_UPLOAD_URI = "https://rupload.facebook.com/ig-api-upload/container-local-cli"


def _configure_instagram_env(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    monkeypatch.setenv("VCM_DATABASE_URL", database_url)
    monkeypatch.setenv("VCM_INSTAGRAM_LOGIN_MODE", "facebook")
    monkeypatch.setenv("VCM_INSTAGRAM_GRAPH_HOST", "https://graph.facebook.com")
    monkeypatch.setenv("VCM_INSTAGRAM_GRAPH_API_VERSION", "v26.0")
    monkeypatch.setenv("VCM_INSTAGRAM_ACCOUNT_ID", _ACCOUNT_ID)
    monkeypatch.setenv("VCM_INSTAGRAM_ACCOUNT_USERNAME", _USERNAME)
    monkeypatch.setenv("VCM_INSTAGRAM_ACCESS_TOKEN", "test-token-never-printed")
    monkeypatch.setenv("VCM_INSTAGRAM_WRITES_ENABLED", "false")
    get_settings.cache_clear()


def _seed_local_upload_unknown(database_url: str, publication_key: str) -> None:
    database = Database(database_url)
    try:
        database.create_schema()
        ledger = InstagramPublicationLedger(database)
        upload_ledger = InstagramResumableUploadLedger(database)
        manifest = InstagramLocalPublishManifest(
            publication_key=publication_key,
            account_id=_ACCOUNT_ID,
            media_sha256="sha256:" + "1" * 64,
            media_size_bytes=1024,
            caption="CLI reconciliation regression",
        )
        ledger.ensure_planned(manifest)  # type: ignore[arg-type]
        ledger.claim_container_request(publication_key)
        upload_ledger.bind_container_response(
            publication_key,
            provider_container_id="container-local-cli",
            upload_uri=_UPLOAD_URI,
        )
        ledger.transition(
            publication_key,
            PublicationStatus.CONTAINER_CREATED,
            expected_statuses={PublicationStatus.CONTAINER_REQUESTED},
            container_id="container-local-cli",
        )
        upload_ledger.claim_upload(publication_key, "container-local-cli")
        upload_ledger.mark_unknown(
            publication_key,
            InstagramProviderError("initial resumable HTTP 400", status_code=400),
        )
        ledger.transition(
            publication_key,
            PublicationStatus.PROCESSING,
            expected_statuses={PublicationStatus.CONTAINER_CREATED},
            provider_status="IN_PROGRESS",
        )
    finally:
        database.close()


def test_reconciliation_service_selects_resumable_path_when_child_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'reconcile-local.db').as_posix()}"
    publication_key = "local.cli.route"
    _configure_instagram_env(monkeypatch, database_url)
    _seed_local_upload_unknown(database_url, publication_key)

    service = None
    database = None
    try:
        service, database = _open_reconciliation_service(publication_key)
        assert isinstance(service, InstagramLocalResumableService)
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
        get_settings.cache_clear()


def test_reconciliation_service_keeps_public_url_path_without_resumable_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'reconcile-public.db').as_posix()}"
    _configure_instagram_env(monkeypatch, database_url)
    database = Database(database_url)
    database.create_schema()
    database.close()

    service = None
    opened_database = None
    try:
        service, opened_database = _open_reconciliation_service("public-url-publication")
        assert type(service) is InstagramProductionService
    finally:
        if service is not None:
            service.close()
        if opened_database is not None:
            opened_database.close()
        get_settings.cache_clear()


def test_cli_reconcile_local_phase_error_becomes_terminal_and_marks_child_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'reconcile-phase.db').as_posix()}"
    publication_key = "local.cli.phase-error"
    _configure_instagram_env(monkeypatch, database_url)
    _seed_local_upload_unknown(database_url, publication_key)

    def fake_request(
        self: InstagramResumableProviderClient,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        assert method == "GET"
        assert data is None
        if path == _ACCOUNT_ID:
            return {"id": _ACCOUNT_ID, "username": _USERNAME}
        if path == f"{_ACCOUNT_ID}/content_publishing_limit":
            return {"data": [{"quota_usage": 0, "config": {"quota_total": 100}}]}
        if path == "container-local-cli":
            assert params == {"fields": "id,status,status_code,video_status"}
            return {
                "id": "container-local-cli",
                "status": "In Progress: Media is still being processed.",
                "status_code": "IN_PROGRESS",
                "video_status": {
                    "uploading_phase": {
                        "status": "error",
                        "bytes_transferred": 0,
                        "source_file_size": 0,
                        "errors": [
                            {
                                "code": 1363008,
                                "message": "OIL Error[FILE_NOT_FOUND: 6]: File not found.",
                            }
                        ],
                    },
                    "processing_phase": {"status": "error"},
                },
            }
        raise AssertionError(f"Unexpected provider read: {method} {path} {params}")

    monkeypatch.setattr(InstagramResumableProviderClient, "_request", fake_request)

    try:
        result = CliRunner().invoke(instagram_production_app, ["reconcile", publication_key])
        assert result.exit_code == 0, result.output
        output = _plain(result.output)
        assert "terminal_failure" in output
        assert "ERROR" in output
        assert "1363008" in output
        assert "FILE_NOT_FOUND" in output
        assert "bytes_transferred=0" in output
        assert "Upload state" in output
        assert "provider_failed" in output

        database = Database(database_url)
        try:
            parent = InstagramPublicationLedger(database).get(publication_key)
            child = InstagramResumableUploadLedger(database).get(publication_key)
            assert parent is not None
            assert parent.status == PublicationStatus.TERMINAL_FAILURE
            assert parent.provider_status == "ERROR"
            assert parent.last_error_message is not None
            assert "1363008" in parent.last_error_message
            assert child is not None
            assert child.state == ResumableUploadState.PROVIDER_FAILED
            assert child.last_error_code == "1363008"
            assert child.last_error_message == parent.last_error_message
        finally:
            database.close()
    finally:
        get_settings.cache_clear()


def test_status_exposes_resumable_child_diagnostics_without_provider_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'status-local.db').as_posix()}"
    publication_key = "local.cli.status"
    _configure_instagram_env(monkeypatch, database_url)
    _seed_local_upload_unknown(database_url, publication_key)

    try:
        result = CliRunner().invoke(instagram_production_app, ["status", publication_key])
        assert result.exit_code == 0, result.output
        output = _plain(result.output)
        assert "Upload state" in output
        assert "upload_unknown" in output
        assert "Upload attempts" in output
        assert "InstagramProviderError" in output
        assert "initial resumable HTTP 400" in output
    finally:
        get_settings.cache_clear()
