from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import pytest

from video_channel_manager import lordchrist_telegraph_publisher as publisher
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
        self.status_calls: list[str] = []
        self.status_overrides: dict[str, tuple[int, bytes]] = {}
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
                    "link_preview_options": {
                        "url": copied["link_preview_options"]["url"],
                        "prefer_large_media": True,
                    },
                },
            }
        raise AssertionError(f"Unexpected JSON URL: {url}")

    def get_status(self, url: str) -> tuple[int, bytes]:
        self.status_calls.append(url)
        if url in self.status_overrides:
            return self.status_overrides[url]
        if url.endswith(".jpg"):
            return 200, JPEG_MAGIC + b"\xe0\x00\x10JFIF"
        return 200, b"<!doctype html>"


def test_telegraph_queue_loads_charnock_cycle_and_separate_jude_manual_article() -> None:
    # Charnock's 15 releases retain their identities and chronology.
    # Jude 1:5 is a separately approved manual-only special, not a scheduled
    # Charnock slot and not an automatic backfill. It now carries the operator's
    # documented release date (Sunday 2026-11-15), which is deliberately off the
    # lane's cron slots (`0 9 * * 2,5`): the schedule can never resolve it, so the
    # date records intent while the release stays a manual dispatch.
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    assert len(items) == 17
    assert [item.ordinal for item in items] == list(range(1, 18))
    assert items[14].publication_id == "lordchrist-telegraph-charnock-history-02"
    assert items[-2].publication_id == "lordchrist-telegraph-jude-1-5-20261105"
    assert items[-2].scheduled_on == date(2026, 11, 15)
    assert items[-2].scheduled_on.weekday() not in {1, 4}
    assert items[-2].is_canary is False
    raw_items = json.loads((ROOT / DEFAULT_QUEUE_PATH).read_text(encoding="utf-8"))["items"]
    jude_raw = next(item for item in raw_items if item["publication_id"] == "lordchrist-telegraph-jude-1-5-20261105")
    assert jude_raw["slot_override_reason"].strip()
    # The rich-v1 article «Рабство свободы» rides the same Telegraph lane as a
    # separate series: its own reviewed bytes, its own cover, no VK wave.
    assert items[-1].publication_id == "lordchrist-telegraph-rabstvo-svobody-20261111"
    assert items[-1].scheduled_on is not None
    assert items[-1].is_canary is False
    assert items[0].publication_id == "lordchrist-telegraph-charnock-01b"
    assert items[0].is_canary is True
    assert all(item.is_ready for item in items)
    # Every edition is Telegraph-native inside its own series directory, never
    # borrowed from another series' folder.
    for item in items:
        assert item.article_path is not None
        assert item.cover_path is not None
        if item.publication_id.endswith("-20261111"):
            assert item.article_path.as_posix().startswith("content/telegram/lordchrist/rich-v1/rabstvo-svobody/")
            assert item.cover_path.as_posix().startswith("content/telegram/lordchrist/rich-v1/rabstvo-svobody/")
            continue
        assert item.article_path.as_posix().startswith("content/telegram/lordchrist/telegraph-v1/")
        assert item.cover_path.as_posix().startswith("content/telegram/lordchrist/telegraph-v1/")


def test_charnock_replacement_map_never_invents_a_public_url_and_tracks_exact_revision() -> None:
    """A reviewed GitHub source is not itself a publicly corrected Telegraph page."""
    import hashlib

    path = ROOT / "docs/audits/2026-11-04-charnock-publication-link-replacement-map.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    queue = {entry.publication_id: entry for entry in load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)}
    assert len(manifest["targets"]) == 5
    for entry in manifest["targets"]:
        publication_id = entry["publication_id"]
        old_url = entry["previous_telegraph_url"]
        assert old_url.startswith("https://telegra.ph/")
        assert entry["previous_public_page_still_uncorrected"] is True
        assert entry["replacement_telegraph_url"] is None
        assert entry["replacement_telegram_message_url"] is None
        assert entry["provider_writes_authorized"] is False
        item = queue[publication_id]
        assert item.article_path is not None
        assert entry["corrected_canonical_document_path"] == item.article_path.as_posix()
        content = (ROOT / item.article_path).read_bytes()
        blob = hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()
        assert entry["corrected_document_git_blob_sha"] == blob


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


