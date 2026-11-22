"""Read-only comparison for the consumed Charnock QC page-reissue operation.

The historical edits of the existing pages are complete. This entrypoint cannot
create or edit Telegraph pages, write to Telegram, or authorize a new release.
It compares the pinned page identity and title plus normalized visible text and
its top-level tags against the manifest-bound reviewed article. An optional
stricter comparison also checks the normalized complete node tree, including
media URLs, link attributes and inline markup. Neither comparison verifies
external media bytes, link availability, rights or exact rendered presentation.
A required mismatch is non-zero; even a match is not publication authority.
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
    sha_content,
)
from video_channel_manager.lordchrist_charnock_reschedule import (
    _normalized_telegraph_digest,
    _normalized_telegraph_node,
)
from video_channel_manager.lordchrist_telegraph_publisher import (
    build_telegraph_payload,
    load_telegraph_queue,
)

# Kept solely so a historical caller gets a clear retirement error, never authority.
CONFIRM = "REISSUE_EXISTING_CHARNOCK_PAGE_ONCE"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RELATIVE = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-qc-reissue-20261121.json")
MANIFEST_PATH = ROOT / MANIFEST_RELATIVE
QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
MAX_CONTENT_BYTES = 65_536
MAX_DIFFERENCES = 5
MAX_DIAGNOSTIC_PATH = 200
# Unknown provider-supplied keys can themselves contain arbitrary text.
DIAGNOSTIC_KEYS = frozenset({"tag", "attrs", "children", "src", "href", "id"})


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_name") != "video-channel-manager.lordchrist-charnock-qc-reissue-manifest"
        or data.get("schema_version") != 1
        or data.get("channel") != "@lordchrist"
        or data.get("author_name") != AUTHOR
        or data.get("author_url") != AUTHOR_URL
    ):
        raise UnsafeRevision("Invalid QC manifest identity")
    pages = data.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise UnsafeRevision("Manifest has no pages")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for key, page in pages.items():
        if not isinstance(key, str) or re.fullmatch(r"[0-9]{2}b?", key) is None or not isinstance(page, dict):
            raise UnsafeRevision("Malformed manifest page")
        for field in ("publication_id", "path", "url", "article_path", "article_git_blob_sha"):
            if not isinstance(page.get(field), str) or not page[field]:
                raise UnsafeRevision(f"{key}: manifest page has no {field}")
        path_value = page["path"]
        if re.fullmatch(r"[A-Za-z0-9_-]+", path_value) is None:
            raise UnsafeRevision(f"{key}: unsafe Telegraph path")
        if page["url"] != "https://telegra.ph/" + path_value:
            raise UnsafeRevision(f"{key}: url does not match path")
        article_path = page["article_path"]
        article = Path(article_path)
        if (
            re.fullmatch(r"[A-Za-z0-9_./-]+", article_path) is None
            or article.is_absolute()
            or ".." in article.parts
            or article.as_posix() != article_path
        ):
            raise UnsafeRevision(f"{key}: unsafe article path")
        if re.fullmatch(r"[0-9a-f]{40}", page["article_git_blob_sha"]) is None:
            raise UnsafeRevision(f"{key}: invalid reviewed article blob")
        if page["publication_id"] in seen_ids or path_value in seen_paths:
            raise UnsafeRevision(f"{key}: duplicate publication or page path")
        seen_ids.add(page["publication_id"])
        seen_paths.add(path_value)
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
    """Visible text and outer tag only; empty nodes and inline attributes are excluded."""
    if not isinstance(nodes, list):
        raise UnsafeRevision("Page content is not a list")
    result: list[tuple[str, str]] = []
    for node in nodes:
        if isinstance(node, str):
            tag = "#text"
        elif isinstance(node, dict) and isinstance(node.get("tag"), str) and node["tag"]:
            tag = node["tag"]
        else:
            raise UnsafeRevision("Malformed top-level Telegraph node")
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
        differences.append(f"visible node count {len(left)} -> {len(right)}")
    return differences


def normalized_tree_differences(before: Any, after: Any) -> list[str]:
    """Report bounded JSON paths without copying values or unknown keys."""
    left = _normalized_telegraph_node(before)
    right = _normalized_telegraph_node(after)
    differences: list[str] = []

    def extend(path: str, segment: str) -> str:
        full = path + segment
        return full if len(full) <= MAX_DIAGNOSTIC_PATH else full[: MAX_DIAGNOSTIC_PATH - 3] + "..."

    def visit(a: Any, b: Any, path: str) -> None:
        if len(differences) >= MAX_DIFFERENCES:
            return
        if type(a) is not type(b):
            differences.append(f"{path}: JSON types differ")
        elif isinstance(a, dict):
            for key in sorted(a.keys() | b.keys()):
                if len(differences) >= MAX_DIFFERENCES:
                    break
                label = repr(key) if key in DIAGNOSTIC_KEYS else "<other-key>"
                child = extend(path, f"[{label}]")
                if key not in a or key not in b:
                    differences.append(f"{child}: key missing on one side")
                else:
                    visit(a[key], b[key], child)
        elif isinstance(a, list):
            if len(a) != len(b):
                differences.append(f"{path}: array lengths differ")
            for index, (left_item, right_item) in enumerate(zip(a, b, strict=False)):
                if len(differences) >= MAX_DIFFERENCES:
                    break
                visit(left_item, right_item, extend(path, f"[{index}]"))
        elif json.dumps(a, ensure_ascii=False, allow_nan=False) != json.dumps(b, ensure_ascii=False, allow_nan=False):
            differences.append(f"{path}: value differs")

    visit(left, right, "content")
    return differences


def readable_edges(nodes: Any) -> dict[str, str]:
    """First and last visible text of a page body, for the operator's readback."""
    semantic = semantic_nodes(nodes)
    if not semantic:
        return {"first_text": "", "last_text": ""}
    return {
        "first_text": _safe_prefix(semantic[0][1], 160),
        "last_text": _safe_prefix(semantic[-1][1], 160),
    }


