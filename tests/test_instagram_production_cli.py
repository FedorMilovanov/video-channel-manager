from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import video_channel_manager.cli.instagram_production as instagram_cli
from video_channel_manager.cli.instagram_production import instagram_production_app
from video_channel_manager.config import get_settings
from video_channel_manager.instagram.production import (
    InstagramPublicationLedger,
    InstagramRuntimeConfig,
    PublicationStatus,
)
from video_channel_manager.persistence import Database


def test_runtime_config_repr_redacts_access_token() -> None:
    token = "super-secret-instagram-token"
    config = InstagramRuntimeConfig(
        login_mode="instagram",
        graph_host="https://graph.instagram.com",
        api_version="v25.0",
        account_id="17841400000000000",
        expected_username="example_creator",
        access_token=token,
        writes_enabled=False,
        media_allowed_hosts=("cdn.example.com",),
        timeout_seconds=30.0,
        poll_interval_seconds=5.0,
        poll_attempts=24,
    )
    assert token not in repr(config)


def test_plan_is_provider_inert_without_instagram_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "provider-inert-plan.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    database = Database(database_url)
    database.create_schema()
    database.close()

    monkeypatch.setenv("VCM_DATABASE_URL", database_url)
    for variable in (
        "VCM_INSTAGRAM_GRAPH_API_VERSION",
        "VCM_INSTAGRAM_ACCOUNT_ID",
        "VCM_INSTAGRAM_ACCOUNT_USERNAME",
        "VCM_INSTAGRAM_ACCESS_TOKEN",
        "VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS",
    ):
        monkeypatch.delenv(variable, raising=False)
    get_settings.cache_clear()

    manifest_path = tmp_path / "plan.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "publication_key": "provider-inert.plan.001",
                "account_id": "17841400000000000",
                "video_url": "https://cdn.example.com/reel.mp4",
                "media_sha256": f"sha256:{'0' * 64}",
                "media_size_bytes": 1,
                "media_content_type": "video/mp4",
                "caption": "planned locally",
            }
        ),
        encoding="utf-8",
    )

    try:
        result = CliRunner().invoke(instagram_production_app, ["plan", str(manifest_path)])
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 0, result.output

    database = Database(database_url)
    try:
        snapshot = InstagramPublicationLedger(database).get("provider-inert.plan.001")
        assert snapshot is not None
        assert snapshot.status == PublicationStatus.PLANNED
        assert snapshot.provider_container_id is None
        assert snapshot.provider_media_id is None
    finally:
        database.close()


def test_validate_public_is_credential_and_database_inert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "VCM_INSTAGRAM_GRAPH_API_VERSION",
        "VCM_INSTAGRAM_ACCOUNT_ID",
        "VCM_INSTAGRAM_ACCOUNT_USERNAME",
        "VCM_INSTAGRAM_ACCESS_TOKEN",
        "VCM_DATABASE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS", '["cdn.example.com"]')
    get_settings.cache_clear()

    media = b"public exact bytes"
    digest = __import__("hashlib").sha256(media).hexdigest()
    manifest_path = tmp_path / "validate-public.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "publication_key": "provider-inert.validate-public.001",
                "account_id": "17841400000000000",
                "video_url": "https://cdn.example.com/reel.mp4",
                "media_sha256": f"sha256:{digest}",
                "media_size_bytes": len(media),
                "media_content_type": "video/mp4",
                "caption": "",
            }
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_verify(manifest, *, allowed_hosts, media_client):
        calls.append((str(manifest.video_url), allowed_hosts))
        assert media_client.headers.get("authorization") is None
        return {
            "video": {
                "url": str(manifest.video_url),
                "sha256": manifest.media_sha256,
                "size_bytes": manifest.media_size_bytes,
                "content_type": manifest.media_content_type,
            }
        }

    monkeypatch.setattr(instagram_cli, "verify_instagram_manifest_media", fake_verify)

    try:
        result = CliRunner().invoke(instagram_production_app, ["validate-public", str(manifest_path)])
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert calls == [("https://cdn.example.com/reel.mp4", ("cdn.example.com",))]
    assert "Instagram public media validation passed" in result.output
    assert "Meta provider calls/writes: none" in result.output
