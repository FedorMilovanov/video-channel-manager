"""Offline and negative tests for immutable public Charnock in-place revisions."""

from __future__ import annotations

import copy
import json

import pytest

from scripts import charnock_telegraph_surgical_revision as s


def page03(monkeypatch):
    nodes = [{"tag": "p", "children": [f"opaque-{i}"]} for i in range(130)]
    nodes[104] = {"tag": "blockquote", "children": [s.OLD_Q29]}
    page = {
        "path": s.CONTRACTS["03"]["path"],
        "title": s.CONTRACTS["03"]["title"],
        "author_name": s.AUTHOR,
        "author_url": s.AUTHOR_URL,
        "content": nodes,
        "image_url": "https://example.test/cover.jpg",
    }
    monkeypatch.setitem(s.CONTRACTS["03"], "sha256", s.sha_content(nodes))
    return page


def history(monkeypatch):
    nodes = [{"tag": "p", "children": [f"opaque-{i}"]} for i in range(76)]
    nodes[8] = {
        "tag": "p",
        "children": [
            s.OLD_BIRTH + " Он учился в Эммануил-колледже. В 1650 году стал ",
            {"tag": "em", "children": ["феллоу"]},
            " — членом академического сообщества.",
        ],
    }
    for index, roman in s.EXPECTED_ROMANS.items():
        nodes[index] = {
            "tag": "p",
            "children": [{"tag": "em", "children": [f"— Стивен Чарнок, беседа {roman} «Название» (беседа I)"]}],
        }
    page = {
        "path": s.CONTRACTS["history-01"]["path"],
        "title": s.CONTRACTS["history-01"]["title"],
        "author_name": s.AUTHOR,
        "author_url": s.AUTHOR_URL,
        "content": nodes,
    }
    monkeypatch.setitem(s.CONTRACTS["history-01"], "sha256", s.sha_content(nodes))
    return page


def changed(before, after):
    return tuple(i for i, (x, y) in enumerate(zip(before["content"], after["content"], strict=True)) if x != y)


def test_q29_only_one_block_changes_without_touching_metadata_or_other_nodes(monkeypatch):
    before = page03(monkeypatch)
    old = copy.deepcopy(before)
    after = s.prepare(before, "03")
    assert before == old
    assert changed(before, after) == (104,)
    assert after["content"][104] == {"tag": "blockquote", "children": [s.NEW_Q29]}
    assert after["image_url"] == before["image_url"]
    assert all(before[k] == after[k] for k in ("title", "path", "author_name", "author_url"))


def test_history_changes_only_birth_and_five_wrapped_credits(monkeypatch):
    before = history(monkeypatch)
    after = s.prepare(before, "history-01")
    assert changed(before, after) == (8, 15, 23, 31, 38, 45)
    assert after["content"][8]["children"][0].startswith(s.NEW_BIRTH)
    assert after["content"][8]["children"][1] == {"tag": "em", "children": ["феллоу"]}
    for index, roman in s.EXPECTED_ROMANS.items():
        val = after["content"][index]["children"][0]["children"][0]
        assert f"беседа {roman}" in val
        assert not val.endswith(" (беседа I)")


@pytest.mark.parametrize(
    "field,value",
    [("author_name", "Forged"), ("author_url", "https://wrong.example"), ("title", "New page"), ("path", "new-url")],
)
def test_metadata_drift_blocks_before_any_edit(monkeypatch, field, value):
    page = page03(monkeypatch)
    page[field] = value
    with pytest.raises(s.UnsafeRevision):
        s.prepare(page, "03")


def test_unreviewed_live_content_blocks(monkeypatch):
    page = page03(monkeypatch)
    page["content"][3]["children"] = ["manual-edited"]
    with pytest.raises(s.UnsafeRevision, match="content SHA changed"):
        s.prepare(page, "03")


def test_quote_content_must_match_even_with_reviewed_fingerprint(monkeypatch):
    page = page03(monkeypatch)
    page["content"][104]["children"] = ["unreviewed quotation"]
    monkeypatch.setitem(s.CONTRACTS["03"], "sha256", s.sha_content(page["content"]))
    with pytest.raises(s.UnsafeRevision, match="q-29 old node"):
        s.prepare(page, "03")


def test_history_credit_format_change_blocks(monkeypatch):
    page = history(monkeypatch)
    page["content"][23]["children"][0]["tag"] = "strong"
    monkeypatch.setitem(s.CONTRACTS["history-01"], "sha256", s.sha_content(page["content"]))
    with pytest.raises(s.UnsafeRevision, match="italic structure"):
        s.prepare(page, "history-01")


def test_readonly_dry_run_does_not_access_account_or_mutate(monkeypatch):
    page = page03(monkeypatch)
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page))
    monkeypatch.setattr(s, "verify_ownership", lambda *_: pytest.fail("ownership called in dry-run"))
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST called in dry-run"))
    out = s.run_one("03", execute=False, confirm=None, receipt_dir=None)
    assert out["effect"] == "DRY_RUN_NO_POST"
    assert out["changed_nodes"] == [104]


