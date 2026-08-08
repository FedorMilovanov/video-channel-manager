from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
import typer
from rich.console import Console

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube import (
    InstalledClientConfig,
    InstalledOAuthFlow,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YouTubeApiClient,
)

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_UPLOAD_BASE_URL = "https://www.googleapis.com/upload/youtube/v3"
_INTENT_SCHEMA = "video-manager.youtube-video-upload-intent"
_INTENT_VERSION = "1.0"
_RESULT_SCHEMA = "video-manager.youtube-video-upload-result"
_RESULT_VERSION = "1.0"
_RANGE_RE = re.compile(r"^bytes=0-(?P<last>\d+)$")
_DEFAULT_CHUNK_SIZE = 16 * 1024 * 1024

console = Console()
app = typer.Typer(no_args_is_help=True, help="Guarded exact-file YouTube video upload.")

ProviderEffect = Literal["not_dispatched", "confirmed_absent", "may_exist", "verified"]


class UploadGuardError(RuntimeError):
    pass


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadGuardError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UploadGuardError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _intent_payload_without_digest(intent: dict[str, Any]) -> dict[str, Any]:
    payload = dict(intent)
    payload.pop("intent_sha256", None)
    return payload


def _intent_digest(intent: dict[str, Any]) -> str:
    return _canonical_sha256(_intent_payload_without_digest(intent))


def _journal_path(data_dir: Path, intent_sha256: str) -> Path:
    key = intent_sha256.removeprefix("sha256:")
    return data_dir.resolve() / "youtube" / "upload-intents" / f"{key}.json"


def _config_and_store(account: str) -> tuple[InstalledClientConfig, TokenStore]:
    settings = get_settings()
    config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
    store = TokenStore(settings.data_dir)
    store.validate_alias(account)
    return config, store


def _access_token(config: InstalledClientConfig, store: TokenStore, account: str) -> str:
    token = store.load_token(account)
    if YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
        raise UploadGuardError(
            "Stored OAuth token has no YouTube write scope. Run: "
            f"video-manager youtube login --account {account} --write --force"
        )
    if token.needs_refresh():
        token = InstalledOAuthFlow(config).refresh(token)
        store.save_token(account, token)
    return token.access_token


def _verify_channel(account: str, expected_channel_id: str) -> None:
    config, store = _config_and_store(account)
    client = YouTubeApiClient(client_config=config, token_store=store, account_alias=account)
    channels = client.list_my_channels()
    ids = {item.ref.remote_id for item in channels}
    if expected_channel_id not in ids:
        joined = ", ".join(sorted(ids)) or "none"
        raise UploadGuardError(
            f"OAuth alias '{account}' does not expose expected channel {expected_channel_id}; got: {joined}"
        )


def _validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_name") != "video-manager.youtube-video-upload-spec":
        raise UploadGuardError("Unexpected upload spec schema_name.")
    if spec.get("schema_version") != "1.0":
        raise UploadGuardError("Unexpected upload spec schema_version.")
    expected = spec.get("expected_media_sha256")
    if not isinstance(expected, str) or not expected.startswith("sha256:") or len(expected) != 71:
        raise UploadGuardError("Spec expected_media_sha256 is invalid.")
    if spec.get("privacy_status") != "private":
        raise UploadGuardError("Guarded first upload must be private.")
    target = spec.get("target_channel_id")
    if not isinstance(target, str) or not target.startswith("UC"):
        raise UploadGuardError("Spec target_channel_id is invalid.")
    title = spec.get("title")
    description = spec.get("description")
    tags = spec.get("tags")
    if not isinstance(title, str) or not title.strip():
        raise UploadGuardError("Spec title is blank.")
    if not isinstance(description, str):
        raise UploadGuardError("Spec description must be a string.")
    if not isinstance(tags, list) or not all(isinstance(item, str) and item.strip() for item in tags):
        raise UploadGuardError("Spec tags must be non-empty strings.")


