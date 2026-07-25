from __future__ import annotations

import pytest

from scripts.refresh_youtube_comments import parse_preflight_summary


def test_parse_preflight_summary() -> None:
    output = """
YouTube comment preflight:
  channel: channel-1
  source snapshot: snapshot-1
  planned operations: 15
  ready now: 12
  already applied: 3
  blockers: 0
  estimated write quota: 600 units
"""
    assert parse_preflight_summary(output) == {
        "planned": 15,
        "ready": 12,
        "already": 3,
        "blockers": 0,
    }


def test_parse_preflight_summary_rejects_incomplete_output() -> None:
    with pytest.raises(ValueError, match="Cannot parse 'blockers'"):
        parse_preflight_summary(
            "planned operations: 1\nready now: 1\nalready applied: 0\n"
        )
