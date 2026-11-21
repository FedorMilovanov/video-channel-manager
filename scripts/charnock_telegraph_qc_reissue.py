"""Fail-closed, one-page-at-a-time QC reissues of existing Charnock Telegraph pages.

A reissue replaces the whole body of one already published page with the payload
built from the reviewed article JSON: same Telegraph path, same author identity,
new title taken from the reviewed article metadata.  It never creates a page,
never touches Telegram, never changes the public URL, and never retries an
ambiguous ``editPage``.

The default action is a public GET plus a dry-run plan.  Execution additionally
requires the original account token, ``REISSUE_EXISTING_CHARNOCK_PAGE_ONCE`` and
a receipt directory outside any git repository.  The manifest pins, for every
page, the publication id, the canonical live path, the reviewed article blob and
the previous public identity, so an operator sees the exact transition.
"""

from __future__ import annotations

import argparse
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
from video_channel_manager.lordchrist_telegraph_publisher import (
    build_telegraph_payload,
    load_telegraph_queue,
)

CONFIRM = "REISSUE_EXISTING_CHARNOCK_PAGE_ONCE"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/charnock-qc-reissue-20261121.json"
QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
MAX_CONTENT_BYTES = 65_536
MAX_DIFFERENCES = 5


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise UnsafeRevision("Manifest has no pages")
    for key, page in pages.items():
        if not isinstance(page, dict):
            raise UnsafeRevision(f"{key}: malformed manifest page")
        for field in ("publication_id", "path", "url", "article_path"):
            if not isinstance(page.get(field), str) or not page[field]:
                raise UnsafeRevision(f"{key}: manifest page has no {field}")
        path_value = page["path"]
        if path_value.startswith("/") or ".." in path_value or " " in path_value:
            raise UnsafeRevision(f"{key}: unsafe Telegraph path")
        if page["url"] != "https://telegra.ph/" + path_value:
            raise UnsafeRevision(f"{key}: url does not match path")
    return pages


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


