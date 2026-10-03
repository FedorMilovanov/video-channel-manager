from __future__ import annotations

from pathlib import Path

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
    attribution = f"— {post.source.author}, «{post.source.work}»"
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
