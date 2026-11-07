from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.milovi_telegram_feed import validate_bundle, state_init
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericRichPhotoPayload

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content/editorial/milovi-cake"
RELEASE = ROOT / "content/telegram/milovi-cake/releases/milovi-feed-20261107-003-runtime.json"
MANIFEST = BASE / "patisserie-profession-history-20261107.manifest.json"
HTML = BASE / "patisserie-profession-history-20261107.html"
NODES = BASE / "patisserie-profession-history-20261107.telegraph-nodes.json"
YAML = ROOT / ".github/workflows/milovi-history-article-due-20261107.yml"
ARTICLE_URL = "https://telegra.ph/Kto-pridumal-konditerskoe-delo-Ot-myasnyh-pirogov-do-iskusstva-desertov-11-07-2"


def test_researched_history_source_is_complete_and_live_telegraph_readback_recorded() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    html = HTML.read_text(encoding="utf-8")
    nodes = json.loads(NODES.read_text(encoding="utf-8"))
    assert m["telegraph_url"] == ARTICLE_URL
    assert m["telegraph_page_images_verified"] == 5
    assert m["telegraph_promotion_verified"] is True
    assert m["promotional_link"] == "https://milovicake.ru/"
    assert m["telegraph_page_nodes_verified"] >= 50
    assert m["words"] >= 1400 and m["sections"] >= 9
    assert len(m["image_urls"]) == 6
    assert len(set(m["image_urls"])) == 6
    assert len(m["source_urls"]) >= 10
    assert html.count("<figure>") == 6 and html.count("</figure>") == 6
    assert len(nodes) == 56
    assert m["telegraph_pending_cover_source"] == m["image_urls"][0]
    assert nodes[0]["tag"] == "figure"
    assert nodes[0]["children"][0]["attrs"]["src"] == m["image_urls"][0]
    assert "source patch awaiting authorized editPage" in m["publication_status"]
    section3 = next(
        i for i, item in enumerate(nodes) if item.get("tag") == "h3" and "3. Одна гравюра" in item["children"][0]
    )
    old_engraving = next(
        i
        for i, item in enumerate(nodes)
        if item.get("tag") == "figure" and item["children"][0]["attrs"]["src"].endswith("DP818745.jpg")
    )
    assert old_engraving == section3 + 2
    assert m["nodes_bytes"] == len(json.dumps(nodes, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert "мясной и рыбной начинкой" in html
    assert "1815" in html
    assert m["html_sha256"] == "sha256:" + hashlib.sha256(HTML.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert m["nodes_sha256"] == "sha256:" + hashlib.sha256(NODES.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert "https://www.metmuseum.org/art/collection/search/390804" in m["source_urls"]
    assert "https://gallica.bnf.fr/accueil/fr/html/surprenante-patisserie" in m["source_urls"]


def test_exact_telegram_caption_points_at_existing_telegraph_page_with_five_images(tmp_path: Path) -> None:
    release = load_release(RELEASE)
    assert release.release_authorized
    assert release.release_id == "milovi-feed-20261107-003"
    assert release.channel_username == "@MiloviCake"
    assert release.chat_id == -1002215328390
    assert release.bot_id == 8716602202
    assert release.daily_verified_limit == 2
    assert len(release.items) == 1
    item = release.items[0]
    assert item.scheduled_at == datetime(2026, 11, 7, 16, 49, tzinfo=ZoneInfo("Europe/Moscow"))
    assert isinstance(item.payload, GenericRichPhotoPayload)
    assert item.payload.schema_version == 2
    assert item.payload.parse_mode == "HTML"
    assert ARTICLE_URL in item.payload.caption
    assert "https://milovicake.ru/" in item.payload.caption
    assert "Иллюстрация" not in item.payload.expected_plain_caption
    assert len(item.payload.expected_plain_caption) < 1024
    assert sum(e.type == "text_link" for e in item.payload.expected_caption_entities) == 2
    assert any(e.type == "bold" for e in item.payload.expected_caption_entities)
    assert any(e.type == "italic" for e in item.payload.expected_caption_entities)
    assert validate_bundle(release.release_id, require_execution_authorized=True)["valid"]
    state_init(release.release_id, state_checkout=tmp_path)
    path = tmp_path / "content/telegram/milovi-cake/feed/milovi-feed-20261107-003.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    assert ledger["entries"][release.release_id]["state"] == "pending"
    assert ledger["entries"][release.release_id]["provider_effect"] == "impossible"
    assert ledger["entries"][release.release_id]["message_id"] is None


def test_workflow_is_single_writer_date_gated_not_provider_client() -> None:
    data = YAML.read_text(encoding="utf-8")
    assert "  schedule:" not in data
    assert "TZ=Europe/Moscow date +%Y-%m-%d" not in data
    assert "Nov 7" in data
    assert "milovi-cake-telegram-publisher" in data
    assert "milovi-telegram-feed-publisher.yml" not in data
    assert "-f operation=publish" not in data
    assert "PUBLISH:@MiloviCake:$PUBLICATION_ID" not in data
    assert "workflow_run.head_sha == github.sha" in data
    assert "state/milovi-cake-telegram" in data
    assert "sendPhoto" not in data
    assert "milovi_history_release_20261108.py migrate" in data
    assert "milovi_history_release_20261108.py due" not in data
    assert "milovi_telegram_feed initialize-state" not in data
    assert "curl" not in data
