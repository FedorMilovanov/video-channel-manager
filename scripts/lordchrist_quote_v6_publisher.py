"""One-writer @lordchrist v6: frozen owner-requested release, exact ledger, no blind replay.

The source-v6 candidate and editorial/rights research records remain unchanged.
No v4 queue or state is eligible for dispatch here.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.lordchrist_cross_track_effect_guard import (
    require_no_cross_track_unresolved_effects,
)
from video_channel_manager.telegram_presentation import _RenderBuilder, formatting_entities_match
from video_channel_manager.telegram_state import (
    initialize_ledger,
    load_dispatch,
    load_ledger,
    prepare_next,
    save_ledger,
    save_model,
    strict_next_post,
    utc_now,
    verify_persisted_intent,
)
from video_channel_manager.telegram_transport import (
    TelegramApiError,
    _api_call,
    preflight_target,
)

from scripts.lordchrist_quote_v6_semantic_gate import SemanticApprovalHold, require_semantic_approval

from scripts.lordchrist_quote_v6_native_readonly import (
    SOURCE_PATH,
    QuoteV6NativeQueue,
    QuoteV6NativePost,
    build_quote_v6_native_queue,
    build_restyled_quote_v6_native_queue,
)

RELEASE_PATH = Path("content/telegram/lordchrist/quote-v6-owner-release.json")
PROFILE_PATH = Path("content/telegram/channels/lordchrist.json")
STATE_PATH = Path(".state/lordchrist")
STATE_LEDGER = Path("content/telegram/lordchrist/quote-v6-publication-ledger.json")
LEGACY_QUEUE = Path("content/telegram/lordchrist/verified-30-posts.json")
LEGACY_LEDGER = Path("content/telegram/lordchrist/publication-ledger.json")
EXPECTED_DIGEST = "sha256:13cac1b9630072b7929d8d96244153284779dc41961469d3f106e289df94eb0d"
EXPECTED_CHAT_ID = -1001295216957
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
FIRST_ID = "lordchrist-ryle-religion-cost"
MOSCOW = ZoneInfo("Europe/Moscow")


def release_and_queue(root: Path) -> QuoteV6NativeQueue:
    release = json.loads((root / RELEASE_PATH).read_text(encoding="utf-8"))
    queue = build_restyled_quote_v6_native_queue(root)
    required = {
        "schema_name": "video-channel-manager.lordchrist-v6-owner-requested-release",
        "schema_version": 1,
        "release_id": "lordchrist-quote-v6-20261106",
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "candidate_digest": EXPECTED_DIGEST,
        "owner_release_requested_on": "2026-11-06",
        "writes_authorized_by_owner_request": True,
        "quote_v4_replay_authorized": False,
        "retired_v4_workflow_must_remain_disabled": True,
        "first_canary_publication_id": FIRST_ID,
        "scheduled_start_moscow_date": "2026-11-08",
        "schedule_time_moscow": "10:00",
        "max_posts_per_run": 1,
        "new_state_ledger_relative_path": STATE_LEDGER.as_posix(),
    }
    if any(release.get(k) != v for k, v in required.items()) or queue.digest != EXPECTED_DIGEST:
        raise ValueError("v6 owner release and exact frozen 30-card candidate differ")
    # The v4 job and its timers must remain disabled; this checks production
    # code instead of treating the old hold as a revocable approval switch.
    workflow = (root / ".github/workflows/lordchrist-telegram-poster.yml").read_text(encoding="utf-8")
    old_job = workflow.split("\n  publish-next:\n", 1)[1].split("\n    runs-on:", 1)[0]
    if "false &&" not in old_job or '- cron: "0 7 * * *"' in workflow or '- cron: "0 18 * * 2,5,0"' in workflow:
        raise ValueError("quote v4 live dispatch route is not retired")
    if queue.release_state != "provider_inert_candidate" or queue.provider_writes_authorized:
        raise ValueError("frozen source candidate was improperly converted to a release")
    return queue


def guard_cross_track(root: Path) -> None:
    # After the failed v4 cutover, the active code queue is v4 but the durable
    # 30-published ledger still belongs to the exact archived predecessor.
    # Reuse the existing channel-wide barrier with its verified predecessor
    # bindings, instead of pretending the retired v4 queue owns that ledger.
    predecessor = root / "content/telegram/lordchrist/archived-old-queues/verified-30-posts.json"
    ledger = root / STATE_PATH / LEGACY_LEDGER
    previous_queue = os.environ.get("LORDCHRIST_PREDECESSOR_QUEUE_PATH")
    previous_ledger = os.environ.get("LORDCHRIST_PREDECESSOR_LEDGER_PATH")
    os.environ["LORDCHRIST_PREDECESSOR_QUEUE_PATH"] = str(predecessor)
    os.environ["LORDCHRIST_PREDECESSOR_LEDGER_PATH"] = str(ledger)
    try:
        require_no_cross_track_unresolved_effects(
            profile_path=root / PROFILE_PATH,
            legacy_queue_path=root / LEGACY_QUEUE,
            legacy_ledger_path=ledger,
            research_ledger_path=root / STATE_PATH / "content/telegram/lordchrist/research-v2/publication-ledger.json",
        )
    finally:
        for key, previous in (
            ("LORDCHRIST_PREDECESSOR_QUEUE_PATH", previous_queue),
            ("LORDCHRIST_PREDECESSOR_LEDGER_PATH", previous_ledger),
        ):
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def target_from_provider():
    token = os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"].strip()
    if not token:
        raise RuntimeError("Telegram bot token not configured")
    proof = preflight_target(
        token=token,
        expected_chat_id=EXPECTED_CHAT_ID,
        expected_bot_id=EXPECTED_BOT_ID,
        expected_bot_username=EXPECTED_BOT_USERNAME,
    )
    return proof, token


def validate_schedule(mode: str, current: datetime) -> None:
    if mode != "scheduled":
        return
    local = current.astimezone(MOSCOW)
    if local.date().isoformat() < "2026-11-08":
        raise ValueError("scheduled v6 posts cannot begin before 2026-11-08 in Moscow")
    start = datetime.combine(local.date(), time(10), tzinfo=MOSCOW)
    # GitHub scheduled events are best-effort: the 2026-11-08 run arrived at
    # 17:03 Moscow, beyond the former 3-hour lease. Accept one late run on
    # the same Moscow date, but never an overnight catch-up or a re-run.
    # prepare_next independently enforces one verified "morning" slot/day.
    if local < start or local >= start + timedelta(minutes=660):
        raise ValueError("scheduled v6 slot is not due or is too late; no backfill")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise ValueError("scheduled re-run forbidden")


def make_rendered(post: QuoteV6NativePost) -> tuple[str, str, tuple]:
    """Re-derive Telegram entities from reviewed HTML, never from guessed prose."""
    import html
    import re

    builder = _RenderBuilder()
    if post.presentation_style == "inline_emphasis":
        body, separator, _remainder = post.html_text.rpartition("\n<i>")
        if not separator:
            raise ValueError("reviewed inline body and attribution are not separable")
        for piece in re.split(r"(<b>.*?</b>|<i>.*?</i>)", body, flags=re.DOTALL):
            if not piece:
                continue
            if piece.startswith("<b>") and piece.endswith("</b>"):
                builder.append_styled(html.unescape(piece[3:-4]), "bold")
            elif piece.startswith("<i>") and piece.endswith("</i>"):
                builder.append_styled(html.unescape(piece[3:-4]), "italic")
            else:
                builder.append(html.unescape(piece))
    else:
        builder.append_styled(post.quote_text, "blockquote")
    builder.append("\n")
    builder.append_styled(post.attribution_line, "italic")
    builder.append("\n\n")
    builder.append(post.hashtags)
    if builder.html_text != post.html_text or builder.text != post.text:
        raise ValueError("source-bound v6 formatting differs from canonical native rendering")
    return builder.html_text, builder.text, builder.entities


def init(root: Path) -> None:
    queue = release_and_queue(root)
    guard_cross_track(root)
    path = root / STATE_PATH / STATE_LEDGER
    if path.exists():
        existing = load_ledger(path, queue)
        print(
            json.dumps(
                {"already_initialized": True, "entries": len(existing.entries), "queue_digest": existing.queue_digest}
            )
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    save_ledger(path, initialize_ledger(queue))
    print(json.dumps({"initialized": True, "entries": 30, "queue_digest": queue.digest}))


def prepare(root: Path, *, mode: str, expected_id: str | None) -> int:
    queue = release_and_queue(root)
    path = root / STATE_PATH / STATE_LEDGER
    ledger = load_ledger(path, queue)
    guard_cross_track(root)
    now = utc_now()
    validate_schedule(mode, now)
    post, reason = strict_next_post(queue, ledger)
    if post is None:
        print(json.dumps({"prepared": False, "reason": reason}))
        return 3
    if mode == "manual" and expected_id != FIRST_ID:
        raise ValueError("only the exact first manual canary may be dispatched explicitly")
    if mode == "manual" and expected_id != post.publication_id:
        raise ValueError("manual canary is not the first pending v6 publication")
    if mode == "scheduled" and expected_id is not None:
        raise ValueError("scheduled dispatch must not carry an explicit publication ID")
    # Expected editorial HOLD is a safe no-op, not a failed provider attempt.
    # No target lookup, intent or protected-state write occurs on this path.
    try:
        require_semantic_approval(root, queue, post)
    except SemanticApprovalHold as exc:
        print(json.dumps({"prepared": False, "reason": "editorial_hold", "detail": str(exc)}, ensure_ascii=False))
        return 3
    proof, _token = target_from_provider()
    result = prepare_next(
        queue,
        ledger,
        run_id=os.environ["GITHUB_RUN_ID"],
        run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        github_sha=os.environ["GITHUB_SHA"],
        github_workflow_sha=os.environ["GITHUB_WORKFLOW_SHA"],
        mode=mode,
        target=proof,
        expected_publication_id=expected_id,
        scheduled_slot="morning" if mode == "scheduled" else None,
        now=now,
    )
    if result.envelope is None:
        print(json.dumps({"prepared": False, "reason": result.reason}))
        return 3
    make_rendered(post)
    save_model(root / ".runtime/lordchrist-v6-dispatch.json", result.envelope)
    save_model(root / ".runtime/lordchrist-v6-target-proof.json", proof)
    save_ledger(path, ledger)
    print(json.dumps({"prepared": True, "publication_id": post.publication_id, "payload_sha256": post.payload_sha256}))
    return 0


def send(root: Path) -> int:
    queue = release_and_queue(root)
    path = root / STATE_PATH / STATE_LEDGER
    ledger = load_ledger(path, queue)
    envelope = load_dispatch(root / ".runtime/lordchrist-v6-dispatch.json")
    entry = verify_persisted_intent(queue, ledger, envelope)
    guard_cross_track(root)
    post = next(p for p in queue.posts if p.publication_id == envelope.publication_id)
    rich, plain, entities = make_rendered(post)
    if envelope.text != plain or envelope.payload_sha256 != post.payload_sha256:
        raise ValueError("persisted dispatch does not bind exact native v6 content")
    # Re-check the exact approved PR and digest before the irreversible POST.
    require_semantic_approval(root, queue, post)
    now = utc_now()
    if now - envelope.prepared_at_utc.astimezone(UTC) > timedelta(minutes=15):
        raise ValueError("prepared v6 dispatch expired before provider call")
    token = os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"].strip()
    if not token:
        raise RuntimeError("missing Telegram credential")
    # Never retry sendMessage. If outcome is ambiguous, leave a blocking may_exist state.
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(connect=15, read=45, write=30, pool=15), trust_env=False) as client:
            msg = _api_call(
                client,
                api_base="https://api.telegram.org",
                token=token,
                method="sendMessage",
                mutation=True,
                payload={
                    "chat_id": envelope.target.chat_id,
                    "text": rich,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                },
            )
        if not isinstance(msg, dict) or not isinstance(msg.get("chat"), dict):
            raise TelegramApiError("provider message identity missing", provider_effect="may_exist")
        chat = msg["chat"]
        if (
            chat.get("id") != EXPECTED_CHAT_ID
            or str(chat.get("username", "")).casefold() != "lordchrist"
            or chat.get("type") != "channel"
        ):
            raise TelegramApiError("provider target differs from exact @lordchrist", provider_effect="may_exist")
        if msg.get("text") != plain or not formatting_entities_match(entities, msg.get("entities")):
            raise TelegramApiError("provider text or formatting differs", provider_effect="may_exist")
        mid = msg.get("message_id")
        if not isinstance(mid, int) or mid < 1:
            raise TelegramApiError("provider message id invalid", provider_effect="may_exist")
        entry.state = "published"
        entry.provider_effect = "verified"
        entry.message_id = mid
        entry.message_url = f"https://t.me/lordchrist/{mid}"
        entry.published_at_utc = utc_now()
        entry.last_error = None
    except TelegramApiError as exc:
        entry.last_error = str(exc)[:800]
        if exc.provider_effect == "may_exist":
            entry.state = "unknown"
            entry.provider_effect = "may_exist"
        else:
            entry.state = "failed"
            entry.provider_effect = exc.provider_effect
            entry.intent_id = None
    except Exception as exc:
        # No duplicate after uncertain transport or provider parsing.
        entry.state = "unknown"
        entry.provider_effect = "may_exist"
        entry.last_error = f"unexpected provider outcome: {type(exc).__name__}"
    save_ledger(path, ledger)
    outcome = {
        "publication_id": post.publication_id,
        "queue_digest": queue.digest,
        "state": entry.state,
        "provider_effect": entry.provider_effect,
        "message_id": entry.message_id,
        "message_url": entry.message_url,
        "intent_id": envelope.intent_id,
        "run_id": envelope.workflow_run_id,
        "attempt": envelope.workflow_run_attempt,
    }
    (root / ".runtime").mkdir(exist_ok=True)
    (root / ".runtime/lordchrist-v6-outcome.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(outcome, ensure_ascii=False))
    return 0 if entry.state == "published" else 6


def migrate_pending_restyle(root: Path) -> None:
    """One-time, exact 11-published/19-pending ledger rebinding; sends nothing.

    The existing state is loaded with the OLD source digest. Published entries
    are immutable, and any intervening publication/intent fails closed.
    """
    from scripts.lordchrist_quote_v6_restyle import build_restyle_preview

    old_queue = build_quote_v6_native_queue(root / SOURCE_PATH)
    proposed = build_restyle_preview(root)
    new_queue = release_and_queue(root)
    if (
        proposed["original_queue_digest"] != old_queue.digest
        or proposed["prospective_queue_digest"] != new_queue.digest
    ):
        raise ValueError("restyle source and release identities differ")
    path = root / STATE_PATH / STATE_LEDGER
    old_ledger = load_ledger(path, old_queue)
    # The manifest holds the identifiers, not an ordinal prefix: source #13
    # has published while #9 and #12 remain pending due to author rotation.
    published_ids = {p["publication_id"] for p in proposed["published_immutable"]}
    pending_ids = {p["publication_id"] for p in proposed["items"]}
    if set(old_ledger.entries) != published_ids | pending_ids:
        raise ValueError("migrate requires exact complete original ledger coverage")
    old_by_id = {p.publication_id: p for p in old_queue.posts}
    new_by_id = {p.publication_id: p for p in new_queue.posts}
    for publication_id, entry in old_ledger.entries.items():
        if publication_id in published_ids:
            if (
                entry.state != "published"
                or entry.provider_effect != "verified"
                or not entry.message_id
                or new_by_id[publication_id].payload_sha256 != old_by_id[publication_id].payload_sha256
            ):
                raise ValueError("published history has advanced or is not immutable: " + publication_id)
        else:
            if (
                entry.state != "pending"
                or entry.provider_effect != "impossible"
                or entry.intent_id is not None
                or entry.workflow_run_id is not None
                or entry.message_id is not None
                or new_by_id[publication_id].payload_sha256 == old_by_id[publication_id].payload_sha256
            ):
                raise ValueError("pending card is not safely rebindable: " + publication_id)
    guard_cross_track(root)
    for publication_id in pending_ids:
        old_ledger.entries[publication_id].payload_sha256 = new_by_id[publication_id].payload_sha256
    old_ledger.queue_digest = new_queue.digest
    save_ledger(path, old_ledger)
    verified = load_ledger(path, new_queue)
    if sum(x.state == "published" for x in verified.entries.values()) != 11:
        raise ValueError("rebound ledger unexpectedly changed publication history")
    print(
        json.dumps(
            {
                "migrated": True,
                "new_queue_digest": new_queue.digest,
                "published_untouched": len(published_ids),
                "pending_rebound": len(pending_ids),
                "provider_effect": "impossible",
            },
            ensure_ascii=False,
        )
    )


def migrate_editorial_revision(root: Path) -> None:
    """Rebind only pending v1 payloads; preserve published records; no API sends."""
    from scripts.lordchrist_quote_v6_restyle import V1_MANIFEST_PATH

    previous_queue = build_restyled_quote_v6_native_queue(root, manifest_path=V1_MANIFEST_PATH)
    new_queue = release_and_queue(root)
    if previous_queue.digest != "sha256:62a15d4b19057509fb38023847ccbdbde319f9d428a9d6463074ae11b3940b03":
        raise ValueError("editorial v2 migration lost the exact live v1 baseline")
    path = root / STATE_PATH / STATE_LEDGER
    ledger = load_ledger(path, previous_queue)
    before = {p.publication_id: p for p in previous_queue.posts}
    after = {p.publication_id: p for p in new_queue.posts}
    if before.keys() != after.keys() or len(before) != 30:
        raise ValueError("editorial migration must preserve all 30 publication IDs")
    changed = []
    published = 0
    for publication_id, entry in ledger.entries.items():
        old_post, new_post = before[publication_id], after[publication_id]
        if entry.state == "published":
            if (
                entry.provider_effect != "verified"
                or not entry.message_id
                or entry.published_at_utc is None
                or new_post.payload_sha256 != old_post.payload_sha256
            ):
                raise ValueError("protected published history changed: " + publication_id)
            published += 1
            continue
        if (
            entry.state != "pending"
            or entry.provider_effect != "impossible"
            or entry.intent_id is not None
            or entry.workflow_run_id is not None
            or entry.message_id is not None
            or entry.last_error is not None
        ):
            raise ValueError("pending editorial migration is not safe: " + publication_id)
        if old_post.payload_sha256 != new_post.payload_sha256:
            changed.append(publication_id)
    if published != 11 or len(ledger.entries) - published != 19 or not changed:
        raise ValueError("editorial v2 migration requires exactly 11 verified and 19 pending with changes")
    guard_cross_track(root)
    for publication_id in changed:
        ledger.entries[publication_id].payload_sha256 = after[publication_id].payload_sha256
    ledger.queue_digest = new_queue.digest
    save_ledger(path, ledger)
    verified = load_ledger(path, new_queue)
    if sum(e.state == "published" for e in verified.entries.values()) != 11:
        raise ValueError("editorial migration disturbed published history")
    print(
        json.dumps(
            {
                "migrated": True,
                "kind": "editorial-v2",
                "published_unchanged": 11,
                "pending_preserved": 19,
                "pending_payload_rebound": len(changed),
                "new_digest": new_queue.digest,
                "provider_send": False,
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "init", "migrate", "migrate-editorial", "prepare", "send"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=("manual", "scheduled"), default="scheduled")
    parser.add_argument("--publication-id")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command in {"init", "migrate", "migrate-editorial"}:
        raise ValueError(
            "Historical v6 ledger initialization/migrations are retired on the live 12/18+ ledger. "
            "No state mutation: prepare a separately reviewed exact pending-only successor release."
        )
    if args.command == "validate":
        queue = release_and_queue(root)
        for post in queue.posts:
            make_rendered(post)
        print(json.dumps({"count": len(queue.posts), "digest": queue.digest, "release_requested": True}))
        return 0
    if args.command == "init":
        init(root)
        return 0
    if args.command == "migrate":
        migrate_pending_restyle(root)
        return 0
    if args.command == "migrate-editorial":
        migrate_editorial_revision(root)
        return 0
    if args.command == "prepare":
        return prepare(root, mode=args.mode, expected_id=args.publication_id)
    return send(root)


if __name__ == "__main__":
    raise SystemExit(main())
