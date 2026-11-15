from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "youtube_exact_playlist_cleanup.py"
SPEC = importlib.util.spec_from_file_location("youtube_exact_playlist_cleanup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


PLS = sorted(module.PLAYLISTS)


def plan() -> dict:
    rows = [
        {"playlist_id": playlist, "old_membership_id": f"OLD-{i}", "new_membership_id": f"NEW-{i}"}
        for i, playlist in enumerate(PLS)
    ]
    result = {
        "schema": "youtube-washer-exact-playlist-cleanup-v1",
        "owner": module.OWNER,
        "account": module.ACCOUNT,
        "obsolete_video_id": module.OLD,
        "protected_video_id": module.NEW,
        "memberships": rows,
    }
    result["plan_sha256"] = module.canonical_hash(result)
    return result


def item(membership: str, playlist: str, video: str) -> dict:
    return {
        "id": membership,
        "snippet": {
            "playlistId": playlist,
            "channelId": module.OWNER,
            "resourceId": {"kind": "youtube#video", "videoId": video},
        },
        "contentDetails": {"videoId": video},
    }


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class DeletedResponse:
    status_code = 204


class MockProvider:
    api_base_url = "https://youtube.example.test"

    def __init__(self, plan: dict, data_dir: Path, *, fail_after: int = -1):
        self.token_store = type("Store", (), {"data_dir": data_dir})()
        self.items = {}
        for row in plan["memberships"]:
            self.items[row["old_membership_id"]] = item(row["old_membership_id"], row["playlist_id"], module.OLD)
            self.items[row["new_membership_id"]] = item(row["new_membership_id"], row["playlist_id"], module.NEW)
        self.requests: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.fail_after = fail_after

    def read_video(self, video_id):
        self.requests.append(("GET_VIDEO", video_id))
        return {
            "id": video_id,
            "snippet": {"channelId": module.OWNER, "title": "Video", "description": "Description"},
            "status": {"privacyStatus": "unlisted" if video_id == module.OLD else "public", "license": "youtube"},
            "contentDetails": {"duration": "PT51M28S", "hasCustomThumbnail": video_id == module.NEW},
        }

    def _safe_request(self, method, url, *, resource, params):
        assert method == "GET" and url.endswith("playlistItems")
        self.requests.append((method, resource))
        ids = params["id"].split(",")
        return Response({"items": [copy.deepcopy(self.items[id]) for id in ids if id in self.items]})

    def _mutation_request(self, method, url, *, resource, params):
        assert method == "DELETE" and url.endswith("playlistItems")
        membership = params["id"]
        self.requests.append((method, membership))
        if self.fail_after == len(self.deleted):
            return None, type("Failure", (), {"provider_effect": "may_exist"})()
        assert membership in self.items
        video = self.items[membership]["contentDetails"]["videoId"]
        assert video == module.OLD
        del self.items[membership]
        self.deleted.append(membership)
        return DeletedResponse(), None


def test_plan_validation_checks_exact_channel_video_and_memberships():
    current = plan()
    module.validate_plan(current)
    current["obsolete_video_id"] = module.NEW
    with pytest.raises(ValueError, match="identity"):
        module.validate_plan(current)
    current = plan()
    current["memberships"].pop()
    current["plan_sha256"] = module.canonical_hash({k: v for k, v in current.items() if k != "plan_sha256"})
    with pytest.raises(ValueError, match="exactly three"):
        module.validate_plan(current)


def test_dry_run_reads_six_entries_and_never_mutates(tmp_path: Path):
    current = plan()
    provider = MockProvider(current, tmp_path)
    result = module.execute(current, provider, execute_write=False)
    assert result == {"status": "dry_run_ready", "verified_entries": 6, "mutations": 0}
    assert all(request[0] != "DELETE" for request in provider.requests)
    assert len(provider.items) == 6


def test_no_playlist_entries_removed_if_wrong_video_or_channel(tmp_path: Path):
    current = plan()
    provider = MockProvider(current, tmp_path)
    provider.items["OLD-1"]["contentDetails"]["videoId"] = module.NEW
    with pytest.raises(ValueError, match="identity"):
        module.execute(current, provider, execute_write=False)
    assert len(provider.items) == 6
    provider = MockProvider(current, tmp_path)
    provider.items["NEW-2"]["snippet"]["channelId"] = "another-channel"
    with pytest.raises(ValueError, match="identity"):
        module.execute(current, provider, execute_write=False)
    assert len(provider.items) == 6


def test_exact_three_deletes_preserve_new_entries_and_original_videos(tmp_path: Path):
    current = plan()
    provider = MockProvider(current, tmp_path)
    backup = tmp_path / "backup.json"
    receipt = tmp_path / "receipt.json"
    result = module.execute(current, provider, execute_write=True, backup_path=backup, receipt_path=receipt)
    assert result["status"] == "completed_live_verified"
    assert result["provider_deletes_verified"] == 3
    assert len(provider.deleted) == 3
    assert sorted(provider.deleted) == ["OLD-0", "OLD-1", "OLD-2"]
    assert sorted(provider.items.keys()) == ["NEW-0", "NEW-1", "NEW-2"]
    assert backup.is_file() and receipt.is_file()
    assert len([name for name, _ in provider.requests if name == "DELETE"]) == 3


def test_ambiguous_middle_delete_holds_remaining_without_retries(tmp_path: Path):
    current = plan()
    provider = MockProvider(current, tmp_path, fail_after=1)
    backup = tmp_path / "backup.json"
    receipt = tmp_path / "receipt.json"
    with pytest.raises(RuntimeError, match="reconciliation"):
        module.execute(current, provider, execute_write=True, backup_path=backup, receipt_path=receipt)
    assert provider.deleted == ["OLD-0"]
    assert all(x in provider.items for x in ("OLD-1", "OLD-2", "NEW-0", "NEW-1", "NEW-2"))
    receipt_data = __import__("json").loads(receipt.read_text(encoding="utf-8"))
    assert receipt_data["status"] == "pending_reconciliation"
    assert len(receipt_data["attempted"]) == 2
    assert len(receipt_data["verified_removed"]) == 1
    with pytest.raises(ValueError, match="journals"):
        module.execute(current, provider, execute_write=True, backup_path=backup, receipt_path=receipt)
    assert provider.deleted == ["OLD-0"]


def test_plan_must_not_target_protected_membership(tmp_path: Path):
    current = plan()
    current["memberships"][0]["old_membership_id"] = current["memberships"][0]["new_membership_id"]
    current["plan_sha256"] = module.canonical_hash({k: v for k, v in current.items() if k != "plan_sha256"})
    with pytest.raises(ValueError, match="duplicate"):
        module.validate_plan(current)
