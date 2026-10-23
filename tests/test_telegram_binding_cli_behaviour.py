"""`telegram_binding_cli` is the read-only gate the runbook promises before a provider write.

`docs/operations/svodka-target-discovery.md` says the CLI "re-checks the live Telegram target from
the pinned ID immediately before any future provider mutation". Nothing executed the module: it had
0% coverage, so the promise rested on the source text alone. These tests run `main()` end to end
against a transport stub and prove what it validates, what it refuses, and that it never writes.

The transport stub is injected through the CLI's own collaborator (`preflight_channel`), so the
real Telegram call sequence runs against `httpx.MockTransport` and no request can leave the process.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager import telegram_binding_cli as cli
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, preflight_channel
from video_channel_manager.telegram_target_binding import load_target_binding
from video_channel_manager.telegram_transport import TelegramApiError

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
LEGACY_PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"

PROFILE = load_channel_profile(PROFILE_PATH)
BINDING = load_target_binding(BINDING_PATH, PROFILE)


def _run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    monkeypatch.setattr("sys.argv", ["python -m video_channel_manager.telegram_binding_cli", *argv])
    code = cli.main()
    return code, capsys.readouterr().out


def _telegram_result(method: str, payload: dict[str, Any]) -> object:
    if method == "getMe":
        return {"id": BINDING.bot_id, "is_bot": True, "username": BINDING.bot_username}
    if method == "getChat":
        assert payload["chat_id"] in {BINDING.chat_id, f"@{BINDING.chat_username}"}
        return {
            "id": BINDING.chat_id,
            "username": BINDING.chat_username,
            "title": PROFILE.channel_title,
            "type": "channel",
        }
    if method == "getChatMember":
        assert payload == {"chat_id": BINDING.chat_id, "user_id": BINDING.bot_id}
        return {
            "status": "administrator",
            "can_post_messages": True,
            "user": {"id": BINDING.bot_id, "is_bot": True, "username": BINDING.bot_username},
        }
    raise AssertionError(f"unexpected Telegram method: {method}")


class _Transport:
    """A provider-free Telegram transport that records every call the CLI makes."""

    def __init__(self, handler: Callable[[str, dict[str, Any]], object] | None = None) -> None:
        self.calls: list[str] = []
        self._handler = handler or _telegram_result

    def _respond(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        self.calls.append(method)
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        try:
            result = self._handler(method, payload)
        except AssertionError as exc:
            return httpx.Response(200, json={"ok": False, "description": str(exc)})
        return httpx.Response(200, json={"ok": True, "result": result})

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace the CLI's transport seam with the real one wired to this stub."""

        transport = self

        def fake_preflight(profile: TelegramChannelProfile, **kwargs: Any) -> GenericTargetProof:
            with httpx.Client(transport=httpx.MockTransport(transport._respond)) as client:
                return preflight_channel(profile, client=client, **kwargs)

        monkeypatch.setattr(cli, "preflight_channel", fake_preflight)


@pytest.fixture()
def transport(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Transport]:
    stub = _Transport()
    stub.install(monkeypatch)
    yield stub


def test_validate_reports_the_pinned_binding_and_never_touches_the_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(*_: object, **__: object) -> object:
        raise AssertionError("validate must not dispatch any provider call")

    monkeypatch.setattr(cli, "preflight_channel", explode)

    code, stdout = _run(
        monkeypatch,
        capsys,
        "validate",
        "--profile",
        str(PROFILE_PATH),
        "--binding",
        str(BINDING_PATH),
    )

    report = json.loads(stdout)
    assert code == 0
    assert report["valid"] is True
    assert report["project_key"] == "svodka"
    assert report["channel_username"] == "@deep_info_life"
    assert report["chat_id"] == BINDING.chat_id
    assert report["bot_id"] == BINDING.bot_id
    assert report["bot_username"] == BINDING.bot_username
    assert report["profile_sha256"] == PROFILE.digest
    assert report["binding_sha256"] == BINDING.digest
    assert report["provider_write_performed"] is False


def test_validate_refuses_a_binding_that_belongs_to_another_channel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(*_: object, **__: object) -> object:
        raise AssertionError("a foreign binding must be refused before any dispatch")

    monkeypatch.setattr(cli, "preflight_channel", explode)
    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m video_channel_manager.telegram_binding_cli",
            "validate",
            "--profile",
            str(LEGACY_PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
        ],
    )

    with pytest.raises(ValueError, match="differs from selected channel profile"):
        cli.main()
    assert capsys.readouterr().out == ""


def test_preflight_requires_the_profile_bot_token_and_sends_nothing_without_it(
    monkeypatch: pytest.MonkeyPatch, transport: _Transport
) -> None:
    monkeypatch.delenv(PROFILE.bot_token_env, raising=False)
    output = ROOT / "tests" / "_never_written_preflight.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m video_channel_manager.telegram_binding_cli",
            "preflight",
            "--profile",
            str(PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(RuntimeError, match=PROFILE.bot_token_env):
        cli.main()

    assert transport.calls == []
    assert not output.exists()


def test_preflight_checks_the_pinned_ids_from_the_binding_not_the_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    transport: _Transport,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(PROFILE.bot_token_env, "test-token")
    monkeypatch.setenv(PROFILE.target_chat_id_env, "-1009999999999")
    monkeypatch.setenv(PROFILE.target_bot_id_env, "1")
    monkeypatch.setenv(PROFILE.target_bot_username_env, "some_other_bot")
    output = tmp_path / "proof.json"

    code, stdout = _run(
        monkeypatch,
        capsys,
        "preflight",
        "--profile",
        str(PROFILE_PATH),
        "--binding",
        str(BINDING_PATH),
        "--output",
        str(output),
    )

    report = json.loads(stdout)
    assert code == 0
    assert transport.calls == ["getMe", "getChat", "getChat", "getChatMember"]
    assert report["preflight"] is True
    assert report["chat_id"] == BINDING.chat_id
    assert report["bot_id"] == BINDING.bot_id
    assert report["bot_username"] == BINDING.bot_username
    assert report["binding_sha256"] == BINDING.digest
    assert report["can_post_messages"] is True

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["schema_name"] == "video-channel-manager.telegram-generic-target-proof"
    assert artifact["chat_id"] == BINDING.chat_id
    assert artifact["bot_id"] == BINDING.bot_id
    assert datetime.fromisoformat(artifact["checked_at_utc"]).tzinfo == UTC


def test_preflight_fails_closed_and_writes_no_artifact_when_the_target_disagrees(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def wrong_channel(method: str, payload: dict[str, Any]) -> object:
        result = _telegram_result(method, payload)
        if method == "getChat" and isinstance(result, dict):
            result = {**result, "username": "another_channel"}
        return result

    stub = _Transport(wrong_channel)
    stub.install(monkeypatch)
    monkeypatch.setenv(PROFILE.bot_token_env, "test-token")
    output = tmp_path / "proof.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m video_channel_manager.telegram_binding_cli",
            "preflight",
            "--profile",
            str(PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(TelegramApiError):
        cli.main()

    assert not output.exists()
    assert capsys.readouterr().out == ""
    assert "getChatMember" not in stub.calls
