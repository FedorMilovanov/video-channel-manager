from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_cross_track_effect_guard import require_no_unresolved_provider_effects
from video_channel_manager.lordchrist_research_retirement import load_lordchrist_research_retirement
from video_channel_manager.telegram_multichannel_state import GenericLedgerEntry, GenericPublicationLedger


PUBLICATION_ID = "lordchrist-research-three-preachers-numbers"
PAYLOAD_SHA = "sha256:4df54902ef389abb9e577c74ff7ab0c60a989cf4795e731b83e0fdb103d59ba9"
RELEASE_SHA = "sha256:b836f9dc6733cdc922e5aaed97c250d1d46484fe75a216c1f12e586214a2626f"
INTENT_ID = "9a5e4fc686f8e28c6a3c0d2aedd08402"
GITHUB_SHA = "eb9ccd52b28b957fbf2e1a6b8989880d6e85c43a"
ATTEMPTED = datetime(2026, 8, 10, 12, 58, 6, 217510, tzinfo=UTC)


def _entry() -> GenericLedgerEntry:
    return GenericLedgerEntry(
        publication_id=PUBLICATION_ID,
        provider_payload_sha256=PAYLOAD_SHA,
        state="unknown",
        provider_effect="may_exist",
        intent_id=INTENT_ID,
        dispatch_mode="manual",
        workflow_run_id="31390497205",
        workflow_run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=GITHUB_SHA,
        attempted_at_utc=ATTEMPTED,
        actual_chat_id=-1001295216957,
        actual_chat_username="lordchrist",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        last_error="Telegram returned link-preview semantics that differ from the exact provider payload",
    )


def _ledger() -> GenericPublicationLedger:
    return GenericPublicationLedger(
        schema_name="video-channel-manager.telegram-generic-publication-ledger",
        schema_version=1,
        release_digest=RELEASE_SHA,
        release_id="lordchrist-research-live-2026-08",
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        profile_sha256="sha256:" + "1" * 64,
        entries={PUBLICATION_ID: _entry()},
    )


def _retirement_payload() -> dict[str, object]:
    return {
        "schema_name": "video-channel-manager.lordchrist-research-retirement",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "release_id": "lordchrist-research-live-2026-08",
        "release_digest": RELEASE_SHA,
        "publication_id": PUBLICATION_ID,
        "provider_payload_sha256": PAYLOAD_SHA,
        "intent_id": INTENT_ID,
        "workflow_run_id": "31390497205",
        "workflow_run_attempt": "1",
        "github_sha": GITHUB_SHA,
        "github_workflow_sha": GITHUB_SHA,
        "attempted_at_utc": ATTEMPTED.isoformat(),
        "actual_chat_id": -1001295216957,
        "actual_chat_username": "lordchrist",
        "bot_id": 8716602202,
        "bot_username": "preaching_mp3_bot",
        "provider_effect": "may_exist",
        "disposition": "retired_no_replay",
        "provider_retry_forbidden": True,
        "successor_activation_authorized": False,
        "evidence_note": (
            "Historical provider effect remains unresolved after bounded read-only recovery. "
            "The exact August research release is retired permanently and must never be replayed."
        ),
        "retired_by": "FedorMilovanov / Issue #286",
        "retired_at_utc": "2026-08-10T18:55:00+00:00",
        "owning_issue": 286,
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_exact_retirement_suppresses_only_matching_research_blocker(tmp_path: Path) -> None:
    ledger = _ledger()
    path = tmp_path / "retirement.json"
    _write(path, _retirement_payload())

    retirement = load_lordchrist_research_retirement(path, ledger=ledger)
    result = require_no_unresolved_provider_effects(
        legacy_entries=(),
        research_entries=ledger.entries.values(),
        retired_research_publication_ids=frozenset({retirement.publication_id}),
    )

    assert result == {"legacy": (), "research": ()}
    assert ledger.entries[PUBLICATION_ID].state == "unknown"
    assert ledger.entries[PUBLICATION_ID].provider_effect == "may_exist"


def test_retirement_provenance_drift_fails_closed(tmp_path: Path) -> None:
    ledger = _ledger()
    payload = _retirement_payload()
    payload["attempted_at_utc"] = "2026-08-10T12:58:07+00:00"
    path = tmp_path / "retirement.json"
    _write(path, payload)

    with pytest.raises(ValueError, match="historical dispatch provenance"):
        load_lordchrist_research_retirement(path, ledger=ledger)


def test_retirement_schema_rejects_target_drift(tmp_path: Path) -> None:
    ledger = _ledger()
    payload = _retirement_payload()
    payload["actual_chat_id"] = -1003527567039
    path = tmp_path / "retirement.json"
    _write(path, payload)

    with pytest.raises(ValueError, match="invalid Lordchrist research retirement evidence"):
        load_lordchrist_research_retirement(path, ledger=ledger)


def test_retirement_never_suppresses_legacy_ambiguity(tmp_path: Path) -> None:
    ledger = _ledger()
    path = tmp_path / "retirement.json"
    _write(path, _retirement_payload())
    retirement = load_lordchrist_research_retirement(path, ledger=ledger)
    legacy = _entry().model_copy(update={"publication_id": "lordchrist-legacy-still-ambiguous"})

    with pytest.raises(ValueError, match="legacy=lordchrist-legacy-still-ambiguous"):
        require_no_unresolved_provider_effects(
            legacy_entries=(legacy,),
            research_entries=ledger.entries.values(),
            retired_research_publication_ids=frozenset({retirement.publication_id}),
        )
