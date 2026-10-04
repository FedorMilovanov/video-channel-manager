from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue
from video_channel_manager.telegram_quote_quality_v4 import (
    assert_future_suffix_quality,
    matched_context_marker,
    semantic_blocks,
    standalone_quote_issues,
)
from video_channel_manager.telegram_quote_standalone_review import (
    ReviewedStandaloneSuffix,
    assert_reviewed_standalone_suffix,
    load_standalone_review,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/telegram/lordchrist"
REVIEW_PATH = CONTENT / "quote-standalone-review-v1.json"


def _reviewed() -> ReviewedStandaloneSuffix:
    return load_standalone_review(REVIEW_PATH)


def _queue():
    return build_depth_runtime_queue(
        candidate_path=CONTENT / "successor-quotes-v1.json",
        translation_ledger_path=CONTENT / "successor-translation-ledger-v1.json",
        integrity_amendment_path=CONTENT / "successor-integrity-amendments-v1.json",
    )


def _with_quote(post, quote: str):
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    expected_attribution = f"— {post.attribution_text}"
    attribution_index = blocks.index(expected_attribution)
    text = "\n\n".join([quote, *blocks[attribution_index:]])
    return post.model_copy(update={"text": text})


def semantic_quotation_sha256(post) -> str:
    from video_channel_manager.telegram_quote_standalone_review import quotation_sha256

    return quotation_sha256(semantic_blocks(post)[0])


def _reviewed_title_for(reviewed: ReviewedStandaloneSuffix, publication_id: str) -> str | None:
    return {
        entry.publication_id: entry.title_context_reference
        for entry in reviewed.entries
        if entry.opening == "title_resolved_anaphora"
    }.get(publication_id)


def test_every_pending_sequence_16_to_60_passes_reviewed_quote_v4_quality_gate() -> None:
    queue = _queue()
    reviewed = _reviewed()

    assert [post.sequence for post in queue.posts[15:]] == list(range(16, 61))
    assert_future_suffix_quality(queue.posts, reviewed=reviewed, published_boundary=15)
    resolved = {entry.publication_id for entry in reviewed.entries if entry.opening == "title_resolved_anaphora"}
    assert len(resolved) == 3
    for post in queue.posts[15:]:
        issues = standalone_quote_issues(post, reviewed_title=_reviewed_title_for(reviewed, post.publication_id))
        assert issues == (), (post.sequence, issues)


def test_reviewed_title_context_resolves_gurnall_plural_pronoun_without_rewriting_quote() -> None:
    post = _queue().posts[16]
    reviewed = _reviewed()

    assert post.sequence == 17
    assert post.title == "Доспехи для страдания, не от страдания"
    assert semantic_blocks(post)[0].startswith("Они даны защищать его в страдании")
    assert matched_context_marker(semantic_blocks(post)[0]) == "они "
    assert _reviewed_title_for(reviewed, post.publication_id) == post.title
    assert standalone_quote_issues(post, reviewed_title=post.title) == ()


def test_reviewed_title_context_resolves_chrysostom_and_bunyan_pronouns_without_rewriting_quote() -> None:
    queue = _queue()
    reviewed = _reviewed()

    chrysostom = queue.posts[31]
    assert chrysostom.title == "Послушание Сына не делает Его рабом"
    assert semantic_blocks(chrysostom)[0].startswith("Он стал послушен как Сын Своему Отцу")
    assert standalone_quote_issues(chrysostom, reviewed_title=chrysostom.title) == ()

    bunyan = queue.posts[35]
    assert bunyan.title == "Его победа — моя во Христе"
    assert semantic_blocks(bunyan)[0].startswith("Если Он и я едины")
    assert matched_context_marker(semantic_blocks(bunyan)[0]) == "если он "
    assert _reviewed_title_for(reviewed, bunyan.publication_id) == bunyan.title
    assert standalone_quote_issues(bunyan, reviewed_title=bunyan.title) == ()


def test_context_dependent_all_other_opening_is_rejected_even_with_visible_title() -> None:
    queue = _queue()
    reviewed = _reviewed()
    victim = queue.posts[15]
    contaminated = victim.model_copy(
        update={"text": _with_quote(victim, "Все иные пути умерщвления греха тщетны.").text}
    )

    assert matched_context_marker(semantic_blocks(contaminated)[0]) == "все иные "
    issues = standalone_quote_issues(contaminated)
    assert any(issue.code == "context_dependent_opening" for issue in issues)

    # No reviewed entry may silently turn the previously published defect into an
    # accepted quote-v4 opening: the reviewed ledger is bound per publication, so
    # the untouched ledger already rejects the substituted quotation.
    assert _reviewed_title_for(reviewed, contaminated.publication_id) is None
    with pytest.raises(ValueError, match="quotation differs from the reviewed text"):
        assert_future_suffix_quality(
            (*queue.posts[:15], contaminated, *queue.posts[16:]),
            reviewed=reviewed,
            published_boundary=15,
        )

    # Even a re-reviewed, hash-consistent entry may not declare a dependent
    # opening self-contained; the deterministic detector still wins.
    entry = reviewed.entries[0]
    rewritten = reviewed.model_copy(
        update={
            "entries": (
                entry.model_copy(
                    update={
                        "opening": "self_contained",
                        "title_context_reference": None,
                        "quotation_sha256": semantic_quotation_sha256(contaminated),
                    }
                ),
                *reviewed.entries[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="context_dependent_opening"):
        assert_future_suffix_quality(
            (*queue.posts[:15], contaminated, *queue.posts[16:]),
            reviewed=rewritten,
            published_boundary=15,
        )


def test_unreviewed_pronoun_opening_is_rejected() -> None:
    post = _with_quote(_queue().posts[15], "Они даны нам милостью Божией для укрепления веры в Него.")

    issues = standalone_quote_issues(post)

    assert any(issue.code == "context_dependent_opening" for issue in issues)


def test_reviewed_pronoun_resolution_is_bound_to_exact_title() -> None:
    post = _queue().posts[16].model_copy(update={"title": "Другая формулировка заголовка"})
    reviewed = _reviewed()

    issues = standalone_quote_issues(post, reviewed_title=_reviewed_title_for(reviewed, post.publication_id))

    assert any(issue.code == "title_resolution_mismatch" for issue in issues)


def test_short_complete_aphorism_is_not_rejected_for_word_count() -> None:
    queue = _queue()
    reviewed = _reviewed()

    for sequence in (37, 42):
        post = queue.posts[sequence - 1]
        assert len(semantic_blocks(post)[0]) < 40
        assert standalone_quote_issues(post) == ()
    assert_future_suffix_quality(queue.posts, reviewed=reviewed, published_boundary=15)


def test_fragment_starting_mid_sentence_is_rejected_by_the_structural_contract() -> None:
    post = _with_quote(_queue().posts[15], "христианин должен искать мира со всеми.")

    issues = standalone_quote_issues(post)

    assert any(issue.code == "incomplete_quotation_fragment" for issue in issues)


def test_fragment_without_sentence_ending_is_rejected_by_the_structural_contract() -> None:
    post = _with_quote(_queue().posts[15], "Благодать Божия, которая спасает грешника и потому")

    issues = standalone_quote_issues(post)

    assert any(issue.code == "incomplete_quotation_fragment" for issue in issues)


def test_thin_editorial_context_is_rejected_without_relying_on_a_character_count() -> None:
    post = _queue().posts[15]
    blocks = [block.strip() for block in post.text.split("\n\n") if block.strip()]
    attribution_index = blocks.index(f"— {post.attribution_text}")
    text = "\n\n".join([*blocks[: attribution_index + 1], "Бог благ.", blocks[-1]])
    thinned = post.model_copy(update={"text": text})

    issues = standalone_quote_issues(thinned)

    assert any(issue.code == "context_not_substantive" for issue in issues)


def test_quality_gate_requires_the_reviewed_ledger_to_match_the_exact_content() -> None:
    queue = _queue()
    reviewed = _reviewed()
    entry = reviewed.entries[0]
    tampered = reviewed.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"payload_sha256": "sha256:" + "0" * 64}),
                *reviewed.entries[1:],
            )
        }
    )

    with pytest.raises(ValueError, match="bound to different content"):
        assert_reviewed_standalone_suffix(tampered, queue.posts, published_boundary=15)


def test_quality_gate_rejects_an_unreviewed_suffix_entry() -> None:
    queue = _queue()
    reviewed = _reviewed()
    truncated = reviewed.model_copy(update={"entries": reviewed.entries[:-1]})

    with pytest.raises(ValueError, match="is missing pending publication"):
        assert_reviewed_standalone_suffix(truncated, queue.posts, published_boundary=15)


def test_quality_gate_does_not_mutate_published_prefix() -> None:
    queue = _queue()
    reviewed = _reviewed()
    published_before = tuple(post.model_dump(mode="json") for post in queue.posts[:15])

    assert_future_suffix_quality(queue.posts, reviewed=reviewed, published_boundary=15)

    published_after = tuple(post.model_dump(mode="json") for post in queue.posts[:15])
    assert published_after == published_before
