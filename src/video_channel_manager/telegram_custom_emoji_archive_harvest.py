from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence
from urllib.parse import quote_plus

import httpx

from video_channel_manager.telegram_custom_emoji_harvest import (
    CustomEmojiExemplarConfig,
    CustomEmojiExemplarSpec,
    CustomEmojiHarvestReport,
    HarvestedExemplar,
    _PublicMessage,
    _TelegramSearchPageParser,
    _sha256_text,
    _verify_custom_emoji_ids,
    load_exemplar_config,
)
from video_channel_manager.telegram_models import DEFAULT_API_BASE

_MAX_ARCHIVE_PAGES = 120
_ARCHIVE_STOP_MARGIN = timedelta(days=2)


def _parse_page(html: str, *, channel_username: str) -> tuple[_PublicMessage, ...]:
    parser = _TelegramSearchPageParser(channel_username=channel_username)
    parser.feed(html)
    parser.close()
    return tuple(parser.messages)


def _validate_public_response(response: httpx.Response, *, context: str) -> None:
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "text/html" not in content_type:
        raise ValueError(f"Telegram public archive returned non-HTML for {context}")


def _select_unique(
    messages: Sequence[_PublicMessage],
    *,
    spec: CustomEmojiExemplarSpec,
) -> _PublicMessage | None:
    fingerprint = " ".join(spec.fingerprint.split()).casefold()
    candidates = [
        message
        for message in messages
        if fingerprint in " ".join(message.text.split()).casefold()
    ]
    if not candidates:
        return None
    dated = [
        message
        for message in candidates
        if message.message_date_utc.date() == spec.expected_date
    ]
    selected = dated if dated else candidates
    unique_by_id = {message.message_id: message for message in selected}
    if len(unique_by_id) != 1:
        ids = sorted(unique_by_id)
        raise ValueError(f"ambiguous public Telegram exemplar {spec.key}; candidate ids={ids}")
    return next(iter(unique_by_id.values()))


def _fetch_search_candidate(
    *,
    client: httpx.Client,
    channel_username: str,
    spec: CustomEmojiExemplarSpec,
) -> _PublicMessage | None:
    bare_channel = channel_username.removeprefix("@")
    response = client.get(f"https://t.me/s/{bare_channel}?q={quote_plus(spec.query)}")
    _validate_public_response(response, context=f"search:{spec.key}")
    return _select_unique(
        _parse_page(response.text, channel_username=channel_username),
        spec=spec,
    )


def _archive_resolve(
    *,
    client: httpx.Client,
    channel_username: str,
    specs: Sequence[CustomEmojiExemplarSpec],
    max_pages: int = _MAX_ARCHIVE_PAGES,
) -> dict[str, _PublicMessage]:
    if not specs:
        return {}
    if not 1 <= max_pages <= _MAX_ARCHIVE_PAGES:
        raise ValueError(f"max_pages must be between 1 and {_MAX_ARCHIVE_PAGES}")

    bare_channel = channel_username.removeprefix("@")
    unresolved = {spec.key: spec for spec in specs}
    resolved: dict[str, _PublicMessage] = {}
    seen_messages: dict[int, _PublicMessage] = {}
    before: int | None = None

    for _ in range(max_pages):
        suffix = "" if before is None else f"?before={before}"
        response = client.get(f"https://t.me/s/{bare_channel}{suffix}")
        _validate_public_response(response, context=f"archive-before:{before or 'latest'}")
        page_messages = _parse_page(response.text, channel_username=channel_username)
        if not page_messages:
            break

        for message in page_messages:
            seen_messages[message.message_id] = message

        corpus = tuple(seen_messages.values())
        for key, spec in tuple(unresolved.items()):
            match = _select_unique(corpus, spec=spec)
            if match is not None:
                resolved[key] = match
                unresolved.pop(key)
        if not unresolved:
            return resolved

        oldest = min(message.message_date_utc for message in page_messages)
        if all(
            oldest.date() < spec.expected_date - _ARCHIVE_STOP_MARGIN
            for spec in unresolved.values()
        ):
            break

        next_before = min(message.message_id for message in page_messages)
        if next_before <= 1 or next_before == before:
            break
        before = next_before

    if unresolved:
        details = ", ".join(
            f"{spec.key}@{spec.expected_date.isoformat()}" for spec in unresolved.values()
        )
        raise ValueError(f"public Telegram archive exhausted before resolving exemplars: {details}")
    return resolved


