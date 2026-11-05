"""Prevent Windows CRLF checkout from invalidating immutable Telegraph article bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("content/telegram/lordchrist/telegraph-v1")
QUEUE = BASE / "article-queue.json"


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def test_all_telegraph_json_paths_are_checked_out_as_lf() -> None:
    """Git attributes must override core.autocrlf=true on Windows runners."""
    queue = json.loads((ROOT / QUEUE).read_text(encoding="utf-8"))
    paths = [QUEUE]
    paths.extend(Path(item["article"]["path"]) for item in queue["items"])
    output = subprocess.check_output(
        ["git", "check-attr", "eol", "--", *(p.as_posix() for p in paths)],
        cwd=ROOT,
        text=True,
    )
    found = {
        line.split(": eol: ", 1)[0]: line.split(": eol: ", 1)[1]
        for line in output.splitlines()
    }
    assert set(found) == {path.as_posix() for path in paths}
    assert set(found.values()) == {"lf"}


def test_all_telegraph_articles_preserve_reviewed_blob_sha_on_checkout() -> None:
    """Every ready article, not merely the selected one, passes exact-byte guard."""
    queue = json.loads((ROOT / QUEUE).read_bytes())
    for item in queue["items"]:
        if item["status"] != "ready":
            continue
        path = ROOT / item["article"]["path"]
        raw = path.read_bytes()
        assert b"\r\n" not in raw, item["publication_id"]
        assert git_blob_sha(raw) == item["article"]["git_blob_sha"], item["publication_id"]
