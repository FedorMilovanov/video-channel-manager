"""Fail-closed tests for the Charnock series in-place editor."""

from __future__ import annotations

import copy
import json

import pytest

from scripts import charnock_telegraph_series_inplace as s

PATH = "Existing-Charnock-page-11-05"


@pytest.fixture
def contract(monkeypatch):
    data = {
        "test": {
            "path": PATH,
            "replacements": [
                {
                    "block_id": "q-1",
                    "before": "Old quoted text.",
                    "after": "New quoted text.",
                    "after_children": [{"tag": "strong", "children": ["New quoted text."]}],
                }
            ],
        }
    }
    monkeypatch.setattr(s, "CONTRACTS", data)
    return data


def page() -> dict:
    return {
        "path": PATH,
        "url": "https://telegra.ph/" + PATH,
        "title": "Existing title",
        "author_name": s.AUTHOR,
        "author_url": s.AUTHOR_URL,
        "content": [
            {"tag": "p", "children": ["opaque"]},
            {"tag": "blockquote", "children": ["Old quoted text."]},
            {"tag": "p", "children": [{"tag": "em", "children": ["— Стивен Чарнок"]}]},
            {"tag": "p", "children": ["tail"]},
        ],
    }


def test_prepare_changes_only_the_pinned_blockquote(contract):
    before = page()
    original = copy.deepcopy(before)
    after, changed = s.prepare(before, "test")
    assert before == original
    assert changed == (1,)
    assert after[1] == {"tag": "blockquote", "children": [{"tag": "strong", "children": ["New quoted text."]}]}
    assert after[0] == before["content"][0] and after[2] == before["content"][2]
    assert len(after) == len(before["content"])


def test_missing_quote_blocks_before_any_edit(contract):
    broken = page()
    broken["content"][1]["children"] = ["Different text."]
    with pytest.raises(s.UnsafeRevision, match="exactly one"):
        s.prepare(broken, "test")


def test_ambiguous_quote_blocks_before_any_edit(contract):
    broken = page()
    broken["content"].append({"tag": "blockquote", "children": ["Old quoted text."]})
    with pytest.raises(s.UnsafeRevision, match="exactly one"):
        s.prepare(broken, "test")


@pytest.mark.parametrize("field,value", [("path", "another-page"), ("author_name", "Forged")])
def test_page_identity_drift_blocks(contract, field, value):
    broken = page()
    broken[field] = value
    with pytest.raises(s.UnsafeRevision):
        s.prepare(broken, "test")


def test_contract_after_text_must_match_children(contract):
    contract["test"]["replacements"][0]["after_children"] = ["Unreviewed text."]
    with pytest.raises(s.UnsafeRevision, match="after-text differs"):
        s.prepare(page(), "test")


def test_dry_run_never_calls_account_or_provider(contract, monkeypatch):
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page()))
    monkeypatch.setattr(s, "verify_ownership", lambda *_: pytest.fail("ownership called in dry-run"))
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST called in dry-run"))
    out = s.run_one("test", execute=False, confirm=None, receipt_dir=None)
    assert out["effect"] == "DRY_RUN_NO_POST"
    assert out["changed_nodes"] == [1]


def test_content_ceiling_blocks_before_any_post(contract, monkeypatch):
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page()))
    monkeypatch.setattr(s, "MAX_CONTENT_BYTES", 10)
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST called over ceiling"))
    with pytest.raises(s.UnsafeRevision, match="ceiling"):
        s.run_one("test", execute=False, confirm=None, receipt_dir=None)


