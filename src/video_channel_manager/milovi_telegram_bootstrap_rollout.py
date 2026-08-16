from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import httpx

from video_channel_manager.milovi_telegram_live_canary import (
    BOT_ID,
    BOT_USERNAME,
    CHAT_ID,
    CHAT_USERNAME,
    _fresh_target_preflight,
    _telegram_call,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
CANDIDATES_PATH = CONTENT / "bootstrap-first-screen-candidates-2026-08.json"
PROOF_PATH = CONTENT / "bootstrap-photo-transport-proof-2026-08.json"
ROLLOUT_PATH = CONTENT / "bootstrap-rollout-candidate-2026-08.json"
WINDOW_PATH = CONTENT / "publishing-window-2026-08.json"
APPROVAL_PATH = CONTENT / "live" / "bootstrap-rollout-approval.json"
STATE_PATH = CONTENT / "live" / "bootstrap-rollout-state.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "telegram-milovi-bootstrap-rollout.yml"
RUNTIME_PATH = pathlib.Path(__file__).resolve()
RUNTIME_DIR = ROOT / ".runtime" / "milovi-bootstrap-rollout"

SOURCE_REPOSITORY = "FedorMilovanov/Milovi_Cake"
SOURCE_COMMIT = "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370"
RELEASE_ID = "milovi-telegram-first-screen-2026-08"
LOCAL_TZ = timezone(timedelta(hours=3))
EARLY_TOLERANCE = timedelta(minutes=5)
LATE_TOLERANCE = timedelta(minutes=75)


def _json_object(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _sha256_path(path: pathlib.Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _approval() -> dict[str, Any] | None:
    if not APPROVAL_PATH.exists():
        return None
    approval = _json_object(APPROVAL_PATH)
    required: dict[str, object] = {
        "schema_name": "video-channel-manager.milovi-telegram-bootstrap-rollout-approval",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "owning_issue": 353,
        "release_id": RELEASE_ID,
        "chat_id": CHAT_ID,
        "chat_username": CHAT_USERNAME,
        "bot_id": BOT_ID,
        "bot_username": BOT_USERNAME,
        "provider_mutation_allowed": True,
        "blind_mutation_retries": 0,
        "timezone": "Europe/Moscow",
        "earliest_publication_local": "09:00",
        "latest_publication_local": "21:00",
        "strict_next_only": True,
    }
    for key, expected in required.items():
        if approval.get(key) != expected:
            raise SystemExit(f"rollout approval mismatch: {key}")

    digests = {
        "runtime_sha256": _sha256_path(RUNTIME_PATH),
        "workflow_sha256": _sha256_path(WORKFLOW_PATH),
        "rollout_sha256": _sha256_path(ROLLOUT_PATH),
        "candidates_sha256": _sha256_path(CANDIDATES_PATH),
        "transport_proof_sha256": _sha256_path(PROOF_PATH),
        "publishing_window_sha256": _sha256_path(WINDOW_PATH),
    }
    for key, actual in digests.items():
        if approval.get(key) != actual:
            raise SystemExit(f"rollout approval digest mismatch: {key}")

    merge_sha = str(approval.get("implementation_merge_sha") or "")
    if len(merge_sha) != 40:
        raise SystemExit("rollout approval implementation merge SHA is invalid")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", merge_sha, "HEAD"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestor.returncode != 0:
        raise SystemExit("approved rollout implementation is not an ancestor of current main")
    return approval


def _frozen_data() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rollout = _json_object(ROLLOUT_PATH)
    candidates = _json_object(CANDIDATES_PATH)
    proof = _json_object(PROOF_PATH)
    window = _json_object(WINDOW_PATH)

    if rollout.get("release_id") != RELEASE_ID or rollout.get("provider_mutation_allowed") is not False:
        raise SystemExit("rollout candidate identity/authority mismatch")
    if rollout.get("chat_id") != CHAT_ID or rollout.get("bot_id") != BOT_ID:
        raise SystemExit("rollout target identity mismatch")
    if window.get("timezone") != "Europe/Moscow":
        raise SystemExit("publishing timezone mismatch")
    if window.get("earliest_publication_local") != "09:00" or window.get("latest_publication_local") != "21:00":
        raise SystemExit("publishing window drift")

    items = rollout.get("items")
    candidate_items = candidates.get("candidates")
    photos = proof.get("photos")
    if not isinstance(items, list) or not isinstance(candidate_items, list) or not isinstance(photos, list):
        raise SystemExit("frozen rollout collections malformed")
    if len(items) != 10 or len(candidate_items) != 10:
        raise SystemExit("expected exactly ten first-screen items")
    candidate_by_id = {str(item["publication_id"]): cast(dict[str, Any], item) for item in candidate_items if isinstance(item, dict)}
    photo_by_id = {str(item["media_id"]): cast(dict[str, Any], item) for item in photos if isinstance(item, dict)}
    if len(candidate_by_id) != 10 or len(photo_by_id) != 9:
        raise SystemExit("frozen candidate/media identities are not unique")

    normalized: list[dict[str, Any]] = []
    for expected_sequence, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise SystemExit("rollout item is not an object")
        item = cast(dict[str, Any], raw)
        if item.get("sequence") != expected_sequence:
            raise SystemExit("rollout sequence is not contiguous")
        publication_id = str(item.get("publication_id") or "")
        candidate = candidate_by_id.get(publication_id)
        if candidate is None or candidate.get("sequence") != expected_sequence:
            raise SystemExit("rollout/candidate publication identity mismatch")
        caption = str(candidate.get("caption") or "")
        if item.get("caption_sha256") != _sha256_text(caption):
            raise SystemExit(f"{publication_id}: caption digest drift")
        operation = str(item.get("operation") or "")
        if operation not in {"sendPhoto", "sendMessage"} or candidate.get("operation") != operation:
            raise SystemExit(f"{publication_id}: operation mismatch")
        planned = datetime.fromisoformat(str(item.get("planned_local") or ""))
        if planned.utcoffset() != timedelta(hours=3):
            raise SystemExit(f"{publication_id}: planned timezone must be +03:00")
        minute = planned.hour * 60 + planned.minute
        if not 9 * 60 <= minute <= 21 * 60:
            raise SystemExit(f"{publication_id}: planned time outside daylight window")
        if operation == "sendPhoto":
            media_id = str(item.get("media_id") or "")
            photo = photo_by_id.get(media_id)
            if photo is None or candidate.get("media_id") != media_id:
                raise SystemExit(f"{publication_id}: media identity mismatch")
            if photo.get("transport_ready") is not True:
                raise SystemExit(f"{publication_id}: transport is not ready")
            if item.get("transport_sha256") != photo.get("transport_sha256"):
                raise SystemExit(f"{publication_id}: transport digest mismatch")
            if item.get("transport_byte_size") != photo.get("transport_byte_size"):
                raise SystemExit(f"{publication_id}: transport byte-size mismatch")
        else:
            if any(item.get(field) is not None for field in ("media_id", "transport_sha256", "transport_byte_size")):
                raise SystemExit(f"{publication_id}: text item unexpectedly binds media")
        normalized.append(item)
    return rollout, normalized, candidate_by_id, photo_by_id


def _state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    state = _json_object(STATE_PATH)
    if state.get("schema_name") != "video-channel-manager.milovi-telegram-bootstrap-rollout-state":
        raise SystemExit("rollout state schema mismatch")
    if state.get("release_id") != RELEASE_ID or state.get("chat_id") != CHAT_ID:
        raise SystemExit("rollout state identity mismatch")
    entries = state.get("items")
    if not isinstance(entries, list):
        raise SystemExit("rollout state items malformed")
    return state


def _next_sequence(state: dict[str, Any] | None) -> int:
    if state is None:
        return 1
    entries = cast(list[object], state["items"])
    expected = 1
    for raw in entries:
        if not isinstance(raw, dict):
            raise SystemExit("rollout state item malformed")
        entry = cast(dict[str, Any], raw)
        if entry.get("sequence") != expected:
            raise SystemExit("rollout state sequence gap")
        if entry.get("status") != "verified" or not isinstance(entry.get("message_id"), int):
            raise SystemExit(f"rollout blocked by unresolved item {expected}: {entry.get('status')}")
        expected += 1
    return expected


def evaluate_plan(now: datetime | None = None) -> dict[str, Any]:
    approval = _approval()
    if approval is None:
        return {"execute": False, "reason": "approval_missing", "provider_access_allowed": False}
    _, items, _, _ = _frozen_data()
    state = _state()
    sequence = _next_sequence(state)
    if sequence > len(items):
        return {"execute": False, "reason": "rollout_complete", "provider_access_allowed": False}

    effective = now or datetime.now(tz=UTC)
    if effective.tzinfo is None:
        raise SystemExit("plan timestamp must be timezone-aware")
    local_now = effective.astimezone(LOCAL_TZ)
    minute = local_now.hour * 60 + local_now.minute
    if not 9 * 60 <= minute <= 21 * 60:
        return {"execute": False, "reason": "quiet_hours", "provider_access_allowed": False, "sequence": sequence}

    item = items[sequence - 1]
    planned = datetime.fromisoformat(str(item["planned_local"]))
    if local_now < planned - EARLY_TOLERANCE:
        return {"execute": False, "reason": "not_due", "provider_access_allowed": False, "sequence": sequence}
    if local_now > planned + LATE_TOLERANCE:
        return {"execute": False, "reason": "missed_slot", "provider_access_allowed": False, "sequence": sequence}
    return {
        "execute": True,
        "reason": "strict_next_due",
        "provider_access_allowed": True,
        "sequence": sequence,
        "publication_id": item["publication_id"],
        "operation": item["operation"],
        "planned_local": item["planned_local"],
    }


def _download_source(photo: dict[str, Any]) -> bytes:
    source_path = str(photo["source_path"])
    safe_path = "/".join(urllib.parse.quote(part, safe="") for part in source_path.split("/"))
    request = urllib.request.Request(
        f"https://raw.githubusercontent.com/{SOURCE_REPOSITORY}/{SOURCE_COMMIT}/{safe_path}",
        headers={"User-Agent": "video-channel-manager-milovi-bootstrap-rollout/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        source = response.read()
    if len(source) != int(photo["source_byte_size"]):
        raise SystemExit("source byte-size mismatch")
    blob = hashlib.sha1(f"blob {len(source)}\0".encode("ascii") + source, usedforsecurity=False).hexdigest()
    if blob != photo["source_git_blob_sha1"]:
        raise SystemExit("source Git blob mismatch")
    if _sha256_bytes(source) != photo["source_sha256"]:
        raise SystemExit("source SHA-256 mismatch")
    return source


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _materialize_photo(photo: dict[str, Any]) -> bytes:
    from PIL import Image  # type: ignore[import-not-found]

    source = _download_source(photo)
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        expected = (int(photo["pixel_width"]), int(photo["pixel_height"]))
        if image.format != "WEBP" or image.size != expected:
            raise SystemExit("source decode mismatch")
        rgb = image.convert("RGB")
    encoded = io.BytesIO()
    rgb.save(encoded, format="JPEG", quality=95, subsampling=0, optimize=False, progressive=False, exif=b"")
    jpeg = encoded.getvalue()
    if len(jpeg) != int(photo["transport_byte_size"]):
        raise SystemExit("transport byte-size drift")
    if _sha256_bytes(jpeg) != photo["transport_sha256"]:
        raise SystemExit("transport SHA-256 drift")
    return jpeg


def _current_item() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    _, items, candidate_by_id, photo_by_id = _frozen_data()
    state = _state()
    sequence = _next_sequence(state)
    if sequence > len(items):
        raise SystemExit("rollout already complete")
    item = items[sequence - 1]
    candidate = candidate_by_id[str(item["publication_id"])]
    photo = photo_by_id.get(str(item.get("media_id") or ""))
    return item, candidate, photo


def prepare() -> int:
    plan = evaluate_plan()
    if plan.get("execute") is not True:
        raise SystemExit(f"rollout prepare blocked: {plan.get('reason')}")
    item, candidate, photo = _current_item()
    if int(item["sequence"]) != int(plan["sequence"]):
        raise SystemExit("plan/strict-next sequence changed")

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    _fresh_target_preflight(token)
    caption = str(candidate["caption"])
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "caption.txt").write_text(caption, encoding="utf-8")
    if item["operation"] == "sendPhoto":
        if photo is None:
            raise SystemExit("photo operation has no proof record")
        (RUNTIME_DIR / "payload.jpg").write_bytes(_materialize_photo(photo))

    existing = _state()
    entries: list[dict[str, Any]] = [] if existing is None else cast(list[dict[str, Any]], existing["items"])
    dispatch = {
        "sequence": item["sequence"],
        "publication_id": item["publication_id"],
        "operation": item["operation"],
        "planned_local": item["planned_local"],
        "caption_sha256": item["caption_sha256"],
        "transport_sha256": item.get("transport_sha256"),
        "status": "dispatch_started",
        "provider_effect": "may_exist_after_next_step",
        "authorization_id": _json_object(APPROVAL_PATH)["authorization_id"],
        "github_sha": os.environ["GITHUB_SHA"],
        "github_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "github_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "dispatch_started_at_utc": datetime.now(tz=UTC).isoformat(),
        "message_id": None,
        "message_url": None,
    }
    state = {
        "schema_name": "video-channel-manager.milovi-telegram-bootstrap-rollout-state",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "release_id": RELEASE_ID,
        "chat_id": CHAT_ID,
        "chat_username": CHAT_USERNAME,
        "bot_id": BOT_ID,
        "bot_username": BOT_USERNAME,
        "items": [*entries, dispatch],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prepared", "sequence": item["sequence"], "provider_write_performed": False}))
    return 0


def _record_terminal(entry: dict[str, Any], *, status: str, effect: str, http_status: int, description: str) -> None:
    entry.update(
        {
            "status": status,
            "provider_effect": effect,
            "provider_response_at_utc": datetime.now(tz=UTC).isoformat(),
            "provider_http_status": http_status,
            "provider_description": description,
            "automatic_replay_allowed": False,
        }
    )


def send() -> int:
    state = _json_object(STATE_PATH)
    entries = state.get("items")
    if not isinstance(entries, list) or not entries or not isinstance(entries[-1], dict):
        raise SystemExit("dispatch-started state missing")
    entry = cast(dict[str, Any], entries[-1])
    if entry.get("status") != "dispatch_started" or entry.get("message_id") is not None:
        raise SystemExit("latest rollout item is not a dispatch-started barrier")
    if entry.get("github_sha") != os.environ.get("GITHUB_SHA"):
        raise SystemExit("dispatch state is not bound to this scheduled revision")

    item, candidate, _ = _current_item_for_dispatch(entry)
    caption = (RUNTIME_DIR / "caption.txt").read_text(encoding="utf-8")
    if _sha256_text(caption) != item["caption_sha256"] or caption != candidate["caption"]:
        raise SystemExit("runtime caption drift")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    try:
        if item["operation"] == "sendPhoto":
            jpeg = (RUNTIME_DIR / "payload.jpg").read_bytes()
            status, body = _telegram_call(
                token,
                "sendPhoto",
                data={"chat_id": str(CHAT_ID), "caption": caption},
                files={"photo": ("milovi.jpg", jpeg, "image/jpeg")},
                retries=0,
            )
        else:
            status, body = _telegram_call(
                token,
                "sendMessage",
                json_payload={"chat_id": CHAT_ID, "text": caption},
                retries=0,
            )
    except (httpx.TimeoutException, httpx.TransportError, RuntimeError) as exc:
        print("Telegram outcome unknown; durable dispatch_started blocks successor", file=sys.stderr)
        print(type(exc).__name__, file=sys.stderr)
        return 2

    if status != 200 or body.get("ok") is not True:
        description = str(body.get("description") or f"HTTP {status}")[:500]
        if 400 <= status < 500:
            _record_terminal(entry, status="provider_rejected", effect="rejected_before_message_creation", http_status=status, description=description)
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            print(f"Telegram non-terminal/unknown provider response HTTP {status}", file=sys.stderr)
        return 2

    result = body.get("result")
    if not isinstance(result, dict):
        print("Telegram success response malformed; outcome treated as unknown", file=sys.stderr)
        return 2
    chat = result.get("chat")
    if not isinstance(chat, dict) or int(chat.get("id", 0)) != CHAT_ID:
        print("Telegram returned wrong chat; outcome treated as unknown", file=sys.stderr)
        return 2
    if str(chat.get("username") or "").casefold() != CHAT_USERNAME.casefold():
        print("Telegram returned wrong username; outcome treated as unknown", file=sys.stderr)
        return 2
    message_id = result.get("message_id")
    if not isinstance(message_id, int) or message_id <= 0:
        print("Telegram returned no positive message_id; outcome treated as unknown", file=sys.stderr)
        return 2
    if item["operation"] == "sendPhoto":
        if result.get("caption") != caption or not isinstance(result.get("photo"), list) or not result["photo"]:
            print("Telegram photo postflight mismatch; outcome treated as unknown", file=sys.stderr)
            return 2
    elif result.get("text") != caption:
        print("Telegram text postflight mismatch; outcome treated as unknown", file=sys.stderr)
        return 2

    entry.update(
        {
            "status": "verified",
            "provider_effect": "verified",
            "provider_response_at_utc": datetime.now(tz=UTC).isoformat(),
            "message_id": message_id,
            "message_url": f"https://t.me/{CHAT_USERNAME}/{message_id}",
            "returned_chat_id": int(chat["id"]),
            "returned_chat_username": str(chat.get("username") or ""),
            "automatic_replay_allowed": False,
        }
    )
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "verified", "sequence": item["sequence"], "message_id": message_id}))
    return 0


def _current_item_for_dispatch(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    _, items, candidate_by_id, photo_by_id = _frozen_data()
    sequence = int(entry["sequence"])
    if not 1 <= sequence <= len(items):
        raise SystemExit("dispatch sequence outside release")
    item = items[sequence - 1]
    if item["publication_id"] != entry.get("publication_id") or item["operation"] != entry.get("operation"):
        raise SystemExit("dispatch identity differs from frozen release")
    candidate = candidate_by_id[str(item["publication_id"])]
    photo = photo_by_id.get(str(item.get("media_id") or ""))
    return item, candidate, photo


def plan_cli() -> int:
    plan = evaluate_plan()
    print(json.dumps(plan, ensure_ascii=False))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"execute={'true' if plan.get('execute') is True else 'false'}\n")
            handle.write(f"reason={plan.get('reason')}\n")
            handle.write(f"sequence={plan.get('sequence', '')}\n")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"plan", "prepare", "send"}:
        raise SystemExit("usage: python -m video_channel_manager.milovi_telegram_bootstrap_rollout {plan|prepare|send}")
    if sys.argv[1] == "plan":
        return plan_cli()
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        raise SystemExit("Milovi rollout provider path is schedule-only")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise SystemExit("GitHub rerun forbidden for Milovi scheduled rollout")
    if sys.argv[1] == "prepare":
        return prepare()
    return send()


if __name__ == "__main__":
    raise SystemExit(main())
