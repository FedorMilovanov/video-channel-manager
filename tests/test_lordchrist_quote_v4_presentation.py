from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
EXPECTED_V4_DIGEST = "sha256:a87dd04d605a749c84ecd47d18c127dd921dddea500781c0fd75a0db20a7be9f"


def _sequence(sequence: int):
    queue = build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )
    post = queue.posts[sequence - 1]
    assert post.sequence == sequence
    return post


def _quote_and_attribution(post):
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    # The reader-facing source line is the reviewed attribution verbatim.
    attribution = f"— {post.attribution_text}"
    attribution_index = blocks.index(attribution)
    quote = "\n\n".join(blocks[:attribution_index])
    return quote, attribution


def test_quote_v4_policy_digest_is_exact_and_reviewed() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    assert policy.policy_id == "lordchrist-quote-v4"
    assert policy.digest == EXPECTED_V4_DIGEST
    assert policy.title_style == "bold"
    assert policy.title_to_quote_separator == "\n"
    assert policy.quote_to_attribution_separator == "\n"
    assert policy.block_separator == "\n\n"


def test_quote_v4_places_title_quote_and_source_in_one_tight_reading_unit() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)
    hashtag_block = post.text.rsplit("\n\n", 1)[-1]

    assert rendered.presentation_policy_id == "lordchrist-quote-v4"
    assert rendered.text.startswith(f"{post.title}\n{quote}\n{attribution}\n\n")
    assert f"{post.title}\n\n{quote}" not in rendered.text
    assert f"{quote}\n\n{attribution}" not in rendered.text
    assert rendered.text.count(attribution) == 1
    assert rendered.text.endswith(hashtag_block)


def test_quote_v4_keeps_bold_title_native_blockquote_and_italic_source_entities() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)

    entity_types = [entity.type for entity in rendered.expected_entities]
    assert entity_types == ["bold", "blockquote", "italic"]
    assert rendered.provider_payload_sha256.startswith("sha256:")
    assert len(rendered.provider_payload_sha256) == 71


def test_quote_v4_title_makes_gurnall_pronoun_referent_visible_without_rewriting_quote() -> None:
    post = _sequence(17)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    assert quote.startswith("Они даны защищать его в страдании")
    assert rendered.text.startswith(f"Доспехи для страдания, не от страдания\n{quote}\n{attribution}")


def test_quote_v4_title_makes_chrysostom_pronoun_referent_visible_without_rewriting_quote() -> None:
    post = _sequence(32)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    assert quote.startswith("Он стал послушен как Сын Своему Отцу")
    assert rendered.text.startswith(f"Послушание Сына не делает Его рабом\n{quote}\n{attribution}")


def test_quote_v4_rendering_is_deterministic_for_same_reviewed_input() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    first = render_post(post, policy)
    second = render_post(post, policy)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def _revalidated(post, **updates):
    """Rebuild a runtime post through validation, so model contracts really apply."""

    payload = post.model_dump(mode="json")
    payload.update(updates)
    return type(post).model_validate(payload)


def _with_reviewed_attribution(post, attribution_text: str):
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    blocks[blocks.index(f"— {post.attribution_text}")] = f"— {attribution_text}"
    return _revalidated(post, attribution_text=attribution_text, text="\n\n".join(blocks))


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def test_quote_v4_uses_the_reviewed_attribution_line_for_every_pending_card() -> None:
    """Systemic guard against the nested-quotation attribution defect.

    The reader-facing line is the reviewed attribution verbatim. Re-deriving it
    from the normalized evidence identity used to produce lines such as
    '— Чарльз Сперджен, «проповедь «Божественный суверенитет», 1856»'.
    """

    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    queue = build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )

    checked = 0
    for post in queue.posts[15:]:
        rendered = render_post(post, policy)
        attribution = f"— {post.attribution_text}"
        quote = _quote_and_attribution(post)[0]

        assert attribution.count("«") == attribution.count("»"), post.publication_id
        depth = 0
        for character in attribution:
            if character == "«":
                assert depth == 0, post.publication_id
                depth += 1
            elif character == "»":
                depth -= 1
        assert depth == 0, post.publication_id

        assert f"{quote}\n{attribution}" in rendered.text, post.publication_id
        assert f"{quote}\n\n{attribution}" not in rendered.text, post.publication_id
        italic = [entity for entity in rendered.expected_entities if entity.type == "italic"]
        assert len(italic) == 1, post.publication_id
        assert italic[0].length == _utf16_length(attribution), post.publication_id
        assert rendered.text[italic[0].offset : italic[0].offset + _utf16_length(attribution)] == attribution
        checked += 1

    assert checked == 45


def test_quote_v4_attribution_entity_starts_after_the_blockquote_and_never_inside_it() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    bold, blockquote, italic = rendered.expected_entities
    assert bold.type == "bold" and blockquote.type == "blockquote" and italic.type == "italic"
    assert bold.offset == 0
    assert blockquote.offset == _utf16_length(post.title) + 1
    assert blockquote.length == _utf16_length(quote)
    assert italic.offset == blockquote.offset + blockquote.length + 1
    assert italic.offset + italic.length == _utf16_length(f"{post.title}\n{quote}\n{attribution}")


def test_quote_v4_provider_payload_hash_is_deterministic_and_attribution_sensitive() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    first = render_post(post, policy)
    second = render_post(post, policy)
    assert first.provider_payload_sha256 == second.provider_payload_sha256

    changed = _with_reviewed_attribution(post, "Чарльз Сперджен, «Божественный суверенитет», 1856")
    assert render_post(changed, policy).provider_payload_sha256 != first.provider_payload_sha256


def test_quote_v4_rejects_a_reviewed_attribution_that_nests_quotation_marks() -> None:
    from pydantic import ValidationError

    post = _sequence(16)

    with pytest.raises(ValidationError, match="must not nest quotation marks"):
        _revalidated(post, attribution_text="Чарльз Сперджен, «проповедь «Божественный суверенитет», 1856»")
    with pytest.raises(ValidationError, match="must keep balanced quotation marks"):
        _revalidated(post, attribution_text="Чарльз Сперджен, «Божественный суверенитет")
    with pytest.raises(ValidationError, match="must begin with the reviewed source author"):
        _revalidated(post, attribution_text="Неизвестный автор, «Божественный суверенитет»")
    with pytest.raises(ValidationError, match="normalized single line"):
        _revalidated(post, attribution_text="Чарльз Сперджен,  «Божественный суверенитет»")


def test_quote_v4_rejects_a_non_standalone_quotation_fragment() -> None:
    post = _sequence(16)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    after_quote = blocks[1:]

    fragment = post.model_copy(
        update={"text": "\n\n".join(["и потому мы приходим к выводу о суверенитете.", *after_quote])}
    )
    with pytest.raises(ValueError, match="must not start mid-sentence"):
        render_post(fragment, policy)

    truncated = post.model_copy(
        update={"text": "\n\n".join(["Нет свойства Бога более утешительного для Его детей, чем", *after_quote])}
    )
    with pytest.raises(ValueError, match="must keep the source sentence ending"):
        render_post(truncated, policy)


def test_short_complete_aphorism_renders_without_a_length_floor() -> None:
    post = _sequence(42)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    quote, attribution = _quote_and_attribution(post)

    assert quote == "Сам Бог есть удел святых."
    rendered = render_post(post, policy)

    assert rendered.text.startswith(f"Наследие святых — Сам Бог\n{quote}\n{attribution}\n\n")
