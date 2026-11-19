"""Fail-closed, independent reader/source/rights acceptance for @lordchrist quote-v6.

This is an additional guard, never an authorization to publish. Unreviewed cards,
stale payloads, unverifiable GitHub reviews and unavailable GitHub APIs all block.
The workflow must run the gate before any pre-send state write and immediately
before the Telegram provider call. All requests here are GET-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.lordchrist_quote_v6_native_readonly import QuoteV6NativePost, QuoteV6NativeQueue

REVIEW_PATH = Path("content/telegram/lordchrist/quote-v6-semantic-review-v1.json")
ACTIVATION_PATH = Path("content/telegram/lordchrist/quote-v6-semantic-activation-v1.json")
RELEASE_ID = "lordchrist-quote-v6-20261106"
REPO = "FedorMilovanov/video-channel-manager"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
_GITHUB = f"https://api.github.com/repos/{REPO}"
GitHubGet = Callable[[str, str], Any]


class SemanticApprovalHold(ValueError):
    """Incomplete or unverifiable meaning/source/rights approval: do not send."""


def _get_json(url: str, token: str) -> Any:
    if not url.startswith(_GITHUB + "/"):
        raise SemanticApprovalHold("unexpected GitHub evidence endpoint")
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "LordChristSemanticPreflight/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:  # noqa: S310 — exact GitHub API prefix above
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise SemanticApprovalHold("independent GitHub review readback unavailable") from exc


def _load(root: Path, path: Path) -> dict[str, Any]:
    try:
        obj = json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SemanticApprovalHold(f"missing/invalid semantic evidence: {path}") from exc
    if not isinstance(obj, dict):
        raise SemanticApprovalHold(f"semantic evidence is not an object: {path}")
    return obj


def _blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw, usedforsecurity=False).hexdigest()


def require_semantic_approval(
    root: Path,
    queue: QuoteV6NativeQueue,
    post: QuoteV6NativePost,
    *,
    github_get: GitHubGet = _get_json,
) -> None:
    """Fail closed unless exact current payload has a truly independently approved PR.

    The two-file arrangement avoids an impossible self-referential PR head SHA:
    a reviewer approves the substantive review file in PR A, which is then
    referenced by exact head SHA and review ID in the separate activation file.
    GitHub readback proves the PR was merged to main and a distinct reviewer
    approved that exact commit and source blob. No local claimed 'approved_by'
    flag, passing tests, or user-requested prior release is sufficient.
    """
    register = _load(root, REVIEW_PATH)
    activation = _load(root, ACTIVATION_PATH)
    if (
        register.get("schema_name") != "lordchrist-quote-v6-semantic-review"
        or register.get("schema_version") != 1
        or register.get("release_id") != RELEASE_ID
        or register.get("queue_digest") != queue.digest
        or register.get("channel_username") != "@lordchrist"
        or activation.get("schema_name") != "lordchrist-quote-v6-semantic-activation"
        or activation.get("schema_version") != 1
        or activation.get("release_id") != RELEASE_ID
        or activation.get("queue_digest") != queue.digest
        or activation.get("channel_username") != "@lordchrist"
    ):
        raise SemanticApprovalHold("stale/mismatched semantic release identity")

    records = register.get("entries")
    grants = activation.get("entries")
    if not isinstance(records, list) or not isinstance(grants, list):
        raise SemanticApprovalHold("malformed semantic review/activation lists")
    if len({row.get("publication_id") for row in records if isinstance(row, dict)}) != len(records) or len(
        {row.get("publication_id") for row in grants if isinstance(row, dict)}
    ) != len(grants):
        raise SemanticApprovalHold("duplicate or non-object semantic review entries")
    row = next((x for x in records if x.get("publication_id") == post.publication_id), None)
    grant = next((x for x in grants if x.get("publication_id") == post.publication_id), None)
    if not isinstance(row, dict) or not isinstance(grant, dict):
        raise SemanticApprovalHold(f"no independent acceptance for {post.publication_id}")
    expected = {
        "publication_id": post.publication_id,
        "payload_sha256": post.payload_sha256,
        "source_russian_sha256": post.source.original_ru_quote_sha256,
        "original_english_span_sha256": post.source.original_english_span_sha256,
        "source_url": post.source.url,
    }
    if any(row.get(k) != value for k, value in expected.items()):
        raise SemanticApprovalHold("post/source SHA binding changed since acceptance")
    if (
        row.get("semantic_verdict") != "PASS_MEANING"
        or row.get("original_collation") != "independently_verified"
        or row.get("russian_translation_review") != "independently_verified"
        or row.get("rights_clearance") != "documented_cleared"
        or row.get("contiguous_source_span_verified") is not True
        or not all(
            isinstance(row.get(k), str) and len(row[k].strip()) >= 35
            for k in ("reader_thesis", "reasoning_link", "reader_misreading", "edition_and_rights_note")
        )
    ):
        raise SemanticApprovalHold(f"semantic/source/rights HOLD: {post.publication_id}")

    number = grant.get("review_pr_number")
    reviewed_head = grant.get("approved_pr_head_sha")
    reviewer = grant.get("reviewer_login")
    review_id = grant.get("github_approval_review_id")
    if (
        not isinstance(number, int)
        or number <= 0
        or not isinstance(reviewed_head, str)
        or not HEX40.fullmatch(reviewed_head)
        or not isinstance(reviewer, str)
        or not reviewer.strip()
        or not isinstance(review_id, int)
        or review_id <= 0
    ):
        raise SemanticApprovalHold("no exact independent GitHub PR approval receipt")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SemanticApprovalHold("GitHub read-only PR review token unavailable")

    pr = github_get(f"{_GITHUB}/pulls/{number}", token)
    if (
        not isinstance(pr, dict)
        or not pr.get("merged_at")
        or pr.get("base", {}).get("ref") != "main"
        or pr.get("head", {}).get("sha") != reviewed_head
        or not isinstance(pr.get("user", {}).get("login"), str)
        or pr["user"]["login"].casefold() == reviewer.casefold()
    ):
        raise SemanticApprovalHold("PR not merged to main or reviewer is author")

    # Review the exact repository file bytes, never an assertion in the grant.
    evidence = github_get(f"{_GITHUB}/contents/{REVIEW_PATH.as_posix()}?ref={reviewed_head}", token)
    if not isinstance(evidence, dict) or evidence.get("sha") != _blob_sha(root / REVIEW_PATH):
        raise SemanticApprovalHold("approved PR did not contain the exact reviewed bytes")

    reviews = github_get(f"{_GITHUB}/pulls/{number}/reviews?per_page=100", token)
    if not isinstance(reviews, list) or len(reviews) >= 100:
        raise SemanticApprovalHold("incomplete GitHub review pagination or malformed reply")
    own = [
        r
        for r in reviews
        if isinstance(r, dict)
        and isinstance(r.get("user"), dict)
        and str(r["user"].get("login", "")).casefold() == reviewer.casefold()
        and r.get("state") in {"APPROVED", "DISMISSED", "CHANGES_REQUESTED"}
    ]
    if (
        not own
        or own[-1].get("id") != review_id
        or own[-1].get("state") != "APPROVED"
        or own[-1].get("commit_id") != reviewed_head
        or not own[-1].get("submitted_at")
    ):
        raise SemanticApprovalHold("approved exact-head independent review absent/revoked")
