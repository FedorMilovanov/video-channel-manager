from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

import httpx

AUTH_PATH = pathlib.Path("content/telegram/milovi-cake/live/canary-authorization.json")
STATE_PATH = pathlib.Path("content/telegram/milovi-cake/live/canary-dispatch-state.json")
ATTEMPTS_DIR = pathlib.Path("content/telegram/milovi-cake/live/attempts")
CANDIDATE_PATH = pathlib.Path("content/telegram/milovi-cake/canary-candidate-2026-08.json")
RUNTIME_DIR = pathlib.Path(".runtime/milovi-canary")

CHAT_ID = -1002215328390
CHAT_USERNAME = "MiloviCake"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
CANARY_EVIDENCE_SHA256 = "sha256:d712ca06f2503bbb7e483f6c8d0fe3f0067b37b834536f7f7861bb38415fa580"
SOURCE_REPO = "FedorMilovanov/Milovi_Cake"
SOURCE_COMMIT = "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370"
SOURCE_PATH = "img/gallery/gallery-18-hd.webp"
SOURCE_BLOB_SHA1 = "3574f726b233583a77b8a6db885f91b49e5189d8"
SOURCE_BYTE_SIZE = 195742
SOURCE_SHA256 = "2fd0336e90d3d42ae70638b33fc51653c14ef3b4c08c1ce6fce7f5c818b65aca"
TRANSPORT_SHA256 = "a9730cc62939845c61191f1a375b2bab35800122c968d6cc757f0ae4340771d5"
TRANSPORT_BYTE_SIZE = 580910
CAPTION_SHA256 = "sha256:fe4552e8cb78183f2f7f32d03792af4b9d4f65a18ec0811bfbced7fb424e0d1c"
AUTHORIZATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _json_object(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _authorization_id(payload: dict[str, Any], *, field: str = "authorization_id") -> str:
    value = str(payload.get(field) or "")
    if not AUTHORIZATION_ID_PATTERN.fullmatch(value):
        raise SystemExit(f"invalid {field}")
    return value


def _telegram_call(
    token: str,
    method: str,
    *,
    json_payload: dict[str, object] | None = None,
    data: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    retries: int,
) -> tuple[int, dict[str, Any]]:
    with httpx.Client(
        timeout=httpx.Timeout(connect=15, read=45, write=45, pool=15),
        transport=httpx.HTTPTransport(retries=retries),
        trust_env=False,
    ) as client:
        response = client.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=json_payload,
            data=data,
            files=files,
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{method}: non-JSON HTTP {response.status_code}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method}: non-object response")
    return response.status_code, cast(dict[str, Any], payload)


def _read_result(token: str, method: str, payload: dict[str, object]) -> dict[str, Any]:
    status, body = _telegram_call(token, method, json_payload=payload, retries=2)
    if status != 200 or body.get("ok") is not True:
        raise SystemExit(f"{method}: read-only preflight failed")
    result = body.get("result")
    if not isinstance(result, dict):
        raise SystemExit(f"{method}: malformed result")
    return cast(dict[str, Any], result)


def _validate_authorization(auth: dict[str, Any]) -> dict[str, Any] | None:
    required: dict[str, object] = {
        "schema_name": "video-channel-manager.milovi-exact-canary-authorization",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": "milovi-cake-canary-001",
        "operation": "sendPhoto",
        "provider_mutation_allowed": True,
        "dispatch_retries": 0,
        "chat_id": CHAT_ID,
        "chat_username": CHAT_USERNAME,
        "bot_id": BOT_ID,
        "bot_username": BOT_USERNAME,
        "canary_evidence_sha256": CANARY_EVIDENCE_SHA256,
        "source_sha256": f"sha256:{SOURCE_SHA256}",
        "transport_sha256": f"sha256:{TRANSPORT_SHA256}",
        "transport_byte_size": TRANSPORT_BYTE_SIZE,
        "caption_sha256": CAPTION_SHA256,
    }
    for key, expected in required.items():
        if auth.get(key) != expected:
            raise SystemExit(f"authorization mismatch: {key}")

    new_authorization_id = _authorization_id(auth)
    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], text=True).strip()
    if parent != auth.get("expected_parent_main_sha"):
        raise SystemExit("authorization parent differs from reviewed main")
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD^", "HEAD"], text=True).splitlines()
    if changed != [AUTH_PATH.as_posix()]:
        raise SystemExit(f"authorization commit contains unexpected files: {changed}")

    if not STATE_PATH.exists():
        if auth.get("supersedes_authorization_id") not in {None, ""}:
            raise SystemExit("first canary authorization cannot supersede another authorization")
        return None

    prior = _json_object(STATE_PATH)
    prior_authorization_id = _authorization_id(prior)
    if prior_authorization_id == new_authorization_id:
        raise SystemExit("same canary authorization cannot be replayed")
    if (
        prior.get("status") != "provider_rejected"
        or prior.get("provider_effect") != "rejected_before_message_creation"
        or prior.get("message_id") is not None
        or prior.get("automatic_replay_allowed") is not False
    ):
        raise SystemExit(f"existing canary state is not successor-safe: {prior.get('status')}")
    if auth.get("supersedes_authorization_id") != prior_authorization_id:
        raise SystemExit("successor authorization must explicitly bind the rejected authorization it supersedes")
    return prior


