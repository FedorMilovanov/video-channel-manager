from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import pytest
import typer

from video_channel_manager.cli.vk import community_probe, flood_reset, vk_app, wall_probe

ROOT = Path(__file__).resolve().parents[1]
CURRENT_STATE = ROOT / "docs" / "operations" / "current-state.md"
QUARANTINE = ROOT / "docs" / "operations" / "vk-credential-quarantine.md"
RUNBOOKS = (CURRENT_STATE, QUARANTINE)


FENCED_BLOCK = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)


def _documented_invocations() -> list[str]:
    """Every runnable `vk ...` command the operator is told to run.

    Only fenced code blocks count. Prose mentions exist to *forbid* commands
    (`vk login --force`), so scraping every inline span would turn a prohibition
    into an instruction and then fail the parse test for the wrong reason.
    """

    invocations: list[str] = []
    for path in RUNBOOKS:
        for block in FENCED_BLOCK.findall(path.read_text(encoding="utf-8")):
            for line in block.splitlines():
                candidate = line.strip()
                if candidate.startswith("vk ") and "..." not in candidate and "<" not in candidate:
                    invocations.append(candidate)
    return invocations


def _root() -> Any:
    return typer.main.get_command(vk_app)


def _parse(argv: list[str]) -> Any:
    """Parse without executing: no settings, no token store, no provider client."""

    root = _root()
    command_name, *rest = argv
    assert command_name in root.commands, f"documented command does not exist: {command_name}"
    return root.commands[command_name].make_context(command_name, rest, resilient_parsing=False)


def _argv_of(invocation: str) -> list[str]:
    return shlex.split(invocation)[1:]  # drop the `vk` program name


def _documented_options(argv: list[str]) -> dict[str, str]:
    """The `--flag value` pairs exactly as the runbook writes them."""

    pairs: dict[str, str] = {}
    for index, token in enumerate(argv):
        if token.startswith("--") and index + 1 < len(argv):
            pairs[token[2:]] = argv[index + 1]
    return pairs


def test_current_state_never_documents_a_probe_of_the_quarantined_credential() -> None:
    """The legacy credential is quarantined by #662; a "one-shot probe" is still a probe.

    `current-state.md` used to spell out the staged recovery with `--account legendary-poet`,
    which instructed exactly the action the quarantine forbids. The commands now live in the
    quarantine runbook, bound to the successor credential only.
    """

    current_state = CURRENT_STATE.read_text(encoding="utf-8")

    assert "vk-credential-quarantine.md" in current_state
    for forbidden in (
        "vk community-probe --account legendary-poet",
        "vk wall-probe --account legendary-poet",
        "vk flood-reset --account legendary-poet",
    ):
        assert forbidden not in current_state, forbidden

    staged = _documented_invocations()
    assert staged, "the quarantine runbook must keep the staged sequence"
    for invocation in staged:
        assert "legendary-poet" not in invocation, invocation


def test_quarantine_runbook_states_the_only_resume_condition() -> None:
    text = QUARANTINE.read_text(encoding="utf-8")

    assert "54555649" in text
    assert "video,wall,groups,offline" in text
    assert "blocked_on_oauth_consent_legacy_quarantined" in text
    # The quarantine must be justified as a policy decision, not as a code-9 rule, or it
    # contradicts wall-safety-contract.md.
    assert "policy decision about one specific" in text.casefold() or "policy decision" in text.casefold()
    assert "must not** be read as a" in text
    assert "24h" in text or ">64h" in text


def test_operator_runbook_documents_the_staged_recovery() -> None:
    invocations = _documented_invocations()

    assert invocations, "the VK recovery runbook must keep explicit commands"
    assert any("flood-reset" in item for item in invocations)
    assert any("community-probe" in item for item in invocations)
    assert any("wall-probe" in item for item in invocations)


@pytest.mark.parametrize("invocation", _documented_invocations())
def test_documented_operator_command_parses_and_binds_its_options(invocation: str) -> None:
    argv = _argv_of(invocation)
    documented = _documented_options(argv)

    context = _parse(argv)

    assert documented, invocation
    for flag, value in documented.items():
        key = flag.replace("-", "_")
        assert key in context.params, f"{invocation}: option --{flag} is not bound by the command"
        parsed = context.params[key]
        assert parsed == value or str(parsed) == value, (invocation, flag, parsed)


def test_flood_reset_rejects_a_missing_or_wrong_confirmation_before_any_lookup() -> None:
    """Reopening a circuit must always be an explicit, typed acknowledgement.

    The guard is deliberately the first statement of the command, so it fires before any
    settings, token store or provider client is constructed. Calling the callback directly
    asserts that ordering: if a future refactor moves the check after `get_settings()`, the
    test fails here instead of on an operator's machine.
    """

    for confirm in (None, 8, 10):
        with pytest.raises(typer.BadParameter) as excinfo:
            flood_reset(method="groups.getById", account="legendary-poet", confirm_code=confirm)
        assert "confirm-code" in str(excinfo.value)


def test_probe_commands_reject_a_non_positive_community_before_any_lookup() -> None:
    for probe in (community_probe, wall_probe):
        for community in (0, -60805374):
            with pytest.raises(typer.BadParameter) as excinfo:
                probe(community=community, account="legendary-poet")
            assert "community" in str(excinfo.value)


def test_recovery_runbook_never_documents_a_provider_write() -> None:
    """The staged recovery is read-only reads plus one local circuit reset."""

    allowed = {"flood-reset", "flood-status", "community-probe", "wall-probe", "accounts", "token-capabilities"}

    for invocation in _documented_invocations():
        command = _argv_of(invocation)[0]
        assert command in allowed, f"{invocation} is a provider-mutating command in a recovery runbook"
