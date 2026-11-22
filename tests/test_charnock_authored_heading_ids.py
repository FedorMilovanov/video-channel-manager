"""Charnock structural proof must not erase explicitly reviewed heading IDs.

All provider responses here are local fakes. No Telegram or Telegraph write is
performed, and the historical article/state bindings are never modified.
"""

from __future__ import annotations

import copy
import itertools
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import charnock_telegraph_qc_reissue as qc
from video_channel_manager import lordchrist_charnock_reschedule as reschedule

URL = "https://telegra.ph/Synthetic-Heading-11-05"
PATH = "Synthetic-Heading-11-05"
MEDIA_BASE = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40
HISTORICAL_BASE = (
    "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/c1bafa972e91d536fc56d86e53b4ce6f3502f37d"
)
MISSING = object()


def _nodes(anchor: object = MISSING) -> list:
    heading: dict = {"tag": "h3", "children": ["Reviewed heading"]}
    if anchor is not MISSING:
        heading["attrs"] = {"id": anchor}
    return [heading, {"tag": "p", "children": ["Exact text"]}]


def _fake_page(nodes: list) -> dict:
    return {
        "path": PATH,
        "url": URL,
        "title": "Reviewed title",
        "author_name": "Reviewed author",
        "author_url": "https://example.invalid/author",
        "content": nodes,
    }


def _payload(nodes: list) -> SimpleNamespace:
    return SimpleNamespace(
        title="Reviewed title",
        author_name="Reviewed author",
        author_url="https://example.invalid/author",
        article_sha256="sha256:" + "a" * 64,
        nodes=nodes,
    )


def _mock_telegraph(monkeypatch: pytest.MonkeyPatch, nodes: list) -> None:
    monkeypatch.setattr(
        reschedule.httpx,
        "get",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "result": _fake_page(nodes)},
        ),
    )


@pytest.mark.parametrize("actual_id", ["different-anchor", MISSING, None, 1, True])
def test_page_proof_rejects_changed_or_missing_reviewed_heading_id(monkeypatch, actual_id) -> None:
    reviewed, live = _nodes("reviewed-anchor"), _nodes(actual_id)
    before = copy.deepcopy((reviewed, live))
    _mock_telegraph(monkeypatch, live)
    with pytest.raises(RuntimeError, match="entire reviewed latest"):
        reschedule._proof_page({"verified_telegraph_url": URL}, _payload(reviewed))
    assert (reviewed, live) == before


def test_page_proof_accepts_exact_reviewed_id_and_additional_generated_id(monkeypatch) -> None:
    reviewed = _nodes("reviewed-anchor") + [{"tag": "h4", "children": ["Second"]}]
    live = copy.deepcopy(reviewed)
    live[2]["attrs"] = {"id": "generated-anchor"}
    live[0]["children"] = ["Reviewed ", "heading"]
    _mock_telegraph(monkeypatch, live)
    reschedule._proof_page({"verified_telegraph_url": URL}, _payload(reviewed))


def test_readonly_structural_qc_flags_authored_id_without_printing_values(monkeypatch) -> None:
    reviewed, live = _nodes("reviewed-secret"), _nodes("provider-secret")
    manifest = {
        "10": {
            "publication_id": "synthetic-charnock-10",
            "article_path": "synthetic.json",
            "article_git_blob_sha": "a" * 40,
            "path": PATH,
            "url": URL,
        }
    }
    page = _fake_page(live)
    page["author_name"], page["author_url"] = qc.AUTHOR, qc.AUTHOR_URL
    monkeypatch.setattr(qc, "reviewed_payload", lambda *args, **kwargs: _payload(reviewed))
    monkeypatch.setattr(qc, "get_public_page", lambda path: page)
    result = qc.run_one("10", media_base_url=MEDIA_BASE, manifest=manifest, require_normalized_tree=True)
    assert result["effect"] == "NORMALIZED_NODE_TREE_MISMATCH"
    assert result["verification"]["visible_text_equal"] is True
    assert result["verification"]["normalized_node_tree_equal"] is False
    assert result["normalized_tree_sha256_before"] != result["normalized_tree_sha256_after"]
    differences = " ".join(result["normalized_tree_differences"])
    assert "id" in differences
    assert "secret" not in differences
    assert result["verification"]["normalized_node_tree_algorithm"] == "target-relative-heading-ids-v2"
    assert (
        qc.annotation_summary(result)["verification"]["normalized_node_tree_algorithm"] == qc.NORMALIZED_TREE_ALGORITHM
    )
    assert result["provider_write_attempted"] is False


@pytest.mark.parametrize("tag", ["h3", "h4"])
@pytest.mark.parametrize("extra_id", [None, False, 0, [], {}])
def test_unreviewed_non_string_id_is_not_normalized(tag, extra_id) -> None:
    reviewed = [{"tag": tag, "children": ["Exact"]}]
    live = [{"tag": tag, "attrs": {"id": extra_id}, "children": ["Exact"]}]
    assert not reschedule._normalized_telegraph_equal(live, reviewed)


