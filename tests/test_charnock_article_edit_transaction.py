"""Charnock editor must never partially replace JSON or Markdown on failures."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.charnock_article_render_md import render_markdown


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "charnock_article_edit.py"
FOOTER = [
    "© Цитаты Чарнока — из книги ",
    {"type": "bold", "text": "«Беседы о существовании и атрибутах Бога»"},
    "; Project Gutenberg, https://www.gutenberg.org/ebooks/53527.",
]


def _files(tmp_path: Path, *, json_footer: bool = True) -> tuple[Path, Path, Path]:
    article = {
        "revision": "reviewed",
        "metadata": {"updated_at": "2026-11-22"},
        "blocks": [
            {"type": "heading", "block_id": "h-1", "size": 1, "text": "Title"},
            {"type": "paragraph", "block_id": "p-1", "text": "Before"},
        ],
    }
    if json_footer:
        article["blocks"].append({"type": "paragraph", "block_id": "p-2", "text": FOOTER})
    article_path = tmp_path / "candidate.json"
    markdown_path = tmp_path / "candidate.md"
    patch_path = tmp_path / "patch.json"
    article_path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readable = {**article, "blocks": article["blocks"] + (
        [{"type": "paragraph", "block_id": "p-2", "text": FOOTER}] if not json_footer else []
    )}
    markdown_path.write_text(render_markdown(readable), encoding="utf-8")
    patch_path.write_text(json.dumps({"replace": {"p-1": "After **bold**"}}, ensure_ascii=False), encoding="utf-8")
    return article_path, markdown_path, patch_path


def _run(article: Path, markdown: Path, patch: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--article", str(article), "--markdown", str(markdown),
         "--patch", str(patch), "--revision", "candidate-reviewed"],
        capture_output=True, text=True, check=False,
    )


def test_editor_updates_json_and_markdown_when_source_credit_is_real(tmp_path: Path) -> None:
    article, markdown, patch = _files(tmp_path)
    result = _run(article, markdown, patch)
    assert result.returncode == 0, result.stderr
    updated = json.loads(article.read_text(encoding="utf-8"))
    assert updated["revision"] == "candidate-reviewed"
    assert updated["blocks"][1]["text"] == ["After ", {"type": "bold", "text": "bold"}]
    assert updated["blocks"][-1]["text"] == FOOTER
    assert markdown.read_text(encoding="utf-8") == render_markdown(updated)


def test_editor_rejects_markdown_only_credit_without_writing(tmp_path: Path) -> None:
    article, markdown, patch = _files(tmp_path, json_footer=False)
    before = (article.read_bytes(), markdown.read_bytes())
    result = _run(article, markdown, patch)
    assert result.returncode != 0
    assert "missing source credit in JSON" in result.stderr
    assert (article.read_bytes(), markdown.read_bytes()) == before


def test_editor_rejects_preexisting_parity_drift_without_writing(tmp_path: Path) -> None:
    article, markdown, patch = _files(tmp_path)
    markdown.write_text(markdown.read_text(encoding="utf-8").replace("Before", "Out of sync"), encoding="utf-8")
    before = (article.read_bytes(), markdown.read_bytes())
    result = _run(article, markdown, patch)
    assert result.returncode != 0
    assert "JSON/Markdown drift before patch" in result.stderr
    assert (article.read_bytes(), markdown.read_bytes()) == before


def test_editor_rejects_patch_that_erases_source_credit(tmp_path: Path) -> None:
    article, markdown, patch = _files(tmp_path)
    patch.write_text(json.dumps({"replace": {"p-2": "No credit now"}}), encoding="utf-8")
    before = (article.read_bytes(), markdown.read_bytes())
    result = _run(article, markdown, patch)
    assert result.returncode != 0
    assert "missing source credit in JSON" in result.stderr
    assert (article.read_bytes(), markdown.read_bytes()) == before


def test_pair_writer_restores_json_if_second_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercise the failure after the first os.replace, not just preflight validation.
    spec = importlib.util.spec_from_file_location("charnock_editor_tested", SCRIPT)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        editor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(editor)
    finally:
        sys.path.pop(0)
    article, markdown, _ = _files(tmp_path)
    before = (article.read_bytes(), markdown.read_bytes())
    original_replace = os.replace
    calls = 0

    def fail_second_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second-file rename failure")
        original_replace(src, dst)

    monkeypatch.setattr(editor.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="simulated second-file"):
        editor._write_pair(article, markdown, '{"revision":"changed"}\n', "Changed\n")
    assert calls == 3  # JSON write, Markdown failure, JSON rollback
    assert (article.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob(".*.tmp"))
