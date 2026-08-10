from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload

_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_visible_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


class _TelegramEmbedParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data_posts: list[str] = []
        self.message_texts: list[str] = []
        self._capture_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        data_post = values.get("data-post", "").strip()
        if data_post and "tgme_widget_message" in classes:
            self.data_posts.append(data_post)

        if self._capture_depth:
            if normalized == "br":
                self._parts.append("\n")
            elif normalized == "img":
                alt = values.get("alt", "")
                if alt:
                    self._parts.append(alt)
            if normalized not in _VOID_TAGS:
                self._capture_depth += 1
            return

        if normalized == "div" and "tgme_widget_message_text" in classes:
            self._capture_depth = 1
            self._parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._capture_depth:
            return
        normalized = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        if normalized == "br":
            self._parts.append("\n")
        elif normalized == "img":
            alt = values.get("alt", "")
            if alt:
                self._parts.append(alt)

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        if tag.casefold() in _VOID_TAGS:
            return
        self._capture_depth -= 1
        if self._capture_depth == 0:
            self.message_texts.append(_normalize_visible_text("".join(self._parts)))
            self._parts = []


class PublicPermalinkCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: int = Field(gt=0)
    message_url: str
    visible_text_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class TelegramResearchPublicPermalinkProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-research-public-permalink-probe"]
    schema_version: Literal[1]
    status: Literal["found", "not_found", "ambiguous"]
    publication_id: str
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_plain_text_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    channel_username: str
    first_message_id: int = Field(gt=0)
    last_message_id: int = Field(gt=0)
    checked_at_utc: datetime
    historical_run_id: str
    historical_run_attempt: str
    historical_outcome_artifact_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    telegram_bot_token_used: Literal[False] = False
    provider_write_performed: Literal[False] = False
    candidates: tuple[PublicPermalinkCandidate, ...]

    @model_validator(mode="after")
    def validate_result_shape(self) -> "TelegramResearchPublicPermalinkProbe":
        if self.last_message_id < self.first_message_id:
            raise ValueError("last_message_id must not precede first_message_id")
        if self.last_message_id - self.first_message_id > 50:
            raise ValueError("public permalink recovery window must remain bounded to at most 51 ids")
        expected_count = {"found": 1, "not_found": 0}.get(self.status)
        if expected_count is not None and len(self.candidates) != expected_count:
            raise ValueError(f"status {self.status} requires exactly {expected_count} candidates")
        if self.status == "ambiguous" and len(self.candidates) < 2:
            raise ValueError("ambiguous status requires at least two candidates")
        return self


def _extract_public_message(html: str, *, username: str, message_id: int) -> tuple[str, ...]:
    parser = _TelegramEmbedParser()
    parser.feed(html)
    parser.close()
    expected_data_post = f"{username.removeprefix('@')}/{message_id}".casefold()
    if expected_data_post not in {value.casefold() for value in parser.data_posts}:
        return ()
    return tuple(text for text in parser.message_texts if text)


def probe_public_permalinks(
    *,
    payload: GenericMessagePayload,
    channel_username: str,
    first_message_id: int,
    last_message_id: int,
    historical_run_id: str,
    historical_run_attempt: str,
    historical_outcome_artifact_sha256: str,
    checked_at_utc: datetime | None = None,
    client: httpx.Client | None = None,
) -> TelegramResearchPublicPermalinkProbe:
    if first_message_id <= 0 or last_message_id < first_message_id:
        raise ValueError("invalid Telegram message-id scan range")
    if last_message_id - first_message_id > 50:
        raise ValueError("public permalink recovery scan range exceeds 51 ids")

    bare_username = channel_username.removeprefix("@")
    expected_text = _normalize_visible_text(payload.expected_plain_text)
    expected_sha = _sha256_text(expected_text)
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15),
        transport=httpx.HTTPTransport(retries=2),
        follow_redirects=False,
        trust_env=False,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "video-channel-manager/telegram-public-recovery",
        },
    )
    candidates: list[PublicPermalinkCandidate] = []
    try:
        for message_id in range(first_message_id, last_message_id + 1):
            url = f"https://t.me/{bare_username}/{message_id}?embed=1&mode=tme"
            response = http_client.get(url)
            if response.status_code in {404, 410}:
                continue
            if response.status_code != 200:
                raise ValueError(f"unexpected public Telegram status {response.status_code} for message {message_id}")
            content_type = response.headers.get("content-type", "").casefold()
            if content_type and "text/html" not in content_type:
                raise ValueError(f"unexpected public Telegram content type for message {message_id}")
            texts = _extract_public_message(response.text, username=bare_username, message_id=message_id)
            if expected_text not in texts:
                continue
            candidates.append(
                PublicPermalinkCandidate(
                    message_id=message_id,
                    message_url=f"https://t.me/{bare_username}/{message_id}",
                    visible_text_sha256=expected_sha,
                )
            )
    finally:
        if own_client:
            http_client.close()

    status: Literal["found", "not_found", "ambiguous"]
    if len(candidates) == 1:
        status = "found"
    elif not candidates:
        status = "not_found"
    else:
        status = "ambiguous"
    return TelegramResearchPublicPermalinkProbe(
        schema_name="video-channel-manager.telegram-research-public-permalink-probe",
        schema_version=1,
        status=status,
        publication_id=payload.publication_id,
        provider_payload_sha256=payload.provider_payload_sha256,
        expected_plain_text_sha256=expected_sha,
        channel_username=f"@{bare_username}",
        first_message_id=first_message_id,
        last_message_id=last_message_id,
        checked_at_utc=checked_at_utc or datetime.now(tz=UTC),
        historical_run_id=historical_run_id,
        historical_run_attempt=historical_run_attempt,
        historical_outcome_artifact_sha256=historical_outcome_artifact_sha256,
        candidates=tuple(candidates),
    )


def _release_message_payload(release_path: Path, publication_id: str) -> GenericMessagePayload:
    release = load_release(release_path)
    matches = [item for item in release.items if item.publication_id == publication_id]
    if len(matches) != 1:
        raise ValueError("publication_id must identify exactly one release item")
    payload = matches[0].payload
    if not isinstance(payload, GenericMessagePayload):
        raise ValueError("public permalink recovery supports message payloads only")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover one historical Telegram message id from public permalinks.")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--channel-username", required=True)
    parser.add_argument("--first-message-id", type=int, required=True)
    parser.add_argument("--last-message-id", type=int, required=True)
    parser.add_argument("--historical-run-id", required=True)
    parser.add_argument("--historical-run-attempt", required=True)
    parser.add_argument("--historical-outcome-artifact-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = _release_message_payload(args.release, args.publication_id)
    result = probe_public_permalinks(
        payload=payload,
        channel_username=args.channel_username,
        first_message_id=args.first_message_id,
        last_message_id=args.last_message_id,
        historical_run_id=args.historical_run_id,
        historical_run_attempt=args.historical_run_attempt,
        historical_outcome_artifact_sha256=args.historical_outcome_artifact_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result.status,
                "publication_id": result.publication_id,
                "range": [result.first_message_id, result.last_message_id],
                "candidate_message_ids": [candidate.message_id for candidate in result.candidates],
                "telegram_bot_token_used": False,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
