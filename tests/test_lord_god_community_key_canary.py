from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from _workflow_actions import assert_actions_pinned, assert_no_retired_refs


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "lord-god-vk-community-key-canary.yml"
SCRIPT = ROOT / "scripts" / "canary_lord_god_community_key.py"

sys.path.insert(0, str(ROOT / "scripts"))

import canary_lord_god_community_key as canary  # noqa: E402

from video_channel_manager.wave_engine.vk_lord_god_wall_provider import (  # noqa: E402
    LORD_GOD_ACCOUNT_ALIAS,
    LORD_GOD_WALL_POLICY_VERSION,
    parse_lord_god_wall_operation,
)


def _future(days: int = 1) -> int:
    return int((datetime.now(UTC) + timedelta(days=days)).timestamp())


def test_canary_operation_is_a_valid_single_text_operation() -> None:
    operation = canary.build_canary_operation(publish_date=_future())

    wall = parse_lord_god_wall_operation(operation)

    assert wall.content_kind == "text"
    assert wall.account_alias == LORD_GOD_ACCOUNT_ALIAS
    assert wall.source_id == canary.CANARY_SOURCE_ID
    assert wall.attachment is None
    assert operation.policy_version == LORD_GOD_WALL_POLICY_VERSION
    assert len(operation.operation_id) == 64


def test_canary_operation_rejects_past_or_far_future_dates() -> None:
    with pytest.raises(ValueError, match="more than one hour"):
        canary.build_canary_operation(publish_date=int(datetime.now(UTC).timestamp()))
    with pytest.raises(ValueError, match="within the next 7 days"):
        canary.build_canary_operation(publish_date=_future(days=30))


def test_canary_cli_refuses_a_wrong_confirmation_without_provider_access() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--publish-date",
            str(_future()),
            "--confirm",
            "WRONG",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "CANARY-LORD-GOD-COMMUNITY-KEY" in result.stderr


def test_canary_workflow_is_manual_main_only_environment_gated() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    pins = assert_actions_pinned(text, source=WORKFLOW.name)
    assert_no_retired_refs(text, source=WORKFLOW.name)
    assert {pin.action for pin in pins} == {"actions/checkout", "actions/setup-python"}

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "github.run_attempt == 1" in text
    assert text.count("environment: The_Lord_God_VK") == 1
    assert "group: lord-god-vk-community-key-canary" in text
    assert "cancel-in-progress: false" in text

    # Exactly one provider write path: the reviewed canary script through
    # the Lord God adapter. No raw wall.post call lives in the workflow.
    assert text.count("python scripts/canary_lord_god_community_key.py") == 1
    assert "wall.post" not in text
    assert "--confirm CANARY-LORD-GOD-COMMUNITY-KEY" in text
    assert "community-key-login" in text
    assert "community-key-capabilities" in text
