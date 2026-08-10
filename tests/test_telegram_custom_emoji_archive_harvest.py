from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from video_channel_manager.telegram_custom_emoji_archive_harvest import (
    harvest_custom_emoji_with_archive_fallback,
)
from video_channel_manager.telegram_custom_emoji_harvest import (
    CustomEmojiExemplarConfig,
    CustomEmojiExemplarSpec,
)


CUSTOM_ID = "5368324170671202286"


def _config() -> CustomEmojiExemplarConfig:
    return CustomEmojiExemplarConfig(
        schema_name="video-channel-manager.telegram-custom-emoji-exemplars",
        schema_version=1,
        channel_username="@deep_info_life",
        exemplars=(
            CustomEmojiExemplarSpec(
                key="evolution-facts-top10",
                query="Мягкие ткани",
                fingerprint="ТОП-10 фактов, которые бьют по эволюции",
                expected_date=date(2026, 3, 25),
            ),
        ),
    )


def _message_html(*, message_id: int, when: str, text: str, custom_id: str | None = None) -> str:
    emoji = (
        f'<tg-emoji emoji-id="{custom_id}">1️⃣</tg-emoji> '
        if custom_id is not None
        else ""
    )
    return f"""
    <div class="tgme_widget_message" data-post="deep_info_life/{message_id}">
      <div class="tgme_widget_message_text js-message_text">{emoji}{text}</div>
      <time datetime="{when}"></time>
    </div>
    """


def test_archive_fallback_resolves_search_miss_without_provider_write() -> None:
    calls: list[str] = []
    search_html = _message_html(
        message_id=500,
        when="2026-08-10T12:00:00+00:00",
        text="Другой материал",
    )
    recent_archive = _message_html(
        message_id=400,
        when="2026-04-01T12:00:00+00:00",
        text="Другой материал",
    )
    target_archive = _message_html(
        message_id=350,
        when="2026-03-25T12:00:00+00:00",
        text="Сводка | ТОП-10 фактов, которые бьют по эволюции",
        custom_id=CUSTOM_ID,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.params.get("q") is not None:
            return httpx.Response(200, text=search_html, headers={"content-type": "text/html"})
        if request.url.params.get("before") == "400":
            return httpx.Response(200, text=target_archive, headers={"content-type": "text/html"})
        return httpx.Response(200, text=recent_archive, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = harvest_custom_emoji_with_archive_fallback(
            _config(),
            checked_at_utc=datetime(2026, 8, 10, 17, 0, tzinfo=UTC),
            client=client,
            max_archive_pages=3,
        )

    assert report.provider_write_performed is False
    assert report.exemplars[0].message_id == 350
    assert report.all_custom_emoji_ids == (CUSTOM_ID,)
    assert len(calls) == 3
    assert "q=" in calls[0]
    assert calls[1].endswith("/s/deep_info_life")
    assert "before=400" in calls[2]


def test_archive_fallback_stops_after_crossing_unresolved_date() -> None:
    calls: list[str] = []
    search_html = _message_html(
        message_id=500,
        when="2026-08-10T12:00:00+00:00",
        text="Другой материал",
    )
    old_archive = _message_html(
        message_id=300,
        when="2026-03-20T12:00:00+00:00",
        text="Другой материал",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.params.get("q") is not None:
            return httpx.Response(200, text=search_html, headers={"content-type": "text/html"})
        return httpx.Response(200, text=old_archive, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="archive exhausted"):
            harvest_custom_emoji_with_archive_fallback(
                _config(),
                client=client,
                max_archive_pages=5,
            )

    assert len(calls) == 2


def test_archive_fallback_rejects_ambiguous_exact_fingerprint() -> None:
    duplicate = "".join(
        [
            _message_html(
                message_id=350,
                when="2026-03-25T12:00:00+00:00",
                text="ТОП-10 фактов, которые бьют по эволюции",
                custom_id=CUSTOM_ID,
            ),
            _message_html(
                message_id=351,
                when="2026-03-25T13:00:00+00:00",
                text="ТОП-10 фактов, которые бьют по эволюции",
                custom_id=CUSTOM_ID,
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=duplicate, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="ambiguous public Telegram exemplar"):
            harvest_custom_emoji_with_archive_fallback(_config(), client=client)
