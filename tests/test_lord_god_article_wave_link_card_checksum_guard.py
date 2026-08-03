from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import link_cards_hardened_entry as entry  # noqa: E402


def test_repeated_og_read_checksum_drift_blocks_source_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: list[dict[str, Any]] = [
        {
            "operation_id": "operation-1",
            "image_sha256": "sha256:first",
            "dimension_check_sha256": "sha256:second",
            "checks": {"og_image_dimensions_verified": True},
            "conflicts": [],
            "status": "verified",
        }
    ]
    manifest: dict[str, Any] = {
        "status": "verified",
        "og_image_dimensions_verified": 1,
        "conflicts": 0,
        "conflicting_operations": 0,
        "global_conflicts": [],
        "items": rows,
        "manifest_sha256": "sha256:before",
    }
    monkeypatch.setattr(
        entry,
        "_original_audit_sources",
        lambda *args, **kwargs: (rows, manifest),
    )

    audited_rows, audited = entry.audit_sources({}, {})

    assert audited["status"] == "blocked"
    assert audited["conflicts"] == 1
    assert audited["conflicting_operations"] == 1
    assert audited["og_image_dimensions_verified"] == 0
    assert audited_rows[0]["status"] == "conflict"
    assert audited_rows[0]["conflicts"] == [
        {
            "code": "og_image_changed_between_audit_passes",
            "detail": "first=sha256:first; dimensions=sha256:second",
        }
    ]
    assert audited["manifest_sha256"] != "sha256:before"


def test_active_entrypoint_activates_guard_before_running_hardened_core() -> None:
    source = (ROOT / "scripts" / "schedule_lord_god_article_wave_v3.py").read_text(encoding="utf-8")

    core_import = "link_cards_hardened as link_cards_module"
    guard_import = "link_cards_hardened_entry as checksum_guard_module"
    assert core_import in source
    assert guard_import in source
    assert source.index(core_import) < source.index(guard_import)
    assert "link_cards_module.guarded_main()" in source
