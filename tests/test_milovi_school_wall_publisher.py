"""Safety regressions for the single Milovi School community-key write pathway."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.platforms.vk import milovi_school_wall_publisher as mp

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "content/editorial/milovi-cake/vk-school-first-canary-preview-20261105.json"
EDITORIAL = ROOT / "content/editorial/milovi-cake/vk-school-wave-20261105.md"


class Store:
    data_dir = Path("data")

    def token_exists(self, alias: str) -> bool:
        return alias == mp.COMMUNITY_ACCOUNT

    def load_token(self, alias: str) -> object:
        return SimpleNamespace(
            token_type="community", scopes=("wall",), access_token="secret", is_expired=lambda: False
        )


def test_exact_source_preview_loads_without_authorizing_provider_write() -> None:
    preview = mp.load_canary_preview(preview_path=PREVIEW, editorial_path=EDITORIAL)
    assert preview["community_id"] == 68859909
    assert preview["owner_id"] == -68859909
    assert preview["message_sha256"] == mp.EXPECTED_TEXT_SHA256
    assert preview["publish_date_unix"] == 1794042000
    assert preview["provider_writes_authorized"] is False
    assert preview["release_eligible"] is False


def test_modification_of_provider_authority_is_rejected(tmp_path: Path) -> None:
    plan = json.loads(PREVIEW.read_text(encoding="utf-8"))
    plan["provider_writes_authorized"] = True
    modified = tmp_path / "modified.json"
    modified.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(mp.MiloviCanaryBlocked, match="provider_writes_authorized"):
        mp.load_canary_preview(preview_path=modified, editorial_path=EDITORIAL)


def test_wrong_community_or_message_digest_is_rejected(tmp_path: Path) -> None:
    plan = json.loads(PREVIEW.read_text(encoding="utf-8"))
    for field, value in (("community_id", 60805374), ("message_sha256", "fake")):
        mod = {**plan, field: value}
        modified = tmp_path / (field + ".json")
        modified.write_text(json.dumps(mod), encoding="utf-8")
        with pytest.raises(mp.MiloviCanaryBlocked):
            mp.load_canary_preview(preview_path=modified, editorial_path=EDITORIAL)


def test_writer_uses_exact_one_postponed_call_and_guards_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = object.__new__(mp.MiloviCommunitySchoolWriter)
    writer.token_store = Store()
    writer.account_alias = mp.COMMUNITY_ACCOUNT
    calls = []
    monkeypatch.setattr(writer, "assert_method_circuit_closed", lambda method: calls.append(("gate", method)))
    monkeypatch.setattr(writer, "_call", lambda method, **kwargs: calls.append((method, kwargs)) or {"post_id": 917})
    p = mp.load_canary_preview(preview_path=PREVIEW, editorial_path=EDITORIAL)
    assert writer.send_one(p) == 917
    assert calls[0] == ("gate", "wall.post")
    assert len(calls) == 2
    _, call = calls[1]
    assert call["params"]["owner_id"] == -68859909
    assert call["params"]["from_group"] is True
    assert call["params"]["publish_date"] == 1794042000
    assert call["params"]["guid"] == mp.EXPECTED_GUID
    assert call["params"]["message"] == p["message"]
    assert call["retry_transient"] is False


def test_invalid_operator_confirmation_blocks_before_network(tmp_path: Path) -> None:
    journal = tmp_path / "intent.json"
    with pytest.raises(mp.MiloviCanaryBlocked, match="confirmation"):
        mp.schedule_canary_once(
            store=Store(),
            api_version="5.199",
            preview_path=PREVIEW,
            editorial_path=EDITORIAL,
            journal_path=journal,
            confirmation="",
            admin_queue_witness="OWNER_REPORTED_EMPTY_2026-11-05",
        )
    assert not journal.exists()


def test_wrong_administrative_witness_blocks_before_network(tmp_path: Path) -> None:
    journal = tmp_path / "intent.json"
    with pytest.raises(mp.MiloviCanaryBlocked, match="witness"):
        mp.schedule_canary_once(
            store=Store(),
            api_version="5.199",
            preview_path=PREVIEW,
            editorial_path=EDITORIAL,
            journal_path=journal,
            confirmation=mp.CONFIRMATION,
            admin_queue_witness="",
        )
    assert not journal.exists()


def test_duplicate_journal_requires_reconciliation(tmp_path: Path) -> None:
    journal = tmp_path / "intent.json"
    journal.write_text('{"state":"unknown"}', encoding="utf-8")
    with pytest.raises(mp.MiloviCanaryBlocked, match="already exists"):
        mp.schedule_canary_once(
            store=Store(),
            api_version="5.199",
            preview_path=PREVIEW,
            editorial_path=EDITORIAL,
            journal_path=journal,
            confirmation=mp.CONFIRMATION,
            admin_queue_witness="OWNER_REPORTED_EMPTY_2026-11-05",
        )
    assert "unknown" in journal.read_text(encoding="utf-8")


def test_single_mocked_ack_creates_durable_journal_without_second_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = tmp_path / "intent.json"
    network = []

    @contextmanager
    def fake_lock(*args: object, **kwargs: object):
        network.append("lock")
        yield

    class FakeCommunityClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def get_community_token_permissions(self) -> tuple[int, tuple[str, ...]]:
            network.append("permissions")
            return 1024, ("wall",)

        def get_community(self, community: int) -> object:
            assert community == 68859909
            return SimpleNamespace(ref=SimpleNamespace(channel_id="68859909"))

        def close(self) -> None:
            pass

    class FakeWriter:
        def __init__(self, **kwargs: object) -> None:
            pass

        def send_one(self, plan: dict) -> int:
            network.append("post")
            assert journal.exists()
            assert json.loads(journal.read_text(encoding="utf-8"))["state"] == "dispatch_started_ambiguous_if_no_ack"
            return 1042

        def close(self) -> None:
            pass

    monkeypatch.setattr(mp, "local_vk_write_lock", fake_lock)
    monkeypatch.setattr(
        mp, "read_public_preflight", lambda **kwargs: {"public_wall_posts": 162, "same_source_url_present": False}
    )
    monkeypatch.setattr(mp, "VkApiClient", FakeCommunityClient)
    monkeypatch.setattr(mp, "MiloviCommunitySchoolWriter", FakeWriter)
    report = mp.schedule_canary_once(
        store=Store(),
        api_version="5.199",
        preview_path=PREVIEW,
        editorial_path=EDITORIAL,
        journal_path=journal,
        confirmation=mp.CONFIRMATION,
        admin_queue_witness="OWNER_REPORTED_EMPTY_2026-11-05",
    )
    assert report["post_id"] == 1042
    assert report["state"] == "vk_accepted_pending_admin_postflight"
    assert network == ["lock", "permissions", "post"]
    assert json.loads(journal.read_text(encoding="utf-8"))["post_id"] == 1042


def test_writer_rejects_legacy_shared_alias_without_loading_it() -> None:
    writer = object.__new__(mp.MiloviCommunitySchoolWriter)
    writer.token_store = Store()
    writer.account_alias = "legendary-poet"
    with pytest.raises(mp.MiloviCanaryBlocked, match="exact account alias"):
        writer.assert_token_scopes("wall")


def test_ambiguous_response_persists_journal_and_blocks_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from video_channel_manager.platforms.vk.writer import VkWriteError

    journal = tmp_path / "journal.json"
    sends = []

    @contextmanager
    def fake_lock(*args: object, **kwargs: object):
        yield

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def get_community_token_permissions(self) -> tuple[int, tuple[str, ...]]:
            return 1024, ("wall",)

        def get_community(self, cid: int) -> object:
            assert cid == 68859909
            return SimpleNamespace(ref=SimpleNamespace(channel_id="68859909"))

        def close(self) -> None:
            pass

    class FakeWriter:
        def __init__(self, **kwargs: object) -> None:
            pass

        def send_one(self, plan: dict) -> int:
            sends.append(1)
            assert json.loads(journal.read_text(encoding="utf-8"))["provider_writes_attempted"] == 1
            raise VkWriteError("Unknown provider outcome", method="wall.post")

        def close(self) -> None:
            pass

    monkeypatch.setattr(mp, "local_vk_write_lock", fake_lock)
    monkeypatch.setattr(mp, "read_public_preflight", lambda **kwargs: {"public_wall_posts": 162})
    monkeypatch.setattr(mp, "VkApiClient", FakeClient)
    monkeypatch.setattr(mp, "MiloviCommunitySchoolWriter", FakeWriter)

    args = dict(
        store=Store(),
        api_version="5.199",
        preview_path=PREVIEW,
        editorial_path=EDITORIAL,
        journal_path=journal,
        confirmation=mp.CONFIRMATION,
        admin_queue_witness="OWNER_REPORTED_EMPTY_2026-11-05",
    )
    with pytest.raises(VkWriteError, match="Unknown provider outcome"):
        mp.schedule_canary_once(**args)
    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["state"] == "provider_result_ambiguous_or_rejected_reconcile_no_retry"
    assert state["provider_writes_attempted"] == 1
    assert sends == [1]
    with pytest.raises(mp.MiloviCanaryBlocked, match="already exists"):
        mp.schedule_canary_once(**args)
    assert sends == [1]
