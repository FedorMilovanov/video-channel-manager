from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field

from video_channel_manager.telegram_html_entities import message_entities_match
from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload


class TelegramResearchRecoveryProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-research-recovery-probe"]
    schema_version: Literal[1]
    status: Literal["found", "not_found", "ambiguous", "webhook_configured"]
    publication_id: str
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_chat_id: int = Field(lt=0)
    expected_chat_username: str
    attempted_at_utc: datetime
    match_window_seconds: int = Field(ge=1, le=900)
    webhook_url_present: bool
    get_updates_called: bool
    get_updates_offset_sent: Literal[False] = False
    updates_confirmed: Literal[False] = False
    webhook_changed: Literal[False] = False
    provider_write_performed: Literal[False] = False
    examined_updates: int = Field(ge=0, le=100)
    matching_update_ids: tuple[int, ...]
    message_id: int | None = Field(default=None, gt=0)
    message_url: str | None = None
    message_date_utc: datetime | None = None
    github_sha: str | None = None
    historical_run_id: str
    historical_run_attempt: str
    historical_outcome_artifact_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _api_result(response: httpx.Response, *, method: str) -> Any:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError(f"Telegram {method} did not return ok=true")
    return payload.get("result")


def _post(
    client: httpx.Client,
    *,
    api_base: str,
    token: str,
    method: str,
    payload: dict[str, Any],
) -> Any:
    response = client.post(f"{api_base.rstrip('/')}/bot{token}/{method}", json=payload)
    return _api_result(response, method=method)


def _matching_channel_post(
    update: object,
    *,
    payload: GenericMessagePayload,
    expected_chat_id: int,
    expected_chat_username: str,
    earliest: datetime,
    latest: datetime,
) -> tuple[int, int, datetime] | None:
    if not isinstance(update, dict):
        return None
    try:
        update_id = int(update["update_id"])
    except (KeyError, TypeError, ValueError):
        return None
    post = update.get("channel_post")
    if not isinstance(post, dict):
        return None
    chat = post.get("chat")
    if not isinstance(chat, dict):
        return None
    try:
        chat_id = int(chat.get("id", 0))
        message_id = int(post.get("message_id", 0))
        message_date = datetime.fromtimestamp(int(post.get("date", 0)), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None
    if chat_id != expected_chat_id or message_id <= 0:
        return None
    if str(chat.get("username") or "").casefold() != expected_chat_username.casefold():
        return None
    if str(post.get("text") or "") != payload.expected_plain_text:
        return None
    if not message_entities_match(payload.expected_entities, post.get("entities")):
        return None
    if message_date < earliest or message_date > latest:
        return None
    return update_id, message_id, message_date


def probe_research_channel_post(
    *,
    payload: GenericMessagePayload,
    expected_chat_id: int,
    expected_chat_username: str,
    attempted_at_utc: datetime,
    match_window_seconds: int,
    token: str,
    historical_run_id: str,
    historical_run_attempt: str,
    historical_outcome_artifact_sha256: str,
    github_sha: str | None = None,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
) -> TelegramResearchRecoveryProbe:
    if attempted_at_utc.tzinfo is None:
        raise ValueError("attempted_at_utc must be timezone-aware")
    if not 1 <= match_window_seconds <= 900:
        raise ValueError("match_window_seconds must be between 1 and 900")

    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=2),
        trust_env=False,
    )
    try:
        webhook = _post(
            http_client,
            api_base=api_base,
            token=token,
            method="getWebhookInfo",
            payload={},
        )
        if not isinstance(webhook, dict):
            raise ValueError("Telegram getWebhookInfo returned invalid data")
        webhook_present = bool(str(webhook.get("url") or ""))
        common: dict[str, Any] = {
            "schema_name": "video-channel-manager.telegram-research-recovery-probe",
            "schema_version": 1,
            "publication_id": payload.publication_id,
            "provider_payload_sha256": payload.provider_payload_sha256,
            "expected_chat_id": expected_chat_id,
            "expected_chat_username": expected_chat_username,
            "attempted_at_utc": attempted_at_utc.astimezone(UTC),
            "match_window_seconds": match_window_seconds,
            "webhook_url_present": webhook_present,
            "get_updates_offset_sent": False,
            "updates_confirmed": False,
            "webhook_changed": False,
            "provider_write_performed": False,
            "github_sha": github_sha,
            "historical_run_id": historical_run_id,
            "historical_run_attempt": historical_run_attempt,
            "historical_outcome_artifact_sha256": historical_outcome_artifact_sha256,
        }
        if webhook_present:
            return TelegramResearchRecoveryProbe(
                status="webhook_configured",
                get_updates_called=False,
                examined_updates=0,
                matching_update_ids=(),
                **common,
            )

        # Deliberately omit offset and allowed_updates. Per Bot API semantics, an
        # update is confirmed only by a later offset; this probe must not advance
        # the queue or change the bot's allowed-update configuration.
        updates = _post(
            http_client,
            api_base=api_base,
            token=token,
            method="getUpdates",
            payload={"limit": 100, "timeout": 0},
        )
        if not isinstance(updates, list):
            raise ValueError("Telegram getUpdates returned invalid data")
        if len(updates) > 100:
            raise ValueError("Telegram getUpdates exceeded requested limit")

        attempted = attempted_at_utc.astimezone(UTC)
        earliest = attempted - timedelta(seconds=match_window_seconds)
        latest = attempted + timedelta(seconds=match_window_seconds)
        matches: list[tuple[int, int, datetime]] = []
        for update in updates:
            match = _matching_channel_post(
                update,
                payload=payload,
                expected_chat_id=expected_chat_id,
                expected_chat_username=expected_chat_username,
                earliest=earliest,
                latest=latest,
            )
            if match is not None:
                matches.append(match)

        if not matches:
            return TelegramResearchRecoveryProbe(
                status="not_found",
                get_updates_called=True,
                examined_updates=len(updates),
                matching_update_ids=(),
                **common,
            )
        if len(matches) > 1:
            return TelegramResearchRecoveryProbe(
                status="ambiguous",
                get_updates_called=True,
                examined_updates=len(updates),
                matching_update_ids=tuple(match[0] for match in matches),
                **common,
            )

        update_id, message_id, message_date = matches[0]
        return TelegramResearchRecoveryProbe(
            status="found",
            get_updates_called=True,
            examined_updates=len(updates),
            matching_update_ids=(update_id,),
            message_id=message_id,
            message_url=f"https://t.me/{expected_chat_username}/{message_id}",
            message_date_utc=message_date,
            **common,
        )
    finally:
        if own_client:
            http_client.close()


