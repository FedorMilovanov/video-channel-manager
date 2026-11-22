"""Unit guards for the one-page QC reissue editor (no network, no provider writes)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import charnock_telegraph_qc_reissue as reissue

ROOT = Path(__file__).resolve().parents[1]
MEDIA = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40


def _manifest() -> dict:
    return reissue.load_manifest()


def _live(key: str, *, title: str | None = None, content: list | None = None) -> dict:
    contract = _manifest()[key]
    return {
        "path": contract["path"],
        "url": contract["url"],
        "title": title or "Прежний заголовок",
        "author_name": reissue.AUTHOR,
        "author_url": reissue.AUTHOR_URL,
        "content": content if content is not None else [{"tag": "p", "children": ["Старый текст страницы."]}],
    }


def _payload(key: str):
    return reissue.reviewed_payload(key, repo_root=ROOT, media_base_url=MEDIA, manifest=_manifest())


class Reader:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = list(pages)
        self.calls = 0

    def __call__(self, path: str) -> dict:
        page = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        assert page["path"] == path
        return page


def test_manifest_pins_thirteen_existing_pages(tmp_path: Path) -> None:
    pages = _manifest()
    assert set(pages) == {"01b", *[f"{n:02d}" for n in range(2, 14)]}
    assert len({page["path"] for page in pages.values()}) == 13
    for key, page in pages.items():
        assert page["url"] == "https://telegra.ph/" + page["path"]
        assert page["article_path"].endswith(f"lordchrist-telegraph-charnock-{key}.json")
        assert len(page["article_git_blob_sha"]) == 40


def test_manifest_matches_queue_blobs() -> None:
    pages = _manifest()
    queue = json.loads((ROOT / reissue.QUEUE_PATH).read_text(encoding="utf-8"))["items"]
    by_id = {item["publication_id"]: item for item in queue}
    for page in pages.values():
        item = by_id[page["publication_id"]]
        assert item["article"]["path"] == page["article_path"]
        assert item["article"]["git_blob_sha"] == page["article_git_blob_sha"]


def test_dry_run_reports_the_plan_without_a_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(reissue, "get_public_page", Reader([_live("01b")]))
    outcome = reissue.run_one(
        "01b",
        repo_root=ROOT,
        media_base_url=MEDIA,
        receipt_dir=tmp_path,
        manifest=_manifest(),
    )
    assert outcome["effect"] == "DRY_RUN_NO_POST"
    assert outcome["node_count_after"] == len(_payload("01b").nodes)
    assert outcome["planned_differences"]
    assert outcome["content_utf8_bytes_after"] <= reissue.MAX_CONTENT_BYTES
    assert list(tmp_path.iterdir()) == []


def test_execute_posts_exactly_once_and_verifies_exact_readback(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("01b")
    monkeypatch.setattr(
        reissue,
        "get_public_page",
        Reader(
            [
                _live("01b"),
                _live("01b"),
                {
                    **_live("01b"),
                    "title": payload.title,
                    "content": payload.nodes,
                },
            ]
        ),
    )
    posts: list[tuple[str, dict]] = []
    monkeypatch.setattr(reissue, "verify_ownership", lambda token, path: None)

    def fake_post(path: str, fields: dict) -> dict:
        posts.append((path, fields))
        return {"path": path.split("/", 1)[1]}

    monkeypatch.setattr(reissue, "post_form", fake_post)
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "token-value")
    outcome = reissue.run_one(
        "01b",
        repo_root=ROOT,
        media_base_url=MEDIA,
        execute=True,
        confirm=reissue.CONFIRM,
        receipt_dir=tmp_path,
        manifest=_manifest(),
    )
    assert outcome["effect"] == "VERIFIED_REISSUE"
    assert outcome["verification"]["mode"] == "exact"
    assert len(posts) == 1
    path, fields = posts[0]
    assert path == "editPage/" + _manifest()["01b"]["path"]
    assert fields["title"] == payload.title
    assert fields["content"] == payload.compact_content_json
    assert "token-value" in json.dumps(fields)
    receipts = list(tmp_path.iterdir())
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["effect"] == "VERIFIED_REISSUE"
    assert receipt["live_sha256"] == reissue.sha_content(payload.nodes)


def test_readback_with_normalised_nodes_is_verified_semantically(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("07")
    normalised = list(payload.nodes)
    normalised.insert(1, {"tag": "br"})
    monkeypatch.setattr(
        reissue,
        "get_public_page",
        Reader([_live("07"), _live("07"), {**_live("07"), "title": payload.title, "content": normalised}]),
    )
    monkeypatch.setattr(reissue, "verify_ownership", lambda token, path: None)
    monkeypatch.setattr(reissue, "post_form", lambda path, fields: {"path": path.split("/", 1)[1]})
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "token-value")
    outcome = reissue.run_one(
        "07",
        repo_root=ROOT,
        media_base_url=MEDIA,
        execute=True,
        confirm=reissue.CONFIRM,
        receipt_dir=tmp_path,
        manifest=_manifest(),
    )
    assert outcome["effect"] == "VERIFIED_REISSUE"
    assert outcome["verification"]["mode"] == "semantic"


def test_readback_mismatch_is_uncertain_and_never_retried(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("07")
    broken = [{"tag": "p", "children": ["Совсем другой текст."]}]
    monkeypatch.setattr(
        reissue,
        "get_public_page",
        Reader([_live("07"), _live("07"), {**_live("07"), "title": payload.title, "content": broken}]),
    )
    monkeypatch.setattr(reissue, "verify_ownership", lambda token, path: None)
    monkeypatch.setattr(reissue, "post_form", lambda path, fields: {"path": path.split("/", 1)[1]})
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "token-value")
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one(
            "07",
            repo_root=ROOT,
            media_base_url=MEDIA,
            execute=True,
            confirm=reissue.CONFIRM,
            receipt_dir=tmp_path,
            manifest=_manifest(),
        )
    receipts = list(tmp_path.iterdir())
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["effect"] == "UNCERTAIN"


def test_edit_changing_the_path_is_uncertain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(reissue, "get_public_page", Reader([_live("07"), _live("07")]))
    monkeypatch.setattr(reissue, "verify_ownership", lambda token, path: None)
    monkeypatch.setattr(reissue, "post_form", lambda path, fields: {"path": "Drugaya-stranica-11-21"})
    monkeypatch.setenv("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "token-value")
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one(
            "07",
            repo_root=ROOT,
            media_base_url=MEDIA,
            execute=True,
            confirm=reissue.CONFIRM,
            receipt_dir=tmp_path,
            manifest=_manifest(),
        )
    assert [p.name for p in tmp_path.iterdir() if "uncertain" in p.name]


def test_live_page_with_foreign_author_is_refused(tmp_path: Path, monkeypatch) -> None:
    stranger = {**_live("09"), "author_name": "Кто-то другой"}
    monkeypatch.setattr(reissue, "get_public_page", Reader([stranger]))
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one("09", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, manifest=_manifest())


def test_already_live_page_requires_reconcile(tmp_path: Path, monkeypatch) -> None:
    payload = _payload("11")
    current = {**_live("11"), "title": payload.title, "content": payload.nodes}
    monkeypatch.setattr(reissue, "get_public_page", Reader([current]))
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one("11", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, manifest=_manifest())
    outcome = reissue.run_one(
        "11",
        repo_root=ROOT,
        media_base_url=MEDIA,
        receipt_dir=tmp_path,
        reconcile=True,
        manifest=_manifest(),
    )
    assert outcome["effect"] == "VERIFIED_REISSUE_RECONCILED"
    assert outcome["live_first_text"] == outcome["target_first_text"]
    assert outcome["live_last_text"] == outcome["target_last_text"]
    assert outcome["live_first_text"]
    assert len(list(tmp_path.iterdir())) == 1


def test_execution_needs_confirmation_and_receipt_directory(monkeypatch) -> None:
    monkeypatch.setattr(reissue, "get_public_page", Reader([_live("02")]))
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one(
            "02",
            repo_root=ROOT,
            media_base_url=MEDIA,
            execute=True,
            confirm="nope",
            receipt_dir=Path("/tmp"),
            manifest=_manifest(),
        )


def test_receipt_directory_inside_git_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(reissue, "get_public_page", Reader([_live("02")]))
    with pytest.raises(reissue.UnsafeRevision):
        reissue.run_one(
            "02",
            repo_root=ROOT,
            media_base_url=MEDIA,
            execute=True,
            confirm=reissue.CONFIRM,
            receipt_dir=ROOT,
            manifest=_manifest(),
        )


def test_manifest_rejects_mismatched_url(tmp_path: Path) -> None:
    document = json.loads((ROOT / reissue.MANIFEST_PATH).read_text(encoding="utf-8"))
    document["pages"]["01b"]["url"] = "https://telegra.ph/drugaya-stranica"
    broken = tmp_path / "manifest.json"
    broken.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(reissue.UnsafeRevision):
        reissue.load_manifest(broken)
