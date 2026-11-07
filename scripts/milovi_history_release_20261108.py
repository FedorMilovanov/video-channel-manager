"""One-date owner reschedule of a never-attempted Milovi Cake Telegram photo.

Strictly migrates ONE protected pending ledger and its index row from the
pre-approved November 7 release to the owner-approved November 8 14:00 MSK.
No provider calls, no retry, and no second Telegram publisher.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.milovi_telegram_feed import (
    MiloviFeedIndex,
    _save_index,
    state_check,
    validate_bundle,
)
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericPublicationLedger,
    initialize_ledger,
    load_ledger,
    save_ledger,
)

PUB = "milovi-feed-20261107-003"
STATE = Path("content/telegram/milovi-cake/feed")
RELEASE = Path("content/telegram/milovi-cake/releases") / f"{PUB}-runtime.json"
EXPECTED_TIME = datetime(2026, 11, 8, 14, 0, tzinfo=ZoneInfo("Europe/Moscow"))
OLD_RELEASE_DIGEST = "sha256:48f7f60ae53ae66572ea25f70dc3f495001f322fd7fbfc59888f99a444cf61b7"
OLD_CANDIDATE_DIGEST = "sha256:244fba0fb8098817eefe54fe8ba63b0fad6e1a50079b86be64e200ce36a26433"
OLD_PROVIDER_PAYLOAD = "sha256:92fe82f4400eeaf56acc46e087bb0e21b4a81d782f74831efd127d65098fed1e"


def reviewed_release():
    validate_bundle(PUB, require_execution_authorized=True)
    release = load_release(RELEASE)
    if (
        release.release_id != PUB
        or len(release.items) != 1
        or release.items[0].scheduled_at != EXPECTED_TIME
        or release.items[0].payload.provider_payload_sha256 != OLD_PROVIDER_PAYLOAD
        or release.channel_username != "@MiloviCake"
        or release.chat_id != -1002215328390
        or release.bot_id != 8716602202
    ):
        raise ValueError("Owner's exact Nov 8 release or Telegram target identity differs")
    return release


def migrate_pending(checkout: Path) -> dict[str, str]:
    """Fail closed unless old index and ledger are exactly never-sent."""
    release = reviewed_release()
    index_path = checkout / STATE / "index.json"
    ledger_path = checkout / STATE / f"{PUB}.json"
    if not index_path.is_file() or not ledger_path.is_file():
        raise ValueError("Original protected index/ledger missing: cannot create a new release silently")
    index = MiloviFeedIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    old = GenericPublicationLedger.model_validate_json(ledger_path.read_text(encoding="utf-8"))
    row = index.entries.get(PUB)
    if row is None:
        raise ValueError("Existing exact publication absent from shared index")
    if (
        row.publication_id != PUB
        or row.release_id != PUB
        or row.ledger_relative_path != str((STATE / f"{PUB}.json")).replace("\\", "/")
        or index.project_key != "milovi-cake"
        or index.channel_username != "@MiloviCake"
    ):
        raise ValueError("Wrong index target identity")
    if old.release_digest == release.digest:
        load_ledger(ledger_path, release)
        if (
            row.release_candidate_sha256 != release.candidate_digest()
            or row.provider_payload_sha256 != OLD_PROVIDER_PAYLOAD
            or row.state != "pending"
            or row.provider_effect != "impossible"
            or row.intent_id is not None
            or row.message_id is not None
        ):
            raise ValueError("Existing migrated ledger/index unsafe or inconsistent")
        return {"migrated": "false", "reason": "exact_existing_new_release"}
    if (
        old.release_digest != OLD_RELEASE_DIGEST
        or old.release_id != PUB
        or old.project_key != "milovi-cake"
        or old.channel_username != "@MiloviCake"
        or old.profile_sha256 != release.profile_sha256
        or set(old.entries) != {PUB}
        or row.release_candidate_sha256 != OLD_CANDIDATE_DIGEST
        or row.provider_payload_sha256 != OLD_PROVIDER_PAYLOAD
        or old.entries[PUB].provider_payload_sha256 != OLD_PROVIDER_PAYLOAD
    ):
        raise ValueError("Original protected pre-revision digest is not exact and provider-inert")
    e = old.entries[PUB]
    if not (
        e.state == row.state == "pending"
        and e.provider_effect == row.provider_effect == "impossible"
        and e.intent_id is None
        and row.intent_id is None
        and e.message_id is None
        and row.message_id is None
        and e.message_url is None
        and row.message_url is None
        and e.attempted_at_utc is None
        and e.published_at_utc is None
        and e.workflow_run_id is None
        and e.workflow_run_attempt is None
    ):
        raise ValueError("Cannot reschedule a possibly sent or uncertain provider effect")
    # Validate the whole revision first; only then stage BOTH files in checkout.
    replacement = initialize_ledger(release)
    row.release_candidate_sha256 = release.candidate_digest()
    row.provider_payload_sha256 = release.items[0].payload.provider_payload_sha256
    row.updated_at_utc = datetime.now(UTC)
    save_ledger(ledger_path, replacement)
    _save_index(index_path, index)
    load_ledger(ledger_path, release)
    return {"migrated": "true", "reason": "exact_original_pending_release_only"}


def due(checkout: Path, *, now: datetime | None = None) -> dict[str, str]:
    reviewed_release()
    clock = (now or datetime.now(UTC)).astimezone(EXPECTED_TIME.tzinfo)
    if clock.date() != EXPECTED_TIME.date():
        return {"dispatch": "false", "reason": "wrong_date"}
    if clock < EXPECTED_TIME or clock >= EXPECTED_TIME + timedelta(minutes=120):
        return {"dispatch": "false", "reason": "outside_exact_owner_authorized_window"}
    row = state_check(PUB, state_checkout=checkout, require_publishable=True)
    if row["state"] != "pending" or row["provider_effect"] != "impossible":
        raise ValueError("Owner's approved article is no longer in exact safe pending state")
    return {"dispatch": "true", "publication_id": PUB, "reason": "owner_exact_nov8_14_msk"}


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("operation", choices=("validate", "migrate", "due"))
    cli.add_argument("--state-checkout", type=Path)
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    if args.operation == "validate":
        r = reviewed_release()
        print(
            json.dumps(
                {
                    "valid": True,
                    "publication_id": PUB,
                    "scheduled": r.items[0].scheduled_at.isoformat(),
                    "provider_writes": 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.state_checkout is None:
        cli.error("state-checkout is required")
    outcome = migrate_pending(args.state_checkout) if args.operation == "migrate" else due(args.state_checkout)
    if args.output is not None:
        with args.output.open("a", encoding="utf-8") as f:
            for key, value in outcome.items():
                f.write(f"{key}={value}\n")
    print(json.dumps(outcome, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