def content_bytes(nodes: Any) -> int:
    return len(json.dumps(nodes, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def semantic_nodes(nodes: Any) -> list[tuple[str, str]]:
    """Tag plus visible text per node, ignoring empty line breaks and image attrs."""
    result: list[tuple[str, str]] = []
    if not isinstance(nodes, list):
        return result
    for node in nodes:
        if not isinstance(node, dict):
            continue
        tag = str(node.get("tag") or "")
        text = normalized(flatten(node))
        if tag == "br" or not text:
            continue
        result.append((tag, text))
    return result


def _safe_prefix(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def describe_differences(before: Any, after: Any) -> list[str]:
    left = semantic_nodes(before)
    right = semantic_nodes(after)
    differences: list[str] = []
    for index, (left_node, right_node) in enumerate(zip(left, right, strict=False)):
        if left_node != right_node:
            differences.append(
                f"node {index}: {left_node[0]} {_safe_prefix(left_node[1])!r} -> "
                f"{right_node[0]} {_safe_prefix(right_node[1])!r}"
            )
        if len(differences) >= MAX_DIFFERENCES:
            return differences
    if len(left) != len(right):
        differences.append(f"node count {len(left)} -> {len(right)}")
    return differences


def check_live_page(page: dict[str, Any], key: str, contract: dict[str, Any]) -> None:
    if page.get("path") != contract["path"]:
        raise UnsafeRevision(f"{key}: live path differs from the pinned path")
    if page.get("author_name") != AUTHOR or page.get("author_url") != AUTHOR_URL:
        raise UnsafeRevision(f"{key}: live author differs from the pinned author")
    if not isinstance(page.get("content"), list) or not page["content"]:
        raise UnsafeRevision(f"{key}: live content is not a non-empty list")


def _check_receipt_dir(receipt_dir: Path | None) -> Path:
    if receipt_dir is None:
        raise UnsafeRevision("A receipt directory is required")
    if not receipt_dir.is_dir() or any((part / ".git").exists() for part in (receipt_dir, *receipt_dir.parents)):
        raise UnsafeRevision("Receipt directory must already exist outside a git repository")
    return receipt_dir


def _receipt_path(receipt_dir: Path, key: str, suffix: str, digest: str) -> Path:
    run_id = os.environ.get("GITHUB_RUN_ID") or "local"
    return receipt_dir / f"charnock-qc-reissue-{key}-{digest[:16]}{suffix}-{run_id}.json"


def _write_receipt(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def reviewed_payload(
    key: str,
    *,
    repo_root: Path,
    media_base_url: str,
    manifest: dict[str, Any],
) -> Any:
    contract = manifest[key]
    queue = repo_root / QUEUE_PATH
    items = load_telegraph_queue(queue, repo_root)
    matches = [item for item in items if item.publication_id == contract["publication_id"]]
    if len(matches) != 1:
        raise UnsafeRevision(f"{key}: publication id is not unique in the queue")
    payload = build_telegraph_payload(repo_root, matches[0], media_base_url=media_base_url)
    if payload.content_utf8_bytes > MAX_CONTENT_BYTES:
        raise UnsafeRevision(
            f"{key}: payload is {payload.content_utf8_bytes} UTF-8 bytes; Telegraph ceiling is {MAX_CONTENT_BYTES}"
        )
    return payload


def run_one(
    key: str,
    *,
    repo_root: Path = ROOT,
    media_base_url: str,
    execute: bool = False,
    confirm: str | None = None,
    receipt_dir: Path | None = None,
    reconcile: bool = False,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pages = manifest if manifest is not None else load_manifest()
    if key not in pages:
        raise UnsafeRevision("Unknown page key")
    if execute and reconcile:
        raise UnsafeRevision("Execution and reconciliation are mutually exclusive")
    contract = pages[key]
    payload = reviewed_payload(key, repo_root=repo_root, media_base_url=media_base_url, manifest=pages)
    target_content = payload.nodes
    target_sha = sha_content(target_content)
    target_bytes = content_bytes(target_content)

    live = get_public_page(contract["path"])
    check_live_page(live, key, contract)
    live_content = live["content"]
    live_sha = sha_content(live_content)
    live_bytes = content_bytes(live_content)
    differences = describe_differences(live_content, target_content)

    result: dict[str, Any] = {
        "article": key,
        "publication_id": contract["publication_id"],
        "path": contract["path"],
        "url": live.get("url"),
        "title_before": live.get("title"),
        "title_after": payload.title,
        "old_sha256": live_sha,
        "new_sha256": target_sha,
        "node_count_before": len(live_content),
        "node_count_after": len(target_content),
        "content_utf8_bytes_before": live_bytes,
        "content_utf8_bytes_after": target_bytes,
        "article_sha256": payload.article_sha256,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }

    if reconcile:
        directory = _check_receipt_dir(receipt_dir)
        if not differences:
            result["effect"] = "VERIFIED_REISSUE_RECONCILED"
            result["verification"] = {"mode": "reconciled", "read_only": True}
        else:
            result["effect"] = "RECONCILE_MISMATCH"
            result["differences"] = differences
        result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_receipt(_receipt_path(directory, key, "-reconciled", target_sha), result)
        return result

    if not differences and live.get("title") == payload.title:
        raise UnsafeRevision(f"{key}: the reviewed reissue is already live; run --reconcile")

    result["effect"] = "DRY_RUN_NO_POST"
    if not execute:
        result["planned_differences"] = differences
        return result

    if confirm != CONFIRM:
        raise UnsafeRevision("Execution requires explicit confirmation")
    directory = _check_receipt_dir(receipt_dir)
    receipt_file = _receipt_path(directory, key, "", target_sha)
    if receipt_file.exists():
        raise UnsafeRevision("Receipt already exists; reconcile first, no POST")
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
    if not token:
        raise UnsafeRevision("Existing Telegraph access token unavailable; no provider edit attempted")
    verify_ownership(token, contract["path"])
    # Second public GET: any intervening edit invalidates the prepared payload.
    recheck = get_public_page(contract["path"])
    check_live_page(recheck, key, contract)
    if sha_content(recheck["content"]) != live_sha:
        raise UnsafeRevision("Live snapshot changed before edit; no POST")
    fields = {
        "access_token": token,
        "title": payload.title,
        "content": payload.compact_content_json,
        "author_name": AUTHOR,
        "author_url": AUTHOR_URL,
        "return_content": "true",
    }
    # One irreversible POST only. Any timeout/error is UNCERTAIN; never retry.
    try:
        edited = post_form("editPage/" + contract["path"], fields)
    except Exception as exc:
        result["effect"] = "UNCERTAIN"
        result["uncertainty"] = f"POST_{type(exc).__name__}"
        _write_receipt(_receipt_path(directory, key, "-uncertain", target_sha), result)
        raise
    if edited.get("path") != contract["path"]:
        result["effect"] = "UNCERTAIN"
        result["uncertainty"] = "editPage changed path"
        _write_receipt(_receipt_path(directory, key, "-uncertain", target_sha), result)
        raise UnsafeRevision("Provider effect UNCERTAIN: editPage changed path; do not retry")
    check = get_public_page(contract["path"])
    if check.get("path") != contract["path"] or check.get("url") != live.get("url"):
        result["effect"] = "UNCERTAIN"
        result["uncertainty"] = "public identity drift"
        result["live_sha256"] = sha_content(check.get("content"))
        _write_receipt(_receipt_path(directory, key, "-uncertain", target_sha), result)
        raise UnsafeRevision("Provider effect UNCERTAIN: public identity drift; do not retry")
    live_sha_after = sha_content(check.get("content"))
    result["live_sha256"] = live_sha_after
    result["live_title"] = check.get("title")
    result["node_count_live"] = len(check.get("content") or [])
    if check.get("content") == target_content:
        result["effect"] = "VERIFIED_REISSUE"
        result["verification"] = {"mode": "exact", "provider_content_exact": True}
    else:
        remaining = describe_differences(check.get("content"), target_content)
        if remaining or check.get("title") != payload.title:
            result["effect"] = "UNCERTAIN"
            result["uncertainty"] = "readback differs from the reviewed payload"
            result["differences"] = remaining
            _write_receipt(_receipt_path(directory, key, "-uncertain", target_sha), result)
            raise UnsafeRevision("Provider effect UNCERTAIN: readback differs; do not retry")
        result["effect"] = "VERIFIED_REISSUE"
        result["verification"] = {
            "mode": "semantic",
            "provider_content_exact": False,
            "node_count_after": len(check.get("content") or []),
            "content_utf8_bytes_after": content_bytes(check.get("content")),
        }
    result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_receipt(_receipt_path(directory, key, "", target_sha), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(load_manifest()), required=True)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
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
            repo_root=args.repo_root,
            media_base_url=args.media_base_url,
            execute=args.execute,
            confirm=args.confirm,
            receipt_dir=args.receipt_dir,
            reconcile=args.reconcile,
        )
    except UnsafeRevision as exc:
        # Local guard messages are written here and never carry credentials.
        print(f"{args.page}: STOP / no automatic retry: {exc}")
        raise SystemExit(2) from None
    except Exception as exc:
        # Never echo arbitrary provider errors (can contain credentials).
        print(f"{args.page}: STOP / no automatic retry ({type(exc).__name__})")
        raise SystemExit(2) from None
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