def test_nested_reviewed_id_and_non_heading_id_are_checked() -> None:
    reviewed = [
        {
            "tag": "blockquote",
            "children": [
                {"tag": "h4", "attrs": {"id": "reviewed"}, "children": ["Nested"]},
                {"tag": "p", "attrs": {"id": "not-a-heading"}, "children": ["Text"]},
            ],
        }
    ]
    live = copy.deepcopy(reviewed)
    live[0]["children"][0]["attrs"]["id"] = "different"
    assert not reschedule._normalized_telegraph_equal(live, reviewed)
    live = copy.deepcopy(reviewed)
    live[0]["children"][1]["attrs"]["id"] = "different"
    assert not reschedule._normalized_telegraph_equal(live, reviewed)
    assert reschedule._normalized_telegraph_equal(reviewed, reviewed)


def test_pair_does_not_rewrite_arbitrary_attribute_or_nested_array() -> None:
    reviewed = [
        {
            "tag": "p",
            "attrs": {"data": {"tag": "h3", "attrs": {"id": "inside-attribute"}}},
            "children": [[{"tag": "h3", "children": ["not a node array"]}]],
        }
    ]
    live = copy.deepcopy(reviewed)
    live[0]["children"][0][0]["attrs"] = {"id": "unreviewed"}
    before = copy.deepcopy((live, reviewed))
    assert not reschedule._normalized_telegraph_equal(live, reviewed)
    assert (live, reviewed) == before
    live = copy.deepcopy(reviewed)
    live[0]["attrs"]["data"]["attrs"]["id"] = "different"
    assert not reschedule._normalized_telegraph_equal(live, reviewed)


def test_paired_comparison_preserves_json_types_and_unrelated_attributes() -> None:
    reviewed = [{"tag": "h3", "attrs": {"id": 1, "class": "kept"}, "children": ["A", " B"]}]
    live = copy.deepcopy(reviewed)
    live[0]["attrs"]["id"] = True  # Python considers True == 1; canonical JSON does not.
    assert not reschedule._normalized_telegraph_equal(live, reviewed)
    live = copy.deepcopy(reviewed)
    live[0]["attrs"]["class"] = "changed"
    assert not reschedule._normalized_telegraph_equal(live, reviewed)
    live[0]["attrs"]["class"] = "kept"
    live[0]["children"] = ["A B"]
    assert reschedule._normalized_telegraph_equal(live, reviewed)


def test_bounded_matrix_never_weakens_the_previous_comparison() -> None:
    attrs = [
        None,
        {},
        {"id": "a"},
        {"id": "b"},
        {"id": 1},
        {"id": True},
        {"id": None},
        {"id": "a", "x": "y"},
        {"x": "y"},
    ]
    children = [["a", "b"], ["ab"], ["A"], [], [{"tag": "h4", "attrs": {"id": "nested"}, "children": ["N"]}]]
    nodes = []
    for tag, attr, child in itertools.product(("h3", "h4", "p"), attrs, children):
        node = {"tag": tag, "children": child}
        if attr is not None:
            node["attrs"] = attr
        nodes.append([node])
    tightened = 0
    for actual, expected in itertools.product(nodes, repeat=2):
        old_equal = reschedule._normalized_telegraph_digest(actual) == reschedule._normalized_telegraph_digest(expected)
        new_equal = reschedule._normalized_telegraph_equal(actual, expected)
        assert old_equal or not new_equal
        tightened += old_equal and not new_equal
    assert len(nodes) ** 2 == 18_225
    assert tightened > 0


def test_pinned_qc_targets_and_historical_digests() -> None:
    """Only local targets and artificial live IDs are examined; no provider read."""
    root = Path(__file__).resolve().parents[1]
    manifest = qc.load_manifest()
    historic_target_hashes = {
        "10": "56b06597af499958efe515cf41ac9284d6c08e18046825ada34de322f7407db0",
        "11": "54b43f6cf87cd84f678fa93d82b99eb652c8aba323e05dc0f4044de2fc5c711a",
        "12": "2eec523bf8e6f93b9d1138e1632fc344c1e7f8e9b3f6c228414a69cdd9b9c71a",
    }
    heading_count = 0
    for key in manifest:
        payload = qc.reviewed_payload(key, repo_root=root, media_base_url=HISTORICAL_BASE, manifest=manifest)
        simulated = copy.deepcopy(payload.nodes)
        stack = list(simulated)
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if node.get("tag") in ("h3", "h4"):
                heading_count += 1
                assert not isinstance(node.get("attrs"), dict) or "id" not in node["attrs"]
                node.setdefault("attrs", {})["id"] = "synthetic-provider-anchor"
            if isinstance(node.get("children"), list):
                stack.extend(node["children"])
        before, after = reschedule._normalized_telegraph_pair_digests(simulated, payload.nodes)
        assert before == after == reschedule._normalized_telegraph_digest(payload.nodes)
        if key in historic_target_hashes:
            assert after == historic_target_hashes[key]
    assert len(manifest) == 13
    assert heading_count == 123
