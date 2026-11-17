from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.platforms.youtube import (
    InstalledClientConfig,
    OAuthToken,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    YouTubeDescriptionWriter,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
    YouTubeWriteScopeError,
)


def _raw() -> dict[str, Any]:
    return {
        "id": "video-test",
        "etag": "one",
        "snippet": {
            "channelId": "channel-test",
            "title": "Russian title",
            "description": "Russian text",
            "categoryId": "22",
            "tags": ["faith"],
            "defaultLanguage": "ru",
            "defaultAudioLanguage": "ru",
        },
        "status": {"privacyStatus": "public"},
        "contentDetails": {"duration": "PT6M"},
        "localizations": {
            "ru": {"title": "Russian title", "description": "Russian text"},
            "en-US": {"title": "English title", "description": "Old English"},
            "de": {"title": "German title", "description": "German text"},
        },
    }


def _writer(
    tmp_path: Path,
    handler: Any,
    *,
    write: bool = True,
    verification_delays: tuple[float, ...] = (),
) -> YouTubeDescriptionWriter:
    store = TokenStore(tmp_path)
    store.save_token(
        "account",
        OAuthToken(
            access_token="fake",
            refresh_token="fake_refresh",
            scopes=[YOUTUBE_FORCE_SSL_SCOPE] if write else [YOUTUBE_READONLY_SCOPE],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    return YouTubeDescriptionWriter(
        client_config=InstalledClientConfig(client_id="fake", client_secret="fake"),
        token_store=store,
        account_alias="account",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://youtube.test",
        verification_delays=verification_delays,
    )


def _args(raw: dict[str, Any]) -> dict[str, Any]:
    sn = raw["snippet"]
    return {
        "video_id": raw["id"],
        "expected_channel_id": sn["channelId"],
        "expected_title": sn["title"],
        "expected_primary_description": sn["description"],
        "expected_snippet_fields": {
            k: sn.get(k) for k in ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage")
        },
        "expected_privacy": raw["status"]["privacyStatus"],
        "expected_duration": raw["contentDetails"]["duration"],
        "expected_localizations": copy.deepcopy(raw["localizations"]),
        "language": "en-US",
        "expected_localized_description": "Old English",
        "new_description": "Improved English.",
    }


def test_localization_only_put_preserves_russian_german_and_metadata(tmp_path: Path) -> None:
    raw = _raw()
    orig = copy.deepcopy(raw)
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        assert request.url.params["part"] == "localizations"
        assert request.method == "PUT"
        payload = json.loads(request.content)
        assert set(payload) == {"id", "localizations"}
        assert payload["localizations"]["en-US"] == {
            "title": "English title",
            "description": "Improved English.",
        }
        assert payload["localizations"]["ru"] == orig["localizations"]["ru"]
        assert payload["localizations"]["de"] == orig["localizations"]["de"]
        raw = copy.deepcopy(raw)
        raw["localizations"] = payload["localizations"]
        return httpx.Response(200, json=raw)

    writer = _writer(tmp_path, handle)
    after = writer.replace_localized_description(**_args(orig))
    assert methods == ["GET", "PUT", "GET"]
    assert after.description == "Russian text"
    assert after.raw["snippet"] == orig["snippet"]
    assert after.raw["localizations"]["de"] == orig["localizations"]["de"]
    assert after.raw["localizations"]["en-US"]["description"] == "Improved English."


@pytest.mark.parametrize(
    "drift",
    [
        "wrong_channel",
        "changed_title",
        "changed_ru_text",
        "changed_en_text",
        "removed_locale",
        "changed_privacy",
        "changed_tags",
        "changed_audio",
        "changed_duration",
        "bad_language",
    ],
)
def test_localization_guard_refuses_stale_or_unsafe_before_put(tmp_path: Path, drift: str) -> None:
    orig = _raw()
    raw = copy.deepcopy(orig)
    args = _args(orig)
    if drift == "wrong_channel":
        raw["snippet"]["channelId"] = "other"
    elif drift == "changed_title":
        raw["snippet"]["title"] = "Other title"
    elif drift == "changed_ru_text":
        raw["snippet"]["description"] = "Other Russian"
    elif drift == "changed_en_text":
        raw["localizations"]["en-US"]["description"] = "Other English"
    elif drift == "removed_locale":
        del raw["localizations"]["de"]
    elif drift == "changed_privacy":
        raw["status"]["privacyStatus"] = "private"
    elif drift == "changed_tags":
        raw["snippet"]["tags"].append("other")
    elif drift == "changed_audio":
        raw["snippet"]["defaultAudioLanguage"] = "en"
    elif drift == "changed_duration":
        raw["contentDetails"]["duration"] = "PT7M"
    else:
        args["language"] = "ru"
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.method == "GET"
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(tmp_path, handle)
    with pytest.raises((YouTubeRevisionConflictError, YouTubeWriteError), match="no PUT sent"):
        writer.replace_localized_description(**args)
    assert methods == ["GET"]


@pytest.mark.parametrize("post_effect", ["changed_audio", "changed_secondary_locale", "changed_primary"])
def test_localization_postflight_drift_blocks_without_replay(tmp_path: Path, post_effect: str) -> None:
    raw = _raw()
    orig = copy.deepcopy(raw)
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal raw
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        payload = json.loads(request.content)
        raw = copy.deepcopy(raw)
        raw["localizations"] = payload["localizations"]
        if post_effect == "changed_audio":
            raw["snippet"]["defaultAudioLanguage"] = "en-US"
        elif post_effect == "changed_secondary_locale":
            raw["localizations"]["de"]["description"] = "Altered"
        else:
            raw["snippet"]["description"] = "Auto translation"
        return httpx.Response(200, json=raw)

    writer = _writer(tmp_path, handle)
    with pytest.raises(YouTubeWriteError, match="postflight drift"):
        writer.replace_localized_description(**_args(orig))
    assert methods == ["GET", "PUT", "GET"]


def test_localization_readonly_token_no_put(tmp_path: Path) -> None:
    raw = _raw()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.method == "GET"
        return httpx.Response(200, json={"items": [raw]})

    writer = _writer(tmp_path, handle, write=False)
    with pytest.raises(YouTubeWriteScopeError):
        writer.replace_localized_description(**_args(raw))
    assert methods == ["GET"]


def test_localization_api_503_never_retries_put(tmp_path: Path) -> None:
    raw = _raw()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [raw]})
        return httpx.Response(503, json={"error": {"message": "Ambiguous failure"}})

    writer = _writer(tmp_path, handle)
    with pytest.raises(YouTubeWriteError):
        writer.replace_localized_description(**_args(raw))
    assert methods == ["GET", "PUT"]


