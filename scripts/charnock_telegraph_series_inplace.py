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


def _semantic_nodes(content: list[Any], exclude: set[int]) -> list[tuple[str, str]]:
    """Tag + visible text for non-target nodes, ignoring empty line-break nodes."""
    nodes: list[tuple[str, str]] = []
    for index, node in enumerate(content):
        if index in exclude or not isinstance(node, dict):
            continue
        tag = str(node.get("tag") or "")
        text = normalized(flatten(node))
        if tag == "br" or not text:
            continue
        nodes.append((tag, text))
    return nodes


def _target_indices_after(content: list[Any], key: str) -> tuple[int, ...]:
    """Require every contract after-blockquote exactly once and no before-blockquote left."""
    indices: list[int] = []
    for replacement in CONTRACTS[key]["replacements"]:
        after = normalized(replacement["after"])
        before = normalized(replacement["before"])
        after_matches = [
            index
            for index, node in enumerate(content)
            if isinstance(node, dict) and node.get("tag") == "blockquote" and normalized(flatten(node)) == after
        ]
        before_matches = [
            index
            for index, node in enumerate(content)
            if isinstance(node, dict) and node.get("tag") == "blockquote" and normalized(flatten(node)) == before
        ]
        if len(after_matches) != 1:
            raise UnsafeRevision(
                f"{key}/{replacement['block_id']}: expected exactly one applied blockquote, found {len(after_matches)}"
            )
        if before_matches:
            raise UnsafeRevision(f"{key}/{replacement['block_id']}: pre-edit blockquote is still present")
        indices.append(after_matches[0])
    if len(set(indices)) != len(indices):
        raise UnsafeRevision(f"{key}: two targets resolved to the same live blockquote")
    return tuple(indices)


