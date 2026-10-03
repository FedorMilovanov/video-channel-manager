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


def test_every_pending_sequence_16_to_60_passes_standalone_quote_quality_gate() -> None:
    queue = _queue()

    assert [post.sequence for post in queue.posts[15:]] == list(range(16, 61))
    assert_future_suffix_quality(queue.posts, published_boundary=15)


def test_quality_gate_never_retroactively_rewrites_published_prefix() -> None:
    queue = _queue()

    for post in queue.posts[:15]:
        # Historical material may predate the new rule. This call is diagnostic
        # only; enforcement begins at sequence 16 and cannot mutate history.
        standalone_quote_issues(post)
    assert [post.sequence for post in queue.posts[:15]] == list(range(1, 16))