def test_inline_images_are_rendered_and_preflighted_before_any_publish_mutation() -> None:
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    item = next(i for i in items if i.publication_id == "lordchrist-telegraph-charnock-history-02")
    payload = build_telegraph_payload(ROOT, item, media_base_url=MEDIA_BASE)

    assert len(payload.inline_media_urls) == 4
    assert all(url.startswith("https://") for url in payload.inline_media_urls)
    image_nodes = [
        node
        for node in payload.nodes
        if isinstance(node, dict)
        and node.get("tag") == "figure"
        and any(isinstance(child, dict) and child.get("tag") == "img" for child in node.get("children", []))
    ]
    assert len(image_nodes) == 5  # cover plus four inline documentary images

    fake = FakeTransport()
    publish_telegraph_page(fake, payload, access_token="safe-test-token")
    assert fake.status_calls[:-1] == [payload.cover_url, *payload.inline_media_urls]
    assert fake.status_calls[-1] == "https://telegra.ph/Charnock-Page-1"
    assert len(fake.multipart_calls) == 1

    unavailable = FakeTransport()
    unavailable.status_overrides[payload.inline_media_urls[0]] = (404, b"")
    with pytest.raises(RuntimeError, match="inline media URL .*not reachable as JPEG"):
        publish_telegraph_page(unavailable, payload, access_token="safe-test-token")
    assert unavailable.multipart_calls == [], "failed media preflight must precede Telegraph page creation"


def test_telegraph_only_new_page_rejected_before_any_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    publication_id = "lordchrist-telegraph-charnock-history-02"
    ledger_path = tmp_path / "ledger.json"
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: pytest.fail("No provider access allowed"))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    with pytest.raises(RuntimeError, match="direct publish-telegraph-only is retired"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert not ledger_path.exists()


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
        "link_preview_large_media": True,
    }
    # The initial send came back without a confirmed large-media preview, so
    # exactly one refresh edit must follow to force the enlarged preview.
    edit_calls = [p for u, p in fake.json_calls if u.endswith("/editMessageText")]
    assert len(edit_calls) == 1
    assert edit_calls[0]["link_preview_options"]["prefer_large_media"] is True
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


