"""One-shot owner-verified editPage for the approved Charnock history-01 polish.

No page or post creation; no Telegram writes. A durable claim in the existing
state ledger must be pushed before a single external edit. Do not rerun after
an ambiguous provider outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.lordchrist_charnock_reschedule import _proof_page
from video_channel_manager.lordchrist_telegraph_publisher import (
    DEFAULT_QUEUE_PATH,
    HttpxLiveTransport,
    _find_item,
    build_telegraph_payload,
    load_telegraph_queue,
    publish_telegraph_page,
)

PUB = "lordchrist-telegraph-charnock-history-01"
PAGE_PATH = (
    "Um-kotoryj-ne-toropilsya-Stiven-CHarnok-i-glubina-mysli-v-ehpohu-bystryh-otvetov--ispravlennoe-izdanie-11-05"
)
PAGE_URL = "https://telegra.ph/" + PAGE_PATH
TITLE = (
    "Как познание Бога, о Котором писал Чарнок, меняет веру, поклонение и повседневную жизнь христианина в XXI веке?"
)
PREVIOUS_ARTICLE_BLOB = "e7767a1f265f28abb3c9917ac9815b1a806858a6"
COVER_BLOB = "a5c455e9200ca4060c1bbb5aa3130d2fcf390f82"
LEDGER_KEY = "history01_editorial_polish_20261115"


def now() -> str:
    return datetime.now(UTC).isoformat()


def api_post(url: str, form: dict[str, str]) -> dict[str, Any]:
    try:
        response = httpx.post(url, data=form, timeout=25, follow_redirects=False)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Telegraph authenticated read failed") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("Telegraph authenticated read rejected") from None
    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Telegraph authenticated read lacks result")
    return result


def verify_owner(token: str) -> None:
    if not token:
        raise RuntimeError("The existing Telegraph author token is required")
    page = api_post(
        "https://api.telegra.ph/getPage/" + PAGE_PATH,
        {"access_token": token, "return_content": "false"},
    )
    if page.get("path") != PAGE_PATH or page.get("url") != PAGE_URL or page.get("title") != TITLE:
        raise RuntimeError("Existing Telegraph page identity changed")
    if page.get("can_edit") is True:
        return
    if page.get("can_edit") is False:
        raise RuntimeError("The retained author token cannot edit this page")
    offset = 0
    while offset < 4000:
        result = api_post(
            "https://api.telegra.ph/getPageList",
            {"access_token": token, "offset": str(offset), "limit": "200"},
        )
        pages = result.get("pages")
        if not isinstance(pages, list):
            raise RuntimeError("Telegraph author page list malformed")
        if any(isinstance(p, dict) and p.get("path") == PAGE_PATH for p in pages):
            return
        offset += len(pages)
        if len(pages) < 200:
            break
    raise RuntimeError("Page ownership not established for the retained token")


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def load_target(root: Path, ledger_path: Path, media_base_url: str) -> tuple[dict[str, Any], dict[str, Any], Any]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"].get(PUB)
    if not isinstance(entry, dict):
        raise RuntimeError("Existing published history-01 ledger entry is absent")
    prior = entry.get("history01_inplace_revision")
    if (
        not isinstance(prior, dict)
        or prior.get("state") != "verified"
        or prior.get("page_url") != PAGE_URL
        or prior.get("message_id") != 1585
        or prior.get("page_provider_effect") != "verified"
        or prior.get("telegram_provider_effect") != "verified"
    ):
        raise RuntimeError("Last verified history-01 release receipt differs")
    q = load_telegraph_queue(root / DEFAULT_QUEUE_PATH, root)
    item = _find_item(q, PUB)
    if not item.is_ready or item.article_blob == PREVIOUS_ARTICLE_BLOB:
        raise RuntimeError("New approved article content is unavailable")
    if item.cover_blob != COVER_BLOB:
        raise RuntimeError("Approved cover changed unexpectedly")
    if item.article_path is None or git_blob((root / item.article_path).read_bytes()) != item.article_blob:
        raise RuntimeError("The queued new article does not match the Git blob")
    manifest = json.loads(
        (root / "docs/audits/2026-11-04-charnock-publication-link-replacement-map.json").read_text(encoding="utf-8")
    )
    (target,) = [x for x in manifest["targets"] if x["publication_id"] == PUB]
    if (
        target.get("editorial_revision_status") != "staged_not_yet_published"
        or target.get("corrected_document_git_blob_sha") != item.article_blob
        or target.get("prior_verified_document_git_blob_sha") != PREVIOUS_ARTICLE_BLOB
    ):
        raise RuntimeError("Editorial release map does not match the revised article")
    payload = build_telegraph_payload(root, item, media_base_url=media_base_url)
    if payload.title != TITLE:
        raise RuntimeError("The approved article title changed")
    return ledger, entry, payload


def execute(stage: str, root: Path, ledger_path: Path, media_base_url: str) -> dict[str, Any]:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    github_sha = os.environ.get("GITHUB_SHA", "")
    if (
        os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY") != "FedorMilovanov/video-channel-manager"
        or os.environ.get("GITHUB_ACTOR") != "FedorMilovanov"
        or not run_id.isdigit()
        or run_attempt != "1"
        or len(github_sha) != 40
    ):
        raise RuntimeError("Exact approved manual one-shot context required")
    ledger, entry, payload = load_target(root, ledger_path, media_base_url)
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
    if stage == "prepare":
        if LEDGER_KEY in entry:
            raise RuntimeError("One-shot editorial revision already claimed; no replay")
        verify_owner(token)
        entry[LEDGER_KEY] = {
            "state": "page_claimed",
            "run_id": run_id,
            "run_attempt": 1,
            "github_sha": github_sha,
            "article_sha256": payload.article_sha256,
            "cover_sha256": payload.cover_sha256,
            "url": PAGE_URL,
            "message_id": 1585,
            "provider_effect": "unknown_until_reconciled",
            "claimed_at_utc": now(),
        }
        ledger_path.write_bytes((json.dumps(ledger, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return {"state": "page_claimed", "url": PAGE_URL}

    if stage == "apply":
        claim = entry.get(LEDGER_KEY)
        if not isinstance(claim, dict) or claim.get("state") != "page_claimed":
            raise RuntimeError("No durable one-shot page claim")
        if (
            claim.get("run_id") != run_id
            or claim.get("run_attempt") != 1
            or claim.get("github_sha") != github_sha
            or claim.get("article_sha256") != payload.article_sha256
            or claim.get("cover_sha256") != payload.cover_sha256
            or claim.get("url") != PAGE_URL
        ):
            raise RuntimeError("A different run or article owns the page claim")
        verify_owner(token)
        transport = HttpxLiveTransport()
        url, path = publish_telegraph_page(
            transport,
            payload,
            access_token=token,
            existing_path=PAGE_PATH,
            allow_split=False,
        )
        if (url, path) != (PAGE_URL, PAGE_PATH):
            raise RuntimeError("Telegraph editPage returned a different page")
        _proof_page({"verified_telegraph_url": PAGE_URL}, payload)
        claim.update(
            state="verified",
            provider_effect="verified",
            verified_at_utc=now(),
        )
        ledger_path.write_bytes((json.dumps(ledger, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return {"state": "verified", "url": PAGE_URL}

    raise RuntimeError("Unknown stage")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "apply"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--media-base-url", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.stage, args.repo_root, args.ledger, args.media_base_url), ensure_ascii=False))


if __name__ == "__main__":
    main()
