from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import mutations  # noqa: E402
from lord_god_article_wave_v3 import photo_wave_v5 as v5  # noqa: E402
from lord_god_article_wave_v3 import photo_wave_v5_upload_retry as retry  # noqa: E402


class FakeReadClient:
    def __init__(self) -> None:
        self.upload_server_calls: list[str] = []
        self.current_user_calls = 0

    def get_current_user(self) -> Any:
        self.current_user_calls += 1
        return SimpleNamespace(user_id=631487)

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        assert method == "photos.getWallUploadServer"
        assert params == {"group_id": 60805374}
        url = f"https://upload.example.test/{len(self.upload_server_calls) + 1}"
        self.upload_server_calls.append(url)
        return {"upload_url": url}


class FakeMutationClient:
    def __init__(self, *, save_error: Exception | None = None) -> None:
        self.save_error = save_error
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def _call(self, method: str, *, params: dict[str, object] | None = None) -> object:
        self.calls.append((method, params))
        assert method == "photos.saveWallPhoto"
        if self.save_error is not None:
            raise self.save_error
        return [{"owner_id": 631487, "id": 457250600}]


def operation() -> dict[str, object]:
    return {
        "operation_id": "lord-god-article-photo-wave-v5-test-08",
        "url": "https://gospod-bog.ru/articles/test/",
        "publish_date": 1786446000,
        "message_sha256": "sha256:test",
    }


def test_empty_upload_response_retries_with_fresh_url_then_saves_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    read_client = FakeReadClient()
    mutation_client = FakeMutationClient()
    journal: dict[str, Any] = {"operations": {}}
    uploaded_urls: list[str] = []

    def fake_upload(upload_url: str, *, operation_id: str, jpeg: bytes) -> dict[str, Any]:
        uploaded_urls.append(upload_url)
        assert operation_id.endswith("-08")
        assert jpeg == b"jpeg"
        if len(uploaded_urls) == 1:
            raise RuntimeError("VK upload response has no photo value")
        return {"photo": "temporary-photo", "hash": "hash", "server": 123}

    monkeypatch.setattr(mutations, "upload_photo_bytes", fake_upload)
    monkeypatch.setattr(retry.time, "sleep", lambda _: None)

    token = retry.prepare_photo_token(
        operation=operation(),
        jpeg=b"jpeg",
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert token == "photo631487_457250600"
    assert uploaded_urls == [
        "https://upload.example.test/1",
        "https://upload.example.test/2",
    ]
    assert read_client.upload_server_calls == uploaded_urls
    assert read_client.current_user_calls == 2
    assert [method for method, _ in mutation_client.calls] == ["photos.saveWallPhoto"]
    entry = journal["operations"][operation()["operation_id"]]
    assert entry["stage"] == "photo_saved"
    assert entry["upload_attempt_count"] == 2
    assert entry["upload_attempts_exhausted"] is False
    assert [item["status"] for item in entry["upload_attempts"]] == [
        "safe_upload_failed",
        "uploaded_and_saved",
    ]
    assert entry["error"] is None


def test_three_safe_upload_failures_stop_before_photo_save(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    read_client = FakeReadClient()
    mutation_client = FakeMutationClient()
    journal: dict[str, Any] = {"operations": {}}

    def fail_upload(upload_url: str, *, operation_id: str, jpeg: bytes) -> dict[str, Any]:
        del upload_url, operation_id, jpeg
        raise RuntimeError("VK upload response has no photo value")

    monkeypatch.setattr(mutations, "upload_photo_bytes", fail_upload)
    monkeypatch.setattr(retry.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed safely after three attempts"):
        retry.prepare_photo_token(
            operation=operation(),
            jpeg=b"jpeg",
            read_client=read_client,
            mutation_client=mutation_client,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    assert len(read_client.upload_server_calls) == 3
    assert read_client.current_user_calls == 3
    assert mutation_client.calls == []
    entry = journal["operations"][operation()["operation_id"]]
    assert entry["stage"] == "photo_upload_failed"
    assert entry.get("post_id") is None
    assert not entry.get("photo_token")
    assert not entry.get("upload_payload")
    assert entry["upload_attempt_count"] == 3
    assert entry["upload_attempts_exhausted"] is True


def test_photo_save_failure_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    read_client = FakeReadClient()
    mutation_client = FakeMutationClient(save_error=RuntimeError("save connection lost"))
    journal: dict[str, Any] = {"operations": {}}

    monkeypatch.setattr(
        mutations,
        "upload_photo_bytes",
        lambda *args, **kwargs: {
            "photo": "temporary-photo",
            "hash": "hash",
            "server": 123,
        },
    )
    monkeypatch.setattr(retry.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="Photo save outcome is unknown"):
        retry.prepare_photo_token(
            operation=operation(),
            jpeg=b"jpeg",
            read_client=read_client,
            mutation_client=mutation_client,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    assert len(read_client.upload_server_calls) == 1
    assert read_client.current_user_calls == 1
    assert [method for method, _ in mutation_client.calls] == ["photos.saveWallPhoto"]
    entry = journal["operations"][operation()["operation_id"]]
    assert entry["stage"] == "photo_save_unknown"


def test_existing_safe_upload_failure_resumes_without_touching_prior_posts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    read_client = FakeReadClient()
    mutation_client = FakeMutationClient()
    item = operation()
    journal: dict[str, Any] = {
        "operations": {
            item["operation_id"]: {
                "operation_id": item["operation_id"],
                "stage": "photo_upload_failed",
                "post_id": None,
                "error": "RuntimeError: VK upload response has no photo value",
            },
            "already-verified": {
                "operation_id": "already-verified",
                "stage": "verified",
                "post_id": 12477,
            },
        }
    }
    monkeypatch.setattr(
        mutations,
        "upload_photo_bytes",
        lambda *args, **kwargs: {
            "photo": "temporary-photo",
            "hash": "hash",
            "server": 123,
        },
    )

    token = retry.prepare_photo_token(
        operation=item,
        jpeg=b"jpeg",
        read_client=read_client,
        mutation_client=mutation_client,
        journal=journal,
        journal_path=tmp_path / "journal.json",
    )

    assert token == "photo631487_457250600"
    assert journal["operations"]["already-verified"] == {
        "operation_id": "already-verified",
        "stage": "verified",
        "post_id": 12477,
    }
    assert journal["operations"][item["operation_id"]]["stage"] == "photo_saved"


def test_retry_journal_redacts_upload_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    read_client = FakeReadClient()
    mutation_client = FakeMutationClient()
    journal: dict[str, Any] = {"operations": {}}

    def fail_with_url(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        raise RuntimeError("failed at https://upload.vk.test/path?secret=token")

    monkeypatch.setattr(mutations, "upload_photo_bytes", fail_with_url)
    monkeypatch.setattr(retry.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed safely after three attempts"):
        retry.prepare_photo_token(
            operation=operation(),
            jpeg=b"jpeg",
            read_client=read_client,
            mutation_client=mutation_client,
            journal=journal,
            journal_path=tmp_path / "journal.json",
        )

    entry = journal["operations"][operation()["operation_id"]]
    serialized = repr(entry)
    assert "upload.vk.test" not in serialized
    assert "secret=token" not in serialized
    assert "<redacted-url>" in serialized


def test_install_patches_only_the_inherited_v5_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(v5.base, "prepare_photo_token", v5.prepare_photo_token)
    retry.install()
    assert v5.base.prepare_photo_token is retry.prepare_photo_token
    assert v5.prepare_photo_token is retry._original_prepare_photo_token
