"""One scheduled replacement only for each owner-deleted Charnock Telegram post.

This does not create/edit Telegraph pages, reset the original receipt or offer
a manual live bypass. The immutable incident manifest binds each calendar slot,
reviewed article bytes, original removed message and verified article URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_BINDING_PATH,
    DEFAULT_PROFILE_PATH,
    DEFAULT_QUEUE_PATH,
    DEFAULT_TELEGRAM_API_BASE,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    load_telegraph_queue,
    render_channel_post,
    save_ledger,
)
from video_channel_manager.lordchrist_telegraph_staged import _ledger, _require_execution_context
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

MOSCOW = ZoneInfo("Europe/Moscow")
MANIFEST = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json")
# Historical 2026-11 manifest is immutable. This separate SHA-pinned v2 binding
# authorizes only the already-published #10 QC article+cover URL on 24 November.
# No source/receipt/date from the legacy manifest is overwritten on disk.
V2_BINDING = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-10-source-media-binding-v2-20261123.json")
V2_BINDING_GIT_BLOB = "7708abcac315acd32794dfdc52e4676278a85c81"
LEGACY_MANIFEST_GIT_BLOB = "9bbacf42933da605ca8f47a4708d23dd18971a8b"
V2_PUBLICATION_ID = "lordchrist-telegraph-charnock-10"
LIVE_WINDOW_HOUR = (12, 13)
# Article 13's public page was corrected in place on 2026-11-21 (q-3, q-9,
# q-11, q-12, q-19).  The hold is now a Telegram send/reissue gate only:
# the correction itself authorizes no new channel post.
CHARNOCK_EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})
# The only manual recovery fallback: future slots in the already-approved immutable manifest.
# Missed 06-08 and editorial-HOLD 13 may NOT be dispatched.
OWNER_DISPATCH_IDS = frozenset(f"lordchrist-telegraph-charnock-{i:02d}" for i in range(9, 13))
OWNER_DISPATCH_CONFIRM = "RUN_APPROVED_CHARNOCK_SLOT_ONCE"
# Read-only backoff after the single allowed sendMessage; never retry the provider mutation.
NEW_POST_PUBLIC_READBACK_DELAYS = (0, 2, 4, 8, 16, 30, 45)


def _file_git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def approved_reissue_entry(repo_root: Path, legacy_entry: dict[str, Any]) -> dict[str, Any]:
    """Resolve exactly one versioned #10 editorial identity, never rewrite history.

    A protected main-branch review must approve this *separate* binding file,
    pinned by its Git blob. The old schedule, deleted message and source ledger
    remain immutable; the new target source/media identity is kept distinct.
    Other Charnock articles retain their original strict fail-closed checks.
    """
    if legacy_entry.get("publication_id") != V2_PUBLICATION_ID:
        return legacy_entry

    old_raw = (repo_root / MANIFEST).read_bytes()
    if _file_git_blob_sha(old_raw) != LEGACY_MANIFEST_GIT_BLOB:
        raise RuntimeError("Historical Charnock release authority drifted")
    bound_raw = (repo_root / V2_BINDING).read_bytes()
    if _file_git_blob_sha(bound_raw) != V2_BINDING_GIT_BLOB:
        raise RuntimeError("Unapproved Charnock v2 source/media binding bytes")
    approved = json.loads(bound_raw)
    if (
        not isinstance(approved, dict)
        or approved.get("schema_name") != "video-channel-manager.lordchrist-charnock-reissue-source-media-binding"
        or approved.get("schema_version") != 2
        or approved.get("publication_id") != V2_PUBLICATION_ID
        or approved.get("channel") != "@lordchrist"
        or approved.get("legacy_manifest_git_blob_sha") != LEGACY_MANIFEST_GIT_BLOB
        or approved.get("legacy_article_git_blob_sha") != legacy_entry["article_git_blob_sha"]
        or approved.get("original_article_sha256") != legacy_entry["source_article_sha256"]
        or approved.get("original_deleted_telegram_message_id") != legacy_entry["deleted_telegram_message_id"]
        or approved.get("existing_telegraph_url") != legacy_entry["verified_telegraph_url"]
        or approved.get("scheduled_on_moscow") != legacy_entry["scheduled_on_moscow"]
        or approved.get("reviewed_node_count") != 97
    ):
        raise RuntimeError("Unreviewed Charnock v2 binding or historic identity drift")
    for key in (
        "reviewed_article_git_blob_sha",
        "reviewed_cover_git_blob_sha",
        "reviewed_media_base_revision",
        "original_github_sha",
    ):
        value = approved.get(key)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise RuntimeError("Malformed Charnock v2 source/media identity")
    tree_digest = approved.get("reviewed_normalized_tree_sha256")
    if not isinstance(tree_digest, str) or re.fullmatch(r"[0-9a-f]{64}", tree_digest) is None:
        raise RuntimeError("Malformed reviewed Charnock normalized tree digest")
    for key in ("reviewed_article_sha256", "original_article_sha256", "original_cover_sha256"):
        if not isinstance(approved.get(key), str) or re.fullmatch(r"sha256:[0-9a-f]{64}", approved[key]) is None:
            raise RuntimeError("Malformed Charnock source or cover SHA-256")
    # The exact v2 blob pin above is the authority; explicit legacy checks
    # prevent mixing the old publication identity with the new target digest.
    return {
        **legacy_entry,
        "article_git_blob_sha": approved["reviewed_article_git_blob_sha"],
        "source_article_sha256": approved["reviewed_article_sha256"],
        "historical_source_article_sha256": approved["original_article_sha256"],
        "original_github_sha": approved["original_github_sha"],
        "original_cover_sha256": approved["original_cover_sha256"],
        "reviewed_cover_git_blob_sha": approved["reviewed_cover_git_blob_sha"],
        "media_base_revision": approved["reviewed_media_base_revision"],
        "reviewed_normalized_tree_sha256": approved["reviewed_normalized_tree_sha256"],
        "reviewed_node_count": approved["reviewed_node_count"],
        "binding_git_blob_sha": V2_BINDING_GIT_BLOB,
    }


def _require_approved_recovery_trigger(args: argparse.Namespace) -> None:
    """Accept scheduled runs or *authenticated* owner-only due-slot manual backup.

    Never accept a caller-supplied clock, past/missed slot, alternate article,
    arbitrary workflow, non-main branch, or different GitHub actor. The
    GitHub-managed GITHUB_EVENT_PATH provides the dispatch inputs, not CLI args.
    Existing receipt and exact-date proof are rechecked separately.
    """
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event == "schedule":
        return
    if event != "workflow_dispatch" or os.environ.get("GITHUB_ACTOR") != "FedorMilovanov":
        raise RuntimeError("Only scheduled or authenticated owner-only dispatch may recover Charnock")
    if args.publication_id not in OWNER_DISPATCH_IDS:
        raise RuntimeError("Dispatch cannot restore missed 06-08 or editorial HOLD 13")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("Missing authenticated GitHub event payload")
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Missing or invalid GitHub dispatch payload") from exc
    inputs = payload.get("inputs") if isinstance(payload, dict) else None
    if (
        not isinstance(inputs, dict)
        or inputs.get("confirm") != OWNER_DISPATCH_CONFIRM
        or inputs.get("publication_id") != args.publication_id
    ):
        raise RuntimeError("Authenticated dispatch inputs do not bind exactly one approved article")


def scheduled_reissue_preflight_status(ledger: dict[str, Any], manifest_entry: dict[str, Any]) -> str:
    """Read-only status for redundant schedule triggers; never authorizes a send.

    An already verified replacement is terminal only when its immutable
    source and target identity still agree with the reviewed incident manifest.
    Any partial or ambiguous intent must fail closed, never auto-replay.
    """
    original = ledger.get("entries", {}).get(manifest_entry["publication_id"])
    if not isinstance(original, dict):
        raise RuntimeError("Charnock original publication receipt missing")
    receipt = original.get("scheduled_reissue")
    if receipt is None:
        return "unclaimed"
    if not isinstance(receipt, dict):
        raise RuntimeError("Malformed Charnock scheduled reissue; reconcile, do not replay")
    expected = {
        "scheduled_on_moscow": manifest_entry["scheduled_on_moscow"],
        "original_deleted_message_id": manifest_entry["deleted_telegram_message_id"],
        "source_article_sha256": manifest_entry["source_article_sha256"],
        "telegraph_url": manifest_entry["verified_telegraph_url"],
    }
    if manifest_entry.get("binding_git_blob_sha"):
        expected["binding_git_blob_sha"] = manifest_entry["binding_git_blob_sha"]
    if (
        receipt.get("state") == "verified"
        and receipt.get("provider_effect") == "verified"
        and type(receipt.get("new_message_id")) is int
        and receipt["new_message_id"] > 0
        and receipt["new_message_id"] != manifest_entry["deleted_telegram_message_id"]
        and original.get("state") == "published"
        and original.get("provider_effect") == "verified"
        and type(original.get("telegram_message_id")) is int
        and original["telegram_message_id"] == manifest_entry["deleted_telegram_message_id"]
        and original.get("telegram_chat_id") == -1001295216957
        and original.get("telegraph_url") == manifest_entry["verified_telegraph_url"]
        and original.get("article_sha256")
        == manifest_entry.get("historical_source_article_sha256", manifest_entry["source_article_sha256"])
        and all(receipt.get(key) == value for key, value in expected.items())
    ):
        return "verified"
    raise RuntimeError("Existing Charnock reissue is not terminal-verified; reconcile without resend")


def _select_due(
    args: argparse.Namespace, ledger: dict[str, Any], *, now: datetime
) -> tuple[dict[str, Any], Any, Any, dict[str, Any]]:
    local = now.astimezone(MOSCOW)
    # Only an already-sent message may be read back after 13:59, on the
    # original Moscow date. Preparing and sending remain strictly in-window.
    late_readback = args.stage == "verify" and local.hour > LIVE_WINDOW_HOUR[-1]
    if local.hour not in LIVE_WINDOW_HOUR and not late_readback:
        raise RuntimeError("Charnock release is allowed only between 12:00 and 13:59 Moscow")
    manifest = json.loads((args.repo_root / MANIFEST).read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("channel") != "@lordchrist"
        or manifest.get("timezone") != "Europe/Moscow"
        or manifest.get("release_time") != "12:00"
        or len(manifest.get("items", [])) != 8
    ):
        raise RuntimeError("Unreviewed or malformed incident reschedule manifest")
    matches = [x for x in manifest["items"] if x["scheduled_on_moscow"] == local.date().isoformat()]
    if len(matches) != 1:
        raise RuntimeError("Exactly one reviewed Charnock edition must be due today")
    entry = matches[0]
    if entry["publication_id"] != args.publication_id:
        raise RuntimeError("Requested article is not the sole due Charnock article")
    entry = approved_reissue_entry(args.repo_root, entry)
    if args.stage in ("prepare", "send") and entry["publication_id"] in CHARNOCK_EDITORIAL_HOLDS:
        raise RuntimeError(
            "Charnock 13 TELEGRAM SEND HOLD: the existing page was corrected in place "
            "2026-11-21; no send or reissue is authorized by that correction"
        )
    queue = load_telegraph_queue(args.repo_root / DEFAULT_QUEUE_PATH, args.repo_root)
    item = _find_item(queue, args.publication_id)
    if not item.is_ready or item.scheduled_on != local.date() or item.channel_post is None:
        raise RuntimeError("Actual editorial queue date/status differs from incident manifest")
    if item.article_blob != entry["article_git_blob_sha"] or item.article_path is None:
        raise RuntimeError("Latest reviewed article is not the approved immutable Git blob")
    if entry.get("reviewed_cover_git_blob_sha") and item.cover_blob != entry["reviewed_cover_git_blob_sha"]:
        raise RuntimeError("Current Charnock cover file is not the approved Git blob")
    data = (args.repo_root / item.article_path).read_bytes()
    actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if actual != entry["article_git_blob_sha"]:
        raise RuntimeError("Article file bytes changed since approval")
    original = ledger.get("entries", {}).get(args.publication_id)
    if not isinstance(original, dict):
        raise RuntimeError("Original published receipt is absent")
    if (
        original.get("state") != "published"
        or original.get("provider_effect") != "verified"
        or original.get("telegram_message_id") != entry["deleted_telegram_message_id"]
        or original.get("telegraph_url") != entry["verified_telegraph_url"]
        or original.get("article_sha256")
        != entry.get("historical_source_article_sha256", entry["source_article_sha256"])
    ):
        raise RuntimeError("Source ledger identity does not match verified source delivery")
    if late_readback:
        # The only allowed post-window effect is public GET + persistence of an
        # existing same-run 'sent' receipt. Never create/claim/send after 13:59.
        receipt = original.get("scheduled_reissue")
        if not isinstance(receipt, dict) or receipt.get("state") != "sent":
            raise RuntimeError("Post-window readback requires the existing sent receipt")
    # The original creation commit is retained for deterministic historical URLs.
    source_sha = original.get("github_sha")
    if not isinstance(source_sha, str) or len(source_sha) != 40:
        raise RuntimeError("Original publication commit missing")
    if entry.get("media_base_revision") and (
        source_sha != entry["original_github_sha"] or original.get("cover_sha256") != entry["original_cover_sha256"]
    ):
        raise RuntimeError("Original Charnock receipt/media provenance drift")
    media_revision = entry.get("media_base_revision", source_sha)
    media_url = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + media_revision
    payload = build_telegraph_payload(args.repo_root, item, media_base_url=media_url)
    if payload.article_sha256 != entry["source_article_sha256"]:
        raise RuntimeError("Corrected source is not byte-identical to its verified Telegraph edition")
    if entry.get("reviewed_normalized_tree_sha256"):
        if (
            len(payload.nodes) != entry["reviewed_node_count"]
            or payload.cover_sha256 != entry["original_cover_sha256"]
            or _normalized_telegraph_digest(payload.nodes, retain_heading_ids=True)
            != entry["reviewed_normalized_tree_sha256"]
        ):
            raise RuntimeError("Reviewed Charnock #10 rendered nodes or cover drifted")
    return entry, item, payload, original


def _readback_existing_post(*, message_id: int) -> bool:
    response = httpx.get(f"https://t.me/lordchrist/{message_id}?embed=1", timeout=15, follow_redirects=True)
    response.raise_for_status()
    return f'data-post="lordchrist/{message_id}"' in response.text


def _prove_owner_deletion(entry: dict[str, Any]) -> None:
    if not _readback_existing_post(message_id=1595):
        raise RuntimeError("Known-good channel readback unavailable; cannot confirm original deletion")
    if _readback_existing_post(message_id=int(entry["deleted_telegram_message_id"])):
        raise RuntimeError("Original Telegram message is still visible; refuse duplicate release")


def _prove_new_public_post(*, message_id: int, telegraph_url: str) -> None:
    """Wait for public widget propagation without EVER sending the Telegram message again."""
    url = f"https://t.me/lordchrist/{message_id}?embed=1"
    for seconds in NEW_POST_PUBLIC_READBACK_DELAYS:
        if seconds:
            time.sleep(seconds)
        try:
            response = httpx.get(url, timeout=20, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        if f'data-post="lordchrist/{message_id}"' in response.text and telegraph_url in response.text:
            return
    raise RuntimeError(
        "New Telegram message is not publicly verified after bounded readback; "
        "reconcile the existing send receipt, never retry sendMessage"
    )


def _normalized_telegraph_node(value: Any, *, retain_heading_ids: bool = False) -> Any:
    """Normalize node text; the legacy default also removes all heading IDs.

    The default is retained for the independently used 1525 page proof. For
    Charnock comparisons, retain IDs first and use the target-relative pair
    normalizer. Lists inside attributes and other arbitrary fields are never
    normalized. The input is not mutated.
    """
    if isinstance(value, list):
        joined: list[Any] = []
        for item in value:
            child = (
                _normalized_telegraph_node(item, retain_heading_ids=retain_heading_ids)
                if isinstance(item, dict)
                else item
            )
            if isinstance(child, str) and joined and isinstance(joined[-1], str):
                joined[-1] += child
            else:
                joined.append(child)
        return joined
    if isinstance(value, dict):
        normalized = dict(value)
        children = value.get("children")
        if isinstance(children, list):
            normalized["children"] = _normalized_telegraph_node(children, retain_heading_ids=retain_heading_ids)
        attrs = value.get("attrs")
        if not retain_heading_ids and value.get("tag") in ("h3", "h4") and isinstance(attrs, dict) and "id" in attrs:
            remaining = {key: child for key, child in attrs.items() if key != "id"}
            if remaining:
                normalized["attrs"] = remaining
            else:
                normalized.pop("attrs")
        return normalized
    return value


def _normalized_telegraph_pair(live: Any, reviewed: Any) -> tuple[Any, Any]:
    """Normalize a live tree relative to its reviewed target, without mutation.

    A string ID on a live h3/h4 is ignored only if its corresponding reviewed
    heading has no explicit ID. The live ID's origin is not established. When
    the reviewed heading specifies an ID, it and its JSON type must match.
    Node alignment follows normalized content/children only; no attributes or
    other arbitrary substructures are traversed or rewritten.
    """
    actual = _normalized_telegraph_node(live, retain_heading_ids=True)
    expected = _normalized_telegraph_node(reviewed, retain_heading_ids=True)

    def visit_list(actual_items: list[Any], expected_items: list[Any]) -> None:
        for actual_child, expected_child in zip(actual_items, expected_items, strict=False):
            # Nested arrays are not node content and were not copied above.
            if isinstance(actual_child, dict) and isinstance(expected_child, dict):
                visit_node(actual_child, expected_child)

    def visit_node(actual_node: dict[str, Any], expected_node: dict[str, Any]) -> None:
        tag = expected_node.get("tag")
        if tag in ("h3", "h4") and actual_node.get("tag") == tag:
            actual_attrs = actual_node.get("attrs")
            expected_attrs = expected_node.get("attrs")
            if (
                isinstance(actual_attrs, dict)
                and isinstance(actual_attrs.get("id"), str)
                and not (isinstance(expected_attrs, dict) and "id" in expected_attrs)
            ):
                remaining = {key: child for key, child in actual_attrs.items() if key != "id"}
                if remaining:
                    actual_node["attrs"] = remaining
                else:
                    actual_node.pop("attrs")
        actual_children = actual_node.get("children")
        expected_children = expected_node.get("children")
        if isinstance(actual_children, list) and isinstance(expected_children, list):
            visit_list(actual_children, expected_children)

    if isinstance(actual, list) and isinstance(expected, list):
        visit_list(actual, expected)
    elif isinstance(actual, dict) and isinstance(expected, dict):
        visit_node(actual, expected)
    return actual, expected


def _normalized_telegraph_digest(value: Any, *, retain_heading_ids: bool = False) -> str:
    """Hash normalized JSON without bool/int or numeric coercions.

    The legacy default ignores all heading IDs. Charnock compares a paired live
    and reviewed tree with ``retain_heading_ids=True``; independent digests do
    not establish fetched media bytes or the provenance of a live heading ID.
    """
    try:
        normalized = _normalized_telegraph_node(value, retain_heading_ids=retain_heading_ids)
        encoded = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Malformed normalized Telegraph content") from exc
    return hashlib.sha256(encoded).hexdigest()


def _normalized_telegraph_pair_digests(live: Any, reviewed: Any) -> tuple[str, str]:
    actual, expected = _normalized_telegraph_pair(live, reviewed)
    return (
        _normalized_telegraph_digest(actual, retain_heading_ids=True),
        _normalized_telegraph_digest(expected, retain_heading_ids=True),
    )


def _normalized_telegraph_equal(live: Any, reviewed: Any) -> bool:
    actual_digest, expected_digest = _normalized_telegraph_pair_digests(live, reviewed)
    return actual_digest == expected_digest


def _proof_page(entry: dict[str, Any], payload: Any) -> None:
    url = entry["verified_telegraph_url"]
    if not isinstance(url, str) or not url.startswith("https://telegra.ph/"):
        raise RuntimeError("Untrusted Telegraph edition URL")
    path = url.removeprefix("https://telegra.ph/")
    if not path or "/" in path or "?" in path or "#" in path:
        raise RuntimeError("Untrusted Telegraph edition path")
    response = httpx.get(
        f"https://api.telegra.ph/getPage/{path}?return_content=true",
        timeout=20,
    )
    response.raise_for_status()
    document = response.json()
    page = document.get("result")
    if (
        not document.get("ok")
        or not isinstance(page, dict)
        or page.get("path") != path
        or page.get("url") != url
        or page.get("title") != payload.title
        or page.get("author_name") != payload.author_name
        or page.get("author_url") != payload.author_url
        or not isinstance(page.get("content"), list)
        or not page["content"]
        or not isinstance(payload.nodes, list)
        or not payload.nodes
        or not _normalized_telegraph_equal(page["content"], payload.nodes)
    ):
        raise RuntimeError("Public Telegraph page is not the entire reviewed latest article edition")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.stage != "preview":
        _require_execution_context(args)
        _require_approved_recovery_trigger(args)
        if args.now is not None:
            raise RuntimeError("Forged clock forbidden on live recovery")
    now = datetime.fromisoformat(args.now) if args.stage == "preview" and args.now else datetime.now(tz=MOSCOW)
    ledger_path, ledger = _ledger(args)
    source, item, payload, original = _select_due(args, ledger, now=now)
    if args.stage == "preview":
        return {
            "publication_id": args.publication_id,
            "date": source["scheduled_on_moscow"],
            "article_sha256": payload.article_sha256,
            "source_url": source["verified_telegraph_url"],
            "old_message_id": source["deleted_telegram_message_id"],
            "already_claimed": "scheduled_reissue" in original,
        }

    if args.stage == "prepare":
        if "scheduled_reissue" in original:
            raise RuntimeError("Scheduled reissue intent already exists; never replay")
        _prove_owner_deletion(source)
        _proof_page(source, payload)
        original["scheduled_reissue"] = {
            "state": "claimed",
            "provider_effect": "may_exist_until_reconciled",
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "github_sha": args.github_sha,
            "scheduled_on_moscow": source["scheduled_on_moscow"],
            "original_deleted_message_id": source["deleted_telegram_message_id"],
            "source_article_sha256": payload.article_sha256,
            "telegraph_url": source["verified_telegraph_url"],
            "claimed_at_moscow": now.astimezone(MOSCOW).isoformat(),
        }
        if source.get("binding_git_blob_sha"):
            original["scheduled_reissue"]["binding_git_blob_sha"] = source["binding_git_blob_sha"]
        save_ledger(ledger_path, ledger)
        return {"stage": "claimed", "publication_id": args.publication_id}

    receipt = original.get("scheduled_reissue")
    if not isinstance(receipt, dict):
        raise RuntimeError("No durable reissue intent; cannot contact provider")
    if (
        receipt.get("run_id") != args.run_id
        or receipt.get("run_attempt") != 1
        or receipt.get("github_sha") != args.github_sha
        or receipt.get("source_article_sha256") != payload.article_sha256
        or receipt.get("telegraph_url") != source["verified_telegraph_url"]
        or receipt.get("scheduled_on_moscow") != source["scheduled_on_moscow"]
        or receipt.get("binding_git_blob_sha") != source.get("binding_git_blob_sha")
    ):
        raise RuntimeError("Reissue intent/reviewed payload drift; fail closed")

    if args.stage == "send":
        if receipt.get("state") != "claimed":
            raise RuntimeError("Send-once already attempted; no replay")
        _prove_owner_deletion(source)
        _proof_page(source, payload)
        profile = load_channel_profile(args.repo_root / DEFAULT_PROFILE_PATH)
        binding = load_target_binding(args.repo_root / DEFAULT_BINDING_PATH, profile=profile)
        token = os.environ.get(profile.bot_token_env, "").strip()
        if not token or binding.chat_id != -1001295216957 or original.get("telegram_chat_id") != binding.chat_id:
            raise RuntimeError("Missing Telegram token or canonical channel binding mismatch")
        transport = HttpxLiveTransport()
        base = f"{DEFAULT_TELEGRAM_API_BASE}/bot{token}"
        me = transport.read_json(f"{base}/getMe", {})
        chat = transport.read_json(f"{base}/getChat", {"chat_id": binding.chat_id})
        if (
            not me.get("ok")
            or int((me.get("result") or {}).get("id", 0)) != binding.bot_id
            or (me.get("result") or {}).get("username") != "preaching_mp3_bot"
            or not chat.get("ok")
            or int((chat.get("result") or {}).get("id", 0)) != binding.chat_id
            or (chat.get("result") or {}).get("username") != "lordchrist"
            or (chat.get("result") or {}).get("type") != "channel"
        ):
            raise RuntimeError("Telegram bot/channel authentication mismatched")
        rendered = render_channel_post(item.channel_post, source["verified_telegraph_url"])
        if not 1 <= rendered.visible_char_count <= 4096:
            raise RuntimeError("Rendered announcement must fit one Telegram L1 message")
        # Network readbacks/authentication may straddle 14:00 even when the
        # stage began within its lease. Check again immediately before POST.
        if datetime.now(tz=MOSCOW).hour not in LIVE_WINDOW_HOUR:
            raise RuntimeError("Charnock Telegram send window expired before provider POST")
        sent = transport.post_json(
            f"{base}/sendMessage",
            {
                "chat_id": binding.chat_id,
                "text": rendered.html_text,
                "parse_mode": "HTML",
                "link_preview_options": {
                    "is_disabled": False,
                    "url": source["verified_telegraph_url"],
                    "prefer_large_media": True,
                    "show_above_text": False,
                },
            },
        )
        result = sent.get("result")
        if not sent.get("ok") or not isinstance(result, dict):
            raise RuntimeError("Telegram provider did not acknowledge a durable new message")
        new_id = int(result.get("message_id", 0))
        if (
            new_id <= 0
            or new_id == source["deleted_telegram_message_id"]
            or int((result.get("chat") or {}).get("id", 0)) != binding.chat_id
        ):
            raise RuntimeError("Telegram provider acknowledged a mismatched message identity")
        urls = {
            e.get("url") for e in result.get("entities", []) if isinstance(e, dict) and e.get("type") == "text_link"
        }
        if source["verified_telegraph_url"] not in urls:
            raise RuntimeError("Telegram receipt lacked exact immutable corrected article link")
        receipt.update(
            state="sent",
            provider_effect="verified_by_api",
            new_message_id=new_id,
            sent_at_moscow=now.astimezone(MOSCOW).isoformat(),
        )
        save_ledger(ledger_path, ledger)
        return {"stage": "sent", "publication_id": args.publication_id, "message_id": new_id}

    if args.stage == "verify":
        if receipt.get("state") != "sent":
            raise RuntimeError("Only a confirmed send can be read back")
        verified_message_id = receipt.get("new_message_id")
        if not isinstance(verified_message_id, int) or verified_message_id <= 0:
            raise RuntimeError("Missing provider-acknowledged replacement message identity")
        _prove_new_public_post(message_id=verified_message_id, telegraph_url=source["verified_telegraph_url"])
        receipt.update(
            state="verified", provider_effect="verified", verified_at_moscow=now.astimezone(MOSCOW).isoformat()
        )
        save_ledger(ledger_path, ledger)
        return {"stage": "verified", "publication_id": args.publication_id, "message_id": verified_message_id}

    raise ValueError(f"Unsupported Charnock scheduled stage {args.stage!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m video_channel_manager.lordchrist_charnock_reschedule")
    parser.add_argument("stage", choices=("preview", "prepare", "send", "verify"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", type=int, default=0)
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--now", help="Only in provider-free preview; never accepted for live stages")
    args = parser.parse_args(argv)
    print(json.dumps(execute(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
