from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_presentation import load_presentation_policy, render_post
from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
EXPECTED_V4_DIGEST = "sha256:e1a7ccefffbf02e2f1bd743d0119769c2717ec0738252959b39df1b8d0d1e7a1"


def _sequence_16():
    queue = build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )
    post = queue.posts[15]
    assert post.sequence == 16
    return post


def test_quote_v4_policy_digest_is_exact_and_reviewed() -> None:
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    assert policy.policy_id == "lordchrist-quote-v4"
    assert policy.digest == EXPECTED_V4_DIGEST
    assert policy.quote_to_attribution_separator == "\n"
    assert policy.block_separator == "\n\n"


def test_quote_v4_places_source_on_immediate_next_line_without_blank_air() -> None:
    post = _sequence_16()
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)
    attribution = f"— {post.source.author}, «{post.source.work}»"
    hashtag_block = post.text.rsplit("\n\n", 1)[-1]

    assert rendered.presentation_policy_id == "lordchrist-quote-v4"
    assert f"\n{attribution}\n\n" in rendered.text
    assert f"\n\n{attribution}" not in rendered.text
    assert rendered.text.count(attribution) == 1
    assert rendered.text.endswith(hashtag_block)


def test_quote_v4_keeps_native_blockquote_and_italic_source_entities() -> None:
    post = _sequence_16()
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")
    rendered = render_post(post, policy)

    entity_types = [entity.type for entity in rendered.expected_entities]
    assert entity_types == ["blockquote", "italic"]
    assert rendered.provider_payload_sha256.startswith("sha256:")
    assert len(rendered.provider_payload_sha256) == 71


def test_quote_v4_rendering_is_deterministic_for_same_reviewed_input() -> None:
    post = _sequence_16()
    policy = load_presentation_policy(CONTENT / "presentation-policy-v4.json")

    first = render_post(post, policy)
    second = render_post(post, policy)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
