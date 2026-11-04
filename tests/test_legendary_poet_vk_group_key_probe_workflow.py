from __future__ import annotations

from pathlib import Path

from _workflow_actions import assert_actions_pinned, assert_no_retired_refs


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "legendary-poet-vk-group-key-probe.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_group_key_probe_is_manual_dispatch_only_and_pinned() -> None:
    text = _workflow_text()

    pins = assert_actions_pinned(text, source=WORKFLOW.name)
    assert_no_retired_refs(text, source=WORKFLOW.name)
    assert {pin.action for pin in pins} == {"actions/checkout"}

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "permissions:\n  contents: read" in text


def test_group_key_probe_targets_both_communities_via_environments() -> None:
    text = _workflow_text()

    # Operator picks the community; each target resolves its own GitHub
    # Environment so the matching community key secret becomes visible.
    assert "target:" in text
    assert "type: choice" in text
    assert "- legendary-poet" in text
    assert "- lord-god" in text
    assert "environment: ${{ inputs.target == 'lord-god' && 'The_Lord_God_VK' || 'the_legendary_poet_API' }}" in text

    # Lord God is pinned to its community id; Legendary Poet keeps the
    # operator-supplied group id with its historical default.
    assert "'60805374' || inputs.group_id" in text
    assert 'default: "235216998"' in text


def test_group_key_probe_env_expressions_are_quoted_yaml_scalars() -> None:
    # Regression: an unquoted `${{ ... }}` value starts a YAML flow mapping
    # and makes GitHub reject the whole workflow file as invalid.
    text = _workflow_text()

    secret_ref = (
        "${{ inputs.target == 'lord-god' && secrets."
        + "LORD_"
        + "SECRET || secrets."
        + "THE_LEGENDARY_POET_"
        + "GROUP_VK }}"
    )
    assert f'VK_GROUP_TOKEN: "{secret_ref}"' in text
    assert 'TARGET: "${{ inputs.target }}"' in text
    assert "VK_GROUP_TOKEN: ${{" not in text
    assert "GROUP_ID: ${{" not in text


def test_group_key_probe_is_read_only_and_never_prints_the_secret() -> None:
    text = _workflow_text()

    # Only the two read calls are made; no provider write method appears.
    assert 'call("groups.getTokenPermissions")' in text
    assert 'call("groups.getById", group_id=group_id)' in text
    assert "wall.post" not in text
    assert "publish_date" not in text
    assert "photos." not in text
    assert "video." not in text
    assert "messages." not in text

    # The token value is read from the environment only; it is never echoed,
    # printed, uploaded or written to a file.
    assert 'os.environ.get("VK_GROUP_TOKEN", "")' in text
    assert "echo $VK_GROUP_TOKEN" not in text
    assert "echo ${VK_GROUP_TOKEN}" not in text
    assert "print(token)" not in text
    assert "upload-artifact" not in text
    assert "group key secret is EMPTY in this context" in text
    assert "secret is present (value hidden)" in text