def _safe_prefix(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _semantic_diff(
    key: str,
    before_content: list[Any],
    live_content: list[Any],
    changed: tuple[int, ...],
) -> list[str]:
    """Explain non-target differences without ever including the access token."""
    live_targets = _target_indices_after(live_content, key)
    before_nodes = _semantic_nodes(before_content, set(changed))
    live_nodes = _semantic_nodes(live_content, set(live_targets))
    differences: list[str] = []
    for index, (before_node, live_node) in enumerate(zip(before_nodes, live_nodes, strict=False)):
        if before_node != live_node:
            differences.append(
                f"node {index}: {before_node[0]} {_safe_prefix(before_node[1])!r} -> "
                f"{live_node[0]} {_safe_prefix(live_node[1])!r}"
            )
        if len(differences) >= 5:
            break
    if len(before_nodes) != len(live_nodes):
        differences.append(f"non-target node count {len(before_nodes)} -> {len(live_nodes)}")
    return differences


def _check_receipt_dir(receipt_dir: Path | None) -> Path:
    if receipt_dir is None:
        raise UnsafeRevision("A receipt directory is required")
    if not receipt_dir.is_dir() or any((part / ".git").exists() for part in (receipt_dir, *receipt_dir.parents)):
        raise UnsafeRevision("Receipt directory must already exist outside a git repository")
    return receipt_dir


def _receipt_path(receipt_dir: Path, key: str, suffix: str, digest: str) -> Path:
    run_id = os.environ.get("GITHUB_RUN_ID") or "local"
    return receipt_dir / f"charnock-telegraph-{key}-{digest[:16]}{suffix}-{run_id}.json"


def _write_receipt(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _reconcile_one(key: str, receipt_dir: Path) -> dict[str, Any]:
    """Read-only proof that an already-applied page still matches every after-blockquote."""
    page = get_public_page(CONTRACTS[key]["path"])
    targets = _target_indices_after(page["content"], key)
    live_sha = sha_content(page["content"])
    result: dict[str, Any] = {
        "article": key,
        "path": CONTRACTS[key]["path"],
        "url": page.get("url"),
        "old_sha256": None,
        "new_sha256": live_sha,
        "live_sha256": live_sha,
        "changed_nodes": list(targets),
        "node_count": len(page["content"]),
        "content_utf8_bytes": _content_bytes(page["content"]),
        "effect": "VERIFIED_IN_PLACE_RECONCILED",
        "verification": {"mode": "reconciled", "read_only": True, "targets_after": list(targets)},
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_receipt(_receipt_path(receipt_dir, key, "-reconciled", live_sha), result)
    return result


def run_one(
    key: str,
    *,
    execute: bool,
    confirm: str | None,
    receipt_dir: Path | None,
    reconcile: bool = False,
) -> dict[str, Any]:
    if key not in CONTRACTS:
        raise UnsafeRevision("Unknown page key")
    if execute and reconcile:
        raise UnsafeRevision("Execution and reconciliation are mutually exclusive")
    if reconcile:
        directory = _check_receipt_dir(receipt_dir)
        return _reconcile_one(key, directory)
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
    if confirm != CONFIRM:
        raise UnsafeRevision("Execution requires explicit confirmation and receipt directory")
    directory = _check_receipt_dir(receipt_dir)
    receipt_file = _receipt_path(directory, key, "", after_sha)
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
    try:
        edited = post_form("editPage/" + CONTRACTS[key]["path"], fields)
    except Exception as exc:
        result["effect"] = "UNCERTAIN"
        result["uncertainty"] = f"POST_{type(exc).__name__}"
        result["run_id"] = os.environ.get("GITHUB_RUN_ID")
        _write_receipt(_receipt_path(directory, key, "-uncertain", after_sha), result)
        raise
    if edited.get("path") != CONTRACTS[key]["path"]:
        result["effect"] = "UNCERTAIN"
        result["uncertainty"] = "editPage changed path"
        result["run_id"] = os.environ.get("GITHUB_RUN_ID")
        _write_receipt(_receipt_path(directory, key, "-uncertain", after_sha), result)
        raise UnsafeRevision("Provider effect UNCERTAIN: editPage changed path; do not retry")
    check = get_public_page(CONTRACTS[key]["path"])
    for field in ("path", "url", "title", "author_name", "author_url", "image_url", "description"):
        if field in page and check.get(field) != page[field]:
            result["effect"] = "UNCERTAIN"
            result["uncertainty"] = f"{field} drift"
            result["live_sha256"] = sha_content(check["content"])
            result["run_id"] = os.environ.get("GITHUB_RUN_ID")
            _write_receipt(_receipt_path(directory, key, "-uncertain", after_sha), result)
            raise UnsafeRevision(f"Provider effect UNCERTAIN: {field} drift; do not retry")
    live_sha = sha_content(check["content"])
    result["live_sha256"] = live_sha
    if check.get("content") == after_content:
        result["effect"] = "VERIFIED_IN_PLACE"
        result["verification"] = {"mode": "exact", "provider_content_exact": True}
    else:
        try:
            differences = _semantic_diff(key, page["content"], check["content"], changed)
        except UnsafeRevision as exc:
            result["effect"] = "UNCERTAIN"
            result["uncertainty"] = str(exc)
            result["run_id"] = os.environ.get("GITHUB_RUN_ID")
            _write_receipt(_receipt_path(directory, key, "-uncertain", after_sha), result)
            raise
        if differences:
            result["effect"] = "UNCERTAIN"
            result["uncertainty"] = "non-target text changed"
            result["differences"] = differences
            result["run_id"] = os.environ.get("GITHUB_RUN_ID")
            _write_receipt(_receipt_path(directory, key, "-uncertain", after_sha), result)
            raise UnsafeRevision("Provider effect UNCERTAIN: non-target text changed; do not retry")
        result["effect"] = "VERIFIED_IN_PLACE"
        result["verification"] = {
            "mode": "semantic",
            "provider_content_exact": False,
            "non_target_text_unchanged": True,
            "node_count_after": len(check["content"]),
            "content_utf8_bytes_after": _content_bytes(check["content"]),
        }
    result["run_id"] = os.environ.get("GITHUB_RUN_ID")
    result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_receipt(_receipt_path(directory, key, "", after_sha), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(CONTRACTS), required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--receipt-dir", type=Path)
    args = parser.parse_args()
    if args.execute and args.reconcile:
        parser.error("--execute and --reconcile are mutually exclusive")
    if args.execute and args.confirm != CONFIRM:
        parser.error("Execution requires --confirm " + CONFIRM)
    try:
        outcome = run_one(
            args.page,
            execute=args.execute,
            confirm=args.confirm,
            receipt_dir=args.receipt_dir,
            reconcile=args.reconcile,
        )
    except Exception as exc:
        # Never echo arbitrary provider errors (can contain credentials).
        print(f"{args.page}: STOP / no automatic retry ({type(exc).__name__})")
        raise SystemExit(2) from None
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
