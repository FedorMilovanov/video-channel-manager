"""Quote-v6 reader gate: no unapproved content reaches protected state or Telegram."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import lordchrist_quote_v6_publisher as publisher
from scripts.lordchrist_quote_v6_semantic_gate import (
    ACTIVATION_PATH,
    REVIEW_PATH,
    SemanticApprovalHold,
    _blob_sha,
    require_semantic_approval,
)
from video_channel_manager.telegram_state import initialize_ledger

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    queue = publisher.release_and_queue(ROOT)
    # A pending card, not one of the 12 historically verified publications.
    post = queue.posts[8]
    assert post.publication_id == "lordchrist-calvin-prayer-opens-treasures"
    for p in (REVIEW_PATH, ACTIVATION_PATH):
        dest = tmp_path / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / p).read_bytes())
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-github-read-only-token")
    return tmp_path, queue, post


def test_inert_context_repair_candidates_preserve_exact_original_russian_spans():
    import html
    import re

    path = ROOT / "docs/audits/2026-11-19-lordchrist-v6-context-repair-candidates-inert.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    source = json.loads(
        (ROOT / "docs/audits/2026-11-06-lordchrist-quote-v6-provider-payload-candidate-inert.json").read_text(
            encoding="utf-8"
        )
    )
    from_source = {item["publication_id"]: item for item in source["items"]}
    assert plan["state_change"] is False
    assert plan["payload_change"] is False
    assert plan["workflow_dispatch"] is False
    assert plan["review_status"] == "editorial_proposal_only_not_approved"
    assert len(plan["candidates"]) == 6
    for item in plan["candidates"]:
        original = from_source[item["publication_id"]]
        assert original["sequence"] == item["sequence"]
        span = re.search(r"<blockquote>(.*?)</blockquote>", original["html_text"], re.DOTALL)
        assert span is not None
        quote = html.unescape(span.group(1))[1:-1]
        proposal = item["source_bound_excerpt_proposal"]
        if proposal is None:
            assert item["editorial_route"]
            continue
        start, end = proposal["start"], proposal["end"]
        assert quote.count(start) == quote.count(end) == 1
        begin = quote.index(start)
        finish = quote.index(end) + len(end)
        assert finish > begin
        assert quote[begin:finish].startswith(start)
        assert quote[begin:finish].endswith(end)


def test_frozen_review_register_has_30_exact_sha_bound_cards_and_zero_grants():
    queue = publisher.release_and_queue(ROOT)
    register = json.loads((ROOT / REVIEW_PATH).read_text(encoding="utf-8"))
    activation = json.loads((ROOT / ACTIVATION_PATH).read_text(encoding="utf-8"))
    assert register["queue_digest"] == activation["queue_digest"] == queue.digest
    assert register["publication_count"] == len(queue.posts) == 30
    assert register["published_snapshot"] == 12
    assert register["pending_snapshot"] == 18
    assert activation["entries"] == []
    by_id = {card["publication_id"]: card for card in register["entries"]}
    assert len(by_id) == 30
    assert set(by_id) == {post.publication_id for post in queue.posts}
    for post in queue.posts:
        card = by_id[post.publication_id]
        assert card["payload_sha256"] == post.payload_sha256
        assert card["source_russian_sha256"] == post.source.original_ru_quote_sha256
        assert card["original_english_span_sha256"] == post.source.original_english_span_sha256
        assert card["source_url"] == post.source.url
        assert card["semantic_verdict"] != "PASS_MEANING"
        assert card["rights_clearance"] == "not_cleared"
    assert sum(card["published_history"] for card in register["entries"]) == 12


def _activate(tmp_path: Path, post):
    review_path = tmp_path / REVIEW_PATH
    review = json.loads(review_path.read_text(encoding="utf-8"))
    card = next(x for x in review["entries"] if x["publication_id"] == post.publication_id)
    card.update(
        semantic_verdict="PASS_MEANING",
        reader_thesis="Человек прибегает к Божьим обетованиям в молитве.",
        reasoning_link="Молитва позволяет поверяющему обетования обращаться к Богу с нуждами.",
        reader_misreading="Читатель может ошибочно принять молитву за способ заставить Бога действовать.",
        edition_and_rights_note="Сверена оригинальная редакция; допустимость выбранного перевода документирована.",
        contiguous_source_span_verified=True,
        original_collation="independently_verified",
        russian_translation_review="independently_verified",
        rights_clearance="documented_cleared",
    )
    review_path.write_text(json.dumps(review, ensure_ascii=False) + "\n", encoding="utf-8")
    activation = json.loads((tmp_path / ACTIVATION_PATH).read_text(encoding="utf-8"))
    activation["entries"] = [
        {
            "publication_id": post.publication_id,
            "review_pr_number": 1045,
            "approved_pr_head_sha": "a" * 40,
            "reviewer_login": "independent-reader",
            "github_approval_review_id": 12345,
        }
    ]
    (tmp_path / ACTIVATION_PATH).write_text(json.dumps(activation, ensure_ascii=False) + "\n", encoding="utf-8")


def _github_receipt(tmp_path: Path, *, mode: str = "valid"):
    def get_json(url: str, token: str):
        assert token == "fixture-github-read-only-token"
        if url.endswith("/pulls/1045"):
            return {
                "merged_at": "2026-11-19T20:00:00Z",
                "base": {"ref": "main"},
                "head": {"sha": "a" * 40},
                "user": {"login": "different-review-author" if mode != "self" else "independent-reader"},
            }
        if url.endswith("/contents/" + REVIEW_PATH.as_posix() + "?ref=" + "a" * 40):
            return {"sha": "f" * 40 if mode == "drift" else _blob_sha(tmp_path / REVIEW_PATH)}
        if url.endswith("/pulls/1045/reviews?per_page=100"):
            return [
                {
                    "id": 12345,
                    "user": {"login": "independent-reader"},
                    "state": "DISMISSED" if mode == "revoked" else "APPROVED",
                    "commit_id": "a" * 40,
                    "submitted_at": "2026-11-19T19:50:00Z",
                }
            ]
        raise AssertionError(f"unexpected read-only evidence URL: {url}")

    return get_json


def test_unapproved_original_review_register_fails_before_github_network(example):
    root, queue, post = example

    def unexpected_get(_url, _token):
        raise AssertionError("must not contact GitHub before local source/rights approval")

    with pytest.raises(SemanticApprovalHold, match="no independent acceptance"):
        require_semantic_approval(root, queue, post, github_get=unexpected_get)


@pytest.mark.parametrize("mode", ["valid", "self", "drift", "revoked"])
def test_approval_requires_distinct_github_reviewer_exact_merged_head_and_blob(example, mode):
    root, queue, post = example
    _activate(root, post)

    def check():
        return require_semantic_approval(root, queue, post, github_get=_github_receipt(root, mode=mode))

    if mode == "valid":
        check()
    else:
        with pytest.raises(SemanticApprovalHold):
            check()


@pytest.mark.parametrize(
    "field,value",
    [
        ("semantic_verdict", "REVIEW_REQUIRED"),
        ("original_collation", "not_verified"),
        ("russian_translation_review", "not_verified"),
        ("rights_clearance", "not_cleared"),
        ("contiguous_source_span_verified", False),
        ("payload_sha256", "sha256:" + "0" * 64),
    ],
)
def test_missing_semantic_rights_translation_or_exact_hash_denies(example, field, value):
    root, queue, post = example
    _activate(root, post)
    path = root / REVIEW_PATH
    r = json.loads(path.read_text(encoding="utf-8"))
    card = next(x for x in r["entries"] if x["publication_id"] == post.publication_id)
    card[field] = value
    path.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticApprovalHold):
        require_semantic_approval(root, queue, post, github_get=_github_receipt(root))


def test_missing_github_token_denies_even_valid_review(example, monkeypatch):
    root, queue, post = example
    _activate(root, post)
    monkeypatch.delenv("GITHUB_TOKEN")
    with pytest.raises(SemanticApprovalHold, match="token unavailable"):
        require_semantic_approval(root, queue, post, github_get=_github_receipt(root))


def test_historical_mutating_cli_commands_cannot_reinitialize_or_rebind_live_ledger(monkeypatch):
    for action in ("init", "migrate", "migrate-editorial"):
        monkeypatch.setattr("sys.argv", ["lordchrist_quote_v6_publisher", action])
        with pytest.raises(ValueError, match="retired"):
            publisher.main()


def test_workflow_refuses_deprecated_manual_state_writes() -> None:
    workflow = (ROOT / ".github/workflows/lordchrist-quote-v6-publisher.yml").read_text(encoding="utf-8")
    guard = 'if [[ "$V6_ACTION" != "publish" ]]; then'
    assert workflow.index(guard) < workflow.index('if [[ "$V6_ACTION" == "initialize" ]]; then')
    assert "pull-requests: read" in workflow
    assert workflow.count("GITHUB_TOKEN: ${{ github.token }}") == 2


def test_prepare_rejects_before_provider_preflight_or_ledger_write(monkeypatch, tmp_path, capsys):
    queue = publisher.release_and_queue(ROOT)
    ledger = initialize_ledger(queue)
    original = ledger.model_copy(deep=True)
    monkeypatch.setattr(publisher, "release_and_queue", lambda _root: queue)
    monkeypatch.setattr(publisher, "load_ledger", lambda _path, _queue: ledger)
    monkeypatch.setattr(publisher, "guard_cross_track", lambda _root: None)
    monkeypatch.setattr(
        publisher, "target_from_provider", lambda: pytest.fail("target lookup reached before editorial approval")
    )
    monkeypatch.setattr(
        publisher, "save_ledger", lambda *_args: pytest.fail("protected state was written before editorial approval")
    )
    monkeypatch.setattr(
        publisher, "prepare_next", lambda *_args, **_kwargs: pytest.fail("dispatch intent before editorial approval")
    )
    assert publisher.prepare(ROOT, mode="manual", expected_id=publisher.FIRST_ID) == 3
    output = json.loads(capsys.readouterr().out)
    assert output["prepared"] is False
    assert output["reason"] == "editorial_hold"
    assert "no independent acceptance" in output["detail"]
    assert ledger == original


def test_no_telegram_http_after_prepared_intent_if_editorial_approval_revoked(monkeypatch, tmp_path):
    # Valid pending Telegram envelope is not enough: send must independently recheck.
    import test_lordchrist_quote_v6_live_publisher as original_tests

    owner, _queue, ledger_path, _envelope = original_tests._prepared_v6_fault_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(
        owner,
        "require_semantic_approval",
        lambda *_args: (_ for _ in ()).throw(SemanticApprovalHold("approval revoked after intent")),
    )
    monkeypatch.setattr(owner, "_api_call", lambda *_args, **_kwargs: pytest.fail("Telegram POST after HOLD"))
    monkeypatch.setattr(owner, "save_ledger", lambda *_args: pytest.fail("ledger changed after HOLD"))
    with pytest.raises(SemanticApprovalHold, match="revoked"):
        owner.send(tmp_path)
    assert ledger_path.exists()
