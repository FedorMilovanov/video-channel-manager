from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    JPEG_MAGIC,
    _apply_telegraph_layout_rules,
    build_telegraph_payload,
    ensure_telegraph_token,
    load_telegraph_queue,
    publish_channel_message,
    publish_telegraph_page,
    render_channel_post,
    render_preview_html_page,
)

ROOT = Path(__file__).resolve().parents[1]
MEDIA_BASE = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40


class FakeTransport:
    def __init__(self, *, trigger_content_too_big_once: bool = False) -> None:
        self.trigger_content_too_big_once = trigger_content_too_big_once
        self.multipart_calls: list[tuple[str, dict[str, bytes]]] = []
        self.json_calls: list[tuple[str, dict[str, Any]]] = []
        self._page_seq = 0

    def post_multipart(self, url: str, fields: Mapping[str, bytes]) -> dict[str, Any]:
        copied = dict(fields)
        self.multipart_calls.append((url, copied))
        if url.endswith("/createAccount"):
            return {"ok": True, "result": {"access_token": "tok_auto_generated_secret"}}
        if url.endswith("/getAccountInfo"):
            return {"ok": True, "result": {"short_name": "lordchrist"}}
        if "/createPage" in url or "/editPage/" in url:
            if self.trigger_content_too_big_once:
                self.trigger_content_too_big_once = False
                return {"ok": False, "error": "CONTENT_TOO_BIG"}
            self._page_seq += 1
            slug = f"Charnock-Page-{self._page_seq}"
            return {"ok": True, "result": {"path": slug, "url": f"https://telegra.ph/{slug}"}}
        raise AssertionError(f"Unexpected multipart URL: {url}")

    def read_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.post_json(url, payload)

    def post_json(self, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        copied = dict(payload)
        self.json_calls.append((url, copied))
        if url.endswith("/getMe"):
            return {"ok": True, "result": {"id": 8716602202, "is_bot": True, "username": "preaching_mp3_bot"}}
        if url.endswith("/getChat"):
            return {"ok": True, "result": {"id": -1001295216957, "username": "lordchrist"}}
        if url.endswith("/sendMessage"):
            return {"ok": True, "result": {"message_id": 4421}}
        if url.endswith("/editMessageText"):
            return {
                "ok": True,
                "result": {
                    "message_id": 4421,
                    "link_preview_options": {"url": copied["link_preview_options"]["url"]},
                },
            }
        raise AssertionError(f"Unexpected JSON URL: {url}")

    def get_status(self, url: str) -> tuple[int, bytes]:
        if url.endswith(".jpg"):
            return 200, JPEG_MAGIC + b"\xe0\x00\x10JFIF"
        return 200, b"<!doctype html>"


def test_telegraph_queue_loads_all_seven_verified_items() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    assert len(items) == 7
    assert items[0].publication_id == "lordchrist-telegraph-charnock-01b"
    assert items[0].is_canary is True
    assert all(item.is_ready for item in items)
    # Every edition is Telegraph-native: article and cover live in telegraph-v1,
    # never borrowed from the rich-v1 lane.
    for item in items:
        assert item.article_path is not None
        assert item.article_path.as_posix().startswith("content/telegram/lordchrist/telegraph-v1/")
        assert item.cover_path is not None
        assert item.cover_path.as_posix().startswith("content/telegram/lordchrist/telegraph-v1/")


def test_all_ready_items_build_valid_telegraph_and_channel_post_payloads() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    for item in items:
        payload = build_telegraph_payload(ROOT, item, media_base_url=MEDIA_BASE)
        assert isinstance(payload.nodes[0], dict)
        assert payload.nodes[0]["tag"] == "figure"
        # H1 title is passed via page title, never duplicated as first heading in body
        assert not (isinstance(payload.nodes[1], dict) and payload.nodes[1].get("tag") in {"h1", "h2"})
        assert payload.content_utf8_bytes < 70_000

        assert item.channel_post is not None
        post = render_channel_post(item.channel_post, "https://telegra.ph/Test-Page-10-23")
        assert "<blockquote expandable>" in post.html_text
        assert "<blockquote>" in post.html_text
        assert 'href="https://telegra.ph/Test-Page-10-23"' in post.html_text
        assert 1_000 <= post.visible_char_count <= 3_950


def test_end_to_end_auto_account_telegraph_and_channel_publish() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    canary = items[0]
    payload = build_telegraph_payload(ROOT, canary, media_base_url=MEDIA_BASE)
    fake = FakeTransport()

    token = ensure_telegraph_token(fake)
    assert token == "tok_auto_generated_secret"

    url, path = publish_telegraph_page(fake, payload, access_token=token)
    assert url == "https://telegra.ph/Charnock-Page-1"
    assert path == "Charnock-Page-1"

    assert canary.channel_post is not None
    rendered = render_channel_post(canary.channel_post, url)
    sent = publish_channel_message(
        fake,
        bot_token="123:test",
        expected_bot_id=8716602202,
        expected_chat_id=-1001295216957,
        rendered_post=rendered,
        preview_refresh_delay_seconds=0.01,
    )
    assert sent == {
        "chat_id": -1001295216957,
        "message_id": 4421,
        "telegraph_url": "https://telegra.ph/Charnock-Page-1",
    }
    send_payload = next(p for u, p in fake.json_calls if u.endswith("/sendMessage"))
    assert send_payload["link_preview_options"] == {
        "is_disabled": False,
        "url": "https://telegra.ph/Charnock-Page-1",
        "prefer_large_media": True,
        "show_above_text": False,
    }


def test_quote_credit_is_plain_emdash_line_outside_blockquote() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    payload = build_telegraph_payload(ROOT, items[0], media_base_url=MEDIA_BASE)
    quote_indexes = [
        i for i, node in enumerate(payload.nodes) if isinstance(node, dict) and node.get("tag") == "blockquote"
    ]
    assert quote_indexes, "expected at least one quotation block"
    charnock_credit_lines = 0
    for idx in quote_indexes:
        node = payload.nodes[idx]
        assert isinstance(node, dict)
        serialized = json.dumps(node, ensure_ascii=False)
        assert "Стивен Чарнок" not in serialized, "credit must not live inside the blockquote"
        # Every quotation is followed by its attribution as a separate plain
        # paragraph, starting with an em dash and carrying no quote bar.
        credit_node = payload.nodes[idx + 1]
        assert isinstance(credit_node, dict) and credit_node.get("tag") == "p"
        credit_text = json.dumps(credit_node, ensure_ascii=False)
        if "— Стивен Чарнок" in credit_text:
            charnock_credit_lines += 1
    assert charnock_credit_lines >= 10

    assert items[0].channel_post is not None
    post = render_channel_post(items[0].channel_post, "https://telegra.ph/Test-Page-10-23")
    assert "</blockquote>\n— <i>" in post.html_text

    # Source footer carries the © sign (reader request)
    assert "© Цитаты Чарнока" in payload.compact_content_json


def test_due_item_resolves_tue_fri_schedule_and_refuses_duplicates() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from video_channel_manager.lordchrist_telegraph_publisher import due_item, main

    moscow = ZoneInfo("Europe/Moscow")
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)

    due, reason = due_item(items, {}, datetime(2026, 10, 27, 12, 0, tzinfo=moscow))
    assert due is not None and due.publication_id == "lordchrist-telegraph-charnock-02"
    assert reason == "due"

    due, reason = due_item(items, {}, datetime(2026, 10, 28, 12, 0, tzinfo=moscow))
    assert due is None and reason == "no_article_scheduled_today"

    published = {"lordchrist-telegraph-charnock-02": {"telegram_message_id": 777}}
    due, reason = due_item(items, published, datetime(2026, 10, 27, 12, 0, tzinfo=moscow))
    assert due is None and reason == "already_published"

    # CLI surface used by the scheduled workflow
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(
            [
                "due",
                "--repo-root",
                str(ROOT),
                "--ledger",
                "state/nonexistent-ledger.json",
                "--now",
                "2026-10-30T12:00:00+03:00",
            ]
        )
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["due"] == "lordchrist-telegraph-charnock-03"