# CLI contract: dry-run has no provider effect; execute is one locked, journaled mutation.
def _make_localization_plan(tmp_path: Path) -> Path:
    import hashlib

    def h(text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    raw = _raw()
    path = tmp_path / "localized-plan.json"
    plan = {
        "schema_name": "video-manager.youtube-localization-fix-plan",
        "schema_version": 1,
        "provider_mutation_authorized": True,
        "project_key": "lord-god-strength",
        "channel_id": "UCeSJsC6go2c9pdJCuUI1BYA",
        "video_id": raw["id"],
        "language": "en-US",
        "expected_title": raw["snippet"]["title"],
        "expected_primary_description": raw["snippet"]["description"],
        "expected_primary_sha256": h(raw["snippet"]["description"]),
        "expected_localizations": raw["localizations"],
        "expected_localized_description": "Old English",
        "before_sha256": h("Old English"),
        "after_description": "Improved English.",
        "after_sha256": h("Improved English."),
        "expected_snippet_fields": _args(raw)["expected_snippet_fields"],
        "expected_privacy": "public",
        "expected_duration": "PT6M",
    }
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


class _FakeCliWriter:
    def __init__(self, *, fail: bool = False) -> None:
        self.raw = _raw()
        self.raw["snippet"]["channelId"] = "UCeSJsC6go2c9pdJCuUI1BYA"
        self.fail = fail
        self.writes = 0

    def read_description(self, video_id: str) -> Any:
        from types import SimpleNamespace

        assert video_id == "video-test"
        return SimpleNamespace(
            channel_id=self.raw["snippet"]["channelId"],
            video_id=video_id,
            title=self.raw["snippet"]["title"],
            description=self.raw["snippet"]["description"],
            raw=copy.deepcopy(self.raw),
        )

    def replace_localized_description(self, **kwargs: Any) -> Any:
        self.writes += 1
        if self.fail:
            raise YouTubeWriteError("Ambiguous 503; may have reached YouTube")
        assert kwargs["language"] == "en-US"
        assert kwargs["expected_localizations"] == self.raw["localizations"]
        self.raw["localizations"]["en-US"]["description"] = kwargs["new_description"]
        return self.read_description(kwargs["video_id"])


def _mock_localization_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, fail: bool = False) -> _FakeCliWriter:
    from contextlib import nullcontext
    from types import SimpleNamespace

    from video_channel_manager.cli import youtube as youtube_cli

    writer = _FakeCliWriter(fail=fail)
    store = SimpleNamespace(load_token=lambda _: SimpleNamespace(scopes=[YOUTUBE_FORCE_SSL_SCOPE]))
    monkeypatch.setattr(youtube_cli, "prepare_windows_youtube_console", lambda: None)
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_writer_components", lambda *_: (store, None, writer))
    monkeypatch.setattr(
        youtube_cli,
        "YouTubeApiClient",
        lambda **_: SimpleNamespace(
            list_my_channels=lambda: [SimpleNamespace(ref=SimpleNamespace(remote_id="UCeSJsC6go2c9pdJCuUI1BYA"))]
        ),
    )
    monkeypatch.setattr(youtube_cli, "local_youtube_write_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(youtube_cli, "presentation_issues", lambda _: [])
    monkeypatch.setattr(youtube_cli, "source_preservation_issues", lambda *_: [])
    return writer


def test_localization_cli_dry_run_never_writes_or_creates_journals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from video_channel_manager.cli import youtube as youtube_cli

    writer = _mock_localization_cli(monkeypatch, tmp_path)
    plan = _make_localization_plan(tmp_path)
    backup, result = tmp_path / "backup.json", tmp_path / "result.json"
    youtube_cli.apply_localization_fix(
        plan,
        account="account",
        confirm_channel="UCeSJsC6go2c9pdJCuUI1BYA",
        execute=False,
        backup_output=backup,
        result_output=result,
        client_secret=None,
    )
    assert writer.writes == 0
    assert not backup.exists() and not result.exists()


def test_localization_cli_single_write_journal_and_second_attempt_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from video_channel_manager.cli import youtube as youtube_cli
    import typer

    writer = _mock_localization_cli(monkeypatch, tmp_path)
    plan = _make_localization_plan(tmp_path)
    backup, result = tmp_path / "backup.json", tmp_path / "result.json"
    opts = {
        "account": "account",
        "confirm_channel": "UCeSJsC6go2c9pdJCuUI1BYA",
        "execute": True,
        "backup_output": backup,
        "result_output": result,
        "client_secret": None,
    }
    youtube_cli.apply_localization_fix(plan, **opts)
    assert writer.writes == 1
    stored = json.loads(result.read_text(encoding="utf-8"))
    assert stored["status"] == "completed"
    assert stored["provider_dispatch"] == "verified"
    assert (
        json.loads(backup.read_text(encoding="utf-8"))["snapshot"]["localizations"]["en-US"]["description"]
        == "Old English"
    )
    with pytest.raises(typer.Exit):
        youtube_cli.apply_localization_fix(plan, **opts)
    assert writer.writes == 1


def test_localization_cli_ambiguous_write_does_not_rollback_or_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from video_channel_manager.cli import youtube as youtube_cli
    import typer

    writer = _mock_localization_cli(monkeypatch, tmp_path, fail=True)
    plan = _make_localization_plan(tmp_path)
    backup, result = tmp_path / "backup.json", tmp_path / "result.json"
    opts = {
        "account": "account",
        "confirm_channel": "UCeSJsC6go2c9pdJCuUI1BYA",
        "execute": True,
        "backup_output": backup,
        "result_output": result,
        "client_secret": None,
    }
    with pytest.raises(typer.Exit) as error:
        youtube_cli.apply_localization_fix(plan, **opts)
    assert error.value.exit_code == 2
    assert writer.writes == 1
    stored = json.loads(result.read_text(encoding="utf-8"))
    assert stored["status"] == "pending_reconciliation"
    assert stored["provider_dispatch"] == "may_exist"
    assert backup.exists()
    with pytest.raises(typer.Exit):
        youtube_cli.apply_localization_fix(plan, **opts)
    assert writer.writes == 1


def test_localization_cli_corrupted_digest_blocked_pre_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from video_channel_manager.cli import youtube as youtube_cli
    import typer

    writer = _mock_localization_cli(monkeypatch, tmp_path)
    plan = _make_localization_plan(tmp_path)
    body = json.loads(plan.read_text(encoding="utf-8"))
    body["after_description"] += " unreviewed modification"
    plan.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(typer.Exit) as error:
        youtube_cli.apply_localization_fix(
            plan,
            account="account",
            confirm_channel="UCeSJsC6go2c9pdJCuUI1BYA",
            execute=False,
            backup_output=None,
            result_output=None,
            client_secret=None,
        )
    assert error.value.exit_code == 2
    assert writer.writes == 0


def test_localization_cli_requires_explicit_write_authority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from video_channel_manager.cli import youtube as youtube_cli
    import typer

    writer = _mock_localization_cli(monkeypatch, tmp_path)
    plan = _make_localization_plan(tmp_path)
    data = json.loads(plan.read_text(encoding="utf-8"))
    data["provider_mutation_authorized"] = False
    plan.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(typer.Exit) as failure:
        youtube_cli.apply_localization_fix(
            plan,
            account="account",
            confirm_channel="UCeSJsC6go2c9pdJCuUI1BYA",
            execute=True,
            backup_output=tmp_path / "no-backup.json",
            result_output=tmp_path / "no-receipt.json",
            client_secret=None,
        )
    assert failure.value.exit_code == 2
    assert writer.writes == 0
    assert not (tmp_path / "no-backup.json").exists()


@pytest.mark.parametrize("stale_reads", [1, 2])
def test_localization_postwrite_eventual_consistency_is_get_only(tmp_path: Path, stale_reads: int) -> None:
    """The first owner read can show the old EN despite one successful PUT."""
    original = _raw()
    current = copy.deepcopy(original)
    methods: list[str] = []
    saved = False
    reads_after_put = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal current, saved, reads_after_put
        methods.append(request.method)
        if request.method == "PUT":
            assert request.url.params["part"] == "localizations"
            assert not saved, "a second mutation must never happen"
            current = copy.deepcopy(current)
            current["localizations"] = json.loads(request.content)["localizations"]
            saved = True
            return httpx.Response(200, json=current)
        if saved:
            reads_after_put += 1
            if reads_after_put <= stale_reads:
                return httpx.Response(200, json={"items": [original]})
        return httpx.Response(200, json={"items": [current]})

    writer = _writer(tmp_path, handle, verification_delays=(0.0, 0.0))
    verified = writer.replace_localized_description(**_args(original))
    assert verified.raw["localizations"]["en-US"]["description"] == "Improved English."
    assert verified.description == original["snippet"]["description"]
    assert methods == ["GET", "PUT", *(["GET"] * (stale_reads + 1))]
    assert methods.count("PUT") == 1


def test_localization_postwrite_persistent_old_get_blocks_without_reput(
    tmp_path: Path,
) -> None:
    """Exhausted reads keep the ambiguous result blocked, without rollback."""
    original = _raw()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            assert request.url.params["part"] == "localizations"
            return httpx.Response(200, json={"id": "video-test"})
        return httpx.Response(200, json={"items": [original]})

    writer = _writer(tmp_path, handle, verification_delays=(0.0, 0.0))
    with pytest.raises(YouTubeWriteError, match="still mismatched after 3 safe GET reads"):
        writer.replace_localized_description(**_args(original))
    assert methods == ["GET", "PUT", "GET", "GET", "GET"]


def test_localization_transport_error_never_enters_eventual_get_loop(
    tmp_path: Path,
) -> None:
    original = _raw()
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            return httpx.Response(503, json={"error": {"message": "ambiguous"}})
        return httpx.Response(200, json={"items": [original]})

    writer = _writer(tmp_path, handle, verification_delays=(0.0, 0.0))
    with pytest.raises(YouTubeWriteError, match="YouTube API 503"):
        writer.replace_localized_description(**_args(original))
    assert methods == ["GET", "PUT"]


def test_localization_postwrite_persistent_language_drift_is_not_accepted(
    tmp_path: Path,
) -> None:
    original = _raw()
    current = copy.deepcopy(original)
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal current
        methods.append(request.method)
        if request.method == "PUT":
            current = copy.deepcopy(current)
            current["localizations"] = json.loads(request.content)["localizations"]
            current["snippet"]["defaultAudioLanguage"] = "en-US"
            return httpx.Response(200, json=current)
        return httpx.Response(200, json={"items": [current]})

    writer = _writer(tmp_path, handle, verification_delays=(0.0, 0.0))
    with pytest.raises(YouTubeWriteError, match="still mismatched after 3 safe GET reads"):
        writer.replace_localized_description(**_args(original))
    assert methods == ["GET", "PUT", "GET", "GET", "GET"]
