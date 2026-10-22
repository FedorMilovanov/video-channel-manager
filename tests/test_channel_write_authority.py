"""The channel write-authority table must describe the profiles, not a memory of them.

Before this test the repository stated the mutable `provider_writes_authorized` flag in prose
and nothing compared the prose with the profile. On 2026-10-22 `telegram-multichannel-runbook.md`
and `svodka-target-discovery.md` both still said Svodka was `provider_writes_authorized=false`
while `content/telegram/channels/svodka.json` had been `true`; the same runbook contradicted
itself eight lines later. A reader could not tell which statement was the rule.

The rule now has one machine-readable home, `docs/operations/channel-write-authority.json`,
derived from the profiles and their pinned bindings. These tests compare that snapshot with the
profiles, with the target bindings, with the protected evidence refs, and with the human-readable
table in the runbook, in both directions, so any of the four drifting fails CI.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "docs" / "operations" / "channel-write-authority.json"
RUNBOOK_PATH = ROOT / "docs" / "operations" / "telegram-multichannel-runbook.md"
PROTECTED_REFS_PATH = ROOT / "docs" / "operations" / "protected-evidence-refs.json"
CHANNELS_DIR = ROOT / "content" / "telegram" / "channels"
PROFILE_SCHEMA = "video-channel-manager.telegram-channel-profile"

TABLE_ROW = re.compile(
    r"^\|\s*`(?P<profile>content/telegram/channels/[^`]+\.json)`\s*"
    r"\|\s*`(?P<project_key>[^`]+)`\s*"
    r"\|\s*`(?P<channel_username>[^`]+)`\s*"
    r"\|\s*`(?P<state_ref>[^`]+)`\s*"
    r"\|\s*`(?P<flag>true|false)`\s*\|$",
    re.MULTILINE,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _discovered_profiles() -> dict[str, Path]:
    """Every channel profile on disk, discovered rather than assumed."""

    found: dict[str, Path] = {}
    for path in sorted(CHANNELS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_name") != PROFILE_SCHEMA:
            continue
        rel = path.relative_to(ROOT).as_posix()
        found[rel] = path
    return found


def _expected_rows() -> dict[str, dict[str, Any]]:
    """Recompute the authority from the profiles themselves."""

    snapshot = _read_json(AUTHORITY_PATH)
    declared = {row["profile"]: row for row in snapshot["channels"]}
    profiles = _discovered_profiles()
    assert set(declared) == set(profiles), {
        "undeclared_profiles": sorted(set(profiles) - set(declared)),
        "declared_but_missing": sorted(set(declared) - set(profiles)),
    }

    rows: dict[str, dict[str, Any]] = {}
    for relative, path in profiles.items():
        profile = load_channel_profile(path)
        binding_path = ROOT / declared[relative]["target_binding"]
        binding = load_target_binding(binding_path, profile)
        rows[relative] = {
            "profile": relative,
            "project_key": profile.project_key,
            "channel_username": profile.channel_username,
            "state_ref": profile.state_branch,
            "concurrency_group": profile.concurrency_group,
            "provider_writes_authorized": profile.provider_writes_authorized,
            "profile_digest": profile.digest,
            "profile_file_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            "target_binding": binding_path.relative_to(ROOT).as_posix(),
            "chat_id": binding.chat_id,
            "bot_id": binding.bot_id,
            "bot_username": binding.bot_username,
        }
    return rows


def test_authority_snapshot_equals_the_profiles_it_describes() -> None:
    snapshot = _read_json(AUTHORITY_PATH)
    assert snapshot["schema_name"] == "video-channel-manager.channel-write-authority"
    assert snapshot["schema_version"] == 1
    assert snapshot["enforced_by"] == "tests/test_channel_write_authority.py"

    declared = {row["profile"]: row for row in snapshot["channels"]}
    expected = _expected_rows()

    assert set(declared) == set(expected)
    for relative, row in expected.items():
        assert declared[relative] == row, {
            "profile": relative,
            "drifted_fields": sorted(k for k in row if declared[relative].get(k) != row[k]),
        }


def test_authority_rows_point_at_surviving_state_refs_and_unique_groups() -> None:
    """A row that names a state ref or a concurrency group must name the real one."""

    snapshot = _read_json(AUTHORITY_PATH)
    protected = {str(item["ref"]) for item in _read_json(PROTECTED_REFS_PATH)["refs"]}

    state_refs = {row["state_ref"] for row in snapshot["channels"]}
    assert state_refs <= protected, sorted(state_refs - protected)

    # Two profiles may share a state ref (@lordchrist has a closed legacy queue and an open
    # historical one), but then they must also share one serialising concurrency group.
    by_state_ref: dict[str, set[str]] = {}
    for row in snapshot["channels"]:
        by_state_ref.setdefault(row["state_ref"], set()).add(row["concurrency_group"])
    for state_ref, groups in by_state_ref.items():
        assert len(groups) == 1, {state_ref: sorted(groups)}


def test_runbook_table_matches_the_authority_snapshot() -> None:
    """The human-readable table is the same claim as the JSON, so it is checked the same way."""

    snapshot = _read_json(AUTHORITY_PATH)
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    rows = list(TABLE_ROW.finditer(text))
    assert rows, "the runbook must carry the channel write-authority table"

    documented = {
        match.group("profile"): {
            "project_key": match.group("project_key"),
            "channel_username": match.group("channel_username"),
            "state_ref": match.group("state_ref"),
            "provider_writes_authorized": match.group("flag") == "true",
        }
        for match in rows
    }
    declared_paths = [match.group("profile") for match in rows]
    assert len(declared_paths) == len(set(declared_paths)), "a profile may appear once in the table"

    expected = {
        row["profile"]: {
            "project_key": row["project_key"],
            "channel_username": row["channel_username"],
            "state_ref": row["state_ref"],
            "provider_writes_authorized": row["provider_writes_authorized"],
        }
        for row in snapshot["channels"]
    }
    assert documented == expected, {
        "only_in_runbook": sorted(set(documented) - set(expected)),
        "only_in_snapshot": sorted(set(expected) - set(documented)),
        "drifted": sorted(k for k in expected if k in documented and documented[k] != expected[k]),
    }


def test_operational_prose_does_not_restate_a_flag_the_snapshot_owns() -> None:
    """A live operational page must cite the snapshot instead of re-asserting the flag.

    Prose is allowed to *require* the gate (`...=true` as a release condition) and is allowed to
    describe artifacts that carry their own flag; what it may not do is claim what a channel
    profile is set to right now, because that is exactly the sentence that went stale.
    """

    snapshot = _read_json(AUTHORITY_PATH)
    profiles = {row["profile"] for row in snapshot["channels"]}
    stale_phrasings = (
        re.compile(r"currently has `provider_writes_authorized="),
        re.compile(r"profile gate: `provider_writes_authorized="),
        re.compile(r"provider writes remain disabled for (?:the )?[A-Z][A-Za-z]+"),
    )

    offenders: list[str] = []
    for path in sorted((ROOT / "docs" / "operations").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if path == RUNBOOK_PATH and "channel-write-authority.json" in text:
            continue
        if any(profile in text for profile in profiles) and any(
            pattern.search(text) for pattern in stale_phrasings
        ):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, {
        "restated_profile_flags": offenders,
        "rule": "cite docs/operations/channel-write-authority.json instead of restating the flag",
    }
