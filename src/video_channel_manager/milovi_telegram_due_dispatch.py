"""Read-only, exact-once due-release guard for Milovi Telegram #809.

A GitHub scheduled workflow may dispatch the *existing* permanent-feed publisher
only for the exact authorized v12-muted release on 2026-11-07 11:00 Moscow.
This module never calls the Telegram provider and never mutates state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release

PUBLICATION_ID = "milovi-feed-20261107-002"
EXPECTED_MEDIA_SHA256 = "sha256:3b680fe94b5007daea9860eeaf16159abf17712887fa3b1714511b48b84143d7"
EXPECTED_PAYLOAD_SHA256 = "sha256:38c6917b999606b72e1f7e95f3a1429a602e5d87f5e53ce5826ec71f5803908c"
EXPECTED_RELEASE_DIGEST = "sha256:9257df1f79b27a6de55e2c591f22975e38b350f3d05cc00bff86e1a3ddac78e2"
EXPECTED_CANDIDATE_DIGEST = "sha256:9fc771f328b91d07600c1d64e9bac14b57d3607547d66c83dde29bd5dc3a9106"
SLOT_UTC = datetime.fromisoformat("2026-11-07T08:00:00+00:00")
EXPIRY_UTC = SLOT_UTC + timedelta(minutes=120)
RELEASE_PATH = Path(f"content/telegram/milovi-cake/releases/{PUBLICATION_ID}-runtime.json")
LEDGER_PATH = f"content/telegram/milovi-cake/feed/{PUBLICATION_ID}.json"
INDEX_PATH = "content/telegram/milovi-cake/feed/index.json"


def require_exact_release() -> None:
    checked = validate_bundle(PUBLICATION_ID, require_execution_authorized=True)
    release = load_release(RELEASE_PATH)
    item = release.items[0]
    if (
        not checked["valid"]
        or checked["blockers"]
        or checked["provider_access_performed"]
        or checked["provider_payload_sha256"] != EXPECTED_PAYLOAD_SHA256
        or checked["release_digest"] != EXPECTED_RELEASE_DIGEST
        or checked["release_candidate_sha256"] != EXPECTED_CANDIDATE_DIGEST
        or release.digest != EXPECTED_RELEASE_DIGEST
        or item.scheduled_at.astimezone(UTC) != SLOT_UTC
        or item.payload.media_sha256 != EXPECTED_MEDIA_SHA256
    ):
        raise ValueError("pinned Milovi release authority/media/slot has drifted")


def dispatch_decision(ledger: dict[str, Any], index: dict[str, Any], *, event: str, now: datetime) -> bool:
    if event not in {"schedule", "workflow_dispatch"}:
        raise ValueError("Milovi due dispatch accepts only schedule or manual dry-run events")
    if now.tzinfo is None:
        raise ValueError("scheduled now must be timezone-aware")
    if event == "schedule" and not (SLOT_UTC <= now.astimezone(UTC) < EXPIRY_UTC):
        raise ValueError("exact Milovi one-time publication window is not open")
    if ledger.get("release_id") != PUBLICATION_ID or ledger.get("release_digest") != EXPECTED_RELEASE_DIGEST:
        raise ValueError("durable ledger is not for exact authorized release")
    if index.get("project_key") != "milovi-cake" or index.get("channel_username") != "@MiloviCake":
        raise ValueError("durable index belongs to wrong Telegram channel")
    expected = index.get("entries", {}).get(PUBLICATION_ID)
    item = ledger.get("entries", {}).get(PUBLICATION_ID)
    if not isinstance(expected, dict) or not isinstance(item, dict):
        raise ValueError("exact initialized publication is missing from durable state")
    if (
        expected.get("release_candidate_sha256") != EXPECTED_CANDIDATE_DIGEST
        or expected.get("provider_payload_sha256") != EXPECTED_PAYLOAD_SHA256
        or item.get("provider_payload_sha256") != EXPECTED_PAYLOAD_SHA256
    ):
        raise ValueError("state payload/candidate binding drifted")

    if item.get("state") == "published" and item.get("provider_effect") == "verified":
        if (
            isinstance(item.get("message_id"), int)
            and item["message_id"] > 0
            and expected.get("message_id") == item["message_id"]
            and expected.get("state") == "published"
            and expected.get("provider_effect") == "verified"
        ):
            return False
        raise ValueError("published state has no exact confirmed Telegram receipt")

    if (
        item.get("state") == "pending"
        and item.get("provider_effect") == "impossible"
        and item.get("intent_id") is None
        and item.get("message_id") is None
        and expected.get("state") == "pending"
        and expected.get("provider_effect") == "impossible"
        and expected.get("intent_id") is None
        and expected.get("message_id") is None
    ):
        return event == "schedule"

    raise ValueError("durable Telegram state has an attempt or unknown effect; refusing dispatch")


def _state_object(path: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "show", f"FETCH_HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"durable state file {path} is not an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=("schedule", "workflow_dispatch"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    require_exact_release()
    decision = dispatch_decision(
        _state_object(LEDGER_PATH),
        _state_object(INDEX_PATH),
        event=args.event,
        now=datetime.now(UTC),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as handle:
        handle.write(f"dispatch={'true' if decision else 'false'}\n")
    print(
        json.dumps(
            {
                "publication_id": PUBLICATION_ID,
                "should_dispatch": decision,
                "event": args.event,
                "provider_access_performed": False,
                "provider_write_performed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
