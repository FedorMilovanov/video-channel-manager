"""Bounded, account-scoped Jude Telegraph title inspection; never a release gate.

The retained account credential is sent only to the two read-like Telegraph
methods below. The report contains counts, not account pages, URLs or tokens.
Two matching complete listings detect many concurrent changes but are not an
atomic snapshot and cannot exclude another account, writer or changed title.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx

from video_channel_manager.platforms.http import HttpClientOwner
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

PUBLICATION_ID = "lordchrist-telegraph-jude-1-5-20261105"
EXPECTED_TITLE = "Один Господь, два чтения: «Иисус» или «Господь» в Иуд. 1:5"
ARTICLE_BLOB = "dd15da234a74eb474963d275c6a9bccfcadb9985"
COVER_BLOB = "909106bc78e05e323815e96fdf7e01dc7dd22eff"
QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
ARTICLE_PATH = Path("content/telegram/lordchrist/telegraph-v1/jude/lordchrist-telegraph-jude-1-5-20261105.json")
COVER_PATH = Path("content/telegram/lordchrist/telegraph-v1/media/lordchrist-telegraph-jude-1-5-20261105-cover.jpg")
PROFILE_PATH = Path("content/telegram/channels/lordchrist-rich.json")
BINDING_PATH = Path("content/telegram/channels/lordchrist-rich-target-binding.json")
ANCHOR_PUBLICATION_ID = "lordchrist-telegraph-peasants-1525-20261115"
ANCHOR_PATH = "1525-pochemu-nemeckie-krestyane-trebovali-prava-vybirat-propovednika-11-15"
PAGE_LIMIT = 200
MAX_ACCOUNT_PAGES = 4000
_MAX_RESPONSE_BYTES = 2_000_000
_API_METHODS = {
    "getAccountInfo": "https://api.telegra.ph/getAccountInfo",
    "getPageList": "https://api.telegra.ph/getPageList",
}


class ProbeError(RuntimeError):
    """A safe diagnostic, without provider responses or authentication data."""


class _ReadClient(HttpClientOwner):
    """One short-lived or borrowed client for the bounded, non-retrying scan."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._initialize_http_client(client, timeout=20.0, follow_redirects=False, trust_env=False)

    @property
    def client(self) -> httpx.Client:
        return self._http_client


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ProbeError("Required local JSON is missing or malformed") from None
    if not isinstance(value, dict):
        raise ProbeError("Required local JSON is not an object")
    return value


