from __future__ import annotations

import json
import re
from pathlib import Path

from video_channel_manager.telegram_presentation import (
    CANONICAL_PRESENTATION_POLICY_PATH,
    DEFAULT_PRESENTATION_POLICY,
    formatting_entities_match,
    load_presentation_policy,
    render_post,
    verify_rendered_post,
)
from video_channel_manager.telegram_publisher import TelegramPost, TelegramQueue, load_queue

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/lordchrist/verified-30-posts.json"
POLICY_PATH = REPOSITORY_ROOT / CANONICAL_PRESENTATION_POLICY_PATH
EXPECTED_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
DIRECT_QUOTE_RE = re.compile(r"«[^»\n]+»")


def _queue_payload() -> dict[str, object]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def _body_quote_count(post: TelegramPost) -> int:
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    return sum(len(DIRECT_QUOTE_RE.findall(block)) for block in blocks[:-2])


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def test_repository_presentation_policy_is_exact_reviewed_v2() -> None:
    policy = load_presentation_policy(POLICY_PATH)
    assert policy == DEFAULT_PRESENTATION_POLICY
    assert policy.policy_id == "lordchrist-editorial-v2"
    assert policy.schema_version == 2
    assert policy.body_quote_emphasis.bold_selection == "longest_direct_quote"
    assert policy.parse_mode == "HTML"
    assert policy.spacing.attribution_to_hashtags == "\n\n\n"
    assert policy.attribution.copyright_prefix is False
    assert policy.link_preview_disabled is True


def test_first_canary_still_renders_like_approved_editorial_style() -> None:
    queue = load_queue(QUEUE_PATH)
    post = queue.posts[0]
    rendered = render_post(post)
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    expected_plain = (
        "\n\n".join(blocks[:-2]) + "\n\n" + f"{post.source.author}, «{post.source.work}»" + "\n\n\n" + blocks[-1]
    )

    assert rendered.text == expected_plain
    assert "© " not in rendered.text
    assert "<b>«Он дал мне покой Своей скорбью и жизнь Своей смертью»</b>" in rendered.html_text
    assert "<i>«Мир тебе»</i>" in rendered.html_text
    assert "<i>«Прощаются тебе грехи твои»</i>" in rendered.html_text
    assert "<b>Джон Беньян</b>, <i>«Путешествие Пилигрима»</i>" in rendered.html_text
    assert "Путешествие Пилигрима»\n\n\n#ДжонБеньян" in rendered.text


def test_second_autonomous_post_bolds_the_substantive_christ_answer_not_the_prompt() -> None:
    queue = load_queue(QUEUE_PATH)
    post = queue.posts[1]
    assert post.publication_id == "lordchrist-bunyan-fire-grace"

    rendered = render_post(post)
    assert "<i>«Что это значит?»</i>" in rendered.html_text
    assert rendered.html_text.count("<i>«Что это значит?»</i>") == 2
    assert (
        "<b>«Это Христос, Который маслом Своей благодати непрестанно поддерживает уже начатое в сердце дело."
        in rendered.html_text
    )
    assert "<b>«Что это значит?»</b>" not in rendered.html_text


def test_all_thirty_posts_render_without_changing_source_queue_digest() -> None:
    queue = load_queue(QUEUE_PATH)
    assert queue.digest == EXPECTED_QUEUE_DIGEST

    provider_hashes: set[str] = set()
    for post in queue.posts:
        rendered = render_post(post)
        verify_rendered_post(post, DEFAULT_PRESENTATION_POLICY, rendered)

        blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
        body = "\n\n".join(blocks[:-2])
        hashtags = blocks[-1]
        expected_attribution = f"{post.source.author}, «{post.source.work}»"

        assert rendered.source_payload_sha256 == post.payload_sha256
        assert rendered.presentation_policy_id == "lordchrist-editorial-v2"
        assert rendered.presentation_policy_sha256 == DEFAULT_PRESENTATION_POLICY.digest
        assert rendered.parse_mode == "HTML"
        assert rendered.link_preview_disabled is True
        assert len(rendered.text) <= 4096
        assert rendered.text.startswith(body)
        assert f"\n\n{expected_attribution}\n\n\n{hashtags}" in rendered.text
        assert rendered.text.endswith(hashtags)
        assert "© " not in rendered.text
        assert f"<b>{post.source.author}</b>" in rendered.html_text
        assert f"<i>«{post.source.work}»</i>" in rendered.html_text
        assert rendered.provider_payload_sha256 not in provider_hashes
        provider_hashes.add(rendered.provider_payload_sha256)

        body_quotes = _body_quote_count(post)
        bold_entities = [entity for entity in rendered.expected_entities if entity.type == "bold"]
        italic_entities = [entity for entity in rendered.expected_entities if entity.type == "italic"]
        assert len(bold_entities) == 1 + (1 if body_quotes else 0), post.publication_id
        assert len(italic_entities) == 1 + max(body_quotes - 1, 0), post.publication_id

    assert len(provider_hashes) == 30


