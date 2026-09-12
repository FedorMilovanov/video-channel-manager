from __future__ import annotations

import json
from io import BytesIO, TextIOWrapper
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console
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


def _cp1252_console() -> tuple[BytesIO, TextIOWrapper, Console]:
    raw = BytesIO()
    stream = TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="")
    console = Console(file=stream, force_terminal=False, color_system=None, width=200)
    return raw, stream, console


def test_validate_local_cyrillic_filename_is_safe_on_cp1252_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "Что Это Такое - Shorts IG CLEAN.mp4"
    raw, stream, legacy_console = _cp1252_console()
    monkeypatch.setattr(instagram_cli, "console", legacy_console)

    evidence = SimpleNamespace(
        path=str(video_path),
        media_sha256=f"sha256:{'1' * 64}",
        media_size_bytes=123,
        structure=SimpleNamespace(moov_before_mdat=True, edit_list_paths=()),
        probe=SimpleNamespace(pixel_format="yuv420p", field_order="progressive"),
        binding=SimpleNamespace(
            ruleset_version="meta-instagram-reels-2026-09-v3",
            container="mp4",
            media_content_type="video/mp4",
            video_codec="h264",
            width=1080,
            height=1920,
            pixel_format="yuv420p",
            field_order="progressive",
            video_frame_rate_fps=30.0,
            video_bitrate_bps=3_600_000,
            audio_codec="aac",
            audio_sample_rate_hz=48_000,
            audio_channels=2,
            audio_bitrate_bps=128_000,
            duration_seconds=174.7,
            advisories=(),
        ),
        closed_gop=SimpleNamespace(
            closed_gop=True,
            intra_frame_count=35,
            idr_frame_count=35,
            nal_length_size=4,
        ),
    )
    monkeypatch.setattr(instagram_cli, "verify_local_reel", lambda _path: evidence)

    result = CliRunner().invoke(instagram_production_app, ["validate-local", str(video_path)])
    stream.flush()
    rendered = raw.getvalue().decode("cp1252")

    assert result.exit_code == 0, result.output
    assert "\\u0427\\u0442\\u043e" in rendered
    assert "Instagram local Reel validation passed" in rendered


def test_validate_public_cyrillic_manifest_error_is_safe_on_cp1252_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "манифест отсутствует.json"
    raw, stream, legacy_console = _cp1252_console()
    monkeypatch.setattr(instagram_cli, "console", legacy_console)

    result = CliRunner().invoke(instagram_production_app, ["validate-public", str(manifest_path)])
    stream.flush()
    rendered = raw.getvalue().decode("cp1252")

    assert result.exit_code == 2
    assert "\\u043c\\u0430\\u043d\\u0438\\u0444\\u0435\\u0441\\u0442" in rendered
    assert "Instagram public media validation failed" in rendered