def test_execute_posts_once_and_verifies_public_readback(contract, monkeypatch, tmp_path):
    before = page()
    after = copy.deepcopy(before)
    after["content"][1] = {"tag": "blockquote", "children": [{"tag": "strong", "children": ["New quoted text."]}]}
    calls = {"get": 0, "post": 0}

    def fake_get(_):
        calls["get"] += 1
        return copy.deepcopy(before if calls["get"] <= 2 else after)

    def fake_post(path, fields):
        calls["post"] += 1
        assert path == "editPage/" + PATH
        assert json.loads(fields["content"]) == after["content"]
        return {"path": PATH, "url": after["url"]}

    monkeypatch.setattr(s, "get_public_page", fake_get)
    monkeypatch.setattr(s, "post_form", fake_post)
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    out = s.run_one("test", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    assert out["effect"] == "VERIFIED_IN_PLACE"
    assert calls == {"get": 3, "post": 1}
    receipts = list(tmp_path.glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["effect"] == "VERIFIED_IN_PLACE"
    assert receipt["changed_nodes"] == [1]
    assert "test-token" not in receipts[0].read_text(encoding="utf-8")


def test_intervening_live_change_blocks_before_post(contract, monkeypatch, tmp_path):
    before = page()
    changed = copy.deepcopy(before)
    changed["content"][3]["children"] = ["someone else edited this"]
    calls = {"get": 0}

    def fake_get(_):
        calls["get"] += 1
        return copy.deepcopy(before if calls["get"] == 1 else changed)

    monkeypatch.setattr(s, "get_public_page", fake_get)
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST after intervening edit"))
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    with pytest.raises(s.UnsafeRevision, match="snapshot changed"):
        s.run_one("test", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)


def test_unknown_page_is_refused(contract):
    with pytest.raises(s.UnsafeRevision, match="Unknown page"):
        s.run_one("other", execute=False, confirm=None, receipt_dir=None)


def _applied_page() -> dict:
    applied = page()
    applied["content"][1] = {
        "tag": "blockquote",
        "children": [{"tag": "strong", "children": ["New quoted text."]}],
    }
    return applied


def test_reconcile_already_applied_page_writes_read_only_receipt(contract, monkeypatch, tmp_path):
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(_applied_page()))
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST called during reconcile"))
    monkeypatch.setattr(s, "verify_ownership", lambda *_: pytest.fail("ownership called during reconcile"))
    out = s.run_one("test", execute=False, confirm=None, receipt_dir=tmp_path, reconcile=True)
    assert out["effect"] == "VERIFIED_IN_PLACE_RECONCILED"
    assert out["verification"]["read_only"] is True
    receipts = list(tmp_path.glob("*-reconciled-*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["effect"] == "VERIFIED_IN_PLACE_RECONCILED"
    assert receipt["changed_nodes"] == [1]


def test_reconcile_refuses_a_page_that_still_has_the_before_text(contract, monkeypatch, tmp_path):
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page()))
    with pytest.raises(s.UnsafeRevision, match="exactly one applied"):
        s.run_one("test", execute=False, confirm=None, receipt_dir=tmp_path, reconcile=True)


def test_semantic_readback_accepts_dropped_empty_break(contract, monkeypatch, tmp_path):
    before = page()
    before["content"].insert(3, {"tag": "br"})
    planned, _ = s.prepare(copy.deepcopy(before), "test")
    live = copy.deepcopy(before)
    live["content"] = [copy.deepcopy(node) for node in planned if node.get("tag") != "br"]
    calls = {"get": 0, "post": 0}

    def fake_get(_):
        calls["get"] += 1
        return copy.deepcopy(before if calls["get"] <= 2 else live)

    def fake_post(path, fields):
        calls["post"] += 1
        assert path == "editPage/" + PATH
        assert json.loads(fields["content"]) == planned
        return {"path": PATH, "url": live["url"]}

    monkeypatch.setattr(s, "get_public_page", fake_get)
    monkeypatch.setattr(s, "post_form", fake_post)
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    out = s.run_one("test", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    assert out["effect"] == "VERIFIED_IN_PLACE"
    assert out["verification"]["mode"] == "semantic"
    assert out["verification"]["provider_content_exact"] is False
    assert calls == {"get": 3, "post": 1}
    receipts = list(tmp_path.glob("charnock-telegraph-test-*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["verification"]["mode"] == "semantic"


def test_uncertain_non_target_change_writes_receipt_and_does_not_claim_success(contract, monkeypatch, tmp_path):
    before = page()
    planned, _ = s.prepare(copy.deepcopy(before), "test")
    live = copy.deepcopy(before)
    live["content"] = copy.deepcopy(planned)
    live["content"][3]["children"] = ["tampered by someone else"]
    calls = {"get": 0}

    def fake_get(_):
        calls["get"] += 1
        return copy.deepcopy(before if calls["get"] <= 2 else live)

    monkeypatch.setattr(s, "get_public_page", fake_get)
    monkeypatch.setattr(s, "post_form", lambda *_: {"path": PATH, "url": live["url"]})
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    with pytest.raises(s.UnsafeRevision, match="non-target text changed"):
        s.run_one("test", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    receipts = list(tmp_path.glob("*-uncertain-*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["effect"] == "UNCERTAIN"
    assert receipt["uncertainty"] == "non-target text changed"
    assert "test-token" not in receipts[0].read_text(encoding="utf-8")


def test_post_error_is_receipted_as_uncertain(contract, monkeypatch, tmp_path):
    before = page()

    def fake_get(_):
        return copy.deepcopy(before)

    def fake_post(*_):
        raise TimeoutError("ambiguous")

    monkeypatch.setattr(s, "get_public_page", fake_get)
    monkeypatch.setattr(s, "post_form", fake_post)
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "test-token")
    with pytest.raises(TimeoutError):
        s.run_one("test", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    receipts = list(tmp_path.glob("*-uncertain-*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["effect"] == "UNCERTAIN"
    assert receipt["uncertainty"] == "POST_TimeoutError"


def test_13_multi_paragraph_quotes_pin_the_whole_live_blockquote():
    q3 = next(r for r in s.CONTRACTS["13"]["replacements"] if r["block_id"] == "q-3")
    q11 = next(r for r in s.CONTRACTS["13"]["replacements"] if r["block_id"] == "q-11")
    assert "Скорее решайтесь верить" in q3["before"]
    assert "Скорее решайтесь верить" in q3["after"]
    assert "Писание будет лёгкой вещью" in q11["before"]
    assert "Писание будет лёгкой вещью" in q11["after"]
    assert "Власть всего зависит от бытия Открывающего" in q11["before"]
    assert "Власть всего зависит от бытия Открывающего" in q11["after"]
