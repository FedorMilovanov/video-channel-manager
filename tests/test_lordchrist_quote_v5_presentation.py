from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.telegram_models import canonical_json, sha256_text
from video_channel_manager.telegram_presentation import (
    DEFAULT_QUOTE_V5_PRESENTATION_POLICY,
    QuotePresentationPolicyV5,
    load_presentation_policy,
    render_post,
)
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue, build_depth_v3_runtime_queue
from video_channel_manager.telegram_quote_standalone_review import load_standalone_review

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
EXPECTED_V5_DIGEST = "sha256:4607230a3385d81d94dc49bd498fbe8f2fbd2d13e029710acf1413b1f8ef2f42"


def _queue(release: str = "v2"):
    builder = build_depth_v3_runtime_queue if release == "v3" else build_depth_runtime_queue
    return builder(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )


def _sequence(sequence: int, release: str = "v2"):
    post = _queue(release).posts[sequence - 1]
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
    assert policy.title_mode == "none"
    assert policy.quote_to_attribution_separator == "\n"
    assert policy.block_separator == "\n\n"
    assert policy == DEFAULT_QUOTE_V5_PRESENTATION_POLICY


def test_quote_v5_policy_file_matches_the_reviewed_default_exactly() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")

    assert policy.model_dump(mode="json") == DEFAULT_QUOTE_V5_PRESENTATION_POLICY.model_dump(mode="json")


def test_quote_v5_review_v2_forbids_title_resolved_anaphora_openings() -> None:
    review = load_standalone_review(CONTENT / "quote-standalone-review-v2.json")

    assert review.schema_version == 2
    assert review.published_boundary == 17
    assert {entry.opening for entry in review.entries} == {"self_contained"}
    assert all(entry.title_context_reference is None for entry in review.entries)


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


def test_quote_v5_restored_anaphora_slots_open_complete_without_any_title() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")

    for sequence, opening in (
        (32, "Христос стал послушным Отцу как Сын"),
        (36, "Если Христос и я соединены"),
    ):
        post = _sequence(sequence, release="v3")
        rendered = render_post(post, policy)
        quote, attribution = _quote_and_attribution(post)

        assert quote.startswith(opening)
        assert rendered.text.startswith(f"{quote}\n{attribution}\n\n")
        assert not rendered.text.startswith(post.title)
        assert [entity.type for entity in rendered.expected_entities] == ["blockquote", "italic"]


def test_quote_v5_short_aphorism_renders_quote_first_without_title() -> None:
    post = _sequence(43)
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    rendered = render_post(post, policy)
    quote, attribution = _quote_and_attribution(post)

    assert quote.startswith("Спасает не интенсивность нашей веры")
    assert rendered.text.startswith(f"{quote}\n{attribution}")
    assert [entity.type for entity in rendered.expected_entities] == ["blockquote", "italic"]


def test_quote_v5_pending_suffix_renders_no_titles_at_all() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v5.json")
    queue = _queue(release="v3")

    for post in queue.posts[17:]:
        rendered = render_post(post, policy)
        entity_types = [entity.type for entity in rendered.expected_entities]
        assert entity_types == ["blockquote", "italic"], post.publication_id


def test_quote_v5_rejects_legacy_title_binding_payloads() -> None:
    payload = DEFAULT_QUOTE_V5_PRESENTATION_POLICY.model_dump(mode="json")
    payload["reviewed_title_payload_sha256s"] = [
        "sha256:3a822e24da42fb4f6e8f2575be5539c4484ffeec395706f57811af5b636e09d8"
    ]

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        QuotePresentationPolicyV5.model_validate(payload)


def test_quote_v5_policy_carries_no_hidden_digest_drift() -> None:
    payload = DEFAULT_QUOTE_V5_PRESENTATION_POLICY.model_dump(mode="json")

    assert sha256_text(canonical_json(payload)) == EXPECTED_V5_DIGEST
