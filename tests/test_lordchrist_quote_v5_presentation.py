from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.telegram_presentation import (
    DEFAULT_QUOTE_V5_PRESENTATION_POLICY,
    QuotePresentationPolicyV5,
    load_presentation_policy,
    render_post,
)
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_standalone_review import load_standalone_review

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
EXPECTED_V5_DIGEST = "sha256:1baa56feba381fcf6147222a8cdc6e0e2da569ad9af3b159fe1b0e548307c1f6"

REVIEWED_TITLE_PAYLOADS = {
    "sha256:3a822e24da42fb4f6e8f2575be5539c4484ffeec395706f57811af5b636e09d8",  # 17 gurnall
    "sha256:9343f845d7ad45803a57110ac68f25bfbc1029fbbb3c94773327fbb125de9b77",  # 32 chrysostom
    "sha256:e761a1a22bfa697f405227702ddbc4a7057b662d79bcef28954c46c791bf0abb",  # 36 bunyan
}


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
    attribution = f"— {post.attribution_text}"
    attribution_index = blocks.index(attribution)
    quote = "\n\n".join(blocks[:attribution_index])
    return quote, attribution


def test_quote_v5_policy_digest_is_exact_and_reviewed() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")

    assert policy.policy_id == "lordchrist-quote-v5"
    assert policy.digest == EXPECTED_V5_DIGEST
    assert policy.title_mode == "reviewed_load_bearing_only"
    assert set(policy.reviewed_title_payload_sha256s) == REVIEWED_TITLE_PAYLOADS
    assert policy.title_style == "bold"
    assert policy.title_to_quote_separator == "\n\n"
    assert policy.quote_to_attribution_separator == "\n"
    assert policy.block_separator == "\n\n"


def test_quote_v5_title_bindings_match_the_reviewed_standalone_evidence() -> None:
    review = load_standalone_review(CONTENT / "quote-standalone-review-v1.json")
    reviewed = {entry.payload_sha256 for entry in review.entries if entry.opening == "title_resolved_anaphora"}

    assert reviewed == set(DEFAULT_QUOTE_V5_PRESENTATION_POLICY.reviewed_title_payload_sha256s)


def test_quote_v5_opens_self_contained_cards_directly_with_the_quotation() -> None:
    post = _sequence(18)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)
    hashtag_block = post.text.rsplit("\n\n", 1)[-1]

    assert rendered.presentation_policy_id == "lordchrist-quote-v5"
    assert rendered.text.startswith(f"{quote}\n{attribution}\n\n")
    assert not rendered.text.startswith(post.title)
    assert f"{quote}\n\n{attribution}" not in rendered.text
    assert rendered.text.count(attribution) == 1
    assert rendered.text.endswith(hashtag_block)
    assert [entity.type for entity in rendered.expected_entities] == ["blockquote", "italic"]


def test_quote_v5_keeps_title_only_for_reviewed_load_bearing_openings_with_air() -> None:
    post = _sequence(17)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    assert quote.startswith("Они даны защищать его в страдании")
    assert rendered.text.startswith(f"{post.title}\n\n{quote}\n{attribution}\n\n")
    assert f"{post.title}\n{quote}" not in rendered.text
    assert f"{quote}\n\n{attribution}" not in rendered.text
    assert [entity.type for entity in rendered.expected_entities] == ["bold", "blockquote", "italic"]


def test_quote_v5_short_aphorism_renders_quote_first_without_title() -> None:
    post = _sequence(43)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    assert quote.startswith("Спасает не интенсивность нашей веры")
    assert rendered.text.startswith(f"{quote}\n{attribution}")
    assert [entity.type for entity in rendered.expected_entities] == ["blockquote", "italic"]


def test_quote_v5_pending_suffix_renders_only_three_reviewed_titles() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    queue = build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )
    titled = [
        post.sequence
        for post in queue.posts[16:]
        if post.payload_sha256 in policy.reviewed_title_payload_sha256s
    ]

    assert titled == [17, 32, 36]


def test_quote_v5_rejects_duplicate_title_bindings() -> None:
    payload = DEFAULT_QUOTE_V5_PRESENTATION_POLICY.model_dump(mode="json")
    binding = payload["reviewed_title_payload_sha256s"][0]
    payload["reviewed_title_payload_sha256s"] = [binding, binding, binding]

    with pytest.raises(ValueError, match="unique"):
        QuotePresentationPolicyV5.model_validate(payload)
