"""Regression tests for the consumed Charnock QC editor's read-only boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import charnock_telegraph_qc_reissue as reissue

ROOT = Path(__file__).resolve().parents[1]
MEDIA = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/" + "a" * 40


def _current_page(key: str, *, title: str | None = None) -> dict:
    manifest = reissue.load_manifest()
    contract = manifest[key]
    payload = reissue.reviewed_payload(key, repo_root=ROOT, media_base_url=MEDIA, manifest=manifest)
    return {
        "path": contract["path"],
        "url": contract["url"],
        "author_name": reissue.AUTHOR,
        "author_url": reissue.AUTHOR_URL,
        "title": payload.title if title is None else title,
        "content": payload.nodes,
    }


def test_reconcile_rejects_wrong_title_even_if_every_node_matches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(reissue, "get_public_page", lambda path: _current_page("10", title="Чужой заголовок"))
    result = reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, receipt_dir=tmp_path, reconcile=True)
    assert result["effect"] == "VISIBLE_TEXT_MISMATCH"
    assert result["verification"]["title_exact"] is False
    assert result["verification"]["visible_text_equal"] is True
    receipt = json.loads(next(tmp_path.iterdir()).read_text(encoding="utf-8"))
    assert receipt["effect"] == "VISIBLE_TEXT_MISMATCH"


def test_execute_is_retired_before_any_provider_read(monkeypatch) -> None:
    def unexpected_read(path: str) -> dict:
        raise AssertionError("retired execution must stop before any provider read")

    monkeypatch.setattr(reissue, "get_public_page", unexpected_read)
    with pytest.raises(reissue.UnsafeRevision, match="retired"):
        reissue.run_one("10", repo_root=ROOT, media_base_url=MEDIA, execute=True)


def test_mismatch_exits_nonzero_for_the_workflow(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["charnock-qc", "--page", "10", "--media-base-url", MEDIA, "--reconcile"])
    monkeypatch.setattr(reissue, "run_one", lambda *args, **kwargs: {"effect": "VISIBLE_TEXT_MISMATCH"})
    with pytest.raises(SystemExit) as error:
        reissue.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["effect"] == "VISIBLE_TEXT_MISMATCH"
