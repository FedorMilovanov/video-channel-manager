from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_quality_v4 import assert_future_suffix_quality, standalone_quote_issues

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"


def _queue():
    return build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )


def _with_quote(post, quote: str):
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    expected_attribution = f"— {post.source.author}, «{post.source.work}»"
    attribution_index = blocks.index(expected_attribution)
    text = "\n\n".join([quote, *blocks[attribution_index:]])
    return post.model_copy(update={"text": text})


def test_every_pending_sequence_16_to_60_passes_standalone_quote_quality_gate() -> None:
    queue = _queue()

    assert [post.sequence for post in queue.posts[15:]] == list(range(16, 61))
    assert_future_suffix_quality(queue.posts, published_boundary=15)


def test_context_dependent_all_other_opening_is_rejected() -> None:
    post = _with_quote(_queue().posts[15], "Все иные пути умерщвления греха тщетны.")

    issues = standalone_quote_issues(post)

    assert any(issue.code == "context_dependent_opening" for issue in issues)


def test_unresolved_pronoun_opening_is_rejected() -> None:
    post = _with_quote(_queue().posts[15], "Они даны нам милостью Божией для укрепления веры.")

    issues = standalone_quote_issues(post)

    assert any(issue.code == "context_dependent_opening" for issue in issues)


def test_short_complete_aphorism_is_not_rejected_for_word_count() -> None:
    post = _queue().posts[36]

    assert post.sequence == 37
    assert standalone_quote_issues(post) == ()


def test_quality_gate_never_retroactively_parses_or_rewrites_published_prefix() -> None:
    queue = _queue()
    published_before = tuple(post.model_dump(mode="json") for post in queue.posts[:15])

    assert_future_suffix_quality(queue.posts, published_boundary=15)

    published_after = tuple(post.model_dump(mode="json") for post in queue.posts[:15])
    assert published_after == published_before
