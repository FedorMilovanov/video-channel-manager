from __future__ import annotations

import argparse

import video_channel_manager.youtube_release_cli as cli


def test_phase_one_release_cli_is_adoption_only_and_provider_inert() -> None:
    root = cli.parser()
    subparser_action = next(action for action in root._actions if isinstance(action, argparse._SubParsersAction))
    assert set(subparser_action.choices) == {"adopt-existing"}
    assert "execute" not in subparser_action.choices
