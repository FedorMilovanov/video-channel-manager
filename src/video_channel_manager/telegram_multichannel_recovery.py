from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome, apply_provider_outcome
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericPublicationLedger,
    load_ledger,
    save_ledger,
    verify_persisted_intent,
)


def confirmed_absent_before_send_outcome(
    envelope: GenericDispatchEnvelope,
    *,
    evidence_note: str,
) -> GenericProviderOutcome:
    note = " ".join(evidence_note.split())
    if not note:
        raise ValueError("pre-send confirmed-absent recovery requires evidence")
    return GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        provider_effect="confirmed_absent",
        retryable=True,
        error=note[:1000],
        receipt=None,
    )


def resolve_confirmed_absent_before_send(
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    *,
    evidence_note: str,
) -> GenericProviderOutcome:
    outcome = confirmed_absent_before_send_outcome(envelope, evidence_note=evidence_note)
    entry = apply_provider_outcome(ledger, envelope, outcome)
    if entry.state != "pending" or entry.provider_effect != "confirmed_absent" or entry.intent_id is not None:
        raise ValueError("pre-send confirmed-absent recovery did not restore a retryable pending entry")
    return outcome


def _load_envelope(path: Path) -> GenericDispatchEnvelope:
    try:
        return GenericDispatchEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid generic dispatch envelope {path}: {exc}") from exc


def resolve_files(
    *,
    release_path: Path,
    ledger_path: Path,
    envelope_path: Path,
    evidence_note: str,
) -> GenericProviderOutcome:
    release = load_release(release_path)
    ledger = load_ledger(ledger_path, release)
    envelope = _load_envelope(envelope_path)
    verify_persisted_intent(release, ledger, envelope)
    outcome = resolve_confirmed_absent_before_send(ledger, envelope, evidence_note=evidence_note)
    save_ledger(ledger_path, ledger)
    return outcome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve a persisted generic Telegram intent only when provider mutation was proven absent before send."
    )
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--evidence-note", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = resolve_files(
        release_path=args.release,
        ledger_path=args.ledger,
        envelope_path=args.envelope,
        evidence_note=args.evidence_note,
    )
    print(
        json.dumps(
            {
                "resolved": True,
                "publication_id": outcome.publication_id,
                "provider_effect": outcome.provider_effect,
                "retryable": outcome.retryable,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