def _build_intent(spec: dict[str, Any], video: Path, account: str) -> dict[str, Any]:
    resolved = video.expanduser().resolve()
    if not resolved.is_file():
        raise UploadGuardError(f"Video file not found: {resolved}")
    actual_sha = _sha256_file(resolved)
    if actual_sha != spec["expected_media_sha256"]:
        raise UploadGuardError(
            f"Video SHA mismatch: expected {spec['expected_media_sha256']} actual {actual_sha}"
        )
    intent: dict[str, Any] = {
        "schema_name": _INTENT_SCHEMA,
        "schema_version": _INTENT_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "account_alias": account,
        "target_channel_id": spec["target_channel_id"],
        "media_path": str(resolved),
        "media_sha256": actual_sha,
        "media_size_bytes": resolved.stat().st_size,
        "mime_type": "video/mp4",
        "notify_subscribers": False,
        "snippet": {
            "title": spec["title"],
            "description": spec["description"],
            "tags": spec["tags"],
            "categoryId": str(spec.get("category_id", "10")),
            "defaultLanguage": str(spec.get("default_language", "ru")),
        },
        "status": {
            "privacyStatus": "private",
            "embeddable": bool(spec.get("embeddable", True)),
            "license": str(spec.get("license", "youtube")),
            "selfDeclaredMadeForKids": bool(spec.get("self_declared_made_for_kids", False)),
            "containsSyntheticMedia": bool(spec.get("contains_synthetic_media", True)),
        },
        "provider_write_authorized": False,
        "provider_effect": "not_dispatched",
    }
    intent["intent_sha256"] = _intent_digest(intent)
    return intent


def _load_and_validate_intent(path: Path) -> dict[str, Any]:
    intent = _read_json(path)
    if intent.get("schema_name") != _INTENT_SCHEMA or intent.get("schema_version") != _INTENT_VERSION:
        raise UploadGuardError("Unexpected upload intent schema.")
    recorded = intent.get("intent_sha256")
    if not isinstance(recorded, str) or recorded != _intent_digest(intent):
        raise UploadGuardError("Upload intent SHA-256 does not match canonical content.")
    if intent.get("target_channel_id") is None or intent.get("media_sha256") is None:
        raise UploadGuardError("Upload intent is incomplete.")
    status = intent.get("status")
    if not isinstance(status, dict) or status.get("privacyStatus") != "private":
        raise UploadGuardError("Only a private first upload is allowed.")
    return intent


def _request_json_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[-2000:]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)
    return str(payload)[-2000:]


def _mark_journal(
    journal_path: Path,
    *,
    intent: dict[str, Any],
    state: str,
    provider_effect: ProviderEffect,
    upload_session_uri: str | None = None,
    video_id: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_name": "video-manager.youtube-video-upload-journal",
        "schema_version": "1.0",
        "updated_at": datetime.now(UTC).isoformat(),
        "intent_sha256": intent["intent_sha256"],
        "account_alias": intent["account_alias"],
        "target_channel_id": intent["target_channel_id"],
        "media_sha256": intent["media_sha256"],
        "state": state,
        "provider_effect": provider_effect,
        "upload_session_uri": upload_session_uri,
        "video_id": video_id,
        "detail": detail,
    }
    _write_json(journal_path, payload)
    return payload


def _parse_resume_offset(response: httpx.Response) -> int:
    if response.status_code != 308:
        raise UploadGuardError(f"Expected HTTP 308 resume response, got {response.status_code}.")
    raw_range = response.headers.get("Range")
    if raw_range is None:
        return 0
    match = _RANGE_RE.fullmatch(raw_range.strip())
    if match is None:
        raise UploadGuardError(f"Unexpected resumable Range header: {raw_range!r}")
    return int(match.group("last")) + 1