def annotation_summary(outcome: dict[str, Any]) -> dict[str, Any]:
    """Keep the essential readback visible even when artifact storage is inaccessible."""
    verification = outcome.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("Comparison result has no verification")
    fields = (
        "article",
        "publication_id",
        "article_git_blob_sha",
        "article_sha256",
        "path",
        "url",
        "media_base_revision",
        "old_sha256",
        "new_sha256",
        "normalized_tree_sha256_before",
        "normalized_tree_sha256_after",
        "normalized_tree_differences",
        "observed_at_utc",
        "run_id",
        "mode",
        "effect",
        "provider_write_attempted",
    )
    checks = (
        "mode",
        "read_only",
        "title_exact",
        "visible_text_equal",
        "provider_content_exact",
        "normalized_node_tree_equal",
        "normalized_node_tree_required",
    )
    return {
        **{field: outcome.get(field) for field in fields},
        "verification": {key: verification.get(key) for key in checks},
    }


def check_live_page(page: dict[str, Any], key: str, contract: dict[str, Any]) -> None:
    if page.get("path") != contract["path"] or page.get("url") != contract["url"]:
        raise UnsafeRevision(f"{key}: live path or URL differs from the pinned identity")
    if page.get("author_name") != AUTHOR or page.get("author_url") != AUTHOR_URL:
        raise UnsafeRevision(f"{key}: live author differs from the pinned author")
    if not isinstance(page.get("content"), list) or not page["content"]:
        raise UnsafeRevision(f"{key}: live content is not a non-empty list")


def _check_receipt_dir(receipt_dir: Path | None) -> Path:
    if receipt_dir is None:
        raise UnsafeRevision("A receipt directory is required")
    try:
        directory = receipt_dir.resolve(strict=True)
    except OSError as exc:
        raise UnsafeRevision("Receipt directory must already exist outside a git repository") from exc
    if not directory.is_dir() or any((part / ".git").exists() for part in (directory, *directory.parents)):
        raise UnsafeRevision("Receipt directory must already exist outside a git repository")
    return directory


def _receipt_path(receipt_dir: Path, key: str, digest: str) -> Path:
    run_id = os.environ.get("GITHUB_RUN_ID") or "local"
    if run_id != "local" and not run_id.isdecimal():
        raise UnsafeRevision("Invalid GitHub run id")
    return receipt_dir / f"charnock-qc-reissue-{key}-{digest[:16]}-reconciled-{run_id}.json"