def test_history_specials_are_manual_only() -> None:
    """Historical specials have no schedule date, so `due` never selects them."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from video_channel_manager.lordchrist_telegraph_publisher import due_item

    moscow = ZoneInfo("Europe/Moscow")
    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    special_ids = {
        "lordchrist-telegraph-charnock-history-01",
        "lordchrist-telegraph-charnock-history-02",
    }
    specials = [item for item in items if item.publication_id in special_ids]
    assert {item.publication_id for item in specials} == special_ids
    assert all(item.scheduled_on is None and item.is_canary is False for item in specials)
    start = datetime(2026, 10, 26, 12, 0, tzinfo=moscow)
    for offset in range(21):
        due, _reason = due_item(items, {}, start + timedelta(days=offset))
        assert due is None or due.publication_id not in special_ids


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

    # An earlier run may have sent the page/message before losing its provider
    # response. Never treat a nonterminal ledger entry as a fresh due article.
    for partial in (
        {"state": "page_dispatch_claimed"},
        {"state": "page_published", "telegraph_url": "https://telegra.ph/existing-page"},
        {"state": "telegram_dispatch_claimed", "telegraph_url": "https://telegra.ph/existing-page"},
        {"telegraph_url": "https://telegra.ph/legacy-partial"},
        {},
    ):
        with pytest.raises(LookupError, match="operator reconciliation required"):
            due_item(
                items,
                {"lordchrist-telegraph-charnock-02": partial},
                datetime(2026, 10, 27, 12, 0, tzinfo=moscow),
            )

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


def test_scheduled_channel_post_quotes_are_verbatim_article_excerpts() -> None:
    import re

    def normalize(text: str) -> str:
        text = text.replace("**", "").replace("*", "").casefold()
        return re.sub(r"[^0-9a-zа-яё]+", " ", text).strip()

    items = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    for item in items:
        if item.is_canary:
            continue  # 01b is already published; its post must not be rewritten retroactively.
        assert item.article_path is not None and item.channel_post is not None
        markdown = (ROOT / item.article_path.with_suffix(".md")).read_text(encoding="utf-8")
        assert normalize(item.channel_post.quote_text) in normalize(markdown), item.publication_id


def test_publish_confirmation_fails_before_any_network_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    import video_channel_manager.lordchrist_telegraph_publisher as publisher

    def forbidden_transport() -> object:
        raise AssertionError("network transport must not be created after a bad confirmation")

    monkeypatch.setattr(publisher, "HttpxLiveTransport", forbidden_transport)
    with pytest.raises(ValueError, match="Confirmation mismatch"):
        publisher.main(
            [
                "publish",
                "--repo-root",
                str(ROOT),
                "--publication-id",
                "lordchrist-telegraph-charnock-02",
                "--media-base-url",
                MEDIA_BASE,
                "--ledger",
                "state/nonexistent-ledger.json",
                "--confirm",
                "PUBLISH:wrong",
            ]
        )


def test_telegraph_only_rejects_existing_public_page_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Revision requires a separately reviewed operation; never overwrite a live URL."""
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            "lordchrist-telegraph-charnock-01b": {
                "publication_id": "lordchrist-telegraph-charnock-01b",
                "telegraph_url": "https://telegra.ph/Original-Charnock-Page-10-24",
                "telegraph_path": "Original-Charnock-Page-10-24",
                "telegram_message_id": 1582,
            }
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

    def forbidden_network() -> object:
        raise AssertionError("public provider must never be contacted before existing-link guard")

    monkeypatch.setattr(publisher, "HttpxLiveTransport", forbidden_network)
    with pytest.raises(RuntimeError, match="already has a Telegraph page"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                "lordchrist-telegraph-charnock-01b",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original


def test_in_place_revision_requires_original_account_token_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            publication_id: {
                "publication_id": publication_id,
                "telegraph_url": "https://telegra.ph/Original-Charnock-Page-10-24",
                "telegraph_path": "Original-Charnock-Page-10-24",
                "telegram_message_id": 1582,
            }
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.delenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: pytest.fail("network must not be contacted"))
    with pytest.raises(RuntimeError, match="original Telegraph account access token"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--revision-confirm",
                f"REVISE:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original


def test_in_place_revision_edits_original_page_without_creating_new_url_or_telegram_post(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original_path = "Original-Charnock-Page-10-24"
    original_url = f"https://telegra.ph/{original_path}"
    record = {
        "publication_id": publication_id,
        "telegraph_url": original_url,
        "telegraph_path": original_path,
        "telegram_message_id": 1582,
        "telegram_chat_id": -1001295216957,
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
                "schema_version": 1,
                "project_key": "lord-god-strength",
                "entries": {publication_id: record},
            }
        ),
        encoding="utf-8",
    )
    fake = FakeTransport()

    def multipart(url: str, fields: Mapping[str, bytes]) -> dict[str, Any]:
        if "/editPage/" in url:
            fake.multipart_calls.append((url, dict(fields)))
            return {"ok": True, "result": {"url": original_url, "path": original_path}}
        return FakeTransport.post_multipart(fake, url, fields)

    fake.post_multipart = multipart  # type: ignore[method-assign]
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: fake)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-original-author-token")
    assert (
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--revision-confirm",
                f"REVISE:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    saved = json.loads(ledger_path.read_text(encoding="utf-8"))["entries"][publication_id]
    assert output["telegraph_url"] == original_url
    assert saved["telegraph_url"] == original_url
    assert saved["telegram_message_id"] == 1582
    assert saved["last_in_place_revision_at_utc"]
    assert any("/editPage/" + original_path in url for url, _ in fake.multipart_calls)
    assert not any("/createPage" in url for url, _ in fake.multipart_calls)
    assert not any(url.endswith("/sendMessage") for url, _ in fake.json_calls)


def test_in_place_revision_refuses_missing_original_page_path_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            publication_id: {
                "publication_id": publication_id,
                "telegraph_url": "https://telegra.ph/Original-Charnock-Page-10-24",
                "telegram_message_id": 1582,
            }
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "owner-token")
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: pytest.fail("network must not be contacted"))
    with pytest.raises(RuntimeError, match="original Telegraph page path"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--revision-confirm",
                f"REVISE:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original


def test_in_place_revision_refuses_changed_url_and_leaves_ledger_intact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original_path = "Original-Charnock-Page-10-24"
    record = {
        "publication_id": publication_id,
        "telegraph_url": f"https://telegra.ph/{original_path}",
        "telegraph_path": original_path,
        "telegram_message_id": 1582,
    }
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {publication_id: record},
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original), encoding="utf-8")
    fake = FakeTransport()

    def multipart(url: str, fields: Mapping[str, bytes]) -> dict[str, Any]:
        if "/editPage/" in url:
            fake.multipart_calls.append((url, dict(fields)))
            return {
                "ok": True,
                "result": {"url": "https://telegra.ph/Changed-Page-10-24", "path": "Changed-Page-10-24"},
            }
        return FakeTransport.post_multipart(fake, url, fields)

    fake.post_multipart = multipart  # type: ignore[method-assign]
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: fake)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "owner-token")
    with pytest.raises(RuntimeError, match="different Telegraph URL"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--revision-confirm",
                f"REVISE:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original
    assert not any("/createPage" in url for url, _ in fake.multipart_calls)


def test_in_place_revision_content_too_big_does_not_create_extra_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            publication_id: {
                "publication_id": publication_id,
                "telegraph_url": "https://telegra.ph/Original-Charnock-Page-10-24",
                "telegraph_path": "Original-Charnock-Page-10-24",
                "telegram_message_id": 1582,
            }
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original), encoding="utf-8")
    fake = FakeTransport(trigger_content_too_big_once=True)
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: fake)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "original-author-token")

    with pytest.raises(RuntimeError, match="refuse createPage split"):
        publisher.main(
            [
                "publish-telegraph-only",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--revision-confirm",
                f"REVISE:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original
    assert [url for url, _ in fake.multipart_calls if "/editPage/" in url] == [
        "https://api.telegra.ph/editPage/Original-Charnock-Page-10-24"
    ]
    assert not any("/createPage" in url for url, _ in fake.multipart_calls)
    assert fake.json_calls == []


def test_publish_partial_record_never_replays_provider_side_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication_id = "lordchrist-telegraph-charnock-01b"
    original = {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            publication_id: {
                "publication_id": publication_id,
                "telegraph_url": "https://telegra.ph/Original-Charnock-Page-10-24",
                "telegraph_path": "Original-Charnock-Page-10-24",
            }
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(publisher, "HttpxLiveTransport", lambda: pytest.fail("network must not be contacted"))
    with pytest.raises(RuntimeError, match="without a verified Telegram receipt"):
        publisher.main(
            [
                "publish",
                "--repo-root",
                str(ROOT),
                "--queue",
                DEFAULT_QUEUE_PATH.as_posix(),
                "--ledger",
                str(ledger_path),
                "--publication-id",
                publication_id,
                "--confirm",
                f"PUBLISH:{publication_id}",
                "--media-base-url",
                MEDIA_BASE,
            ]
        )
    assert json.loads(ledger_path.read_text(encoding="utf-8")) == original


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


def test_telegraph_workflow_fail_closed_release_gate_precedes_provider_send() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-telegraph-poster.yml").read_text(encoding="utf-8")
    release_gate = workflow.index("      - name: Require approved exact Telegraph bytes and current-main CI")
    send_step = workflow.index("      - name: Run Telegraph publisher")
    assert release_gate < send_step
    preflight = workflow[release_gate:send_step]
    assert '[[ "$ACTION" == "preview" ]]' in preflight
    assert '[[ "$GITHUB_REF" == "refs/heads/main" ]]' in preflight
    assert '[[ "$current_main" == "$GITHUB_SHA" ]]' in preflight
    assert "telegram_github_quality_gate --workflow ci.yml" in preflight
    assert "LORDCHRIST_TELEGRAPH_POSTING_ENABLED" in preflight
    assert "LORDCHRIST_TELEGRAPH_APPROVED_PUBLICATION_ID" in preflight
    assert "LORDCHRIST_TELEGRAPH_APPROVED_ARTICLE_BLOB_SHA" in preflight
    assert 'article["git_blob_sha"] != approved_sha' in preflight
    assert "hashlib.sha1" in preflight
    assert "article_path.is_relative_to(root)" in preflight