def _release_message_payload(release_path: Path, publication_id: str) -> GenericMessagePayload:
    release = load_release(release_path)
    matches = [item for item in release.items if item.publication_id == publication_id]
    if len(matches) != 1:
        raise ValueError("publication_id must identify exactly one release item")
    payload = matches[0].payload
    if not isinstance(payload, GenericMessagePayload):
        raise ValueError("recovery probe supports message payloads only")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provider-read-only recovery probe for one existing Telegram channel post."
    )
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--expected-chat-id", type=int, required=True)
    parser.add_argument("--expected-chat-username", required=True)
    parser.add_argument("--attempted-at-utc", required=True)
    parser.add_argument("--match-window-seconds", type=int, default=180)
    parser.add_argument("--historical-run-id", required=True)
    parser.add_argument("--historical-run-attempt", required=True)
    parser.add_argument("--historical-outcome-artifact-sha256", required=True)
    parser.add_argument("--github-sha")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = os.environ.get("LORDCHRIST_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("LORDCHRIST_TELEGRAM_BOT_TOKEN is required")
    attempted_at = datetime.fromisoformat(args.attempted_at_utc.replace("Z", "+00:00"))
    payload = _release_message_payload(args.release, args.publication_id)
    probe = probe_research_channel_post(
        payload=payload,
        expected_chat_id=args.expected_chat_id,
        expected_chat_username=args.expected_chat_username.removeprefix("@"),
        attempted_at_utc=attempted_at,
        match_window_seconds=args.match_window_seconds,
        token=token,
        historical_run_id=args.historical_run_id,
        historical_run_attempt=args.historical_run_attempt,
        historical_outcome_artifact_sha256=args.historical_outcome_artifact_sha256,
        github_sha=args.github_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(probe.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": probe.status,
                "publication_id": probe.publication_id,
                "message_id": probe.message_id,
                "message_url": probe.message_url,
                "examined_updates": probe.examined_updates,
                "get_updates_offset_sent": False,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