def test_execute_requires_confirmation_and_existing_token(monkeypatch, tmp_path):
    page = page03(monkeypatch)
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page))
    monkeypatch.setattr(s, "verify_ownership", lambda *_: pytest.fail("no owner call"))
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("no POST allowed"))
    with pytest.raises(s.UnsafeRevision, match="confirmation"):
        s.run_one("03", execute=True, confirm="", receipt_dir=tmp_path)
    monkeypatch.delenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", raising=False)
    with pytest.raises(s.UnsafeRevision, match="token unavailable"):
        s.run_one("03", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)


def test_wrong_account_never_reaches_editpage(monkeypatch):
    def fake_post(operation, fields):
        assert operation == "getPage/" + s.CONTRACTS["03"]["path"]
        return {"path": s.CONTRACTS["03"]["path"], "can_edit": False}

    monkeypatch.setattr(s, "post_form", fake_post)
    with pytest.raises(s.UnsafeRevision, match="cannot edit"):
        s.verify_ownership("private-token", s.CONTRACTS["03"]["path"])


def test_missing_can_edit_falls_back_to_owned_pages(monkeypatch):
    paths = []

    def fake_post(op, data):
        paths.append(op)
        if op.startswith("getPage/"):
            return {"path": s.CONTRACTS["03"]["path"]}
        assert op == "getPageList"
        return {"pages": [{"path": s.CONTRACTS["03"]["path"]}]}

    monkeypatch.setattr(s, "post_form", fake_post)
    s.verify_ownership("private-token", s.CONTRACTS["03"]["path"])
    assert paths == ["getPage/" + s.CONTRACTS["03"]["path"], "getPageList"]


def test_one_post_and_verified_full_readback_receipt(monkeypatch, tmp_path):
    page = page03(monkeypatch)
    after = s.prepare(page, "03")
    pages = [copy.deepcopy(page), copy.deepcopy(page), copy.deepcopy(after)]
    monkeypatch.setattr(s, "get_public_page", lambda _: pages.pop(0))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "secret-not-logged")
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    calls = []

    def fake_post(operation, fields):
        calls.append((operation, fields))
        assert operation == "editPage/" + s.CONTRACTS["03"]["path"]
        assert fields["access_token"] == "secret-not-logged"
        assert json.loads(fields["content"]) == after["content"]
        return {"path": s.CONTRACTS["03"]["path"]}

    monkeypatch.setattr(s, "post_form", fake_post)
    out = s.run_one("03", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    assert out["effect"] == "VERIFIED_IN_PLACE"
    assert len(calls) == 1 and not pages
    receipts = list(tmp_path.glob("charnock-telegraph-03-*.json"))
    assert len(receipts) == 1
    assert "secret-not-logged" not in receipts[0].read_text(encoding="utf8")


def test_changed_intermediate_get_blocks_before_post(monkeypatch, tmp_path):
    page = page03(monkeypatch)
    modified = copy.deepcopy(page)
    modified["content"][0]["children"] = ["concurrent edit"]
    pages = [page, modified]
    monkeypatch.setattr(s, "get_public_page", lambda _: pages.pop(0))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "secret")
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    monkeypatch.setattr(s, "post_form", lambda *_: pytest.fail("POST after changed GET"))
    with pytest.raises(s.UnsafeRevision, match="content SHA changed"):
        s.run_one("03", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)


def test_ambiguous_post_never_auto_retries(monkeypatch, tmp_path):
    page = page03(monkeypatch)
    monkeypatch.setattr(s, "get_public_page", lambda _: copy.deepcopy(page))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "secret")
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    count = []

    def fake_post(*_):
        count.append(1)
        raise TimeoutError("ambiguous provider result")

    monkeypatch.setattr(s, "post_form", fake_post)
    with pytest.raises(TimeoutError):
        s.run_one("03", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    assert len(count) == 1
    assert list(tmp_path.iterdir()) == []


def test_readback_mismatch_is_uncertain_and_does_not_retry(monkeypatch, tmp_path):
    page = page03(monkeypatch)
    changed = copy.deepcopy(page)
    changed["content"][1]["children"] = ["unexpected after post"]
    pages = [page, page, changed]
    monkeypatch.setattr(s, "get_public_page", lambda _: pages.pop(0))
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "secret")
    monkeypatch.setattr(s, "verify_ownership", lambda *_: None)
    calls = []

    def fake_post(*_):
        calls.append(1)
        return {"path": s.CONTRACTS["03"]["path"]}

    monkeypatch.setattr(s, "post_form", fake_post)
    with pytest.raises(s.UnsafeRevision, match="UNCERTAIN"):
        s.run_one("03", execute=True, confirm=s.CONFIRM, receipt_dir=tmp_path)
    assert len(calls) == 1 and list(tmp_path.iterdir()) == []
