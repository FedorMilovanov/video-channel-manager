from __future__ import annotations

import json
from pathlib import Path

AUTH = Path("content/telegram/lordchrist/rich-v1/live-canary-controller-2026-08-18.json")
RELEASE = Path("content/telegram/lordchrist/rich-v1/live-canary-release-2026-08-18.json")
WORKFLOW = Path(".github/workflows/lordchrist-rich-live-controller.yml")
LIVE_WORKFLOW = Path(".github/workflows/lordchrist-rich-live-canary.yml")


def test_controller_authorization_is_exact_provider_free_and_one_shot() -> None:
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    assert auth == {
        "schema_name": "video-channel-manager.lordchrist-rich-live-controller",
        "schema_version": 1,
        "controller_id": "lordchrist-rich-live-controller-2026-08-18-v2",
        "owning_issue": 473,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "chat_id": -1001295216957,
        "bot_id": 8716602202,
        "bot_username": "preaching_mp3_bot",
        "publication_id": "lordchrist-rich-sermons-survive-century",
        "release_path": str(RELEASE).replace("\\", "/"),
        "release_git_blob_sha": "f154548075690983dabd885701c2fbc3d80ecd6f",
        "workflow": "lordchrist-rich-live-canary.yml",
        "ref": "main",
        "confirm": "PUBLISH:lordchrist-rich-sermons-survive-century",
        "execute_not_before_moscow": "2026-08-18T23:30:00+03:00",
        "execute_not_after_moscow": "2026-08-19T01:30:00+03:00",
        "dispatch_once": True,
        "provider_access_allowed": False,
        "provider_write_performed": False,
    }


def test_completed_rich_one_shot_workflows_are_retired_but_evidence_remains() -> None:
    assert AUTH.exists()
    assert RELEASE.exists()
    assert not WORKFLOW.exists()
    assert not LIVE_WORKFLOW.exists()


def test_refreshed_release_digest_is_pre_provider_and_cross_midnight_only() -> None:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert release["revision"] == "v2-pre-provider-refresh"
    assert release["execute_not_before_moscow"] == "2026-08-18T23:30:00+03:00"
    assert release["execute_not_after_moscow"] == "2026-08-19T01:30:00+03:00"
    assert release["max_combined_verified_per_day_moscow"] == 2
    assert release["max_rich_verified_per_day_moscow"] == 1
    assert (
        "original release window was superseded before any durable intent or provider effect existed"
        in release["approval_basis"]
    )