def test_longest_direct_quote_is_selected_deterministically() -> None:
    payload = _queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    text = str(first["text"])  # type: ignore[index]
    blocks = text.split("\n\n")
    body_one = (
        "Первый плотный абзац сохраняет валидную структуру карточки: «коротко». "
        "Затем здесь появляется «эта реплика заметно длиннее остальных и поэтому должна стать главным акцентом», "
        "после чего повествование спокойно продолжается без изменения исходного принципа оформления."
    )
    body_two = (
        "Второй плотный абзац нужен не ради оформления, а чтобы fixture соответствовал production schema. "
        "В нём остаётся ещё одна «коротко» реплика, но она не должна конкурировать с содержательной длинной цитатой первого абзаца."
    )
    first["text"] = body_one + "\n\n" + body_two + "\n\n" + blocks[-2] + "\n\n" + blocks[-1]  # type: ignore[index]
    post = TelegramQueue.model_validate(payload).posts[0]

    rendered = render_post(post)
    assert "<b>«эта реплика заметно длиннее остальных и поэтому должна стать главным акцентом»</b>" in rendered.html_text
    assert rendered.html_text.count("<i>«коротко»</i>") == 2
    assert "<b>«коротко»</b>" not in rendered.html_text


def test_no_direct_quote_body_does_not_invent_emphasis() -> None:
    payload = _queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    text = str(first["text"])  # type: ignore[index]
    blocks = text.split("\n\n")
    body = "\n\n".join(blocks[:-2]).replace("«", "").replace("»", "")
    first["text"] = body + "\n\n" + blocks[-2] + "\n\n" + blocks[-1]  # type: ignore[index]
    post = TelegramQueue.model_validate(payload).posts[0]

    rendered = render_post(post)
    body_length_utf16 = _utf16_length(body)
    body_entities = [entity for entity in rendered.expected_entities if entity.offset < body_length_utf16]
    assert body_entities == []
    assert [entity.type for entity in rendered.expected_entities] == ["bold", "italic"]


def test_renderer_html_escapes_source_characters_without_changing_plain_text() -> None:
    payload = _queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    original = str(first["text"])  # type: ignore[index]
    marker = "едва Христианин"
    first["text"] = original.replace(marker, "A & B < C — едва Христианин", 1)  # type: ignore[index]
    post = TelegramQueue.model_validate(payload).posts[0]

    rendered = render_post(post)
    assert "A & B < C" in rendered.text
    assert "A &amp; B &lt; C" in rendered.html_text
    assert "A & B < C" not in rendered.html_text


def test_renderer_uses_telegram_utf16_entity_offsets() -> None:
    payload = _queue_payload()
    first = payload["posts"][0]  # type: ignore[index]
    original = str(first["text"])  # type: ignore[index]
    old_quote = "«Он дал мне покой Своей скорбью и жизнь Своей смертью»"
    emoji_quote = "«🔥 Он дал мне покой Своей скорбью и жизнь Своей смертью»"
    first["text"] = original.replace(old_quote, emoji_quote, 1)  # type: ignore[index]
    post = TelegramQueue.model_validate(payload).posts[0]

    rendered = render_post(post)
    body_bold = [entity for entity in rendered.expected_entities if entity.type == "bold"][0]
    plain_before = rendered.text.split(emoji_quote, 1)[0]
    assert body_bold.offset == _utf16_length(plain_before)
    assert body_bold.length == _utf16_length(emoji_quote)
    assert body_bold.length == len(emoji_quote) + 1  # astral emoji occupies two UTF-16 code units


def test_formatting_postflight_requires_exact_bold_and_italic_entities_but_allows_hashtags() -> None:
    queue = load_queue(QUEUE_PATH)
    rendered = render_post(queue.posts[0])
    actual = [entity.model_dump(mode="json") for entity in rendered.expected_entities]
    actual.append({"type": "hashtag", "offset": 9999, "length": 10})
    assert formatting_entities_match(rendered.expected_entities, actual) is True

    wrong = [dict(item) for item in actual]
    first_formatting = next(item for item in wrong if item["type"] in {"bold", "italic"})
    first_formatting["length"] = int(first_formatting["length"]) + 1
    assert formatting_entities_match(rendered.expected_entities, wrong) is False

    assert formatting_entities_match(rendered.expected_entities, None) is False


def test_rendered_provider_hash_covers_presentation_not_only_source_text() -> None:
    queue = load_queue(QUEUE_PATH)
    first = render_post(queue.posts[0])
    second = render_post(queue.posts[1])
    assert first.provider_payload_sha256 != first.source_payload_sha256
    assert first.provider_payload_sha256 != second.provider_payload_sha256


def test_policy_json_is_canonical_and_has_no_hidden_unreviewed_keys() -> None:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy = load_presentation_policy(POLICY_PATH)
    assert raw == policy.model_dump(mode="json")
    assert set(raw) == {
        "schema_name",
        "schema_version",
        "policy_id",
        "parse_mode",
        "body_quote_emphasis",
        "attribution",
        "spacing",
        "link_preview_disabled",
    }
