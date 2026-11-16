"""Static acceptance checks for original #1619 popup-only rich message markup."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from video_channel_manager import lordchrist_peasants1525_popup_preview as popup
from video_channel_manager.lordchrist_peasants1525_inplace import (
    PAGE_URL,
    PUBLICATION_ID,
)
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    _find_item,
    load_telegraph_queue,
)

ROOT = Path(__file__).resolve().parents[1]


def _post():
    queue = load_telegraph_queue(ROOT / DEFAULT_QUEUE_PATH, ROOT)
    item = _find_item(queue, PUBLICATION_ID)
    return item.channel_post


def test_four_native_inline_callback_definitions_not_telegraph_links():
    rendered = popup.render(_post())
    assert set(rendered) == {"html", "skip_entity_detection"}
    assert rendered["skip_entity_detection"] is True
    html = rendered["html"]
    assert html.count("<tg-button ") == 4
    assert html.count('style="link"') == 4
    for term in popup.TERM_KEYS:
        assert html.count('data="lc1525:' + term + '"') == 1
    assert "<tg-reference" not in html
    assert "name=" not in html
    assert 'data="lc1525:pastor"' not in html
    assert 'data="lc1525:luther"' not in html
    assert html.count(PAGE_URL) == 1


def test_authorized_identity_and_original_page_are_unchanged():
    assert popup.POST_MESSAGE_ID == 1619
    assert popup.REQUIRED_CHAT_ID == -1001295216957
    assert popup.REQUIRED_BOT_ID == 8716602202
    assert popup.CALLBACK_PREFIX == "lc1525:"
    rendered = popup.render(_post())["html"]
    assert rendered.startswith("<p><b>1525 ГОД:")
    assert "Мартина Лютера" in rendered
    assert "выбирать пастора" in rendered
    assert "<blockquote expandable>" in rendered
    assert rendered.endswith("</a></p>")
    assert popup.ARTICLE_CTA in rendered


def test_no_extra_footer_no_story_unfriendly_tables_or_media():
    rendered = popup.render(_post())["html"]
    assert "<table" not in rendered
    assert "<tg-button-row" not in rendered
    assert "<footer" not in rendered
    assert "<img" not in rendered
    assert "<h1>" not in rendered
    assert rendered.count("<p>") == 5
    assert rendered.count("<blockquote") == 2
    assert rendered.count("<br><br>") == 4
    assert rendered.index("Меммингена") < rendered.index(popup.ARTICLE_CTA)


def test_invalid_term_is_rejected():
    with pytest.raises(ValueError, match="Unknown glossary term"):
        popup._button("пастора", "pastor")


def test_changed_editorial_text_fails_closed():
    post = _post()
    edited = replace(post, lead_paragraphs=("Несогласованная замена текста", post.lead_paragraphs[1]))
    with pytest.raises(ValueError, match="Editorial term occurrence changed"):
        popup.render(edited)
