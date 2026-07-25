#!/usr/bin/env python3
"""Validate one source-led video article and its claim/source ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from video_channel_manager.editorial.article_sources import validate_article_source_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("ledger", type=Path)
    return parser


def _load_ledger(path: Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read source ledger {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Source ledger must be a JSON object")
    return payload


def main() -> int:
    args = _parser().parse_args()
    try:
        article_text = args.article.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"Cannot read article {args.article}: {exc}") from exc
    summary = validate_article_source_bundle(article_text, _load_ledger(args.ledger))
    print(
        "Video article source bundle is valid:\n"
        f"  article: {args.article}\n"
        f"  ledger: {args.ledger}\n"
        f"  claims: {summary['claims']}\n"
        f"  sources: {summary['sources']}\n"
        f"  ledger sha256: {summary['ledger_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
