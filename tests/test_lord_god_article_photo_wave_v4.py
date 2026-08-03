from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import photo_wave_v4 as photo  # noqa: E402


def test_photo_v4_builds_new_ids_and_future_schedule() -> None:
    policy = photo.build_photo_policy(ROOT)

    assert policy["schema_version"] == 4
    assert policy["decision_set_id"] == photo.PHOTO_DECISION_SET_ID
    assert policy["attachment_mode"] == "explicit-wall-photo-plus-text-link"
    assert policy["asset_mode"] == "materialized-jpeg-1200x630"
    assert len(policy["operations"]) == 10
    assert policy["summary"]["first_publish_at"] == "2026-08-04T14:00:00+03:00"
    assert policy["summary"]["last_publish_at"] == "2026-08-13T14:00:00+03:00"

    for ordinal, operation in enumerate(policy["operations"], start=1):
        assert operation["operation_id"].startswith(
            f"{photo.PHOTO_DECISION_SET_ID}-{ordinal:02d}-"
        )
        assert operation["source_operation_id"].startswith(
            "lord-god-article-wave-v3-202608-"
        )
        publish_at = datetime.fromisoformat(operation["publish_at"])
        assert publish_at.day == ordinal + 3
        assert publish_at.hour == 14
        assert operation["url"] in operation["message"]


def test_photo_v4_journal_is_contract_isolated(tmp_path: Path) -> None:
    policy = photo.build_photo_policy(ROOT)
    journal_path = tmp_path / "photo-journal-v4.json"
    old = {
        "schema_name": "video-manager.vk-lord-god-article-wave-journal",
        "schema_version": 4,
        "decision_set_id": "lord-god-article-wave-v3-202608",
        "policy_sha256": "sha256:old",
        "execution_contract_sha256": "sha256:old",
        "operations": {
            "old-canary": {"stage": "photo_save_unknown"},
        },
    }
    journal_path.write_text(json.dumps(old), encoding="utf-8")

    with pytest.raises(RuntimeError, match="another execution contract"):
        photo.load_photo_journal(journal_path, policy)


def test_photo_v4_fresh_journal_has_no_imported_operations() -> None:
    policy = photo.build_photo_policy(ROOT)
    journal = photo.fresh_photo_journal(policy)

    assert journal["decision_set_id"] == photo.PHOTO_DECISION_SET_ID
    assert journal["policy_sha256"] == policy["policy_sha256"]
    assert journal["execution_contract_sha256"] == policy[
        "execution_contract_sha256"
    ]
    assert journal["operations"] == {}


def test_active_runner_has_no_parsed_link_call() -> None:
    runner = (ROOT / "scripts" / "run-lord-god-article-wave.ps1").read_text(
        encoding="utf-8"
    )
    entrypoint = (
        ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py"
    ).read_text(encoding="utf-8")

    assert "wall.parseAttachedLink" not in runner
    assert "photo_wave_v4 as photo_wave_module" in entrypoint
    assert "photo_wave_module.guarded_main()" in entrypoint
