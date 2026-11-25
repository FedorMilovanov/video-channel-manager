"""Regression checks for the owner-accepted Charnock credit/quote patch."""

from __future__ import annotations

import copy

import pytest

from scripts import charnock_telegraph_credit_revision as revision

from scripts.charnock_telegraph_credit_revision import load_pair, prepare_nodes, same_tree
from scripts.charnock_telegraph_surgical_revision import UnsafeRevision


@pytest.mark.parametrize("key,expected_count", [("11", 2), ("12", 1), ("13", 1)])
def test_exact_patch_preserves_all_unrelated_live_nodes(key: str, expected_count: int) -> None:
    _, old, new = load_pair(key)
    live = copy.deepcopy(old.nodes)
    # Telegraph may supply heading IDs. Preserve these existing anchors.
    heading = next(node for node in live if isinstance(node, dict) and node.get("tag") == "h3")
    heading["attrs"] = {"id": "existing-live-heading"}
    before = copy.deepcopy(live)
    effect, after, indices = prepare_nodes(key, live, old.nodes, new.nodes)
    assert effect == "READY_FOR_REVIEW_NO_POST"
    assert len(indices) == expected_count
    assert indices[-1] == len(live)
    assert len(after) == len(live) + 1
    assert live == before
    assert after[0] == before[0]  # exact cover node
    assert all(after[i] == node for i, node in enumerate(before) if i not in indices)
    assert same_tree(after, new.nodes)
    effect, unchanged, indices = prepare_nodes(key, after, old.nodes, new.nodes)
    assert effect == "ALREADY_CORRECT_NO_POST"
    assert unchanged == after
    assert indices == []


@pytest.mark.parametrize("key", ["11", "12", "13"])
def test_drift_in_existing_cover_fails_closed(key: str) -> None:
    _, old, new = load_pair(key)
    live = copy.deepcopy(old.nodes)
    live[0]["children"][0]["attrs"]["src"] = "https://example.invalid/other.jpg"
    with pytest.raises(UnsafeRevision, match="Live page differs"):
        prepare_nodes(key, live, old.nodes, new.nodes)


def test_unrelated_candidate_mutation_rejected() -> None:
    _, old, new = load_pair("12")
    changed = copy.deepcopy(new.nodes)
    changed[0]["children"][0]["attrs"]["src"] = "https://example.invalid/other.jpg"
    with pytest.raises(UnsafeRevision, match="only append"):
        prepare_nodes("12", old.nodes, old.nodes, changed)


def test_apply_requires_durable_claim_before_single_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    live = {
        "path": "existing",
        "url": "https://telegra.ph/existing",
        "title": "Original",
        "author_name": "Господь Бог",
        "author_url": "https://t.me/lordchrist",
        "image_url": "https://example.invalid/cover.jpg",
        "content": [{"tag": "figure"}, {"tag": "p", "children": ["original"]}],
    }
    proposed = [*live["content"], {"tag": "p", "children": ["credit"]}]
    before = revision.sha_content(live["content"])
    after = revision.sha_content(proposed)
    result = {
        "path": "existing",
        "effect": "READY_FOR_REVIEW_NO_POST",
        "before_sha256": before,
        "after_sha256": after,
    }
    monkeypatch.setattr(revision, "require_owner_dispatch", lambda key: ("a" * 40, before, after))
    monkeypatch.setattr(revision, "build_plan", lambda key: (result, live, proposed))
    monkeypatch.setattr(revision, "require_current_main", lambda: "a" * 40)
    monkeypatch.setattr(revision, "verify_ownership", lambda token, path: calls.append("ownership"))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")

    def persist(key: str, data: dict, *, previous_blob: str | None = None) -> str:
        if data["state"] == "claimed_may_exist":
            assert previous_blob is None
            calls.append("claim")
        else:
            assert previous_blob == "b" * 40
            calls.append("verified")
        return "b" * 40

    def fetch(path: str) -> dict:
        return {**live, "content": proposed} if "post" in calls else live

    def post(path: str, fields: dict) -> dict:
        assert calls == ["ownership", "claim"]
        calls.append("post")
        return {"path": "existing"}

    monkeypatch.setattr(revision, "persist_receipt", persist)
    monkeypatch.setattr(revision, "get_public_page", fetch)
    monkeypatch.setattr(revision, "post_form", post)
    assert revision.apply("11")["state"] == "verified"
    assert calls == ["ownership", "claim", "post", "verified"]

    calls.clear()

    def existing_claim(*args: object, **kwargs: object) -> str:
        raise UnsafeRevision("Existing claim")

    monkeypatch.setattr(revision, "persist_receipt", existing_claim)
    with pytest.raises(UnsafeRevision, match="Existing claim"):
        revision.apply("11")
    assert calls == ["ownership"]