def _materialize_payload() -> tuple[bytes, str]:
    from PIL import Image  # type: ignore[import-not-found]

    candidate = _json_object(CANDIDATE_PATH)
    if candidate.get("publication_id") != "milovi-cake-canary-001" or candidate.get("operation") != "sendPhoto":
        raise SystemExit("candidate identity mismatch")
    caption_block = candidate.get("caption")
    if not isinstance(caption_block, dict):
        raise SystemExit("candidate caption block missing")
    caption = str(caption_block.get("text") or "")
    if f"sha256:{hashlib.sha256(caption.encode('utf-8')).hexdigest()}" != CAPTION_SHA256:
        raise SystemExit("caption digest mismatch")
    if len(caption) > 1024:
        raise SystemExit("caption exceeds Telegram photo limit")

    safe_path = "/".join(urllib.parse.quote(part, safe="") for part in SOURCE_PATH.split("/"))
    request = urllib.request.Request(
        f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/{safe_path}",
        headers={"User-Agent": "video-channel-manager-milovi-exact-canary/2"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        source = response.read()
    if len(source) != SOURCE_BYTE_SIZE:
        raise SystemExit("source byte-size mismatch")
    git_blob = hashlib.sha1(
        f"blob {len(source)}\0".encode("ascii") + source,
        usedforsecurity=False,
    ).hexdigest()
    if git_blob != SOURCE_BLOB_SHA1 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("source identity mismatch")

    with Image.open(io.BytesIO(source)) as image:
        image.load()
        if image.format != "WEBP" or image.size != (1024, 1536):
            raise SystemExit("source decode mismatch")
        rgb = image.convert("RGB")
    encoded = io.BytesIO()
    rgb.save(
        encoded,
        format="JPEG",
        quality=95,
        subsampling=0,
        optimize=False,
        progressive=False,
        exif=b"",
    )
    jpeg = encoded.getvalue()
    if len(jpeg) != TRANSPORT_BYTE_SIZE or hashlib.sha256(jpeg).hexdigest() != TRANSPORT_SHA256:
        raise SystemExit("deterministic JPEG transport drift")
    return jpeg, caption


def _fresh_target_preflight(token: str) -> None:
    me = _read_result(token, "getMe", {})
    if int(me["id"]) != BOT_ID or me.get("is_bot") is not True:
        raise SystemExit("fresh bot id mismatch")
    if str(me.get("username") or "").casefold() != BOT_USERNAME.casefold():
        raise SystemExit("fresh bot username mismatch")

    alias = _read_result(token, "getChat", {"chat_id": f"@{CHAT_USERNAME}"})
    numeric = _read_result(token, "getChat", {"chat_id": CHAT_ID})
    for chat in (alias, numeric):
        if int(chat["id"]) != CHAT_ID or str(chat.get("type") or "") != "channel":
            raise SystemExit("fresh target id/type mismatch")
        if str(chat.get("username") or "").casefold() != CHAT_USERNAME.casefold():
            raise SystemExit("fresh target username mismatch")

    membership = _read_result(token, "getChatMember", {"chat_id": CHAT_ID, "user_id": BOT_ID})
    member_user = membership.get("user")
    if not isinstance(member_user, dict):
        raise SystemExit("fresh membership proof has no user identity")
    if int(member_user["id"]) != BOT_ID or member_user.get("is_bot") is not True:
        raise SystemExit("fresh membership proof resolved a different identity")
    member_username = str(member_user.get("username") or "")
    if member_username and member_username.casefold() != BOT_USERNAME.casefold():
        raise SystemExit("fresh membership proof bot username mismatch")
    member_status = str(membership.get("status") or "")
    can_post = member_status == "creator" or membership.get("can_post_messages") is True
    if member_status not in {"administrator", "creator"} or not can_post:
        raise SystemExit("fresh membership proof lacks channel posting authority")


def _archive_prior_rejection(prior: dict[str, Any] | None) -> str | None:
    if prior is None:
        return None
    authorization_id = _authorization_id(prior)
    ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ATTEMPTS_DIR / f"{authorization_id}.json"
    archive_bytes = json.dumps(prior, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    if archive_path.exists() and archive_path.read_bytes() != archive_bytes:
        raise SystemExit("existing rejected-attempt archive disagrees with canonical prior state")
    archive_path.write_bytes(archive_bytes)
    return archive_path.as_posix()


def prepare() -> int:
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise SystemExit("GitHub rerun forbidden for exact canary")
    auth = _json_object(AUTH_PATH)
    prior = _validate_authorization(auth)
    jpeg, caption = _materialize_payload()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    _fresh_target_preflight(token)
    prior_archive = _archive_prior_rejection(prior)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "p18.jpg").write_bytes(jpeg)
    (RUNTIME_DIR / "caption.txt").write_text(caption, encoding="utf-8")
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_name": "video-channel-manager.milovi-exact-canary-dispatch-state",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": "milovi-cake-canary-001",
        "status": "dispatch_started",
        "provider_effect": "may_exist_after_next_step",
        "authorization_commit_sha": os.environ["GITHUB_SHA"],
        "authorization_id": _authorization_id(auth),
        "supersedes_authorization_id": auth.get("supersedes_authorization_id"),
        "prior_state_archive": prior_archive,
        "chat_id": CHAT_ID,
        "chat_username": CHAT_USERNAME,
        "bot_id": BOT_ID,
        "bot_username": BOT_USERNAME,
        "membership_preflight": "administrator_with_can_post_messages_proved",
        "transport_sha256": f"sha256:{TRANSPORT_SHA256}",
        "caption_sha256": CAPTION_SHA256,
        "github_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "github_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "dispatch_started_at_utc": datetime.now(tz=UTC).isoformat(),
        "provider_write_may_have_occurred": False,
        "last_durable_stage": "dispatch_barrier_committed",
        "retry_policy": "never_replay",
        "required_next_action": "execute_exact_authorized_send_once",
        "automatic_replay_allowed": False,
        "message_id": None,
        "message_url": None,
    }
    _write_state(state)
    print(json.dumps({"status": "prepared", "chat_id": CHAT_ID, "provider_write_performed": False}))
    return 0


def _record_dispatch_started(state: dict[str, Any]) -> None:
    state.update(
        {
            "provider_write_may_have_occurred": True,
            "last_durable_stage": "dispatch_started",
            "retry_policy": "never_replay",
            "required_next_action": "read_reconcile_exact_message_identity_if_process_stops",
            "automatic_replay_allowed": False,
        }
    )
    _write_state(state)


def _record_unknown_outcome(
    state: dict[str, Any],
    *,
    failure_type: str,
    detail: str,
    last_durable_stage: str,
    http_status: int | None = None,
) -> None:
    state.update(
        {
            "status": "unknown_requires_reconciliation",
            "provider_effect": "may_exist",
            "provider_write_may_have_occurred": True,
            "last_durable_stage": last_durable_stage,
            "retry_policy": "never_replay",
            "required_next_action": "read_reconcile_exact_message_identity",
            "automatic_replay_allowed": False,
            "stop_recorded_at_utc": datetime.now(tz=UTC).isoformat(),
            "stop_failure_type": failure_type,
            "stop_detail": detail,
        }
    )
    if http_status is not None:
        state["provider_http_status"] = http_status
    _write_state(state)


def _stop_unknown(
    state: dict[str, Any],
    *,
    failure_type: str,
    detail: str,
    last_durable_stage: str,
    exit_code: int = 75,
    http_status: int | None = None,
) -> NoReturn:
    _record_unknown_outcome(
        state,
        failure_type=failure_type,
        detail=detail,
        last_durable_stage=last_durable_stage,
        http_status=http_status,
    )
    raise SystemExit(exit_code)


def _record_deterministic_rejection(state: dict[str, Any], status: int, description: str) -> None:
    state.update(
        {
            "status": "provider_rejected",
            "provider_effect": "rejected_before_message_creation",
            "provider_write_may_have_occurred": False,
            "last_durable_stage": "provider_rejected_before_message_creation",
            "retry_policy": "requires_new_reviewed_successor_authorization",
            "required_next_action": "review_rejection_and_issue_explicit_successor_authorization",
            "provider_response_at_utc": datetime.now(tz=UTC).isoformat(),
            "provider_http_status": status,
            "provider_description": description,
            "message_id": None,
            "message_url": None,
            "automatic_replay_allowed": False,
        }
    )
    _write_state(state)


def send() -> int:
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise SystemExit("GitHub rerun forbidden for exact canary")
    state = _json_object(STATE_PATH)
    if state.get("status") != "dispatch_started" or state.get("message_id") is not None:
        raise SystemExit("dispatch-started barrier missing or already consumed")
    if state.get("authorization_commit_sha") != os.environ.get("GITHUB_SHA"):
        raise SystemExit("dispatch state is not bound to this authorization commit")

    jpeg = (RUNTIME_DIR / "p18.jpg").read_bytes()
    caption = (RUNTIME_DIR / "caption.txt").read_text(encoding="utf-8")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    _record_dispatch_started(state)
    try:
        status, body = _telegram_call(
            token,
            "sendPhoto",
            data={"chat_id": str(CHAT_ID), "caption": caption},
            files={"photo": ("p18.jpg", jpeg, "image/jpeg")},
            retries=0,
        )
    except (httpx.TimeoutException, httpx.TransportError, RuntimeError) as exc:
        _record_unknown_outcome(
            state,
            failure_type="transport_or_response_decode_error",
            detail=f"{type(exc).__name__}: {exc}",
            last_durable_stage="dispatch_started",
        )
        print(
            "Telegram transport outcome is unknown; structured reconciliation evidence persisted; automatic replay forbidden",
            file=sys.stderr,
        )
        raise SystemExit(75) from exc

    if status != 200 or body.get("ok") is not True:
        description = str(body.get("description") or "")
        if 400 <= status < 500 and body.get("ok") is False:
            _record_deterministic_rejection(state, status, description)
            print(
                f"Telegram rejected exact canary HTTP={status} description={description}; no automatic replay",
                file=sys.stderr,
            )
            raise SystemExit(76)
        _record_unknown_outcome(
            state,
            failure_type="non_terminal_provider_response",
            detail=description or f"HTTP {status} without terminal rejection proof",
            last_durable_stage="provider_response_received",
            http_status=status,
        )
        print(
            f"Telegram returned non-terminal failure HTTP={status}; structured reconciliation evidence persisted; no automatic replay",
            file=sys.stderr,
        )
        raise SystemExit(75)

    message = body.get("result")
    if not isinstance(message, dict):
        _stop_unknown(
            state,
            failure_type="malformed_success_response",
            detail="Telegram success response has no message",
            last_durable_stage="provider_success_response_received",
        )
    chat = message.get("chat")
    if not isinstance(chat, dict):
        _stop_unknown(
            state,
            failure_type="malformed_success_response",
            detail="Telegram success response has no chat identity",
            last_durable_stage="provider_success_response_received",
        )
    if int(chat["id"]) != CHAT_ID or str(chat.get("type") or "") != "channel":
        _stop_unknown(
            state,
            failure_type="success_identity_mismatch",
            detail="Telegram returned unexpected chat id/type",
            last_durable_stage="provider_success_response_received",
        )
    if str(chat.get("username") or "").casefold() != CHAT_USERNAME.casefold():
        _stop_unknown(
            state,
            failure_type="success_identity_mismatch",
            detail="Telegram returned unexpected chat username",
            last_durable_stage="provider_success_response_received",
        )
    if str(message.get("caption") or "") != caption:
        _stop_unknown(
            state,
            failure_type="success_payload_mismatch",
            detail="Telegram returned caption drift",
            last_durable_stage="provider_success_response_received",
        )
    photos = message.get("photo")
    if not isinstance(photos, list) or not photos:
        _stop_unknown(
            state,
            failure_type="success_payload_mismatch",
            detail="Telegram returned no photo collection",
            last_durable_stage="provider_success_response_received",
        )
    message_id = int(message["message_id"])
    if message_id <= 0:
        _stop_unknown(
            state,
            failure_type="success_identity_mismatch",
            detail="Telegram returned invalid message_id",
            last_durable_stage="provider_success_response_received",
        )

    state.update(
        {
            "status": "verified",
            "provider_effect": "verified",
            "provider_write_may_have_occurred": True,
            "last_durable_stage": "verified",
            "retry_policy": "never_replay",
            "required_next_action": "none",
            "verified_at_utc": datetime.now(tz=UTC).isoformat(),
            "message_id": message_id,
            "message_url": f"https://t.me/{CHAT_USERNAME}/{message_id}",
            "returned_chat_id": int(chat["id"]),
            "returned_chat_username": str(chat.get("username") or ""),
            "returned_photo_count": len(photos),
            "automatic_replay_allowed": False,
        }
    )
    _write_state(state)
    print(
        json.dumps(
            {
                "status": "verified",
                "message_id": message_id,
                "message_url": state["message_url"],
                "provider_effect": "verified",
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "send"}:
        raise SystemExit("usage: python -m video_channel_manager.milovi_telegram_live_canary prepare|send")
    return prepare() if sys.argv[1] == "prepare" else send()


if __name__ == "__main__":
    raise SystemExit(main())
