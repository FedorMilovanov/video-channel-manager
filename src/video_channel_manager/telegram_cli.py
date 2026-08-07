from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from video_channel_manager.telegram_publisher import (
    TelegramApiError,
    dispatch_prepared,
    initialize_ledger_file,
    load_dispatch,
    load_ledger,
    load_queue,
    load_target_proof,
    preflight_target,
    prepare_next,
    preview_next,
    require_execution_enabled,
    require_preflight_config,
    resolve_entry,
    save_ledger,
    save_model,
    verify_persisted_intent,
)

INITIALIZE_CONFIRMATION = "INITIALIZE_NEW_LORDCHRIST_LEDGER"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded @lordchrist Telegram queue runner")
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    sub = root.add_subparsers(dest="command", required=True)

    sub.add_parser("validate")

    initialize = sub.add_parser("initialize-ledger")
    initialize.add_argument("--confirm", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    preflight.add_argument("--expected-chat-id", type=int, required=True)
    preflight.add_argument("--expected-bot-id", type=int, required=True)
    preflight.add_argument("--expected-bot-username", required=True)
    preflight.add_argument("--output", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--mode", choices=("manual", "scheduled"), required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--github-sha", required=True)
    prepare.add_argument("--github-workflow-sha", required=True)
    prepare.add_argument("--expected-publication-id")
    prepare.add_argument("--target-proof", type=Path, required=True)
    prepare.add_argument("--dispatch", type=Path, required=True)

    verify = sub.add_parser("verify-intent")
    verify.add_argument("--dispatch", type=Path, required=True)

    send = sub.add_parser("send")
    send.add_argument("--dispatch", type=Path, required=True)

    sub.add_parser("preview")

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

    if args.command == "initialize-ledger":
        if args.confirm != INITIALIZE_CONFIRMATION:
            raise RuntimeError(f"ledger initialization requires exact confirmation {INITIALIZE_CONFIRMATION}")
        ledger = initialize_ledger_file(args.ledger, queue)
        print(
            json.dumps(
                {
                    "initialized": True,
                    "queue_digest": ledger.queue_digest,
                    "ledger_entries": len(ledger.entries),
                },
                ensure_ascii=False,
            )
        )
        return 0

    ledger = load_ledger(args.ledger, queue)

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
        prepared = preview_next(queue, ledger)
        post = prepared.post
        print(
            json.dumps(
                {
                    "queue_digest": queue.digest,
                    "reason": prepared.reason,
                    "post": (
                        {
                            "publication_id": post.publication_id,
                            "sequence": post.sequence,
                            "payload_sha256": post.payload_sha256,
                            "text": post.text,
                        }
                        if post is not None
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "preflight":
        require_preflight_config(queue_digest=queue.digest)
        try:
            proof = preflight_target(
                token=_token(),
                expected_chat_id=args.expected_chat_id,
                expected_bot_id=args.expected_bot_id,
                expected_bot_username=args.expected_bot_username,
            )
        except TelegramApiError as exc:
            print(
                json.dumps(
                    {
                        "preflight": False,
                        "error": str(exc),
                        "retryable": exc.retryable,
                        "retry_after_seconds": exc.retry_after_seconds,
                    },
                    ensure_ascii=False,
                )
            )
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
                    "chat_type": proof.chat_type,
                    "can_post_messages": proof.can_post_messages,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "prepare":
        target = load_target_proof(args.target_proof)
        prepared = prepare_next(
            queue,
            ledger,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            github_sha=args.github_sha,
            github_workflow_sha=args.github_workflow_sha,
            mode=args.mode,
            target=target,
            expected_publication_id=args.expected_publication_id,
        )
        if prepared.envelope is None:
            print(json.dumps({"prepared": False, "reason": prepared.reason}, ensure_ascii=False))
            blocking_markers = (
                "strict queue blocked",
                "manual canary",
                "manual publication_id mismatch",
                "manual execution requires",
            )
            if any(marker in prepared.reason for marker in blocking_markers):
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
                    "workflow_run_id": prepared.envelope.workflow_run_id,
                    "workflow_run_attempt": prepared.envelope.workflow_run_attempt,
                    "github_sha": prepared.envelope.github_sha,
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
                    "workflow_run_id": entry.workflow_run_id,
                    "workflow_run_attempt": entry.workflow_run_attempt,
                    "github_sha": entry.github_sha,
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
                    "message_url": entry.message_url,
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
                    "message_id": entry.message_id,
                    "message_url": entry.message_url,
                },
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
