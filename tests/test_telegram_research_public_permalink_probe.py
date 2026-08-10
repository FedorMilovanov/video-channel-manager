from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import render_message_payload
from video_channel_manager.telegram_research_public_permalink_probe import probe_public_permalinks

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
ARTIFACT_SHA = "sha256:" + "a" * 64
CHECKED_AT = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)


def _payload():
    profile = load_channel_profile(PROFILE_PATH)
    return render_message_payload(
        profile,
        publication_id="lordchrist-research-public-permalink-test",
        html_text=(
            "<b>📖 Не рекорд, а мера труда</b>\n\n"
            "Точный исследовательский текст без URL.\n\n"
            "<i>✦ Благодарим Бога за верный труд.</i>"
        ),
    )


def _embed_html(payload, message_id: int, *, username: str = "lordchrist", text: str | None = None) -> str:
    visible = payload.expected_plain_text if text is None else text
    parts = visible.split("\n")
    rendered = "<br/>".join(parts)
    rendered = rendered.replace("📖", '<img class="emoji" alt="📖"/>', 1)
    return (
        "<!doctype html><html><body>"
        f'<div class="tgme_widget_message" data-post="{username}/{message_id}">'
        f'<div class="tgme_widget_message_text js-message_text" dir="auto"><b>{rendered}</b></div>'
        "</div></body></html>"
    )


def _probe(client: httpx.Client, *, first_id: int = 1475, last_id: int = 1477):
    return probe_public_permalinks(
        payload=_payload(),
        channel_username="@lordchrist",
        first_message_id=first_id,
        last_message_id=last_id,
        historical_run_id="31390497205",
        historical_run_attempt="1",
        historical_outcome_artifact_sha256=ARTIFACT_SHA,
        checked_at_utc=CHECKED_AT,
        client=client,
    )


def test_public_permalink_probe_finds_one_exact_visible_text_without_bot_api() -> None:
    payload = _payload()
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        message_id = int(request.url.path.rsplit("/", 1)[-1])
        requested_ids.append(message_id)
        if message_id == 1476:
            body = _embed_html(payload, message_id)
            return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"}, request=request)
        return httpx.Response(404, text="not found", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe(client)

    assert requested_ids == [1475, 1476, 1477]
    assert result.status == "found"
    assert result.telegram_bot_token_used is False
    assert result.provider_write_performed is False
    assert [candidate.message_id for candidate in result.candidates] == [1476]
    assert result.candidates[0].message_url == "https://t.me/lordchrist/1476"
    expected_sha = "sha256:" + hashlib.sha256(payload.expected_plain_text.encode("utf-8")).hexdigest()
    assert result.expected_plain_text_sha256 == expected_sha
    assert result.candidates[0].visible_text_sha256 == expected_sha
    assert payload.expected_plain_text not in result.model_dump_json()


def test_public_permalink_probe_requires_exact_target_data_post_and_text() -> None:
    payload = _payload()

    def handler(request: httpx.Request) -> httpx.Response:
        message_id = int(request.url.path.rsplit("/", 1)[-1])
        if message_id == 1475:
            body = _embed_html(payload, message_id, username="another_channel")
        elif message_id == 1476:
            body = _embed_html(payload, message_id, text=payload.expected_plain_text + " drift")
        else:
            body = "<html><body>no Telegram widget</body></html>"
        return httpx.Response(200, text=body, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe(client)

    assert result.status == "not_found"
    assert result.candidates == ()


def test_public_permalink_probe_fails_closed_on_multiple_exact_matches() -> None:
    payload = _payload()

    def handler(request: httpx.Request) -> httpx.Response:
        message_id = int(request.url.path.rsplit("/", 1)[-1])
        body = _embed_html(payload, message_id)
        return httpx.Response(200, text=body, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _probe(client, first_id=1475, last_id=1476)

    assert result.status == "ambiguous"
    assert [candidate.message_id for candidate in result.candidates] == [1475, 1476]


def test_public_permalink_probe_rejects_unexpected_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="unexpected public Telegram status 429"):
            _probe(client, first_id=1475, last_id=1475)


def test_public_permalink_probe_rejects_unbounded_scan_range() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404, request=request))) as client:
        with pytest.raises(ValueError, match="exceeds 51 ids"):
            _probe(client, first_id=1475, last_id=1526)