def _to_harvested(
    *,
    config: CustomEmojiExemplarConfig,
    resolved: dict[str, _PublicMessage],
) -> tuple[HarvestedExemplar, ...]:
    bare_channel = config.channel_username.removeprefix("@")
    return tuple(
        HarvestedExemplar(
            key=spec.key,
            message_id=resolved[spec.key].message_id,
            message_url=f"https://t.me/{bare_channel}/{resolved[spec.key].message_id}",
            message_date_utc=resolved[spec.key].message_date_utc,
            visible_text_sha256=_sha256_text(resolved[spec.key].text),
            custom_emoji_ids=resolved[spec.key].custom_emoji_ids,
        )
        for spec in config.exemplars
    )


def harvest_custom_emoji_with_archive_fallback(
    config: CustomEmojiExemplarConfig,
    *,
    token: str | None = None,
    api_base: str = DEFAULT_API_BASE,
    checked_at_utc: datetime | None = None,
    client: httpx.Client | None = None,
    max_archive_pages: int = _MAX_ARCHIVE_PAGES,
) -> CustomEmojiHarvestReport:
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=2),
        follow_redirects=False,
        trust_env=False,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "video-channel-manager/svodka-custom-emoji-archive-harvest",
        },
    )
    try:
        resolved: dict[str, _PublicMessage] = {}
        unresolved: list[CustomEmojiExemplarSpec] = []
        for spec in config.exemplars:
            match = _fetch_search_candidate(
                client=http_client,
                channel_username=config.channel_username,
                spec=spec,
            )
            if match is None:
                unresolved.append(spec)
            else:
                resolved[spec.key] = match

        resolved.update(
            _archive_resolve(
                client=http_client,
                channel_username=config.channel_username,
                specs=unresolved,
                max_pages=max_archive_pages,
            )
        )
        exemplars = _to_harvested(config=config, resolved=resolved)
        if not any(item.custom_emoji_ids for item in exemplars):
            raise ValueError(
                "no custom emoji ids were discoverable in the selected public Telegram exemplars"
            )

        all_ids = tuple(
            sorted(
                {
                    custom_id
                    for exemplar in exemplars
                    for custom_id in exemplar.custom_emoji_ids
                },
                key=int,
            )
        )
        verified = (
            _verify_custom_emoji_ids(
                token=token,
                api_base=api_base,
                custom_ids=all_ids,
                exemplars=exemplars,
                client=http_client,
            )
            if token
            else ()
        )
        return CustomEmojiHarvestReport(
            schema_name="video-channel-manager.telegram-custom-emoji-harvest-report",
            schema_version=1,
            channel_username=config.channel_username,
            checked_at_utc=checked_at_utc or datetime.now(tz=UTC),
            bot_api_validation_performed=bool(token),
            exemplars=exemplars,
            all_custom_emoji_ids=all_ids,
            verified_custom_emoji=verified,
        )
    finally:
        if own_client:
            http_client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Harvest Svodka custom emoji ids with a bounded public archive fallback."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-bot-api", action="store_true")
    parser.add_argument("--max-archive-pages", type=int, default=_MAX_ARCHIVE_PAGES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_exemplar_config(args.config)
    token = None
    if args.verify_bot_api:
        token = os.environ.get("SVODKA_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("SVODKA_TELEGRAM_BOT_TOKEN is required for Bot API verification")
    report = harvest_custom_emoji_with_archive_fallback(
        config,
        token=token,
        max_archive_pages=args.max_archive_pages,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "channel_username": report.channel_username,
                "exemplar_message_ids": [item.message_id for item in report.exemplars],
                "custom_emoji_count": len(report.all_custom_emoji_ids),
                "custom_emoji_ids": list(report.all_custom_emoji_ids),
                "bot_api_validation_performed": report.bot_api_validation_performed,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
