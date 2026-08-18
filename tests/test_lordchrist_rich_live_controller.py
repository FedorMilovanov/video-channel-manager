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


def test_controller_workflow_has_no_telegram_provider_surface() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "on:\n  push:" in source
    assert "workflow_dispatch:" not in source
    assert "schedule:" not in source
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in source
    assert "api.telegram.org" not in source
    assert "sendRichMessage" not in source
    assert "sendMessage" not in source
    assert "provider-free" in source
    assert "actions: write" in source
    assert "issues: write" in source
    assert "telegram_github_quality_gate" in source
    assert "GITHUB_RUN_ATTEMPT" in source
    assert "workflow dispatch returned HTTP" in source
    assert source.count("/dispatches") == 1
    assert "lordchrist-rich-live-canary.yml" in source
    assert "PUBLISH:lordchrist-rich-sermons-survive-century" in source


def test_controller_and_live_workflow_keep_provider_boundary_separate() -> None:
    controller = WORKFLOW.read_text(encoding="utf-8")
    live = LIVE_WORKFLOW.read_text(encoding="utf-8")
    assert "group: lordchrist-rich-live-controller-v2" in controller
    assert "group: lordchrist-telegram-publisher" in live
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in controller
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" in live
    assert "lordchrist_rich_live_canary send" not in controller
    assert live.count("lordchrist_rich_live_canary send") == 1


def test_refreshed_release_digest_is_pre_provider_and_cross_midnight_only() -> None:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert release["revision"] == "v2-pre-provider-refresh"
    assert release["execute_not_before_moscow"] == "2026-08-18T23:30:00+03:00"
    assert release["execute_not_after_moscow"] == "2026-08-19T01:30:00+03:00"
    assert release["max_combined_verified_per_day_moscow"] == 2
    assert release["max_rich_verified_per_day_moscow"] == 1
    assert "original release window was superseded before any durable intent or provider effect existed" in release[
        "approval_basis"
    ]
