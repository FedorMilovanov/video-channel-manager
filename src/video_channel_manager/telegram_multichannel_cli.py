from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_outcome import (
    GenericProviderOutcome,
    GenericSendProviderEffect,
    apply_provider_outcome,
)
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericPublicationLedger,
    initialize_ledger,
    load_ledger,
    prepare_next,
    save_ledger,
    skip_expired_pending,
    verify_dispatch_against_release,
    verify_persisted_intent,
)
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPollPayload,
    GenericTargetProof,
    TelegramApiError,
    send_message_once,
    send_poll_once,
)
from video_channel_manager.telegram_publication_freshness import (
    publication_freshness,
    skip_expired_pending_by_freshness,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Durable generic multi-channel Telegram publication runtime")
    sub = root.add_subparsers(dest="command", required=True)

    initialize = sub.add_parser("initialize-ledger")
    initialize.add_argument("--release", type=Path, required=True)
    initialize.add_argument("--output", type=Path, required=True)
    initialize.add_argument("--confirm", required=True)

    skip_expired = sub.add_parser("skip-expired")
    skip_expired.add_argument("--release", type=Path, required=True)
    skip_expired.add_argument("--ledger", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--profile", type=Path, required=True)
    prepare.add_argument("--release", type=Path, required=True)
    prepare.add_argument("--ledger", type=Path, required=True)
    prepare.add_argument("--target-proof", type=Path, required=True)
    prepare.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    prepare.add_argument("--publication-id")
    prepare.add_argument(
        "--recover-stale-predecessors",
        action="store_true",
        help="Recover only bounded-stale pending predecessors before an exact manual dispatch.",
    )
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--github-sha", required=True)
    prepare.add_argument("--github-workflow-sha", required=True)
    prepare.add_argument("--envelope-output", type=Path, required=True)

    verify = sub.add_parser("verify-intent")
    verify.add_argument("--release", type=Path, required=True)
    verify.add_argument("--ledger", type=Path, required=True)
    verify.add_argument("--envelope", type=Path, required=True)

    send = sub.add_parser("send-once")
    send.add_argument("--profile", type=Path, required=True)
    send.add_argument("--release", type=Path, required=True)
    send.add_argument("--ledger", type=Path, required=True)
    send.add_argument("--envelope", type=Path, required=True)
    send.add_argument("--outcome-output", type=Path, required=True)

    apply = sub.add_parser("apply-outcome")
    apply.add_argument("--release", type=Path, required=True)
    apply.add_argument("--ledger", type=Path, required=True)
    apply.add_argument("--envelope", type=Path, required=True)
    apply.add_argument("--outcome", type=Path, required=True)

    validate = sub.add_parser("validate-ledger")
    validate.add_argument("--release", type=Path, required=True)
    validate.add_argument("--ledger", type=Path, required=True)
    return root


def _load_model(path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid runtime artifact {path}: {exc}") from exc


def _write_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _require_runtime_profile(profile: TelegramChannelProfile, release: GenericReleaseQueue) -> None:
    if not profile.provider_writes_authorized:
        raise ValueError("selected Telegram channel profile is write-disabled")
    if not release.release_authorized:
        raise ValueError("selected Telegram release is not authorized")
    if (
        release.project_key != profile.project_key
        or release.channel_username.casefold() != profile.channel_username.casefold()
        or release.profile_sha256 != profile.digest
    ):
        raise ValueError("selected Telegram release differs from channel profile")


def _require_release_target(release: GenericReleaseQueue, target: GenericTargetProof) -> None:
    if release.chat_id is None or release.bot_id is None or release.bot_username is None:
        raise ValueError("authorized release has no exact Telegram target identity")
    if (
        target.chat_id != release.chat_id
        or target.bot_id != release.bot_id
        or target.bot_username.casefold() != release.bot_username.casefold()
        or target.channel_username.casefold() != release.channel_username.casefold()
    ):
        raise ValueError("dispatch target differs from exact release-bound Telegram identity")


def _token(profile: TelegramChannelProfile) -> str:
    token = os.environ.get(profile.bot_token_env, "").strip()
    if not token:
        raise ValueError(f"missing Telegram token in {profile.bot_token_env}")
    return token


def _configured_max_publication_lag_minutes() -> int | None:
    raw = os.environ.get("MAX_PUBLICATION_LAG_MINUTES", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MAX_PUBLICATION_LAG_MINUTES must be an integer") from exc
    if not 1 <= value <= 360:
        raise ValueError("MAX_PUBLICATION_LAG_MINUTES must be between 1 and 360")
    return value


def _recover_expired_before_exact_manual_prepare(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    mode: str,
    expected_publication_id: str | None,
    recover_stale_predecessors: bool = False,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Apply bounded stale predecessors only under an explicit exact-manual opt-in.

    The caller persists this mutation only if the requested strict-next dispatch
    is successfully prepared, so a wrong or premature publication_id cannot
    advance durable state.
    """

    if not recover_stale_predecessors:
        return ()
    if mode != "manual" or expected_publication_id is None:
        raise ValueError("stale predecessor recovery requires exact manual prepare with publication_id")
    max_lag_minutes = _configured_max_publication_lag_minutes()
    if max_lag_minutes is None:
        raise ValueError("stale predecessor recovery requires MAX_PUBLICATION_LAG_MINUTES")
    return skip_expired_pending_by_freshness(
        release,
        ledger,
        now=now,
        max_lag_minutes=max_lag_minutes,
    )


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (TelegramApiError, ValueError)):
        return " ".join(str(exc).split())[:1000]
    return f"unexpected provider runtime error: {type(exc).__name__}"


def _provider_effect(exc: TelegramApiError) -> GenericSendProviderEffect:
    effect = exc.provider_effect
    if effect in {"not_dispatched", "confirmed_absent", "may_exist", "verified"}:
        return cast(GenericSendProviderEffect, effect)
    return "may_exist"


def _failure_outcome(
    envelope: GenericDispatchEnvelope,
    *,
    effect: GenericSendProviderEffect,
    retryable: bool,
    error: str,
) -> GenericProviderOutcome:
    return GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        provider_effect=effect,
        retryable=retryable,
        error=error,
        receipt=None,
    )


def _send_exact_payload(
    profile: TelegramChannelProfile,
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    *,
    now: datetime | None = None,
) -> GenericProviderOutcome:
    try:
        _require_runtime_profile(profile, release)
        _require_release_target(release, envelope.target)
        item = verify_dispatch_against_release(release, envelope)
        verify_persisted_intent(release, ledger, envelope)
        token = _token(profile)
        max_lag_minutes = _configured_max_publication_lag_minutes()
        if max_lag_minutes is not None:
            decision = publication_freshness(
                release,
                envelope.publication_id,
                now=now or datetime.now(tz=UTC),
                max_lag_minutes=max_lag_minutes,
            )
            if not decision.eligible:
                return _failure_outcome(
                    envelope,
                    effect="confirmed_absent",
                    retryable=True,
                    error=f"publication freshness gate closed before provider mutation: {decision.reason}",
                )
        if isinstance(item.payload, GenericMessagePayload):
            receipt = send_message_once(profile, envelope.target, item.payload, token=token, now=now)
        elif isinstance(item.payload, GenericPollPayload):
            receipt = send_poll_once(profile, envelope.target, item.payload, token=token, now=now)
        else:
            raise ValueError("unsupported generic Telegram provider payload")
    except TelegramApiError as exc:
        effect = _provider_effect(exc)
        retryable = exc.retryable if effect in {"not_dispatched", "confirmed_absent"} else False
        return _failure_outcome(
            envelope,
            effect=effect,
            retryable=retryable,
            error=_safe_error(exc),
        )
    except ValueError as exc:
        return _failure_outcome(
            envelope,
            effect="not_dispatched",
            retryable=True,
            error=_safe_error(exc),
        )
    except Exception as exc:
        return _failure_outcome(
            envelope,
            effect="may_exist",
            retryable=False,
            error=_safe_error(exc),
        )

    return GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        provider_effect="verified",
        retryable=False,
        error=None,
        receipt=receipt,
    )


def main() -> int:
    args = parser().parse_args()

    if args.command == "initialize-ledger":
        release = load_release(args.release)
        expected = f"INITIALIZE:{release.digest}"
        if args.confirm != expected:
            raise ValueError("ledger initialization confirmation does not match exact release digest")
        if not release.release_authorized:
            raise ValueError("publication ledger requires an authorized immutable release")
        if args.output.exists():
            raise ValueError(f"refusing to overwrite existing Telegram ledger: {args.output}")
        ledger = initialize_ledger(release)
        save_ledger(args.output, ledger)
        print(
            json.dumps(
                {
                    "initialized": True,
                    "release_id": release.release_id,
                    "release_digest": release.digest,
                    "entries": len(ledger.entries),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "skip-expired":
        release = load_release(args.release)
        if not release.release_authorized:
            raise ValueError("stale-publication skipping requires an authorized immutable release")
        ledger = load_ledger(args.ledger, release)
        max_lag_minutes = _configured_max_publication_lag_minutes()
        if max_lag_minutes is None:
            skipped = skip_expired_pending(release, ledger)
        else:
            skipped = skip_expired_pending_by_freshness(
                release,
                ledger,
                max_lag_minutes=max_lag_minutes,
            )
        if skipped:
            save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "skipped": list(skipped),
                    "count": len(skipped),
                    "release_digest": release.digest,
                    "ledger_changed": bool(skipped),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "validate-ledger":
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        counts: dict[str, int] = {}
        for entry in ledger.entries.values():
            counts[entry.state] = counts.get(entry.state, 0) + 1
        print(json.dumps({"valid": True, "states": counts, "release_digest": release.digest}, ensure_ascii=False))
        return 0

    if args.command == "prepare":
        profile = load_channel_profile(args.profile)
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        recovered = _recover_expired_before_exact_manual_prepare(
            release,
            ledger,
            mode=args.mode,
            expected_publication_id=args.publication_id,
            recover_stale_predecessors=args.recover_stale_predecessors,
        )
        target = _load_model(args.target_proof, GenericTargetProof)
        prepared = prepare_next(
            profile,
            release,
            ledger,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            github_sha=args.github_sha,
            github_workflow_sha=args.github_workflow_sha,
            mode=args.mode,
            target=target,
            expected_publication_id=args.publication_id,
        )
        if prepared.envelope is None:
            print(json.dumps({"prepared": False, "reason": prepared.reason}, ensure_ascii=False))
            return 3
        save_ledger(args.ledger, ledger)
        _write_model(args.envelope_output, prepared.envelope)
        print(
            json.dumps(
                {
                    "prepared": True,
                    "publication_id": prepared.envelope.publication_id,
                    "intent_id": prepared.envelope.intent_id,
                    "provider_payload_sha256": prepared.envelope.provider_payload_sha256,
                    "recovered_expired": list(recovered),
                    "reason": prepared.reason,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "verify-intent":
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        entry = verify_persisted_intent(release, ledger, envelope)
        print(
            json.dumps(
                {
                    "verified": True,
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                    "intent_id": entry.intent_id,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "send-once":
        profile = load_channel_profile(args.profile)
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        outcome = _send_exact_payload(profile, release, ledger, envelope)
        _write_model(args.outcome_output, outcome)
        print(
            json.dumps(
                {
                    "provider_effect": outcome.provider_effect,
                    "publication_id": outcome.publication_id,
                    "retryable": outcome.retryable,
                    "message_url": outcome.receipt.message_url if outcome.receipt else None,
                    "outcome": str(args.outcome_output),
                },
                ensure_ascii=False,
            )
        )
        return 0 if outcome.provider_effect == "verified" else 4

    if args.command == "apply-outcome":
        release = load_release(args.release)
        ledger = load_ledger(args.ledger, release)
        envelope = _load_model(args.envelope, GenericDispatchEnvelope)
        outcome = _load_model(args.outcome, GenericProviderOutcome)
        entry = apply_provider_outcome(ledger, envelope, outcome)
        save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "applied": True,
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                    "message_url": entry.message_url,
                },
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
