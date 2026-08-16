from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import subprocess
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import httpx
from PIL import Image

AUTH_PATH = pathlib.Path("content/telegram/milovi-cake/live/canary-authorization.json")
STATE_PATH = pathlib.Path("content/telegram/milovi-cake/live/canary-dispatch-state.json")
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


def _read_api(token: str, method: str, payload: dict[str, object]) -> dict[str, object]:
    with httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=2),
        trust_env=False,
    ) as client:
        response = client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
    try:
        body = response.json()
    except ValueError as exc:
        raise SystemExit(f"{method}: non-JSON HTTP {response.status_code}") from exc
    if response.status_code != 200 or not isinstance(body, dict) or body.get("ok") is not True:
        raise SystemExit(f"{method}: read-only preflight failed")
    result = body.get("result")
    if not isinstance(result, dict):
        raise SystemExit(f"{method}: malformed result")
    return result


def _validate_authorization(auth: dict[str, object]) -> None:
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
    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], text=True).strip()
    if parent != auth.get("expected_parent_main_sha"):
        raise SystemExit("authorization parent differs from reviewed main")
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD^", "HEAD"], text=True).splitlines()
    if changed != [AUTH_PATH.as_posix()]:
        raise SystemExit(f"authorization commit contains unexpected files: {changed}")
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        raise SystemExit(f"canary state already exists; replay forbidden: {state.get('status')}")


def _materialize_payload() -> tuple[bytes, str]:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    if candidate.get("publication_id") != "milovi-cake-canary-001" or candidate.get("operation") != "sendPhoto":
        raise SystemExit("candidate identity mismatch")
    caption = str(candidate["caption"]["text"])
    if f"sha256:{hashlib.sha256(caption.encode('utf-8')).hexdigest()}" != CAPTION_SHA256:
        raise SystemExit("caption digest mismatch")
    if len(caption) > 1024:
        raise SystemExit("caption exceeds Telegram photo limit")

    safe_path = "/".join(urllib.parse.quote(part, safe="") for part in SOURCE_PATH.split("/"))
    request = urllib.request.Request(
        f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/{safe_path}",
        headers={"User-Agent": "video-channel-manager-milovi-exact-canary/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        source = response.read()
    if len(source) != SOURCE_BYTE_SIZE:
        raise SystemExit("source byte-size mismatch")
    git_blob = hashlib.sha1(f"blob {len(source)}\0".encode("ascii") + source, usedforsecurity=False).hexdigest()
    if git_blob != SOURCE_BLOB_SHA1 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("source identity mismatch")

    with Image.open(io.BytesIO(source)) as image:
        image.load()
        if image.format != "WEBP" or image.size != (1024, 1536):
            raise SystemExit("source decode mismatch")
        rgb = image.convert("RGB")
    encoded = io.BytesIO()
    rgb.save(encoded, format="JPEG", quality=95, subsampling=0, optimize=False, progressive=False, exif=b"")
    jpeg = encoded.getvalue()
    if len(jpeg) != TRANSPORT_BYTE_SIZE or hashlib.sha256(jpeg).hexdigest() != TRANSPORT_SHA256:
        raise SystemExit("deterministic JPEG transport drift")
    return jpeg, caption


def _fresh_target_preflight(token: str) -> None:
    me = _read_api(token, "getMe", {})
    if int(me["id"]) != BOT_ID or me.get("is_bot") is not True:
        raise SystemExit("fresh bot id mismatch")
    if str(me.get("username") or "").casefold() != BOT_USERNAME.casefold():
        raise SystemExit("fresh bot username mismatch")
    alias = _read_api(token, "getChat", {"chat_id": f"@{CHAT_USERNAME}"})
    numeric = _read_api(token, "getChat", {"chat_id": CHAT_ID})
    for chat in (alias, numeric):
        if int(chat["id"]) != CHAT_ID or str(chat.get("type") or "") != "channel":
            raise SystemExit("fresh target id/type mismatch")
        if str(chat.get("username") or "").casefold() != CHAT_USERNAME.casefold():
            raise SystemExit("fresh target username mismatch")


def main() -> int:
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise SystemExit("GitHub rerun forbidden for exact canary")
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    _validate_authorization(auth)
    jpeg, caption = _materialize_payload()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    _fresh_target_preflight(token)

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
        "authorization_id": auth["authorization_id"],
        "chat_id": CHAT_ID,
        "chat_username": CHAT_USERNAME,
        "bot_id": BOT_ID,
        "transport_sha256": f"sha256:{TRANSPORT_SHA256}",
        "caption_sha256": CAPTION_SHA256,
        "github_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "github_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "dispatch_started_at_utc": datetime.now(tz=UTC).isoformat(),
        "message_id": None,
        "message_url": None,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prepared", "chat_id": CHAT_ID, "provider_write_performed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
