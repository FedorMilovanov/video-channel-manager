"""Read-only, exact-payload plan for owner-accepted Charnock 11–13 corrections.

No provider mutations, tokens, queue changes, or Telegram authority. Preserve all
existing media and unrelated live nodes. A later writer must persist a durable
intent bound to this plan before a single editPage call and verify its readback.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.charnock_telegraph_qc_reissue import (
    QUEUE_PATH,
    ROOT,
    check_live_page,
    load_manifest,
    reviewed_payload,
)
from scripts.charnock_telegraph_surgical_revision import (
    UnsafeRevision,
    get_public_page,
    sha_content,
)
from video_channel_manager.lordchrist_charnock_reschedule import _normalized_telegraph_pair_digests
from video_channel_manager.lordchrist_telegraph_publisher import (
    build_telegraph_payload,
    load_telegraph_queue,
)

MEDIA_BASE = "https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/c1bafa972e91d536fc56d86e53b4ce6f3502f37d"
CANDIDATES = {
    "11": (
        "content/research/charnock-q10-translation-review-20261123/charnock-11-q10-proposed.json",
        "ba2114af09e5d46d4abc8de56003aca829326377",
    ),
    "12": (
        "content/research/charnock-source-credit-candidates-20261123/charnock-12.json",
        "5e22ddf59873b818e77f0ddb21ec6d701b55793d",
    ),
    "13": (
        "content/research/charnock-source-credit-candidates-20261123/charnock-13.json",
        "cd6b6771c0299660c84fc95cef1caf5d8c0424d8",
    ),
}


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def same_tree(live: Any, reviewed: Any) -> bool:
    left, right = _normalized_telegraph_pair_digests(live, reviewed)
    return left == right


def load_pair(key: str, repo_root: Path = ROOT) -> tuple[dict[str, Any], Any, Any]:
    if key not in CANDIDATES:
        raise UnsafeRevision("Only articles 11–13 are in this correction")
    manifest = load_manifest()
    contract = manifest[key]
    old = reviewed_payload(key, repo_root=repo_root, media_base_url=MEDIA_BASE, manifest=manifest)
    queue = load_telegraph_queue(repo_root / QUEUE_PATH, repo_root)
    item = next(item for item in queue if item.publication_id == contract["publication_id"])
    path, expected = CANDIDATES[key]
    candidate_path = Path(path)
    if blob_sha((repo_root / candidate_path).read_bytes()) != expected:
        raise UnsafeRevision("Accepted correction source bytes changed")
    new = build_telegraph_payload(
        repo_root,
        replace(item, article_path=candidate_path, article_blob=expected),
        media_base_url=MEDIA_BASE,
    )
    for field in ("publication_id", "title", "author_name", "author_url", "cover_url", "cover_sha256",
                  "inline_media_urls"):
        if getattr(old, field) != getattr(new, field):
            raise UnsafeRevision("Correction changed page identity or media")
    return contract, old, new


def prepare_nodes(
    key: str, live: list[Any], old: list[Any], new: list[Any]
) -> tuple[str, list[Any], list[int]]:
    """Return a raw-live-preserving surgical patch; fail closed on any drift."""
    if key not in CANDIDATES or len(new) != len(old) + 1:
        raise UnsafeRevision("Unexpected candidate node count")
    footer = new[-1]
    if (
        not isinstance(footer, dict)
        or footer.get("tag") != "p"
        or "© Цитаты Чарнока" not in json.dumps(footer, ensure_ascii=False)
        or "gutenberg.org/ebooks/53527" not in json.dumps(footer, ensure_ascii=False)
    ):
        raise UnsafeRevision("Expected bibliographic footer missing")
    changed = [i for i, (a, b) in enumerate(zip(old, new[:-1], strict=True)) if a != b]
    if key == "11":
        if len(changed) != 1:
            raise UnsafeRevision("Article 11 must change exactly one quotation")
        index = changed[0]
        before, after = old[index], new[index]
        if (
            not isinstance(before, dict)
            or not isinstance(after, dict)
            or before.get("tag") != "blockquote"
            or after.get("tag") != "blockquote"
            or "странное расстройство у некоторых имений" not in json.dumps(before, ensure_ascii=False)
            or "неожиданные неудачи в имущественных делах" not in json.dumps(after, ensure_ascii=False)
        ):
            raise UnsafeRevision("Article 11 quote anchor differs")
    elif changed:
        raise UnsafeRevision("Articles 12–13 must only append the footer")
    if same_tree(live, new):
        return "ALREADY_CORRECT_NO_POST", copy.deepcopy(live), []
    if not same_tree(live, old) or len(live) != len(old):
        raise UnsafeRevision("Live page differs from pinned previous edition; no edit plan")
    proposed = copy.deepcopy(live)
    for index in changed:
        proposed[index] = copy.deepcopy(new[index])
    proposed.append(copy.deepcopy(footer))
    if not same_tree(proposed, new):
        raise UnsafeRevision("Patched live nodes do not match the accepted candidate")
    if len(json.dumps(proposed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > 64000:
        raise UnsafeRevision("Conservative content byte limit exceeded")
    return "READY_FOR_REVIEW_NO_POST", proposed, [*changed, len(old)]


def plan(key: str) -> dict[str, Any]:
    contract, old, new = load_pair(key)
    live = get_public_page(contract["path"])
    check_live_page(live, key, contract)
    if live.get("title") != old.title:
        raise UnsafeRevision("Live title differs")
    effect, proposed, changed = prepare_nodes(key, live["content"], old.nodes, new.nodes)
    return {
        "article": key,
        "publication_id": contract["publication_id"],
        "path": contract["path"],
        "url": contract["url"],
        "effect": effect,
        "old_article_blob": contract["article_git_blob_sha"],
        "accepted_candidate_blob": CANDIDATES[key][1],
        "cover_sha256": old.cover_sha256,
        "media_base_url": MEDIA_BASE,
        "before_sha256": sha_content(live["content"]),
        "after_sha256": sha_content(proposed),
        "changed_node_indices": changed,
        "before_count": len(live["content"]),
        "after_count": len(proposed),
        "provider_write_attempted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(CANDIDATES), required=True)
    args = parser.parse_args()
    try:
        result = plan(args.page)
    except UnsafeRevision as exc:
        raise SystemExit(f"STOP: {exc}") from None
    except Exception as exc:
        raise SystemExit(f"STOP: {type(exc).__name__}") from None
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
