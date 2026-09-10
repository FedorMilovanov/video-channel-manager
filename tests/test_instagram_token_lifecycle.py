from __future__ import annotations

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from video_channel_manager.cli import instagram_production as cli
from video_channel_manager.instagram.production import InstagramProviderError


runner = CliRunner()


class _DatabaseStub:
    def close(self) -> None:
        pass


class _PreflightServiceStub:
    def __init__(self, error: InstagramProviderError, *, login_mode: str = "facebook") -> None:
        self.config = SimpleNamespace(login_mode=login_mode)
        self._error = error

    def preflight(self) -> dict[str, object]:
        raise self._error

    def close(self) -> None:
        pass


def test_preflight_classifies_meta_code_190_without_echoing_raw_provider_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _PreflightServiceStub(
        InstagramProviderError(
            "Error validating access token: secret-looking-provider-detail",
            status_code=400,
            error_code="190",
        )
    )
    monkeypatch.setattr(cli, "_open_service", lambda: (service, _DatabaseStub()))

    result = runner.invoke(cli.instagram_production_app, ["preflight"])

    assert result.exit_code == 2
    assert "OAuth error code 190" in result.output
    assert "access token is invalid or expired" in result.output
    assert "fresh Page Access Token" in result.output
    assert "VCM_INSTAGRAM_WRITES_ENABLED=false" in result.output
    assert "No provider write was attempted" in result.output
    assert "secret-looking-provider-detail" not in result.output


def test_preflight_keeps_noncredential_provider_error_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _PreflightServiceStub(
        InstagramProviderError(
            "Provider rejected an unsupported field",
            status_code=400,
            error_code="100",
        )
    )
    monkeypatch.setattr(cli, "_open_service", lambda: (service, _DatabaseStub()))

    result = runner.invoke(cli.instagram_production_app, ["preflight"])

    assert result.exit_code == 2
    assert "Provider rejected an unsupported field" in result.output
    assert "OAuth error code 190" not in result.output


def test_instagram_login_code_190_uses_generic_token_remediation() -> None:
    message = cli._preflight_failure_message(
        InstagramProviderError("expired", status_code=400, error_code="190"),
        login_mode="instagram",
    )

    assert "configured Instagram credential" in message
    assert "Page Access Token" not in message
    assert "No provider write was attempted" in message
