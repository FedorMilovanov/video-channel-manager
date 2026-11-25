from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import milovi_history_vk_schedule_20261108 as vk

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "content/editorial/milovi-cake/history-vk-20261108-1400.json"


def test_vk_history_exact_owner_date_and_two_links_are_pinned():
    p = vk.load_plan(PLAN)
    assert p["publish_date_unix"] == 1794135600
    assert p["scheduled_at"] == "2026-11-08T14:00:00+03:00"
    assert p["owner_id"] == -68859909
    assert p["community_id"] == 68859909
    assert p["credential_alias"] == "vk-milovi-cake-community-key"
    assert p["message"].count(vk.SOURCE) == 1 and p["message"].count(vk.CAKE) == 1
    assert p["message_sha256"] == vk.sha(p["message"])
    assert p["vk_native_article_created"] is False
    assert p["provider_write_attempts"] == 0


@pytest.mark.parametrize(
    "field,bad",
    [
        ("community_id", 68859908),
        ("scheduled_at", "2026-11-08T19:00:00+03:00"),
        ("publish_date_unix", 1794135601),
        ("credential_alias", "default"),
        ("provider_write_attempts", 1),
        ("vk_native_article_created", True),
    ],
)
def test_vk_frozen_plan_rejects_identity_and_schedule_changes(tmp_path: Path, field: str, bad: object):
    plan = vk.load_plan(PLAN)
    plan[field] = bad
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(vk.VkHistoryReleaseBlocked):
        vk.load_plan(path)


def _mock_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, response: dict) -> list[dict]:
    actions: list[dict] = []

    class FakeToken:
        token_type = "community"
        scopes = ["wall"]

        def is_expired(self):
            return False

    class FakeStore:
        def __init__(self, *args, **kwargs):
            self.data_dir = tmp_path

        def token_exists(self, alias):
            return alias in (vk.ALIAS, vk.SERVICE)

        def load_token(self, alias):
            return FakeToken()

    class FakeRead:
        def get_community_token_permissions(self):
            return 8192, {"wall"}

        def get_community(self, community):
            return SimpleNamespace(ref=SimpleNamespace(channel_id=str(community)))

        def close(self):
            pass

    class FakeWriter:
        def assert_method_circuit_closed(self, *args):
            pass

        def assert_token_scopes(self, *args):
            return FakeToken()

        def _call(self, method, params, retry_transient=True):
            actions.append({"method": method, "params": dict(params), "retry": retry_transient})
            return response

        def close(self):
            pass

    witness = tmp_path / "admin_snapshot.json"
    witness.write_text(
        json.dumps(
            {
                "schema": "milovi-history-vk-admin-postponed-preflight-v1",
                "community_id": vk.COMMUNITY,
                "owner_id": vk.OWNER,
                "read_only": True,
                "provider_writes": 0,
                "status": "ok",
                "completed_read": True,
                "checked_utc": "2026-11-07T12:00:00+00:00",
                "postponed_total": 0,
                "exact_story_postponed": [],
                "exact_slot_other_posts": [],
                "items": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(vk, "ADMIN_WITNESS", witness)
    monkeypatch.setattr(vk, "VkTokenStore", FakeStore)
    monkeypatch.setattr(vk, "VkApiClient", lambda **kwargs: FakeRead())
    monkeypatch.setattr(vk, "MiloviCommunitySchoolWriter", lambda **kwargs: FakeWriter())
    monkeypatch.setattr(
        vk,
        "_read_public_duplicate_guard",
        lambda *_args, **_kwargs: {"published_count": 153, "same_source_public_matches": 0},
    )
    monkeypatch.setattr(vk, "local_vk_write_lock", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(vk, "community_vk_write_lock_path", lambda *args, **kwargs: tmp_path / "lock")
    monkeypatch.setattr(vk, "get_settings", lambda: SimpleNamespace(vk_api_version="5.199"))
    return actions


def test_vk_one_exact_postponed_provider_write_then_no_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = _mock_provider(monkeypatch, tmp_path, {"post_id": 654})
    journal = tmp_path / "persist/history.json"
    result = vk.schedule_once(
        plan_path=PLAN,
        journal_path=journal,
        data_dir=tmp_path,
        confirmation=vk.CONFIRM,
        now=datetime(2026, 11, 7, 12, tzinfo=UTC),
    )
    assert len(calls) == 1
    assert calls[0]["method"] == "wall.post"
    assert calls[0]["retry"] is False
    payload = calls[0]["params"]
    assert payload["owner_id"] == -68859909
    assert payload["from_group"] is True
    assert payload["publish_date"] == 1794135600
    assert payload["guid"] == vk.load_plan(PLAN)["guid"]
    assert result["post_id"] == 654
    assert result["state"] == "vk_accepted_postponed_pending_admin_postflight"
    stored = json.loads(journal.read_text(encoding="utf-8"))
    assert stored["provider_writes_attempted"] == 1
    assert stored["post_id"] == 654
    assert stored["native_article_created"] is False
    with pytest.raises(vk.VkHistoryReleaseBlocked, match="journal exists"):
        vk.schedule_once(
            plan_path=PLAN,
            journal_path=journal,
            data_dir=tmp_path,
            confirmation=vk.CONFIRM,
            now=datetime(2026, 11, 7, 12, tzinfo=UTC),
        )
    assert len(calls) == 1


def test_unknown_vk_result_remains_journalled_and_never_retried(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = _mock_provider(monkeypatch, tmp_path, {})
    journal = tmp_path / "history.json"
    with pytest.raises(vk.VkHistoryReleaseBlocked, match="no exact positive"):
        vk.schedule_once(
            plan_path=PLAN,
            journal_path=journal,
            data_dir=tmp_path,
            confirmation=vk.CONFIRM,
            now=datetime(2026, 11, 7, 12, tzinfo=UTC),
        )
    record = json.loads(journal.read_text(encoding="utf-8"))
    assert record["state"] == "unknown_or_rejected_vk_provider_response_NO_RETRY"
    assert record["provider_writes_attempted"] == 1
    assert record["post_id"] is None
    with pytest.raises(vk.VkHistoryReleaseBlocked, match="journal exists"):
        vk.schedule_once(
            plan_path=PLAN,
            journal_path=journal,
            data_dir=tmp_path,
            confirmation=vk.CONFIRM,
            now=datetime(2026, 11, 7, 12, tzinfo=UTC),
        )
    assert len(calls) == 1


def test_wrong_vk_authorization_blocks_before_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = _mock_provider(monkeypatch, tmp_path, {"post_id": 123})
    with pytest.raises(vk.VkHistoryReleaseBlocked, match="confirmation"):
        vk.schedule_once(
            plan_path=PLAN,
            journal_path=tmp_path / "x.json",
            data_dir=tmp_path,
            confirmation="other",
            now=datetime(2026, 11, 7, 12, tzinfo=UTC),
        )
    assert not calls