def test_telegraph_workflow_has_midday_tue_fri_cron_without_timezone() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-telegraph-poster.yml").read_text(encoding="utf-8")
    assert '- cron: "0 9 * * 2,5"' in workflow  # 09:00 UTC = 12:00 Europe/Moscow
    schedule_block = workflow.split("permissions:", 1)[0]
    functional = [ln for ln in schedule_block.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert not any("timezone:" in ln for ln in functional)
    assert "lordchrist_telegraph_publisher due" in workflow
    assert "steps.resolve.outputs.publication_id" in workflow


def test_layout_rules_merge_quotes_tag_chapter_and_space_headings() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    item02 = next(i for i in items if i.publication_id.endswith("-02"))
    payload = build_telegraph_payload(ROOT, item02, media_base_url=MEDIA_BASE)
    nodes = payload.nodes

    blockquotes = [n for n in nodes if isinstance(n, dict) and n.get("tag") == "blockquote"]
    doc = json.loads((ROOT / item02.article_path).read_text(encoding="utf-8"))  # type: ignore[arg-type]
    raw_quotes = sum(1 for b in doc["blocks"] if b["type"] == "blockquote")
    # Article 02 clusters are merged editorially in the article itself, so the
    # publisher receives no back-to-back quotes and must not invent merges.
    assert len(blockquotes) == raw_quotes, "article-level merged quotes must pass through unchanged"

    # exactly one credit line per merged quote group
    def _is_credit(n: object) -> bool:
        if not isinstance(n, dict) or n.get("tag") != "p":
            return False
        ch = n.get("children")
        return (
            isinstance(ch, list)
            and len(ch) == 1
            and isinstance(ch[0], dict)
            and ch[0].get("tag") == "em"
            and "Стивен Чарнок" in json.dumps(ch[0], ensure_ascii=False)
        )

    credits = [n for n in nodes if _is_credit(n)]
    assert len(credits) == len(blockquotes) - 1  # minus the Scripture epigraph
    assert "(беседа I)" in json.dumps(credits[0], ensure_ascii=False)
    # Scripture epigraph credit stays bare — no chapter tag
    assert "— Мал. 1:11" in payload.compact_content_json
    assert "Мал. 1:11 (беседа" not in payload.compact_content_json

    # Heading air: a spacer precedes headings after prose, but never doubles
    # up right after a quotation block (credit paragraph).
    for pos, node in enumerate(nodes):
        if isinstance(node, dict) and node.get("tag") in {"h3", "h4"} and pos >= 2:
            prev = nodes[pos - 1]
            before_prev = nodes[pos - 2]
            is_spacer = isinstance(prev, dict) and prev.get("tag") == "p" and prev.get("children") == [{"tag": "br"}]
            if is_spacer:
                is_credit = (
                    isinstance(before_prev, dict)
                    and before_prev.get("tag") == "p"
                    and isinstance(before_prev.get("children"), list)
                    and len(before_prev["children"]) == 1
                    and isinstance(before_prev["children"][0], dict)
                    and before_prev["children"][0].get("tag") == "em"
                )
                assert not is_credit, "no double air after a quote"

    # Channel digest: blank line between points, bold leads preserved
    assert item02.channel_post is not None
    post = render_channel_post(item02.channel_post, "https://telegra.ph/Test-Page-10-23")
    digest = post.html_text.split("<blockquote expandable>", 1)[1]
    assert "\n\n• <b>" in digest


def test_layout_rules_merge_back_to_back_quotes_with_trailing_ellipsis() -> None:
    credit = {"tag": "p", "children": [{"tag": "em", "children": ["— Стивен Чарнок, «О бытии Бога»"]}]}
    nodes: list[dict[str, Any] | str] = [
        {"tag": "blockquote", "children": ["Первый фрагмент."]},
        json.loads(json.dumps(credit)),
        {"tag": "blockquote", "children": ["Второй фрагмент."]},
        json.loads(json.dumps(credit)),
        {"tag": "p", "children": ["Авторский абзац."]},
    ]
    out = _apply_telegraph_layout_rules(nodes)
    quotes = [n for n in out if isinstance(n, dict) and n.get("tag") == "blockquote"]
    assert len(quotes) == 1, "back-to-back quotes must merge into one block"
    merged_children = quotes[0].get("children") or []
    assert " …" in json.dumps(merged_children, ensure_ascii=False), "fragments join with a trailing ellipsis"
    credit_texts = [
        n["children"][0]["children"][0]
        for n in out
        if isinstance(n, dict) and n.get("tag") == "p" and n.get("children") and isinstance(n["children"][0], dict)
    ]
    assert credit_texts == ["— Стивен Чарнок, «О бытии Бога» (беседа I)"], "one credit, chapter tag appended"


def test_content_too_big_splits_cleanly_at_heading_with_zero_text_loss() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    payload = build_telegraph_payload(ROOT, items[1], media_base_url=MEDIA_BASE)
    fake = FakeTransport(trigger_content_too_big_once=True)

    url, path = publish_telegraph_page(fake, payload, access_token="tok")
    # Part 2 is created first (Page-1), then Part 1 linking to Part 2 (Page-2)
    assert url == "https://telegra.ph/Charnock-Page-2"
    assert path == "Charnock-Page-2"

    part1_call = fake.multipart_calls[-1][1]
    part1_json = part1_call["content"].decode("utf-8")
    assert "https://telegra.ph/Charnock-Page-1" in part1_json
    assert "Читать окончание главы →" in part1_json


def test_preview_html_page_embeds_both_tabs() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    payload = build_telegraph_payload(ROOT, items[0], media_base_url=MEDIA_BASE)
    assert items[0].channel_post is not None
    post = render_channel_post(items[0].channel_post, "https://telegra.ph/Preview-10-23")
    page = render_preview_html_page(payload, post, "https://example.com/cover.jpg")
    assert "⚡ ПОСМОТРЕТЬ" in page
    assert "tg-expandable collapsed" in page
    assert payload.title in page


def test_01b_has_zero_overlapping_english_spans_with_article_01() -> None:
    j01 = json.loads(
        (ROOT / "content/telegram/lordchrist/rich-v1/charnock/lordchrist-rich-charnock-01.json").read_text("utf-8")
    )
    j01b = json.loads(
        (ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-01b.json").read_text(
            "utf-8"
        )
    )

    def extract_ranges(doc: dict[str, Any]) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        for s in doc["sources"]:
            ev = s.get("evidence", "")
            if ev.startswith("EN: "):
                body, _, tail = ev[4:].partition("  [смещение ")
                off = int(tail.split()[0])
                ranges.append((off, off + len(body)))
        return ranges

    r1 = extract_ranges(j01)
    r1b = extract_ranges(j01b)
    assert len(r1b) == 28
    for a1, b1 in r1:
        for a2, b2 in r1b:
            assert b1 <= a2 or b2 <= a1, f"Overlap found: [{a1}:{b1}] vs [{a2}:{b2}]"


def test_channel_chat_mismatch_fails_closed() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    assert items[0].channel_post is not None
    rendered = render_channel_post(items[0].channel_post, "https://telegra.ph/Charnock-Page-1")
    fake = FakeTransport()
    with pytest.raises(ValueError, match="target chat verification failed"):
        publish_channel_message(
            fake,
            bot_token="123:test",
            expected_bot_id=8716602202,
            expected_chat_id=-1009999999999,
            rendered_post=rendered,
        )


def test_cover_url_preflight_blocks_before_telegraph_dispatch() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    payload = build_telegraph_payload(
        ROOT,
        items[0],
        media_base_url="https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/main",
    )

    class BrokenCoverTransport(FakeTransport):
        def get_status(self, url: str) -> tuple[int, bytes]:
            _ = url
            return 404, b""

    broken = BrokenCoverTransport()
    with pytest.raises(RuntimeError, match="is not reachable as JPEG"):
        publish_telegraph_page(broken, payload=payload, access_token="test-token")
    assert broken.multipart_calls == []


def test_live_transport_ambiguous_mutations_never_replay() -> None:
    import httpx

    from video_channel_manager.lordchrist_telegraph_publisher import HttpxLiveTransport
    from video_channel_manager.platforms.http import HttpTransportFailure

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("ambiguous timeout after dispatch", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        live = HttpxLiveTransport(http_client=client)
        with pytest.raises(HttpTransportFailure) as exc1:
            live.post_multipart("https://api.telegra.ph/createPage", {"title": b"T"})
        assert exc1.value.attempts == 1
        assert calls == 1

        with pytest.raises(HttpTransportFailure) as exc2:
            live.post_json("https://api.telegram.org/botX/sendMessage", {"chat_id": 1, "text": "x"})
        assert exc2.value.attempts == 1
        assert calls == 2
