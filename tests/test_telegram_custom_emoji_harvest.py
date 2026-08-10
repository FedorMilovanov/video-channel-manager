from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from video_channel_manager.telegram_custom_emoji_harvest import (
    CustomEmojiExemplarConfig,
    CustomEmojiExemplarSpec,
    harvest_custom_emoji,
)


CUSTOM_ID = "5368324170671202286"


def _config() -> CustomEmojiExemplarConfig:
    return CustomEmojiExemplarConfig(
        schema_name="video-channel-manager.telegram-custom-emoji-exemplars",
        schema_version=1,
        channel_username="@deep_info_life",
        exemplars=(
            CustomEmojiExemplarSpec(
                key="animal-world-top10",
                query="Животный мир",
                fingerprint="ТОП-10: Животный мир, о котором ты не знал",
                expected_date=date(2026, 3, 21),
            ),
        ),
    )


def _public_html() -> str:
    return f"""
    <html><body>
      <div class="tgme_widget_message" data-post="deep_info_life/321">
        <div class="tgme_widget_message_text js-message_text">
          <tg-emoji emoji-id="{CUSTOM_ID}">1️⃣</tg-emoji>
          ТОП-10: Животный мир, о котором ты не знал
        </div>
        <time datetime="2026-03-21T17:01:00+00:00"></time>
      </div>
    </body></html>
    """


def test_harvest_discovers_public_custom_emoji_without_provider_write() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "t.me"
        return httpx.Response(200, text=_public_html(), headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = harvest_custom_emoji(
            _config(),
            checked_at_utc=datetime(2026, 8, 10, 16, 0, tzinfo=UTC),
            client=client,
        )

    assert report.provider_write_performed is False
    assert report.bot_api_validation_performed is False
    assert report.all_custom_emoji_ids == (CUSTOM_ID,)
    assert report.exemplars[0].message_id == 321
    assert report.exemplars[0].custom_emoji_ids == (CUSTOM_ID,)


def test_harvest_validates_ids_with_read_only_get_custom_emoji_stickers() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method + " " + request.url.path)
        if request.method == "GET":
            return httpx.Response(200, text=_public_html(), headers={"content-type": "text/html"})
        assert request.url.path.endswith("/getCustomEmojiStickers")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "file_id": "safe-file-id",
                        "file_unique_id": "safe-unique-id",
                        "type": "custom_emoji",
                        "width": 100,
                        "height": 100,
                        "is_animated": True,
                        "is_video": False,
                        "emoji": "1️⃣",
                        "set_name": "ExampleNumbers",
                        "custom_emoji_id": CUSTOM_ID,
                        "needs_repainting": False,
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = harvest_custom_emoji(
            _config(),
            token="test-token",
            checked_at_utc=datetime(2026, 8, 10, 16, 0, tzinfo=UTC),
            client=client,
        )

    assert report.bot_api_validation_performed is True
    assert report.provider_write_performed is False
    assert calls == [
        "GET /s/deep_info_life",
        "POST /bottest-token/getCustomEmojiStickers",
    ]
    verified = report.verified_custom_emoji[0]
    assert verified.custom_emoji_id == CUSTOM_ID
    assert verified.emoji == "1️⃣"
    assert verified.set_name == "ExampleNumbers"
    assert verified.source_exemplar_keys == ("animal-world-top10",)
    assert verified.source_message_ids == (321,)
