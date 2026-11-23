#!/usr/bin/env python3
"""Apply a reviewed editorial patch to a Charnock rich-article JSON.

The patch is a small JSON file::

    {
      "replace": {"p-6": "New paragraph text with **bold**."},
      "insert_after": {
        "q-10": [
          {"type": "paragraph", "block_id": "p-20", "text": "New paragraph."}
        ]
      }
    }

Only top-level paragraphs and headings can be replaced; quotations are never
edited through this tool.  New blocks are inserted directly after the named
block.  The Markdown source is re-rendered from the JSON afterwards, so the
review surface cannot drift from what will be published.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from charnock_article_render_md import iter_text, render_markdown

INLINE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|\[(.+?)\]\((.+?)\)", re.S)


def parse_inline(text: str) -> list[Any]:
    """Parse the narrow inline subset used by the series into rich spans."""
    spans: list[Any] = []
    pos = 0
    for match in INLINE.finditer(text):
        if match.start() > pos:
            spans.append(text[pos : match.start()])
        if match.group(1) is not None:
            spans.append({"type": "bold", "text": match.group(1)})
        elif match.group(2) is not None:
            spans.append({"type": "italic", "text": match.group(2)})
        else:
            spans.append({"type": "url", "text": match.group(3), "url": match.group(4)})
        pos = match.end()
    if pos < len(text):
        spans.append(text[pos:])
    if not spans:
        return [""]
    if len(spans) == 1 and isinstance(spans[0], str):
        return spans[0]
    return spans


def find_block(
    blocks: list[dict[str, Any]], block_id: str
) -> tuple[int, dict[str, Any]]:
    for index, block in enumerate(blocks):
        if block.get("block_id") == block_id:
            return index, block
    raise SystemExit(f"block not found: {block_id}")


def _require_source_credit(article: dict[str, Any]) -> None:
    """The only publishable source credit is the one carried in JSON blocks."""
    blocks = article.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise SystemExit("article has no block list")
    footer = blocks[-1]
    if footer.get("type") != "paragraph":
        raise SystemExit("missing source credit in last JSON paragraph")
    credit = iter_text(footer.get("text", ""))
    if (
        not credit.startswith("© Цитаты Чарнока")
        or "gutenberg.org/ebooks/53527" not in credit
    ):
        raise SystemExit("missing source credit in JSON; no files written")


def _stage_bytes(target: Path, contents: bytes, *, suffix: str = ".tmp") -> Path:
    """Stage bytes on the destination filesystem before replacing anything."""
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{target.name}.",
        suffix=suffix,
        dir=target.parent,
        delete=False,
    ) as stream:
        stream.write(contents)
        return Path(stream.name)


def _write_pair(
    article_path: Path, markdown_path: Path, json_text: str, markdown_text: str
) -> None:
    """Prestage both files; roll back on failure or preserve unrecoverable backups.

    A two-file replacement cannot be power-loss atomic. If restoration also
    fails, keep the exact original bytes in an on-disk .rollback file and
    report its location. Do not silently discard the recovery copy.
    """
    originals = (
        (article_path, article_path.read_bytes(), json_text.encode("utf-8")),
        (markdown_path, markdown_path.read_bytes(), markdown_text.encode("utf-8")),
    )
    staged: list[tuple[Path, Path, Path]] = []
    replaced: list[tuple[Path, Path]] = []
    preserve_backups: set[Path] = set()
    try:
        for target, previous, updated in originals:
            candidate = _stage_bytes(target, updated)
            try:
                rollback = _stage_bytes(target, previous, suffix=".rollback")
            except BaseException:
                candidate.unlink(missing_ok=True)
                raise
            staged.append((target, candidate, rollback))
        for target, candidate, rollback in staged:
            os.replace(candidate, target)
            replaced.append((target, rollback))
    except BaseException as write_error:
        restore_errors: list[tuple[Path, Path, BaseException]] = []
        for target, rollback in reversed(replaced):
            try:
                os.replace(rollback, target)
            except BaseException as restore_error:
                preserve_backups.add(rollback)
                restore_errors.append((target, rollback, restore_error))
        if restore_errors:
            evidence = "; ".join(
                f"target={target}; backup={backup}; error={error!r}"
                for target, backup, error in restore_errors
            )
            raise RuntimeError(
                "JSON/Markdown pair update AND rollback failed; "
                "original backup(s) retained for manual recovery: "
                f"{evidence}; first error={write_error!r}"
            ) from write_error
        raise
    finally:
        for _target, candidate, rollback in staged:
            candidate.unlink(missing_ok=True)
            if rollback not in preserve_backups:
                rollback.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--markdown",
        type=Path,
        help="Markdown source to rewrite (default: JSON sibling)",
    )
    args = parser.parse_args(argv)

    # Validate the original published-source pair before modifying either file.
    # The Markdown review copy must never supply missing JSON-only content.
    if args.markdown is not None and args.markdown.resolve() == args.article.resolve():
        raise SystemExit("article and Markdown paths must differ")
    original_json = args.article.read_text(encoding="utf-8")
    article = json.loads(original_json)
    markdown_path = args.markdown or args.article.with_suffix(".md")
    if not markdown_path.exists():
        raise SystemExit(f"missing existing reviewed Markdown: {markdown_path}")
    old_markdown = markdown_path.read_text(encoding="utf-8")
    _require_source_credit(article)
    if render_markdown(article).rstrip("\n") != old_markdown.rstrip("\n"):
        raise SystemExit("JSON/Markdown drift before patch; no files written")
    patch = json.loads(args.patch.read_text(encoding="utf-8"))
    blocks = article.get("blocks")
    if not isinstance(blocks, list):
        raise SystemExit("article has no block list")

    for block_id, text in patch.get("replace", {}).items():
        _, block = find_block(blocks, block_id)
        if block.get("type") not in {"paragraph", "heading"}:
            raise SystemExit(
                f"{block_id}: only paragraphs and headings may be replaced"
            )
        block["text"] = parse_inline(text)

    for anchor_id, new_blocks in patch.get("insert_after", {}).items():
        index, _ = find_block(blocks, anchor_id)
        prepared: list[dict[str, Any]] = []
        for raw in new_blocks:
            block = dict(raw)
            if block.get("type") not in {"paragraph", "heading"}:
                raise SystemExit(
                    f"insert after {anchor_id}: unsupported type {block.get('type')!r}"
                )
            block["text"] = parse_inline(block["text"])
            prepared.append(block)
        blocks[index + 1 : index + 1] = prepared

    seen: set[str] = set()
    for block in blocks:
        block_id = block.get("block_id")
        if block_id in seen:
            raise SystemExit(f"duplicate block id after patch: {block_id}")
        seen.add(block_id)

    article["revision"] = args.revision
    article.setdefault("metadata", {})["updated_at"] = date.today().isoformat()
    _require_source_credit(article)
    # Render/validate both outputs before the first write. Stage both files and
    # a rollback copy so a failed second replacement restores the original pair.
    new_markdown = render_markdown(article)
    new_json = json.dumps(article, ensure_ascii=False, indent=2) + "\n"
    _write_pair(args.article, markdown_path, new_json, new_markdown)
    print(
        f"applied {len(patch.get('replace', {}))} replacements and "
        f"{sum(len(v) for v in patch.get('insert_after', {}).values())} insertions; "
        f"rewrote {markdown_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