def _write_receipt(path: Path, result: dict[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as receipt:
            receipt.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    except FileExistsError as exc:
        raise UnsafeRevision("Read-only receipt already exists; select a new receipt directory") from exc


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
    item = matches[0]
    if (
        item.article_path is None
        or item.article_path.as_posix() != contract["article_path"]
        or item.article_blob != contract["article_git_blob_sha"]
    ):
        raise UnsafeRevision(f"{key}: queue article path or blob differs from the reviewed QC manifest")
    payload = build_telegraph_payload(repo_root, item, media_base_url=media_base_url)
    if payload.content_utf8_bytes > MAX_CONTENT_BYTES:
        raise UnsafeRevision(
            f"{key}: payload is {payload.content_utf8_bytes} UTF-8 bytes; Telegraph ceiling is {MAX_CONTENT_BYTES}"
        )
    if not semantic_nodes(payload.nodes):
        raise UnsafeRevision(f"{key}: reviewed payload has no visible text")
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
    require_normalized_tree: bool = False,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Old flags and confirmations do not revive this completed one-shot editor.
    if execute:
        raise UnsafeRevision("The historical QC edit execution is retired; no provider access was attempted")
    pages = manifest if manifest is not None else load_manifest(repo_root / MANIFEST_RELATIVE)
    if not isinstance(key, str) or re.fullmatch(r"[0-9]{2}b?", key) is None or key not in pages:
        raise UnsafeRevision("Unknown page key")
    contract = pages[key]
    payload = reviewed_payload(key, repo_root=repo_root, media_base_url=media_base_url, manifest=pages)
    target_content = payload.nodes
    target_sha = sha_content(target_content)

    live = get_public_page(contract["path"])
    check_live_page(live, key, contract)
    live_content = live["content"]
    live_sha = sha_content(live_content)
    differences = describe_differences(live_content, target_content)
    live_tree_sha = _normalized_telegraph_digest(live_content)
    target_tree_sha = _normalized_telegraph_digest(target_content)
    tree_equal = live_tree_sha == target_tree_sha
    tree_differences = [] if tree_equal else normalized_tree_differences(live_content, target_content)
    title_exact = live.get("title") == payload.title
    if not title_exact or differences:
        effect = "VISIBLE_TEXT_MISMATCH"
    elif require_normalized_tree:
        effect = "NORMALIZED_NODE_TREE_MATCH" if tree_equal else "NORMALIZED_NODE_TREE_MISMATCH"
    else:
        effect = "VISIBLE_TEXT_MATCH"
    media_base = re.fullmatch(
        r"https://raw\.githubusercontent\.com/FedorMilovanov/video-channel-manager/([a-f0-9]{40})/?",
        media_base_url,
    )
    live_edges = readable_edges(live_content)
    target_edges = readable_edges(target_content)
    mode = "dry-run"
    if reconcile:
        mode = "structural-reconcile" if require_normalized_tree else "reconcile"
    result: dict[str, Any] = {
        "article": key,
        "publication_id": contract["publication_id"],
        "article_path": contract["article_path"],
        "article_git_blob_sha": contract["article_git_blob_sha"],
        "media_base_revision": media_base.group(1) if media_base else None,
        "path": contract["path"],
        "url": live.get("url"),
        "title_before": live.get("title"),
        "title_after": payload.title,
        "old_sha256": live_sha,
        "new_sha256": target_sha,
        "normalized_tree_sha256_before": live_tree_sha,
        "normalized_tree_sha256_after": target_tree_sha,
        "node_count_before": len(live_content),
        "node_count_after": len(target_content),
        "content_utf8_bytes_before": content_bytes(live_content),
        "content_utf8_bytes_after": content_bytes(target_content),
        "article_sha256": payload.article_sha256,
        "live_first_text": live_edges["first_text"],
        "live_last_text": live_edges["last_text"],
        "target_first_text": target_edges["first_text"],
        "target_last_text": target_edges["last_text"],
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "effect": effect,
        "provider_write_attempted": False,
        "differences": differences,
        "normalized_tree_differences": tree_differences,
        "verification": {
            "mode": "normalized_node_tree" if require_normalized_tree else "normalized_visible_text_and_top_level_tags",
            "read_only": True,
            "title_exact": title_exact,
            "visible_text_equal": not differences,
            "provider_content_exact": live_sha == target_sha,
            "normalized_node_tree_equal": tree_equal,
            "normalized_node_tree_required": require_normalized_tree,
            "normalized_node_tree_excludes": [
                "all h3/h4 heading ids and attrs emptied by removing id",
                "adjacent text fragments in content and children arrays",
            ],
            "visible_text_comparison_excludes": [
                "media sources",
                "link targets",
                "inline markup",
                "non-text nodes",
                "exact whitespace",
            ],
        },
    }
    if reconcile:
        directory = _check_receipt_dir(receipt_dir)
        _write_receipt(_receipt_path(directory, key, target_sha), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", required=True)
    parser.add_argument("--media-base-url", required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--require-normalized-tree", action="store_true")
    parser.add_argument("--receipt-dir", type=Path)
    # Accept old flags only to fail closed with a clear message and no GET.
    parser.add_argument("--execute", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--confirm", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        outcome = run_one(
            args.page,
            repo_root=args.repo_root,
            media_base_url=args.media_base_url,
            execute=args.execute,
            confirm=args.confirm,
            receipt_dir=args.receipt_dir,
            reconcile=args.reconcile,
            require_normalized_tree=args.require_normalized_tree,
        )
    except UnsafeRevision as exc:
        print(f"{args.page}: STOP: {exc}")
        raise SystemExit(2) from None
    except Exception as exc:
        # Do not echo arbitrary provider errors.
        print(f"{args.page}: STOP ({type(exc).__name__})")
        raise SystemExit(2) from None
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
    if outcome["effect"] in {"VISIBLE_TEXT_MISMATCH", "NORMALIZED_NODE_TREE_MISMATCH"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