def _blob(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        raise ProbeError("Required bound bytes are unavailable") from None
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _validate_target(root: Path) -> None:
    """Check exact queue, immutable article/cover bytes and canonical target."""
    queue = _object(root / QUEUE_PATH)
    items = queue.get("items")
    if not isinstance(items, list):
        raise ProbeError("Telegraph queue is malformed")
    matches = [item for item in items if isinstance(item, dict) and item.get("publication_id") == PUBLICATION_ID]
    if len(matches) != 1:
        raise ProbeError("Exact Jude queue identity is missing or ambiguous")
    item = matches[0]
    article, cover = item.get("article"), item.get("cover")
    if (
        item.get("status") != "ready"
        or item.get("is_canary") is not False
        or not isinstance(article, dict)
        or article.get("path") != ARTICLE_PATH.as_posix()
        or article.get("git_blob_sha") != ARTICLE_BLOB
        or not isinstance(cover, dict)
        or cover.get("path") != COVER_PATH.as_posix()
        or cover.get("git_blob_sha") != COVER_BLOB
        or _blob(root / ARTICLE_PATH) != ARTICLE_BLOB
        or _blob(root / COVER_PATH) != COVER_BLOB
    ):
        raise ProbeError("Exact Jude article or cover binding differs")
    document = _object(root / ARTICLE_PATH)
    metadata = document.get("metadata")
    if (
        document.get("document_id") != PUBLICATION_ID
        or document.get("project_key") != "lord-god-strength"
        or not isinstance(metadata, dict)
        or metadata.get("title") != EXPECTED_TITLE
    ):
        raise ProbeError("Exact Jude article identity or title differs")

    try:
        profile = load_channel_profile(root / PROFILE_PATH)
        binding = load_target_binding(root / BINDING_PATH, profile=profile)
    except ValueError:
        raise ProbeError("Canonical Lordchrist target binding differs") from None
    if (
        profile.project_key != "lord-god-strength"
        or profile.channel_username != "@lordchrist"
        or binding.chat_id != -1001295216957
        or binding.chat_username != "lordchrist"
        or binding.bot_id != 8716602202
        or binding.bot_username != "preaching_mp3_bot"
    ):
        raise ProbeError("Canonical Lordchrist target binding differs")


def _validate_ledger(ledger: dict[str, Any]) -> str:
    entries = ledger.get("entries")
    if (
        ledger.get("schema_name") != "video-channel-manager.lordchrist-telegraph-ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("project_key") != "lord-god-strength"
        or not isinstance(entries, dict)
        or any(not isinstance(key, str) or not isinstance(value, dict) for key, value in entries.items())
    ):
        raise ProbeError("Durable Telegraph ledger identity or schema differs")
    anchor = entries.get(ANCHOR_PUBLICATION_ID)
    expected = {
        "publication_id": ANCHOR_PUBLICATION_ID,
        "state": "published",
        "provider_effect": "verified",
        "telegram_provider_effect": "verified",
        "telegram_chat_id": -1001295216957,
        "telegram_message_id": 1619,
        "telegraph_path": ANCHOR_PATH,
        "telegraph_url": "https://telegra.ph/" + ANCHOR_PATH,
    }
    if not isinstance(anchor, dict) or any(anchor.get(key) != value for key, value in expected.items()):
        raise ProbeError("Known verified channel/account anchor does not match the ledger")
    return "entry_present_reconcile" if PUBLICATION_ID in entries else "no_entry"


def _read(client: httpx.Client, token: str, method: str, fields: dict[str, str]) -> dict[str, Any]:
    """Use an allowlist of read-only methods; never reveal errors or follow redirects."""
    url = _API_METHODS.get(method)
    if url is None:
        raise ProbeError("Unsupported provider read method")
    try:
        response = client.post(url, data={**fields, "access_token": token}, follow_redirects=False)
        response.raise_for_status()
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise ProbeError("Provider read response exceeded its size limit")
        document = response.json()
    except (httpx.HTTPError, ValueError):
        raise ProbeError("Provider account read failed; no result can be inferred") from None
    if not isinstance(document, dict) or document.get("ok") is not True or not isinstance(document.get("result"), dict):
        raise ProbeError("Provider account read was rejected or malformed")
    return cast(dict[str, Any], document["result"])


def _page_count(client: httpx.Client, token: str) -> int:
    result = _read(client, token, "getAccountInfo", {"fields": json.dumps(["page_count"])})
    count = result.get("page_count")
    if type(count) is not int or not 0 <= count <= MAX_ACCOUNT_PAGES:
        raise ProbeError("Account page count is missing, malformed or outside the scan bound")
    return count


def _snapshot(client: httpx.Client, token: str, total: int) -> dict[str, str]:
    pages_by_path: dict[str, str] = {}
    for offset in range(0, total, PAGE_LIMIT):
        result = _read(client, token, "getPageList", {"offset": str(offset), "limit": str(PAGE_LIMIT)})
        pages = result.get("pages")
        if (
            type(result.get("total_count")) is not int
            or result["total_count"] != total
            or not isinstance(pages, list)
            or len(pages) != min(PAGE_LIMIT, total - offset)
        ):
            raise ProbeError("Account listing changed or was incomplete")
        for page in pages:
            if not isinstance(page, dict):
                raise ProbeError("Account page entry is malformed")
            path, url, title = page.get("path"), page.get("url"), page.get("title")
            if (
                not isinstance(path, str)
                or re.fullmatch(r"[A-Za-z0-9_-]{1,512}", path) is None
                or url != "https://telegra.ph/" + path
                or not isinstance(title, str)
                or not 1 <= len(title) <= 256
                or path in pages_by_path
            ):
                raise ProbeError("Account page identity is malformed or duplicated")
            pages_by_path[path] = title
    if len(pages_by_path) != total:
        raise ProbeError("Account listing is incomplete")
    return pages_by_path


def _fold_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold().replace("ё", "е")
    return "".join(char for char in normalized if char.isalnum())


def _title_counts(pages: dict[str, str]) -> tuple[int, int]:
    exact = possible = 0
    expected = _fold_title(EXPECTED_TITLE)
    for title in pages.values():
        folded = _fold_title(title)
        if title == EXPECTED_TITLE:
            exact += 1
        elif (
            folded == expected
            or (("иуд" in folded or "jude" in folded) and "5" in folded)
            or "одингосподьдвачтения" in folded
        ):
            possible += 1
    return exact, possible


def inspect_account(
    *,
    client: httpx.Client,
    token: str,
    ledger: dict[str, Any],
    repo_root: Path,
    main_sha: str,
    state_sha: str,
) -> dict[str, Any]:
    """Inspect only the bound account's titles; never claim global provider absence."""
    if (
        not isinstance(token, str)
        or not token.strip()
        or re.fullmatch(r"[a-f0-9]{40}", main_sha) is None
        or re.fullmatch(r"[a-f0-9]{40}", state_sha) is None
    ):
        raise ProbeError("Token or exact main/state identity is missing")
    _validate_target(repo_root)
    ledger_status = _validate_ledger(ledger)
    count = _page_count(client, token)
    first = _snapshot(client, token, count)
    if _page_count(client, token) != count:
        raise ProbeError("Account changed during the first scan")
    second = _snapshot(client, token, count)
    if _page_count(client, token) != count or first != second:
        raise ProbeError("Account changed between scans")
    if ANCHOR_PATH not in first:
        raise ProbeError("Known verified page anchor is not owned by this account")
    exact, possible = _title_counts(first)
    return {
        "publication_id": PUBLICATION_ID,
        "article_blob": ARTICLE_BLOB,
        "main_sha": main_sha,
        "state_sha": state_sha,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "ledger_status": ledger_status,
        "account_anchor": "verified_ledger_page_owned",
        "account_page_count": count,
        "exact_title_matches": exact,
        "possible_related_title_matches": possible,
        "two_consistent_account_scans": True,
        "scan_scope": "single_owned_account_titles_only",
        "other_accounts_checked": False,
        "page_contents_checked": False,
        "telegram_history_checked": False,
        "provider_write_performed": False,
        "publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect one bound Telegraph account without publication")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        ledger = _object(args.ledger)
        with _ReadClient() as owner:
            report = inspect_account(
                client=owner.client,
                token=os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", ""),
                ledger=ledger,
                repo_root=args.repo_root,
                main_sha=os.environ.get("GITHUB_SHA", ""),
                state_sha=os.environ.get("LEDGER_SHA", ""),
            )
    except ProbeError as exc:
        print(f"Read-only Jude account probe stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
