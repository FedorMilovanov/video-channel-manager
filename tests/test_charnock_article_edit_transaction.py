"""Charnock editor must recover both files or retain original rollback evidence."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

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
    article_path.write_text(
        json.dumps(article, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    extra = [] if json_footer else [{"type": "paragraph", "block_id": "p-2", "text": FOOTER}]
    readable = {**article, "blocks": article["blocks"] + extra}
    markdown_path.write_text(render_markdown(readable), encoding="utf-8")
    patch_path.write_text(
        json.dumps({"replace": {"p-1": "After **bold**"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return article_path, markdown_path, patch_path


def _run(article: Path, markdown: Path, patch: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--article",
            str(article),
            "--markdown",
            str(markdown),
            "--patch",
            str(patch),
            "--revision",
            "candidate-reviewed",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_editor_updates_json_and_markdown_when_source_credit_is_real(
    tmp_path: Path,
) -> None:
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


def test_editor_rejects_preexisting_parity_drift_without_writing(
    tmp_path: Path,
) -> None:
    article, markdown, patch = _files(tmp_path)
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace("Before", "Out of sync"),
        encoding="utf-8",
    )
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


def test_pair_writer_restores_json_if_second_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert calls == 4  # JSON write, Markdown failure, Markdown restore, JSON restore
    assert (article.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_recovery_copy_survives_failed_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If both the second write and rollback fail, do not erase old JSON bytes."""
    spec = importlib.util.spec_from_file_location("charnock_editor_double_failure", SCRIPT)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        editor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(editor)
    finally:
        sys.path.pop(0)
    article, markdown, _ = _files(tmp_path)
    original_json, original_md = article.read_bytes(), markdown.read_bytes()
    original_replace = os.replace
    calls = 0

    def fail_write_and_restore(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls in (2, 4):
            raise OSError(f"simulated failure at replace #{calls}")
        original_replace(src, dst)

    monkeypatch.setattr(editor.os, "replace", fail_write_and_restore)
    with pytest.raises(RuntimeError, match="backup\\(s\\) retained") as caught:
        editor._write_pair(article, markdown, '{"revision":"changed"}\\n', "Changed\\n")
    assert calls == 4
    assert article.read_bytes() != original_json  # rollback was blocked
    assert markdown.read_bytes() == original_md
    saved = list(tmp_path.glob(".*.rollback"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == original_json
    assert str(saved[0]) in str(caught.value)
    assert "first error" in str(caught.value)
    assert not list(tmp_path.glob(".*.tmp"))
    # Operator can restore exact original bytes from the retained backup.
    original_replace(saved[0], article)
    assert (article.read_bytes(), markdown.read_bytes()) == (original_json, original_md)


def test_interrupt_after_successful_rename_restores_both_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """First replace succeeds, but an interrupt lands before the next bytecode."""
    spec = importlib.util.spec_from_file_location("charnock_editor_interrupt", SCRIPT)
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

    def replace_then_interrupt(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        original_replace(src, dst)
        if calls == 1:
            raise KeyboardInterrupt("after successful first rename")

    monkeypatch.setattr(editor.os, "replace", replace_then_interrupt)
    with pytest.raises(KeyboardInterrupt, match="after successful first rename"):
        editor._write_pair(article, markdown, '{"revision":"changed"}\\n', "Changed\\n")
    assert calls == 2  # rename, rollback of exact original JSON
    assert (article.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob(".*.rollback"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX source-mode preservation")
def test_editor_preserves_original_mode_for_both_files(tmp_path: Path) -> None:
    article, markdown, patch = _files(tmp_path)
    os.chmod(article, 0o644)
    os.chmod(markdown, 0o640)
    before = (article.stat().st_mode & 0o777, markdown.stat().st_mode & 0o777)
    result = _run(article, markdown, patch)
    assert result.returncode == 0, result.stderr
    assert (article.stat().st_mode & 0o777, markdown.stat().st_mode & 0o777) == before


def test_staging_failure_cleans_up_temporary_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed chmod must not leave a partial staged file or change the source."""
    spec = importlib.util.spec_from_file_location("charnock_editor_staging", SCRIPT)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        editor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(editor)
    finally:
        sys.path.pop(0)
    article, markdown, _ = _files(tmp_path)
    before = (article.read_bytes(), markdown.read_bytes())

    def fail_chmod(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated failure while setting original source mode")

    monkeypatch.setattr(editor.os, "chmod", fail_chmod)
    with pytest.raises(OSError, match="source mode"):
        editor._stage_bytes(article, b"new staged content")
    assert (article.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob(".*.tmp"))


def _load_editor_for_lock_test(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        editor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(editor)
        return editor
    finally:
        sys.path.pop(0)


def test_concurrent_edit_of_same_pair_fails_closed(tmp_path: Path) -> None:
    """A second process cannot pass preflight while the first owns both files."""
    article, markdown, patch = _files(tmp_path)
    editor = _load_editor_for_lock_test("charnock_editor_lock_same_pair")
    before = (article.read_bytes(), markdown.read_bytes())
    with editor._exclusive_pair_lock(article, markdown):
        result = _run(article, markdown, patch)
        assert result.returncode != 0
        assert "Charnock editor lock exists" in result.stderr
        assert (article.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob("*.charnock-edit.lock"))
    result = _run(article, markdown, patch)
    assert result.returncode == 0, result.stderr
    reviewed = json.loads(article.read_text(encoding="utf-8"))
    assert render_markdown(reviewed) == markdown.read_text(encoding="utf-8")


def test_shared_markdown_path_is_exclusive_across_different_json(tmp_path: Path) -> None:
    """Different JSON filenames must not concurrently overwrite one reviewed MD."""
    article, markdown, patch = _files(tmp_path)
    editor = _load_editor_for_lock_test("charnock_editor_lock_shared_md")
    other = tmp_path / "other.json"
    other.write_bytes(article.read_bytes())
    before = (other.read_bytes(), markdown.read_bytes())
    command = [
        sys.executable,
        str(SCRIPT),
        "--article",
        str(other),
        "--markdown",
        str(markdown),
        "--patch",
        str(patch),
        "--revision",
        "other-process",
    ]
    with editor._exclusive_pair_lock(article, markdown):
        outcome = subprocess.run(command, capture_output=True, text=True, check=False)
        assert outcome.returncode != 0
        assert "Charnock editor lock exists" in outcome.stderr
        assert (other.read_bytes(), markdown.read_bytes()) == before
    assert not list(tmp_path.glob("*.charnock-edit.lock"))


def test_stale_lock_is_never_removed_automatically(tmp_path: Path) -> None:
    """A crash remnant requires inspection; it never authorizes a risky retry."""
    article, markdown, patch = _files(tmp_path)
    lock = Path(str(article.resolve()) + ".charnock-edit.lock")
    lock.write_text("pid=unknown\n", encoding="utf-8")
    before = (article.read_bytes(), markdown.read_bytes())
    try:
        outcome = _run(article, markdown, patch)
        assert outcome.returncode != 0
        assert "inspect before manual removal" in outcome.stderr
        assert lock.read_text(encoding="utf-8") == "pid=unknown\n"
        assert (article.read_bytes(), markdown.read_bytes()) == before
    finally:
        lock.unlink()
    assert not list(tmp_path.glob("*.charnock-edit.lock"))