def _readback(
    client: httpx.Client,
    *,
    token: str,
    video_id: str,
    expected_channel_id: str,
    intent: dict[str, Any],
) -> dict[str, Any]:
    response = client.get(
        f"{_API_BASE_URL}/videos",
        params={"part": "snippet,status", "id": video_id, "maxResults": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        raise UploadGuardError(
            f"YouTube readback HTTP {response.status_code}: {_request_json_error(response)}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise UploadGuardError("YouTube readback returned non-object JSON.")
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise UploadGuardError(f"YouTube readback did not return exact video ID {video_id}.")
    item = items[0]
    snippet = item.get("snippet")
    status = item.get("status")
    if not isinstance(snippet, dict) or not isinstance(status, dict):
        raise UploadGuardError("YouTube readback is missing snippet/status.")
    if str(snippet.get("channelId") or "") != expected_channel_id:
        raise UploadGuardError("Uploaded video readback belongs to a different channel.")
    expected_snippet = intent["snippet"]
    expected_status = intent["status"]
    for key in ("title", "description", "categoryId", "defaultLanguage"):
        if snippet.get(key) != expected_snippet.get(key):
            raise UploadGuardError(f"Uploaded video readback mismatch: snippet.{key}")
    if list(snippet.get("tags") or []) != list(expected_snippet.get("tags") or []):
        raise UploadGuardError("Uploaded video readback mismatch: snippet.tags")
    for key in ("privacyStatus", "embeddable", "license", "selfDeclaredMadeForKids", "containsSyntheticMedia"):
        if status.get(key) != expected_status.get(key):
            raise UploadGuardError(f"Uploaded video readback mismatch: status.{key}")
    return item


def _resume_upload(
    *,
    intent: dict[str, Any],
    journal_path: Path,
    session_uri: str,
    token: str,
    start_offset: int,
    chunk_size: int,
) -> str:
    media = Path(str(intent["media_path"])).expanduser().resolve()
    total = int(intent["media_size_bytes"])
    if _sha256_file(media) != intent["media_sha256"]:
        raise UploadGuardError("Media SHA changed after intent creation.")
    if media.stat().st_size != total:
        raise UploadGuardError("Media size changed after intent creation.")
    if start_offset < 0 or start_offset > total:
        raise UploadGuardError(f"Invalid resume offset: {start_offset}")

    headers_base = {
        "Authorization": f"Bearer {token}",
        "Content-Type": str(intent["mime_type"]),
    }
    with httpx.Client(timeout=httpx.Timeout(connect=30.0, read=180.0, write=180.0, pool=30.0)) as client:
        offset = start_offset
        with media.open("rb") as handle:
            handle.seek(offset)
            while offset < total:
                chunk = handle.read(min(chunk_size, total - offset))
                if not chunk:
                    raise UploadGuardError("Unexpected EOF while reading media.")
                end = offset + len(chunk) - 1
                headers = dict(headers_base)
                headers["Content-Length"] = str(len(chunk))
                headers["Content-Range"] = f"bytes {offset}-{end}/{total}"
                try:
                    response = client.put(session_uri, headers=headers, content=chunk)
                except httpx.HTTPError as exc:
                    _mark_journal(
                        journal_path,
                        intent=intent,
                        state="upload_unknown",
                        provider_effect="may_exist",
                        upload_session_uri=session_uri,
                        detail=f"Transport ambiguity during media PUT at offset {offset}: {type(exc).__name__}",
                    )
                    raise UploadGuardError(
                        "Upload outcome is ambiguous. Do NOT start a new upload. "
                        "Use the resume command with this same intent."
                    ) from exc

                if response.status_code == 308:
                    confirmed = _parse_resume_offset(response)
                    if confirmed <= offset:
                        raise UploadGuardError(
                            f"YouTube did not advance resumable offset: sent from {offset}, confirmed {confirmed}"
                        )
                    offset = confirmed
                    handle.seek(offset)
                    _mark_journal(
                        journal_path,
                        intent=intent,
                        state="uploading",
                        provider_effect="may_exist",
                        upload_session_uri=session_uri,
                        detail=f"Confirmed uploaded bytes: 0-{offset - 1}",
                    )
                    continue

                if response.status_code in {200, 201}:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        _mark_journal(
                            journal_path,
                            intent=intent,
                            state="upload_unknown",
                            provider_effect="may_exist",
                            upload_session_uri=session_uri,
                            detail="Final media PUT returned non-JSON success response.",
                        )
                        raise UploadGuardError(
                            "Upload may have completed but the response was unusable. "
                            "Do NOT start a new upload; reconcile the existing session."
                        ) from exc
                    if not isinstance(payload, dict) or not payload.get("id"):
                        raise UploadGuardError("Final YouTube upload response has no video ID.")
                    return str(payload["id"])

                if 400 <= response.status_code < 500:
                    _mark_journal(
                        journal_path,
                        intent=intent,
                        state="rejected",
                        provider_effect="confirmed_absent",
                        upload_session_uri=session_uri,
                        detail=f"Media PUT rejected HTTP {response.status_code}: {_request_json_error(response)}",
                    )
                    raise UploadGuardError(
                        f"YouTube rejected media upload HTTP {response.status_code}: {_request_json_error(response)}"
                    )

                _mark_journal(
                    journal_path,
                    intent=intent,
                    state="upload_unknown",
                    provider_effect="may_exist",
                    upload_session_uri=session_uri,
                    detail=f"Media PUT HTTP {response.status_code}; manual resume required.",
                )
                raise UploadGuardError(
                    f"YouTube media upload returned HTTP {response.status_code}. "
                    "Do NOT start a new upload; use resume on the same session."
                )
    raise UploadGuardError("Upload loop ended without a final video ID.")


@app.command("plan")
def plan(
    spec: Annotated[Path, typer.Option("--spec", help="Canonical upload spec JSON")],
    video: Annotated[Path, typer.Option("--video", help="Exact local MP4")],
    account: Annotated[str, typer.Option("--account")] = "legendary-poet",
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """Perform live read-only channel preflight and freeze an exact upload intent."""

    settings = get_settings()
    try:
        spec_payload = _read_json(spec)
        _validate_spec(spec_payload)
        _verify_channel(account, str(spec_payload["target_channel_id"]))
        intent = _build_intent(spec_payload, video, account)
        journal = _journal_path(settings.data_dir, str(intent["intent_sha256"]))
        if journal.is_file():
            previous = _read_json(journal)
            if previous.get("provider_effect") in {"may_exist", "verified"}:
                raise UploadGuardError(
                    f"Existing durable journal blocks a new plan: {journal} "
                    f"(provider_effect={previous.get('provider_effect')})"
                )
        _mark_journal(
            journal,
            intent=intent,
            state="planned",
            provider_effect="not_dispatched",
            detail="Fresh read-only channel preflight passed. No provider write dispatched.",
        )
        if output is None:
            output = Path("operator-output") / "black-man-youtube-upload-intent.json"
        _write_json(output, intent)
    except (OSError, ValueError, UploadGuardError) as exc:
        console.print(f"[red]Upload plan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print("[green]UPLOAD PLAN READY — NO PROVIDER WRITE.[/green]")
    console.print(f"Channel: {intent['target_channel_id']}")
    console.print(f"Media SHA: {intent['media_sha256']}")
    console.print(f"Title: {intent['snippet']['title']}")
    console.print(f"Privacy: {intent['status']['privacyStatus']}")
    console.print(f"Intent: {intent['intent_sha256']}")
    console.print(f"OPEN/SEND THIS FILE: {output.resolve()}")
    console.print(f"Authorization phrase for a later execute: UPLOAD:{intent['intent_sha256']}")


@app.command("execute")
def execute(
    intent_path: Annotated[Path, typer.Option("--intent", help="Frozen upload intent JSON")],
    confirm: Annotated[str, typer.Option("--confirm", help="Exact UPLOAD:sha256:... confirmation")],
    chunk_size_mib: Annotated[int, typer.Option("--chunk-size-mib", min=1, max=64)] = 16,
) -> None:
    """Execute one exact private upload after explicit digest-bound authorization."""

    settings = get_settings()
    try:
        intent = _load_and_validate_intent(intent_path)
        required = f"UPLOAD:{intent['intent_sha256']}"
        if confirm != required:
            raise UploadGuardError(f"Exact confirmation required: {required}")
        _verify_channel(str(intent["account_alias"]), str(intent["target_channel_id"]))

        media = Path(str(intent["media_path"])).expanduser().resolve()
        if not media.is_file():
            raise UploadGuardError(f"Media file not found: {media}")
        if _sha256_file(media) != intent["media_sha256"]:
            raise UploadGuardError("Media SHA changed after intent creation.")
        if media.stat().st_size != int(intent["media_size_bytes"]):
            raise UploadGuardError("Media size changed after intent creation.")

        config, store = _config_and_store(str(intent["account_alias"]))
        token = _access_token(config, store, str(intent["account_alias"]))
        journal_path = _journal_path(settings.data_dir, str(intent["intent_sha256"]))
        if journal_path.is_file():
            existing = _read_json(journal_path)
            effect = existing.get("provider_effect")
            state = existing.get("state")
            if effect == "verified":
                raise UploadGuardError(f"Intent already completed with video ID {existing.get('video_id')}.")
            if effect == "may_exist" or state not in {"planned", "rejected"}:
                raise UploadGuardError(
                    f"Durable journal blocks a new videos.insert: state={state} provider_effect={effect}. "
                    "Use resume/reconciliation instead."
                )

        _mark_journal(
            journal_path,
            intent=intent,
            state="dispatching",
            provider_effect="may_exist",
            detail="Durable intent persisted before videos.insert session creation.",
        )

        body = {"snippet": intent["snippet"], "status": intent["status"]}
        media_size = int(intent["media_size_bytes"])
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(media_size),
            "X-Upload-Content-Type": str(intent["mime_type"]),
        }
        params = {
            "uploadType": "resumable",
            "part": "snippet,status",
            "notifySubscribers": "false",
        }
        with httpx.Client(timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0)) as client:
            try:
                response = client.post(
                    f"{_UPLOAD_BASE_URL}/videos",
                    params=params,
                    headers=headers,
                    json=body,
                )
            except httpx.HTTPError as exc:
                _mark_journal(
                    journal_path,
                    intent=intent,
                    state="session_unknown",
                    provider_effect="may_exist",
                    detail=f"Transport ambiguity during videos.insert session creation: {type(exc).__name__}",
                )
                raise UploadGuardError(
                    "videos.insert session outcome is ambiguous. Do NOT retry or start another upload."
                ) from exc

        if response.status_code != 200:
            if 400 <= response.status_code < 500:
                _mark_journal(
                    journal_path,
                    intent=intent,
                    state="rejected",
                    provider_effect="confirmed_absent",
                    detail=f"Session creation rejected HTTP {response.status_code}: {_request_json_error(response)}",
                )
            else:
                _mark_journal(
                    journal_path,
                    intent=intent,
                    state="session_unknown",
                    provider_effect="may_exist",
                    detail=f"Session creation HTTP {response.status_code}: {_request_json_error(response)}",
                )
            raise UploadGuardError(
                f"YouTube resumable-session creation HTTP {response.status_code}: {_request_json_error(response)}"
            )

        session_uri = response.headers.get("Location")
        if not session_uri:
            _mark_journal(
                journal_path,
                intent=intent,
                state="session_unknown",
                provider_effect="may_exist",
                detail="YouTube returned 200 but no resumable Location header.",
            )
            raise UploadGuardError("YouTube returned no resumable upload session URI. Do NOT retry videos.insert.")

        _mark_journal(
            journal_path,
            intent=intent,
            state="uploading",
            provider_effect="may_exist",
            upload_session_uri=session_uri,
            detail="Resumable upload session created; media upload begins.",
        )
        video_id = _resume_upload(
            intent=intent,
            journal_path=journal_path,
            session_uri=session_uri,
            token=token,
            start_offset=0,
            chunk_size=chunk_size_mib * 1024 * 1024,
        )

        _mark_journal(
            journal_path,
            intent=intent,
            state="uploaded_pending_readback",
            provider_effect="may_exist",
            upload_session_uri=session_uri,
            video_id=video_id,
            detail="YouTube returned a video ID; exact readback required.",
        )
        with httpx.Client(timeout=45.0) as client:
            readback = _readback(
                client,
                token=token,
                video_id=video_id,
                expected_channel_id=str(intent["target_channel_id"]),
                intent=intent,
            )
        result: dict[str, Any] = {
            "schema_name": _RESULT_SCHEMA,
            "schema_version": _RESULT_VERSION,
            "completed_at": datetime.now(UTC).isoformat(),
            "intent_sha256": intent["intent_sha256"],
            "target_channel_id": intent["target_channel_id"],
            "media_sha256": intent["media_sha256"],
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "provider_effect": "verified",
            "verified_readback": readback,
            "thumbnail_applied": False,
            "playlist_mutated": False,
            "visibility_changed_after_upload": False,
        }
        result["result_sha256"] = _canonical_sha256(result)
        output = Path("operator-output") / "black-man-youtube-upload-result.json"
        _write_json(output, result)
        _mark_journal(
            journal_path,
            intent=intent,
            state="verified",
            provider_effect="verified",
            upload_session_uri=session_uri,
            video_id=video_id,
            detail=f"Exact private upload readback verified. Result: {output.resolve()}",
        )
    except (OSError, ValueError, UploadGuardError, httpx.HTTPError) as exc:
        console.print(f"[red]Upload execution stopped:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print("[bold green]PRIVATE YOUTUBE UPLOAD VERIFIED.[/bold green]")
    console.print(f"Video ID: {video_id}")
    console.print(f"URL: https://www.youtube.com/watch?v={video_id}")
    console.print(f"OPEN/SEND THIS FILE: {output.resolve()}")
    console.print("Thumbnail / playlist / public visibility: NOT DISPATCHED.")


@app.command("resume")
def resume(
    intent_path: Annotated[Path, typer.Option("--intent")],
    confirm: Annotated[str, typer.Option("--confirm", help="Exact RESUME:sha256:... confirmation")],
    chunk_size_mib: Annotated[int, typer.Option("--chunk-size-mib", min=1, max=64)] = 16,
) -> None:
    """Reconcile and continue the same resumable session; never creates another videos.insert."""

    settings = get_settings()
    try:
        intent = _load_and_validate_intent(intent_path)
        required = f"RESUME:{intent['intent_sha256']}"
        if confirm != required:
            raise UploadGuardError(f"Exact confirmation required: {required}")
        _verify_channel(str(intent["account_alias"]), str(intent["target_channel_id"]))
        config, store = _config_and_store(str(intent["account_alias"]))
        token = _access_token(config, store, str(intent["account_alias"]))
        journal_path = _journal_path(settings.data_dir, str(intent["intent_sha256"]))
        if not journal_path.is_file():
            raise UploadGuardError("No durable upload journal exists for this intent.")
        journal = _read_json(journal_path)
        if journal.get("provider_effect") == "verified":
            raise UploadGuardError(f"Intent is already verified as video {journal.get('video_id')}.")
        session_uri = journal.get("upload_session_uri")
        if not isinstance(session_uri, str) or not session_uri:
            raise UploadGuardError(
                "No known resumable session URI. A new videos.insert is forbidden; manual reconciliation is required."
            )
        media_size = int(intent["media_size_bytes"])
        with httpx.Client(timeout=60.0) as client:
            response = client.put(
                session_uri,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Length": "0",
                    "Content-Range": f"bytes */{media_size}",
                },
                content=b"",
            )
        if response.status_code in {200, 201}:
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("id"):
                raise UploadGuardError("Completed session response has no video ID.")
            video_id = str(payload["id"])
        elif response.status_code == 308:
            offset = _parse_resume_offset(response)
            video_id = _resume_upload(
                intent=intent,
                journal_path=journal_path,
                session_uri=session_uri,
                token=token,
                start_offset=offset,
                chunk_size=chunk_size_mib * 1024 * 1024,
            )
        else:
            raise UploadGuardError(
                f"Session reconciliation HTTP {response.status_code}: {_request_json_error(response)}"
            )

        _mark_journal(
            journal_path,
            intent=intent,
            state="uploaded_pending_readback",
            provider_effect="may_exist",
            upload_session_uri=session_uri,
            video_id=video_id,
            detail="Same resumable session completed; exact readback required.",
        )
        with httpx.Client(timeout=45.0) as client:
            readback = _readback(
                client,
                token=token,
                video_id=video_id,
                expected_channel_id=str(intent["target_channel_id"]),
                intent=intent,
            )
        result: dict[str, Any] = {
            "schema_name": _RESULT_SCHEMA,
            "schema_version": _RESULT_VERSION,
            "completed_at": datetime.now(UTC).isoformat(),
            "intent_sha256": intent["intent_sha256"],
            "target_channel_id": intent["target_channel_id"],
            "media_sha256": intent["media_sha256"],
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "provider_effect": "verified",
            "verified_readback": readback,
            "thumbnail_applied": False,
            "playlist_mutated": False,
            "visibility_changed_after_upload": False,
        }
        result["result_sha256"] = _canonical_sha256(result)
        output = Path("operator-output") / "black-man-youtube-upload-result.json"
        _write_json(output, result)
        _mark_journal(
            journal_path,
            intent=intent,
            state="verified",
            provider_effect="verified",
            upload_session_uri=session_uri,
            video_id=video_id,
            detail=f"Resumed upload readback verified. Result: {output.resolve()}",
        )
    except (OSError, ValueError, UploadGuardError, httpx.HTTPError) as exc:
        console.print(f"[red]Upload resume stopped:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print("[bold green]RESUMED PRIVATE YOUTUBE UPLOAD VERIFIED.[/bold green]")
    console.print(f"Video ID: {video_id}")
    console.print(f"URL: https://www.youtube.com/watch?v={video_id}")
    console.print(f"OPEN/SEND THIS FILE: {output.resolve()}")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
