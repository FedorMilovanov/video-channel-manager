"""Fail-closed, one-page-at-a-time corrections for the Charnock Telegraph series.

This is deliberately narrower than a publisher: it edits exactly one existing
page from a pinned before/after contract, never creates a page, never touches
Telegram, and never retries an ambiguous ``editPage``.  The default action is a
public GET + dry-run.  Execution additionally requires the original account
token, ``EDIT_EXISTING_CHARNOCK_PAGE_ONCE`` and an outside-repository receipt
directory.

The live page is treated as the source of the whole document: only the pinned
blockquote nodes are replaced, so unrelated live revisions are preserved.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.charnock_telegraph_surgical_revision import (
    AUTHOR,
    AUTHOR_URL,
    UnsafeRevision,
    get_public_page,
    post_form,
    sha_content,
    verify_ownership,
)

CONFIRM = "EDIT_EXISTING_CHARNOCK_PAGE_ONCE"
CONTRACTS_PATH = (
    Path(__file__).resolve().parents[1]
    / "content/telegram/lordchrist/telegraph-v1/charnock/charnock-inplace-contracts-20261121.json"
)
MAX_CONTENT_BYTES = 65_536
MAX_CONTENT_GROWTH = 8_192


def load_contracts(path: Path = CONTRACTS_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise UnsafeRevision("Contracts document has no pages")
    for key, contract in pages.items():
        if not isinstance(contract, dict) or not isinstance(contract.get("path"), str):
            raise UnsafeRevision(f"{key}: malformed contract")
        replacements = contract.get("replacements")
        if not isinstance(replacements, list) or not replacements:
            raise UnsafeRevision(f"{key}: no replacements")
        for rep in replacements:
            if not isinstance(rep, dict) or not all(
                isinstance(rep.get(field), str) for field in ("block_id", "before", "after")
            ):
                raise UnsafeRevision(f"{key}: malformed replacement")
            if not isinstance(rep.get("after_children"), list):
                raise UnsafeRevision(f"{key}: replacement has no Telegraph children")
    return pages


CONTRACTS = load_contracts()


def flatten(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(flatten(item) for item in value)
    if isinstance(value, dict):
        if "children" in value:
            return str(flatten(value["children"]))
        text = value.get("text")
        if isinstance(text, str):
            return text
    return ""


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_target(content: list[Any], before: str) -> int:
    matches = [
        index
        for index, node in enumerate(content)
        if isinstance(node, dict)
        and node.get("tag") == "blockquote"
        and normalized(flatten(node.get("children"))) == normalized(before)
    ]
    if len(matches) != 1:
        raise UnsafeRevision(f"expected exactly one live blockquote, found {len(matches)}")
    return matches[0]


def checked_page(page: dict[str, Any], key: str) -> None:
    contract = CONTRACTS[key]
    if page.get("path") != contract["path"]:
        raise UnsafeRevision(f"{key}: live path differs from pinned path")
    if page.get("author_name") != AUTHOR or page.get("author_url") != AUTHOR_URL:
        raise UnsafeRevision(f"{key}: live author differs from pinned author")
    if not isinstance(page.get("content"), list):
        raise UnsafeRevision(f"{key}: live content is not a list")


def prepare(page: dict[str, Any], key: str) -> tuple[list[Any], tuple[int, ...]]:
    """Return a full live-content clone with ONLY the pinned blockquotes replaced."""
    checked_page(page, key)
    proposal = copy.deepcopy(page["content"])
    changed: list[int] = []
    for replacement in CONTRACTS[key]["replacements"]:
        index = find_target(proposal, replacement["before"])
        new_node = {"tag": "blockquote", "children": copy.deepcopy(replacement["after_children"])}
        if normalized(flatten(new_node)) != normalized(replacement["after"]):
            raise UnsafeRevision(f"{key}/{replacement['block_id']}: contract after-text differs")
        proposal[index] = new_node
        changed.append(index)
    if len(set(changed)) != len(changed):
        raise UnsafeRevision(f"{key}: two replacements target the same node")
    actual = tuple(
        index
        for index, (before_node, after_node) in enumerate(zip(page["content"], proposal, strict=True))
        if before_node != after_node
    )
    if actual != tuple(sorted(changed)):
        raise UnsafeRevision(f"{key}: unexpected changed-node set {actual!r}")
    if len(proposal) != len(page["content"]):
        raise UnsafeRevision(f"{key}: node count changed")
    return proposal, actual


def _content_bytes(content: list[Any]) -> int:
    return len(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def run_one(
    key: str,
    *,
    execute: bool,
    confirm: str | None,
    receipt_dir: Path | None,
) -> dict[str, Any]:
    if key not in CONTRACTS:
        raise UnsafeRevision("Unknown page key")
    page = get_public_page(CONTRACTS[key]["path"])
    before_sha = sha_content(page["content"])
    after_content, changed = prepare(page, key)
    after_sha = sha_content(after_content)
    before_bytes = _content_bytes(page["content"])
    after_bytes = _content_bytes(after_content)
    if after_bytes > MAX_CONTENT_BYTES:
        raise UnsafeRevision(
            f"{key}: edited content is {after_bytes} UTF-8 bytes; Telegraph ceiling is {MAX_CONTENT_BYTES}"
        )
    if after_bytes - before_bytes > MAX_CONTENT_GROWTH:
        raise UnsafeRevision(f"{key}: content grew by more than {MAX_CONTENT_GROWTH} bytes")
    result: dict[str, Any] = {
        "article": key,
        "path": CONTRACTS[key]["path"],
        "url": page.get("url"),
        "old_sha256": before_sha,
        "new_sha256": after_sha,
        "changed_nodes": list(changed),
        "node_count": len(page["content"]),
        "content_utf8_bytes_before": before_bytes,
        "content_utf8_bytes_after": after_bytes,
        "effect": "DRY_RUN_NO_POST",
    }
    if not execute:
        return result
    if confirm != CONFIRM or receipt_dir is None:
        raise UnsafeRevision("Execution requires explicit confirmation and receipt directory")
    if not receipt_dir.is_dir() or any((part / ".git").exists() for part in (receipt_dir, *receipt_dir.parents)):
        raise UnsafeRevision("Receipt directory must already exist outside a git repository")
    receipt_file = receipt_dir / f"charnock-telegraph-{key}-{after_sha[:16]}.json"
    if receipt_file.exists():
        raise UnsafeRevision("Receipt already exists; reconcile first, no POST")
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
    if not token:
        raise UnsafeRevision("Existing Telegraph access token unavailable; no provider edit attempted")
    verify_ownership(token, CONTRACTS[key]["path"])
    # Second public GET: any intervening edit invalidates the prepared payload.
    recheck = get_public_page(CONTRACTS[key]["path"])
    checked_page(recheck, key)
    if sha_content(recheck["content"]) != before_sha:
        raise UnsafeRevision("Live snapshot changed before edit; no POST")
    fields = {
        "access_token": token,
        "title": str(page.get("title") or ""),
        "content": json.dumps(after_content, ensure_ascii=False, separators=(",", ":")),
        "author_name": str(page.get("author_name") or ""),
        "author_url": str(page.get("author_url") or ""),
        "return_content": "true",
    }
    # One irreversible POST only. Any timeout/error is UNCERTAIN; never retry.
    edited = post_form("editPage/" + CONTRACTS[key]["path"], fields)
    if edited.get("path") != CONTRACTS[key]["path"]:
        raise UnsafeRevision("Provider effect UNCERTAIN: editPage changed path; do not retry")
    check = get_public_page(CONTRACTS[key]["path"])
    for field in ("path", "url", "title", "author_name", "author_url", "image_url", "description"):
        if field in page and check.get(field) != page[field]:
            raise UnsafeRevision(f"Provider effect UNCERTAIN: {field} drift; do not retry")
    if check.get("content") != after_content:
        raise UnsafeRevision("Provider effect UNCERTAIN: full content mismatch; do not retry")
    result["effect"] = "VERIFIED_IN_PLACE"
    result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt_file.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(CONTRACTS), required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--receipt-dir", type=Path)
    args = parser.parse_args()
    if args.execute and args.confirm != CONFIRM:
        parser.error("Execution requires --confirm " + CONFIRM)
    try:
        outcome = run_one(
            args.page,
            execute=args.execute,
            confirm=args.confirm,
            receipt_dir=args.receipt_dir,
        )
    except Exception as exc:
        # Never echo arbitrary provider errors (can contain credentials).
        print(f"{args.page}: STOP / no automatic retry ({type(exc).__name__})")
        raise SystemExit(2) from None
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
