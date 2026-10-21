from __future__ import annotations

from pathlib import Path

from _workflow_actions import assert_actions_pinned, assert_no_retired_refs


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_A = ROOT / "src" / "video_channel_manager" / "wave_engine" / "package_a.py"
MP3_CONTRACT = ROOT / "docs" / "operations" / "mp3-batch-processing-contract.md"


def test_ci_uses_pinned_action_releases_at_reviewed_minimums() -> None:
    text = CI.read_text(encoding="utf-8")

    pins = assert_actions_pinned(text, source="ci.yml")
    pinned_actions = {pin.action for pin in pins}
    assert pinned_actions == {"actions/checkout", "actions/setup-python", "actions/upload-artifact"}

    # Every reference carries a documented release; the shared contract enforces
    # the reviewed minimum, full-SHA pinning and the retired-ref denylist.
    assert all(pin.version is not None for pin in pins)
    assert_no_retired_refs(text, source="ci.yml")


def test_unclosed_sqlite_connections_are_blocking_and_production_closes_them() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    package_a = PACKAGE_A.read_text(encoding="utf-8")

    assert '"error:unclosed database.*:ResourceWarning"' in pyproject
    assert "from contextlib import closing" in package_a
    assert "with closing(sqlite3.connect(uri, uri=True)) as connection:" in package_a
    assert "with sqlite3.connect(uri, uri=True) as connection:" not in package_a


def test_mp3_contract_records_fail_closed_identity_rules() -> None:
    text = MP3_CONTRACT.read_text(encoding="utf-8")

    for phrase in (
        "schema_version`: `1.1`",
        "source_id_sha256_conflict",
        "sha256_multiple_source_ids",
        "explicit exact metadata wins canonical selection",
        "1,000 ready tracks",
        "40 deterministic chunks of 25",
    ):
        assert phrase in text
