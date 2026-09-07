"""Historical production facade with a separate editorial canary approval gate.

Transport verification proves that Telegram accepted the exact reviewed rich
document. It does not by itself approve reader-facing copy for recurring
publication. Releases that opt into ``editorial_approval_required`` therefore
record transport verification first and require a separate provider-free
owner approval before the legacy activation timestamp is populated.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from video_channel_manager import telegram_historical_production_core as _core
from video_channel_manager.telegram_historical_production_core import (
    CHANNEL as CHANNEL,
    CHAT_ID as CHAT_ID,
    CHAT_USERNAME as CHAT_USERNAME,
    HISTORICAL_LEDGER_RELATIVE as HISTORICAL_LEDGER_RELATIVE,
    LEDGER_SCHEMA as LEDGER_SCHEMA,
    MOSCOW as MOSCOW,
    OWNING_ISSUE as OWNING_ISSUE,
    PROJECT as PROJECT,
    REPOSITORY as REPOSITORY,
    STATE_BRANCH as STATE_BRANCH,
    _guard_unresolved as _guard_unresolved,
    _validate_second_pass as _validate_second_pass,
    bind_successor_cycle as bind_successor_cycle,
    build_document as build_document,
    coverage_status as coverage_status,
    decide_scheduled as decide_scheduled,
    guard_state as guard_state,
    load_release as load_release,
    release_digest as release_digest,
    run_preflight as run_preflight,
    send as send,
    successor_cycle_is_bound as successor_cycle_is_bound,
)
from video_channel_manager.telegram_rich_provider import TelegramRichProviderOutcome

TRANSPORT_VERIFIED_FIELD = "canary_transport_verified_at_utc"
EDITORIAL_APPROVED_FIELD = "canary_editorial_approved_at_utc"
EDITORIAL_APPROVED_BY_FIELD = "canary_editorial_approved_by"

_ORIGINAL_NEW_LEDGER = _core.new_ledger
_ORIGINAL_LOAD_LEDGER = _core.load_ledger
_ORIGINAL_APPLY = _core.apply


def _editorial_approval_required(release: dict[str, Any]) -> bool:
    value = release.get("editorial_approval_required", False)
    if not isinstance(value, bool):
        raise ValueError("historical editorial_approval_required must be boolean")
    return value


def new_ledger(release: dict[str, Any], queue: Any, planned_dates: tuple[str, ...]) -> dict[str, Any]:
    """Create the durable ledger, adding explicit two-phase canary state for v2."""

    ledger = _ORIGINAL_NEW_LEDGER(release, queue, planned_dates)
    if _editorial_approval_required(release):
        ledger[TRANSPORT_VERIFIED_FIELD] = None
        ledger[EDITORIAL_APPROVED_FIELD] = None
        ledger[EDITORIAL_APPROVED_BY_FIELD] = None
    return ledger


def _validate_editorial_gate(ledger: dict[str, Any], release: dict[str, Any]) -> None:
    if not _editorial_approval_required(release):
        return
    required = (TRANSPORT_VERIFIED_FIELD, EDITORIAL_APPROVED_FIELD, EDITORIAL_APPROVED_BY_FIELD)
    if any(field not in ledger for field in required):
        raise ValueError("historical v2 ledger is missing explicit editorial canary gate fields")

    transport_at = ledger.get(TRANSPORT_VERIFIED_FIELD)
    approved_at = ledger.get(EDITORIAL_APPROVED_FIELD)
    approved_by = ledger.get(EDITORIAL_APPROVED_BY_FIELD)
    activation_at = ledger.get("canary_verified_at_utc")

    for label, value in (("transport", transport_at), ("editorial approval", approved_at)):
        if value is None:
            continue
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"historical canary {label} timestamp must be timezone-aware")

    if approved_at is None:
        if approved_by is not None or activation_at is not None:
            raise ValueError("historical schedule cannot be armed before explicit editorial approval")
        return
    if transport_at is None:
        raise ValueError("historical editorial approval requires prior transport verification")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("historical editorial approval requires approved_by")
    if activation_at != approved_at:
        raise ValueError("historical activation timestamp must equal exact editorial approval timestamp")

    canary_id = str(release["canary_publication_id"])
    raw = _core._entry(ledger, canary_id)
    if raw.get("state") != "published" or raw.get("provider_effect") != "verified" or not raw.get("message_id"):
        raise ValueError("historical editorial approval requires an exact verified canary publication")


def load_ledger(
    path: Path,
    release: dict[str, Any],
    queue: Any,
    planned_dates: tuple[str, ...],
    *,
    create: bool = False,
) -> dict[str, Any]:
    """Load the exact release ledger and prove its editorial activation semantics."""

    ledger = _ORIGINAL_LOAD_LEDGER(path, release, queue, planned_dates, create=create)
    _validate_editorial_gate(ledger, release)
    return ledger


def apply(
    ledger: dict[str, Any],
    release: dict[str, Any],
    intent: dict[str, Any],
    outcome: TelegramRichProviderOutcome,
) -> dict[str, Any]:
    """Apply provider evidence without automatically approving reader-facing copy."""

    updated = _ORIGINAL_APPLY(ledger, release, intent, outcome)
    publication_id = str(intent.get("publication_id") or "")
    if (
        _editorial_approval_required(release)
        and publication_id == release["canary_publication_id"]
        and outcome.provider_effect == "verified"
    ):
        transport_at = updated.get("canary_verified_at_utc")
        if not isinstance(transport_at, str) or not transport_at:
            raise ValueError("verified historical canary did not produce a transport timestamp")
        updated[TRANSPORT_VERIFIED_FIELD] = transport_at
        updated[EDITORIAL_APPROVED_FIELD] = None
        updated[EDITORIAL_APPROVED_BY_FIELD] = None
        updated["canary_verified_at_utc"] = None
    _validate_editorial_gate(updated, release)
    return updated


def approve_canary(
    ledger: dict[str, Any],
    release: dict[str, Any],
    *,
    expected_message_id: int,
    approved_by: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Provider-free owner approval that alone arms the recurring schedule."""

    if not _editorial_approval_required(release):
        raise ValueError("historical release does not require the explicit editorial approval gate")
    _validate_editorial_gate(ledger, release)
    if ledger.get(EDITORIAL_APPROVED_FIELD) is not None:
        raise ValueError("historical canary is already editorially approved")
    if ledger.get(TRANSPORT_VERIFIED_FIELD) is None:
        raise ValueError("historical canary has not been transport-verified")
    if not approved_by.strip():
        raise ValueError("historical canary approval requires approved_by")

    raw = _core._entry(ledger, str(release["canary_publication_id"]))
    if (
        raw.get("state") != "published"
        or raw.get("provider_effect") != "verified"
        or raw.get("message_id") != expected_message_id
    ):
        raise ValueError("historical canary approval message id differs from durable verified provider evidence")

    approved_at = (now or datetime.now(tz=UTC)).astimezone(UTC).isoformat()
    ledger[EDITORIAL_APPROVED_FIELD] = approved_at
    ledger[EDITORIAL_APPROVED_BY_FIELD] = approved_by.strip()
    # Backward-compatible scheduler activation field. For v2 this timestamp
    # means editorial approval, never raw transport success.
    ledger["canary_verified_at_utc"] = approved_at
    _validate_editorial_gate(ledger, release)
    return ledger


