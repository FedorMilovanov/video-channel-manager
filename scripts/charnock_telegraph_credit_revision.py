"""Exact-payload, one-shot in-place correction of Charnock 11–13.

Default is read-only. The separate owner-dispatch workflow requires exact
reviewed before/after digests and an atomic durable claim before one editPage.
No new pages, media, queue changes, or Telegram sends.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.charnock_telegraph_qc_reissue import (
    MANIFEST_RELATIVE,
    QUEUE_PATH,
    ROOT,
    check_live_page,
    load_manifest,
    reviewed_payload,
)
from scripts.charnock_telegraph_surgical_revision import (
    UnsafeRevision,
    get_public_page,
    post_form,
    sha_content,
    verify_ownership,
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
    manifest = load_manifest(repo_root / MANIFEST_RELATIVE)
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
    for field in (
        "publication_id",
        "title",
        "author_name",
        "author_url",
        "cover_url",
        "cover_sha256",
        "inline_media_urls",
    ):
        if getattr(old, field) != getattr(new, field):
            raise UnsafeRevision("Correction changed page identity or media")
    return contract, old, new


def prepare_nodes(key: str, live: list[Any], old: list[Any], new: list[Any]) -> tuple[str, list[Any], list[int]]:
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


def build_plan(key: str) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    contract, old, new = load_pair(key)
    live = get_public_page(contract["path"])
    check_live_page(live, key, contract)
    if live.get("title") != old.title:
        raise UnsafeRevision("Live title differs")
    effect, proposed, changed = prepare_nodes(key, live["content"], old.nodes, new.nodes)
    result = {
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
    return result, live, proposed


def plan(key: str) -> dict[str, Any]:
    return build_plan(key)[0]


REPOSITORY = "FedorMilovanov/video-channel-manager"
STATE_BRANCH = "state/lordchrist-telegram"
CONFIRM = "APPLY_EXACT_CHARNOCK_TEXT_CORRECTION_ONCE"


def gh_json(endpoint: str, *, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["gh", "api", endpoint]
    kwargs: dict[str, Any] = {}
    if fields is not None:
        command.extend(["--method", "PUT", "--input", "-"])
        kwargs["input"] = json.dumps(fields, ensure_ascii=True)
    completed = subprocess.run(command, text=True, capture_output=True, check=True, **kwargs)
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise UnsafeRevision("Unexpected GitHub response")
    return result


def require_current_main() -> str:
    sha = os.environ.get("GITHUB_SHA", "")
    if (
        re.fullmatch(r"[a-f0-9]{40}", sha) is None
        or gh_json(f"repos/{REPOSITORY}/commits/main").get("sha") != sha
    ):
        raise UnsafeRevision("Current protected main changed; stop")
    return sha


def require_owner_dispatch(key: str) -> tuple[str, str, str]:
    expected_env = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": "FedorMilovanov",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    if any(os.environ.get(name) != value for name, value in expected_env.items()):
        raise UnsafeRevision("Owner-only exact-main first-attempt workflow required")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    inputs = event.get("inputs") or {}
    if inputs.get("page") != key or inputs.get("mode") != "apply" or inputs.get("confirm") != CONFIRM:
        raise UnsafeRevision("Exact page and owner confirmation required")
    before, after = inputs.get("expected_before"), inputs.get("expected_after")
    if not all(isinstance(d, str) and re.fullmatch(r"[a-f0-9]{64}", d) for d in (before, after)):
        raise UnsafeRevision("Exact dry-run before/after SHA-256 digests required")
    return require_current_main(), before, after


def persist_receipt(key: str, data: dict[str, Any], *, previous_blob: str | None = None) -> str:
    if key not in CANDIDATES:
        raise UnsafeRevision("Unexpected receipt key")
    path = f"content/telegram/lordchrist/telegraph-v1/charnock/editorial-correction-receipts/20261124-{key}.json"
    endpoint = f"repos/{REPOSITORY}/contents/{path}"
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fields = {
        "message": f"chore(lordchrist): Charnock {key} editorial correction {data['state']}",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": STATE_BRANCH,
    }
    if previous_blob is not None:
        fields["sha"] = previous_blob
    # With no sha this is create-only: an existing durable claim blocks replay.
    response = gh_json(endpoint, fields=fields)
    actual_blob = (response.get("content") or {}).get("sha")
    if actual_blob != blob_sha(raw):
        raise UnsafeRevision("Receipt write outcome uncertain; no retry")
    readback = gh_json(endpoint + "?ref=" + STATE_BRANCH)
    if (
        readback.get("sha") != actual_blob
        or readback.get("encoding") != "base64"
        or base64.b64decode(readback["content"]) != raw
    ):
        raise UnsafeRevision("Receipt readback differs; no retry")
    return actual_blob


def apply(key: str) -> dict[str, Any]:
    github_sha, expected_before, expected_after = require_owner_dispatch(key)
    result, live, proposed = build_plan(key)
    if result["effect"] == "ALREADY_CORRECT_NO_POST":
        return result
    if result["before_sha256"] != expected_before or result["after_sha256"] != expected_after:
        raise UnsafeRevision("Live snapshot or correction changed after owner review")
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
    if not token:
        raise UnsafeRevision("Telegraph owner credential unavailable")
    path = result["path"]
    verify_ownership(token, path)
    require_current_main()
    claim = {
        **result,
        "state": "claimed_may_exist",
        "github_sha": github_sha,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "claimed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    claim_blob = persist_receipt(key, claim)
    # The durable claim exists even if the process now crashes. No blind replay.
    try:
        require_current_main()
        recheck = get_public_page(path)
        for field in ("path", "url", "title", "author_name", "author_url"):
            if recheck.get(field) != live.get(field):
                raise UnsafeRevision("Page identity changed after claim")
        if sha_content(recheck.get("content")) != expected_before:
            raise UnsafeRevision("Page content changed after claim")
        fields = {
            "access_token": token,
            "title": live["title"],
            "author_name": live["author_name"],
            "author_url": live["author_url"],
            "content": json.dumps(proposed, ensure_ascii=False, separators=(",", ":")),
            "return_content": "true",
        }
        edited = post_form("editPage/" + path, fields)
        if edited.get("path") != path:
            raise UnsafeRevision("Unexpected editPage result")
        check = get_public_page(path)
        for field in ("path", "url", "title", "author_name", "author_url", "image_url"):
            if check.get(field) != live.get(field):
                raise UnsafeRevision("Post-edit metadata differs")
        if not same_tree(check.get("content"), proposed):
            raise UnsafeRevision("Post-edit normalized tree differs")
        if check["content"][0] != live["content"][0]:
            raise UnsafeRevision("Post-edit cover node differs")
        verified = {
            **claim,
            "effect": "VERIFIED_IN_PLACE",
            "provider_write_attempted": True,
            "state": "verified",
            "provider_readback_sha256": sha_content(check["content"]),
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        persist_receipt(key, verified, previous_blob=claim_blob)
        return verified
    except Exception:
        # A claim is durable; do not attempt the provider operation again.
        raise UnsafeRevision("Durable claim exists; reconcile the existing page and receipt, never retry") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(CANDIDATES), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply(args.page) if args.apply else plan(args.page)
    except UnsafeRevision as exc:
        raise SystemExit(f"STOP: {exc}") from None
    except Exception as exc:
        raise SystemExit(f"STOP: {type(exc).__name__}") from None
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
