from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from video_channel_manager.telegram_publisher import (
    TelegramApiError,
    dispatch_prepared,
    load_dispatch,
    load_or_initialize_ledger,
    load_queue,
    load_target_proof,
    preflight_target,
    prepare_next,
    require_execution_enabled,
    resolve_entry,
    save_ledger,
    save_model,
    verify_persisted_intent,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded @lordchrist Telegram queue runner")
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    sub = root.add_subparsers(dest="command", required=True)

    sub.add_parser("validate")

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    preflight.add_argument("--expected-chat-id", type=int, required=True)
    preflight.add_argument("--expected-bot-username", required=True)
    preflight.add_argument("--output", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--target-proof", type=Path, required=True)
    prepare.add_argument("--dispatch", type=Path, required=True)

    verify = sub.add_parser("verify-intent")
    verify.add_argument("--dispatch", type=Path, required=True)

    send = sub.add_parser("send")
    send.add_argument("--dispatch", type=Path, required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("--mode", choices=("manual", "scheduled"), default="manual")

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--publication-id", required=True)
    resolve.add_argument("--resolution", choices=("confirmed_published", "confirmed_absent", "skip"), required=True)
    resolve.add_argument("--evidence-note", required=True)
    resolve.add_argument("--resolved-by", required=True)
    resolve.add_argument("--message-id", type=int)
    resolve.add_argument("--expected-chat-id", type=int)
    return root


def _token() -> str:
    token = os.environ.get("LORDCHRIST_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("missing LORDCHRIST_TELEGRAM_BOT_TOKEN")
    return token


def main() -> int:
    args = parser().parse_args()
    queue = load_queue(args.queue)
    ledger = load_or_initialize_ledger(args.ledger, queue)

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "valid": True,
                    "count": len(queue.posts),
                    "queue_digest": queue.digest,
                    "ledger_entries": len(ledger.entries),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "preview":
        # Preview is local-only. The deep copy prevents mutation of the state
        # branch ledger while still exercising exact strict-order selection.
        from video_channel_manager.telegram_publisher import TargetProof, utc_now

        synthetic = TargetProof(
            schema_name="video-channel-manager.telegram-target-proof",
            schema_version=1,
            bot_id=1,
            bot_username="preview_bot",
            chat_id=-1000000000000,
            chat_username="lordchrist",
            chat_title="preview",
            member_status="administrator",
            can_post_messages=True,
            checked_at_utc=utc_now(),
        )
        prepared = prepare_next(
            queue,
            ledger.model_copy(deep=True),
            run_id="preview",
            mode=args.mode,
            target=synthetic,
        )
        print(
            json.dumps(
                {
                    "queue_digest": queue.digest,
                    "reason": prepared.reason,
                    "post": prepared.envelope.model_dump(mode="json") if prepared.envelope else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "preflight":
        require_execution_enabled(queue_digest=queue.digest, mode=args.mode)
        try:
            proof = preflight_target(
                token=_token(),
                expected_chat_id=args.expected_chat_id,
                expected_bot_username=args.expected_bot_username,
            )
        except TelegramApiError as exc:
            print(json.dumps({"preflight": False, "error": str(exc)}, ensure_ascii=False))
            return 4
        save_model(args.output, proof)
        print(
            json.dumps(
                {
                    "preflight": True,
                    "bot_id": proof.bot_id,
                    "bot_username": proof.bot_username,
                    "chat_id": proof.chat_id,
                    "chat_username": proof.chat_username,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "prepare":
        target = load_target_proof(args.target_proof)
        prepared = prepare_next(queue, ledger, run_id=args.run_id, mode=args.mode, target=target)
        if prepared.envelope is None:
            print(json.dumps({"prepared": False, "reason": prepared.reason}, ensure_ascii=False))
            if prepared.reason.startswith("strict queue blocked") or "manual canary" in prepared.reason:
                return 5
            return 3
        save_model(args.dispatch, prepared.envelope)
        save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "prepared": True,
                    "publication_id": prepared.envelope.publication_id,
                    "sequence": prepared.envelope.sequence,
                    "intent_id": prepared.envelope.intent_id,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "verify-intent":
        envelope = load_dispatch(args.dispatch)
        entry = verify_persisted_intent(queue, ledger, envelope)
        print(
            json.dumps(
                {
                    "verified": True,
                    "publication_id": entry.publication_id,
                    "intent_id": entry.intent_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "send":
        envelope = load_dispatch(args.dispatch)
        require_execution_enabled(queue_digest=queue.digest, mode=envelope.dispatch_mode)
        entry = dispatch_prepared(queue, envelope, ledger, token=_token())
        save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                    "message_id": entry.message_id,
                    "error": entry.last_error,
                },
                ensure_ascii=False,
            )
        )
        return 0 if entry.state == "published" else 4

    if args.command == "resolve":
        entry = resolve_entry(
            ledger,
            args.publication_id,
            resolution=args.resolution,
            evidence_note=args.evidence_note,
            resolved_by=args.resolved_by,
            message_id=args.message_id,
            expected_chat_id=args.expected_chat_id,
        )
        save_ledger(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "publication_id": entry.publication_id,
                    "state": entry.state,
                    "provider_effect": entry.provider_effect,
                },
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
