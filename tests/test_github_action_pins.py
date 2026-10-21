from __future__ import annotations

import pytest

from _workflow_actions import (
    MINIMUM_RELEASES,
    ActionPinError,
    assert_actions_pinned,
    assert_no_retired_refs,
    iter_action_pins,
    workflow_pins,
)


def test_every_workflow_action_is_pinned_to_a_full_commit_sha() -> None:
    """No workflow may execute a moving tag, branch or short SHA."""

    pins_by_workflow = workflow_pins()

    assert pins_by_workflow, "expected at least one workflow file"
    assert all(pins for pins in pins_by_workflow.values()), "every workflow must pin its actions"


def test_pinned_actions_meet_the_reviewed_minimum_release() -> None:
    """A reviewed minimum blocks downgrades without freezing routine bumps."""

    observed: set[str] = set()

    for workflow, pins in workflow_pins().items():
        for pin in pins:
            minimum = MINIMUM_RELEASES.get(pin.action)
            if minimum is None:
                continue
            observed.add(pin.action)
            assert pin.release >= minimum, (workflow, pin.action, pin.version)

    assert observed == set(MINIMUM_RELEASES)


def test_single_source_of_truth_publication_runtime_is_pinned_consistently() -> None:
    """Every workflow must agree on one release of a shared action."""

    releases_by_action: dict[str, set[str]] = {}

    for pins in workflow_pins().values():
        for pin in pins:
            releases_by_action.setdefault(pin.action, set()).add(pin.version or "")

    assert all(len(releases) == 1 for releases in releases_by_action.values()), releases_by_action


def test_unpinned_action_reference_is_rejected() -> None:
    with pytest.raises(ActionPinError, match="full 40-hex commit SHA"):
        assert_actions_pinned("      - uses: actions/checkout@v4\n", source="fixture.yml")


def test_short_sha_action_reference_is_rejected() -> None:
    with pytest.raises(ActionPinError, match="full 40-hex commit SHA"):
        assert_actions_pinned(
            "      - uses: actions/checkout@3d3c42e # v7.0.1\n",
            source="fixture.yml",
        )


def test_undocumented_release_comment_is_rejected() -> None:
    with pytest.raises(ActionPinError, match="must document its release version"):
        assert_actions_pinned(
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n",
            source="fixture.yml",
        )


def test_reviewed_minimum_blocks_a_downgrade() -> None:
    with pytest.raises(ActionPinError, match="below the reviewed minimum"):
        assert_actions_pinned(
            "      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.0\n",
            source="fixture.yml",
        )


def test_retired_reference_is_rejected_even_when_well_formed() -> None:
    retired = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"

    with pytest.raises(ActionPinError, match="retired action reference is back"):
        assert_actions_pinned(f"      - uses: {retired} # v7.0.0\n", source="fixture.yml")
    with pytest.raises(ActionPinError, match="retired action reference is present"):
        assert_no_retired_refs(f"      - uses: {retired} # v7.0.0\n", source="fixture.yml")


def test_parser_reads_action_ref_and_release() -> None:
    pins = iter_action_pins("      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2\n")

    assert len(pins) == 1
    assert pins[0].action == "actions/upload-artifact"
    assert pins[0].version == "v7.0.2"
    assert pins[0].release == (7, 0, 2)
    assert pins[0].reference == "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9"