def _install_core_overrides() -> None:
    """Make the existing CLI use the two-phase gate without duplicating transport code."""

    _core.new_ledger = new_ledger
    _core.load_ledger = load_ledger
    _core.apply = apply


def _approval_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telegram_historical_production approve-canary")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--message-id", type=int, required=True)
    parser.add_argument("--approved-by", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the production CLI, intercepting the provider-free approval command."""

    _install_core_overrides()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "approve-canary":
        args = _approval_parser().parse_args(arguments[1:])
        release, queue, _registry, _profile_path, aux = load_release(args.release, args.root)
        ledger = load_ledger(args.ledger, release, queue, tuple(aux["planned_dates"]))
        updated = approve_canary(
            ledger,
            release,
            expected_message_id=args.message_id,
            approved_by=args.approved_by,
        )
        _core._write(args.ledger, updated)
        print(
            json.dumps(
                {
                    "publication_id": release["canary_publication_id"],
                    "message_id": args.message_id,
                    "transport_verified_at_utc": updated[TRANSPORT_VERIFIED_FIELD],
                    "editorial_approved_at_utc": updated[EDITORIAL_APPROVED_FIELD],
                    "editorial_approved_by": updated[EDITORIAL_APPROVED_BY_FIELD],
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    return _core.main(arguments)


# Install for callers that import this module and invoke the core orchestration
# functions indirectly before calling ``main``.
_install_core_overrides()


__all__ = [
    "CHANNEL",
    "CHAT_ID",
    "CHAT_USERNAME",
    "EDITORIAL_APPROVED_BY_FIELD",
    "EDITORIAL_APPROVED_FIELD",
    "HISTORICAL_LEDGER_RELATIVE",
    "LEDGER_SCHEMA",
    "MOSCOW",
    "OWNING_ISSUE",
    "PROJECT",
    "REPOSITORY",
    "STATE_BRANCH",
    "TRANSPORT_VERIFIED_FIELD",
    "_guard_unresolved",
    "_validate_second_pass",
    "apply",
    "approve_canary",
    "bind_successor_cycle",
    "build_document",
    "coverage_status",
    "decide_scheduled",
    "guard_state",
    "load_ledger",
    "load_release",
    "main",
    "new_ledger",
    "release_digest",
    "run_preflight",
    "send",
    "successor_cycle_is_bound",
]


if __name__ == "__main__":
    raise SystemExit(main())
