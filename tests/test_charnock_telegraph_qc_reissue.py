"""Read-only Charnock QC comparisons: no network in these tests."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import charnock_telegraph_qc_reissue as reissue
from scripts import charnock_telegraph_surgical_revision as surgical

ROOT = Path(__file__).resolve().parents[1]
MEDIA = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40


def _manifest() -> dict:
    return reissue.load_manifest()


def _payload(key: str):
    return reissue.reviewed_payload(key, repo_root=ROOT, media_base_url=MEDIA, manifest=_manifest())


def _live(key: str, *, title: str | None = None, content: list | None = None) -> dict:
    contract = _manifest()[key]
    return {
        "path": contract["path"],
        "url": contract["url"],
        "title": "Прежний заголовок" if title is None else title,
        "author_name": reissue.AUTHOR,
        "author_url": reissue.AUTHOR_URL,
        "content": content if content is not None else [{"tag": "p", "children": ["Старый текст страницы."]}],
    }


class Reader:
    def __init__(self, page: dict) -> None:
        self.page = page
        self.calls = 0

    def __call__(self, path: str) -> dict:
        self.calls += 1
        assert self.page["path"] == path
        return self.page


def test_manifest_pins_thirteen_existing_pages() -> None:
    pages = _manifest()
    assert set(pages) == {"01b", *[f"{n:02d}" for n in range(2, 14)]}
    assert len({page["path"] for page in pages.values()}) == 13
    for key, page in pages.items():
        assert page["url"] == "https://telegra.ph/" + page["path"]
        assert page["article_path"].endswith(f"lordchrist-telegraph-charnock-{key}.json")
        assert len(page["article_git_blob_sha"]) == 40


def test_manifest_matches_queue_blobs() -> None:
    queue = json.loads((ROOT / reissue.QUEUE_PATH).read_text(encoding="utf-8"))["items"]
    by_id = {item["publication_id"]: item for item in queue}
    for page in _manifest().values():
        item = by_id[page["publication_id"]]
        assert item["article"]["path"] == page["article_path"]
        assert item["article"]["git_blob_sha"] == page["article_git_blob_sha"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://telegra.ph/different"),
        ("path", "different?unsafe=1"),
        ("article_path", "../../outside.json"),
        ("article_git_blob_sha", "z" * 40),
    ],
)
def test_manifest_rejects_unsafe_or_unbound_identity(tmp_path: Path, field: str, value: str) -> None:
    document = json.loads(reissue.MANIFEST_PATH.read_text(encoding="utf-8"))
    document["pages"]["01b"][field] = value
    broken = tmp_path / "manifest.json"
    broken.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(reissue.UnsafeRevision):
        reissue.load_manifest(broken)


def test_manifest_rejects_duplicate_page_identity(tmp_path: Path) -> None:
    document = json.loads(reissue.MANIFEST_PATH.read_text(encoding="utf-8"))
    document["pages"]["02"]["publication_id"] = document["pages"]["01b"]["publication_id"]
    broken = tmp_path / "manifest.json"
    broken.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(reissue.UnsafeRevision, match="duplicate"):
        reissue.load_manifest(broken)


@pytest.mark.parametrize("field", ["article_path", "article_git_blob_sha"])
def test_qc_manifest_must_bind_the_actual_queue_article_before_get(field: str, monkeypatch) -> None:
    manifest = _manifest()
    manifest["10"][field] = _manifest()["11"][field]
    monkeypatch.setattr(reissue, "get_public_page", lambda path: pytest.fail("source drift must stop before GET"))
    with pytest.raises(reissue.UnsafeRevision, match="queue article path or blob"):
        reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, manifest=manifest)


def test_nondefault_repo_root_selects_its_own_manifest(tmp_path: Path, monkeypatch) -> None:
    document = json.loads(reissue.MANIFEST_PATH.read_text(encoding="utf-8"))
    document["pages"]["10"]["path"] = "different-pinned-page"
    document["pages"]["10"]["url"] = "https://telegra.ph/different-pinned-page"
    manifest_path = tmp_path / reissue.MANIFEST_RELATIVE
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    payload = _payload("10")
    monkeypatch.setattr(reissue, "reviewed_payload", lambda *args, **kwargs: payload)
    page = {**_live("10", title=payload.title, content=payload.nodes), **document["pages"]["10"]}
    page["author_name"], page["author_url"] = reissue.AUTHOR, reissue.AUTHOR_URL
    reader = Reader(page)
    monkeypatch.setattr(reissue, "get_public_page", reader)
    result = reissue.run_one("10", repo_root=tmp_path, media_base_url=MEDIA)
    assert reader.calls == 1
    assert result["path"] == "different-pinned-page"


def test_read_only_preview_reports_difference_without_receipt(tmp_path: Path, monkeypatch) -> None:
    reader = Reader(_live("01b"))
    monkeypatch.setattr(reissue, "get_public_page", reader)
    outcome = reissue.run_one("01b", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path)
    assert outcome["effect"] == "VISIBLE_TEXT_MISMATCH"
    assert outcome["mode"] == "dry-run"
    assert outcome["node_count_after"] == len(_payload("01b").nodes)
    assert outcome["differences"]
    assert outcome["verification"]["title_exact"] is False
    assert outcome["provider_write_attempted"] is False
    assert reader.calls == 1
    assert list(tmp_path.iterdir()) == []


def test_read_only_preview_is_allowed_when_visible_text_already_matches(monkeypatch) -> None:
    payload = _payload("11")
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("11", title=payload.title, content=payload.nodes)))
    outcome = reissue.run_one("11", repo_root=ROOT, media_base_url=MEDIA)
    assert outcome["effect"] == "VISIBLE_TEXT_MATCH"
    assert outcome["mode"] == "dry-run"
    assert outcome["verification"]["title_exact"] is True
    assert outcome["verification"]["visible_text_equal"] is True
    assert outcome["verification"]["provider_content_exact"] is True


def test_exact_read_only_match_writes_one_immutable_receipt(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("11")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("11", title=payload.title, content=payload.nodes)))
    outcome = reissue.run_one("11", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, reconcile=True)
    assert outcome["effect"] == "VISIBLE_TEXT_MATCH"
    assert outcome["article_git_blob_sha"] == _manifest()["11"]["article_git_blob_sha"]
    assert outcome["verification"]["title_exact"] is True
    assert outcome["verification"]["visible_text_equal"] is True
    assert outcome["verification"]["provider_content_exact"] is True
    assert outcome["live_first_text"] == outcome["target_first_text"]
    assert outcome["live_last_text"] == outcome["target_last_text"]
    receipt_path = next(tmp_path.iterdir())
    before = receipt_path.read_bytes()
    receipt = json.loads(before)
    assert receipt == outcome
    with pytest.raises(reissue.UnsafeRevision, match="already exists"):
        reissue.run_one("11", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, reconcile=True)
    assert receipt_path.read_bytes() == before


def test_text_mismatch_cannot_be_marked_as_a_match(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("07")
    broken = [{"tag": "p", "children": ["Совсем другой текст."]}]
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("07", title=payload.title, content=broken)))
    outcome = reissue.run_one("07", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, reconcile=True)
    assert outcome["effect"] == "VISIBLE_TEXT_MISMATCH"
    assert outcome["verification"]["title_exact"] is True
    assert outcome["verification"]["visible_text_equal"] is False
    assert outcome["differences"]
    assert json.loads(next(tmp_path.iterdir()).read_text(encoding="utf-8"))["effect"] == "VISIBLE_TEXT_MISMATCH"


def test_visible_text_match_does_not_claim_media_or_markup_equality(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("10")
    changed = copy.deepcopy(payload.nodes)
    changed[0]["children"][0]["attrs"]["src"] = "https://example.invalid/other-image.jpg"
    changed.insert(1, {"tag": "br"})
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("10", title=payload.title, content=changed)))
    outcome = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, reconcile=True)
    assert outcome["effect"] == "VISIBLE_TEXT_MATCH"
    assert outcome["verification"]["provider_content_exact"] is False
    assert outcome["verification"]["normalized_node_tree_equal"] is False
    assert outcome["verification"]["normalized_node_tree_required"] is False
    assert outcome["normalized_tree_differences"]
    assert outcome["media_base_revision"] == "a" * 40
    assert outcome["verification"]["visible_text_comparison_excludes"] == [
        "media sources",
        "link targets",
        "inline markup",
        "non-text nodes",
        "exact whitespace",
    ]
    assert outcome["node_count_before"] != outcome["node_count_after"]


def test_exact_content_field_distinguishes_json_boolean_and_number(monkeypatch) -> None:
    payload = _payload("10")
    target = copy.deepcopy(payload.nodes)
    target[0]["children"][0]["attrs"]["test"] = 1
    live = copy.deepcopy(target)
    live[0]["children"][0]["attrs"]["test"] = True
    assert live == target  # Python equality alone does not distinguish these JSON values.
    monkeypatch.setattr(reissue, "reviewed_payload", lambda *args, **kwargs: replace(payload, nodes=target))
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("10", title=payload.title, content=live)))
    outcome = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA)
    assert outcome["effect"] == "VISIBLE_TEXT_MATCH"
    assert outcome["verification"]["provider_content_exact"] is False
    assert outcome["verification"]["normalized_node_tree_equal"] is False
    assert any("JSON types differ" in diff for diff in outcome["normalized_tree_differences"])
    assert outcome["old_sha256"] != outcome["new_sha256"]


def test_full_tree_match_accepts_only_documented_provider_normalization(monkeypatch) -> None:
    payload = _payload("10")
    live = copy.deepcopy(payload.nodes)
    heading = next(node for node in live if isinstance(node, dict) and node.get("tag") == "h3")
    assert isinstance(heading["children"][0], str)
    heading["attrs"] = {"id": "generated-heading-anchor"}
    text = heading["children"][0]
    heading["children"] = [text[:3], text[3:]]
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("10", title=payload.title, content=live)))
    result = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, require_normalized_tree=True)
    assert result["effect"] == "NORMALIZED_NODE_TREE_MATCH"
    assert result["verification"]["provider_content_exact"] is False
    assert result["verification"]["mode"] == "normalized_node_tree"
    assert result["verification"]["normalized_node_tree_equal"] is True
    assert result["verification"]["normalized_node_tree_required"] is True
    assert result["normalized_tree_sha256_before"] == result["normalized_tree_sha256_after"]
    assert result["normalized_tree_differences"] == []


@pytest.mark.parametrize("change", ["image", "link", "markup", "empty_node", "whitespace"])
def test_strict_tree_detects_changes_visible_text_alone_can_miss(monkeypatch, change) -> None:
    payload = _payload("10")
    target = [
        {"tag": "figure", "children": [{"tag": "img", "attrs": {"src": "https://media.invalid/one"}}]},
        {
            "tag": "p",
            "children": [{"tag": "a", "attrs": {"href": "https://source.invalid/one"}, "children": ["A B"]}],
        },
    ]
    live = copy.deepcopy(target)
    if change == "image":
        live[0]["children"][0]["attrs"]["src"] = "https://media.invalid/two"
    elif change == "link":
        live[1]["children"][0]["attrs"]["href"] = "https://source.invalid/two"
    elif change == "markup":
        live[1]["children"][0]["tag"] = "em"
    elif change == "empty_node":
        live.insert(1, {"tag": "br"})
    else:
        live[1]["children"][0]["children"] = ["A   B"]
    assert reissue.describe_differences(live, target) == []
    monkeypatch.setattr(reissue, "reviewed_payload", lambda *a, **k: replace(payload, nodes=target))
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("10", title=payload.title, content=live)))
    result = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, require_normalized_tree=True)
    assert result["effect"] == "NORMALIZED_NODE_TREE_MISMATCH"
    assert result["verification"]["visible_text_equal"] is True
    assert result["verification"]["normalized_node_tree_equal"] is False
    assert result["normalized_tree_sha256_before"] != result["normalized_tree_sha256_after"]
    assert result["normalized_tree_differences"]
    assert result["provider_write_attempted"] is False


def test_strict_mismatch_exits_nonzero_and_still_records_evidence(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = _payload("10")
    live = copy.deepcopy(payload.nodes)
    live[0]["children"][0]["attrs"]["src"] = "https://different.invalid/image"
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("10", title=payload.title, content=live)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qc",
            "--page",
            "10",
            "--media-base-url",
            MEDIA,
            "--reconcile",
            "--require-normalized-tree",
            "--receipt-dir",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        reissue.main()
    assert exc.value.code == 2
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["mode"] == "structural-reconcile"
    assert outcome["verification"]["mode"] == "normalized_node_tree"
    assert outcome["effect"] == "NORMALIZED_NODE_TREE_MISMATCH"
    assert json.loads(next(tmp_path.iterdir()).read_text(encoding="utf-8")) == outcome
    summary = reissue.annotation_summary(outcome)
    assert summary["effect"] == outcome["effect"]
    assert summary["normalized_tree_sha256_before"] == outcome["normalized_tree_sha256_before"]
    assert summary["verification"]["normalized_node_tree_equal"] is False
    assert "live_first_text" not in summary and "differences" not in summary
    assert "visible_text_comparison_excludes" not in summary["verification"]
    with pytest.raises(ValueError, match="no verification"):
        reissue.annotation_summary({})


def test_tree_differences_are_bounded_and_do_not_print_values() -> None:
    before = [{"tag": "p", "children": [str(i), {"tag": "br"}]} for i in range(10)]
    after = [{"tag": "p", "children": [f"secret-{i}", {"tag": "br"}]} for i in range(10)]
    differences = reissue.normalized_tree_differences(before, after)
    assert len(differences) == reissue.MAX_DIFFERENCES
    assert all("secret" not in item for item in differences)


def test_tree_diagnostics_hide_unknown_keys_and_limit_deep_paths() -> None:
    before = {"secret-provider-key": "old"}
    after = {"secret-provider-key": "new"}
    for _ in range(30):
        before = {"children": [before]}
        after = {"children": [after]}
    differences = reissue.normalized_tree_differences(before, after)
    assert len(differences) == 1
    assert "secret-provider-key" not in differences[0]
    assert len(differences[0]) <= reissue.MAX_DIAGNOSTIC_PATH + len(": value differs")
    assert "..." in differences[0]

    unknown_key = "secret-" * 10_000
    assert "secret" not in " ".join(reissue.normalized_tree_differences({unknown_key: "old"}, {unknown_key: "new"}))


def test_visible_comparison_excludes_link_targets_but_checks_outer_tags() -> None:
    def node(tag: str, href: str) -> list:
        return [{"tag": tag, "children": [{"tag": "a", "attrs": {"href": href}, "children": ["Текст"]}]}]

    assert reissue.describe_differences(node("p", "https://one.invalid"), node("p", "https://two.invalid")) == []
    assert reissue.describe_differences(node("p", "https://one.invalid"), node("h3", "https://one.invalid"))
    assert reissue.describe_differences(["extra text"], [])
    assert (
        reissue.describe_differences([{"tag": "p", "children": ["a   b"]}], [{"tag": "p", "children": ["a b"]}]) == []
    )


@pytest.mark.parametrize("nodes", [None, [{"children": ["text"]}], [42]])
def test_invalid_top_level_nodes_fail_closed(nodes) -> None:
    with pytest.raises(reissue.UnsafeRevision):
        reissue.semantic_nodes(nodes)


def test_empty_reviewed_payload_is_not_a_match(monkeypatch) -> None:
    monkeypatch.setattr(
        reissue,
        "build_telegraph_payload",
        lambda *args, **kwargs: SimpleNamespace(nodes=[{"tag": "figure"}], content_utf8_bytes=10),
    )
    with pytest.raises(reissue.UnsafeRevision, match="no visible text"):
        reissue.reviewed_payload("10", repo_root=ROOT, media_base_url=MEDIA, manifest=_manifest())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "wrong-page"),
        ("url", "https://telegra.ph/wrong-page"),
        ("url", None),
        ("author_name", "Кто-то другой"),
        ("author_url", "https://t.me/different"),
        ("content", []),
    ],
)
def test_public_page_identity_must_match_exactly(field: str, value, monkeypatch) -> None:
    stranger = {**_live("09"), field: value}
    monkeypatch.setattr(reissue, "get_public_page", lambda path: stranger)
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one("09", repo_root=ROOT, media_base_url=MEDIA)


def test_receipt_directory_inside_git_or_symlink_to_it_is_refused(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("02")
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("02", title=payload.title, content=payload.nodes)))
    with pytest.raises(reissue.UnsafeRevision, match="outside a git repository"):
        reissue.run_one("02", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=ROOT, reconcile=True)
    link = tmp_path / "repo-link"
    try:
        link.symlink_to(ROOT, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("directory symlinks unavailable")
    with pytest.raises(reissue.UnsafeRevision, match="outside a git repository"):
        reissue.run_one("02", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=link, reconcile=True)


def test_reconcile_requires_a_safe_existing_receipt_directory(monkeypatch) -> None:
    payload = _payload("02")
    monkeypatch.setattr(reissue, "get_public_page", Reader(_live("02", title=payload.title, content=payload.nodes)))
    with pytest.raises(reissue.UnsafeRevision, match="receipt directory"):
        reissue.run_one("02", repo_root=ROOT, media_base_url=MEDIA, reconcile=True)


@pytest.mark.parametrize("reconcile", [False, True])
def test_historical_execute_confirmation_never_grants_provider_access(reconcile: bool, monkeypatch) -> None:
    monkeypatch.setattr(reissue, "load_manifest", lambda *args, **kwargs: pytest.fail("must stop before loading"))
    monkeypatch.setattr(reissue, "get_public_page", lambda path: pytest.fail("must stop before GET"))
    with pytest.raises(reissue.UnsafeRevision, match="retired"):
        reissue.run_one("10", media_base_url=MEDIA, execute=True, confirm=reissue.CONFIRM, reconcile=reconcile)


def test_retired_cli_execute_is_nonzero_without_provider_access(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["charnock-qc", "--page", "10", "--media-base-url", MEDIA, "--execute", "--confirm", reissue.CONFIRM],
    )
    monkeypatch.setattr(reissue, "get_public_page", lambda path: pytest.fail("must stop before GET"))
    with pytest.raises(SystemExit) as error:
        reissue.main()
    assert error.value.code == 2
    assert "retired" in capsys.readouterr().out


@pytest.mark.parametrize("reconcile", [False, True])
def test_mismatch_cli_exits_nonzero_in_both_modes(tmp_path: Path, reconcile: bool, monkeypatch, capsys) -> None:
    payload = _payload("10")
    monkeypatch.setattr(
        reissue, "get_public_page", Reader(_live("10", title="Другой заголовок", content=payload.nodes))
    )
    argv = ["charnock-qc", "--page", "10", "--media-base-url", MEDIA, "--receipt-dir", str(tmp_path)]
    if reconcile:
        argv.append("--reconcile")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as error:
        reissue.main()
    assert error.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["effect"] == "VISIBLE_TEXT_MISMATCH"
    assert result["verification"]["title_exact"] is False
    if reconcile:
        assert json.loads(next(tmp_path.iterdir()).read_text(encoding="utf-8")) == result
    else:
        assert list(tmp_path.iterdir()) == []


def test_real_reader_uses_only_one_public_get_without_credentials(monkeypatch) -> None:
    payload = _payload("10")
    page = _live("10", title=payload.title, content=payload.nodes)
    requests = []

    def fake_read(request) -> bytes:
        requests.append(request)
        assert request.get_method() == "GET"
        assert request.full_url == "https://api.telegra.ph/getPage/" + page["path"] + "?return_content=true"
        assert request.data is None
        assert "access_token" not in request.full_url
        assert "Authorization" not in request.headers
        return json.dumps({"ok": True, "result": page}, ensure_ascii=False).encode("utf-8")

    monkeypatch.setattr(surgical, "_read", fake_read)
    monkeypatch.setattr(surgical, "post_form", lambda *args, **kwargs: pytest.fail("provider POST forbidden"))
    result = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA)
    assert result["effect"] == "VISIBLE_TEXT_MATCH"
    assert len(requests) == 1


def test_reader_has_no_provider_mutation_helpers_or_token() -> None:
    text = (ROOT / "scripts/charnock_telegraph_qc_reissue.py").read_text(encoding="utf-8")
    for forbidden in ("post_form", "verify_ownership", "LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "editPage/", "sendMessage"):
        assert forbidden not in text
