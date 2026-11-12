"""Single Windows GET-only proof of owner-approved Lord God Instagram quote IMAGE posts.

Runs independently of GitHub's delayed scheduled events. Reuses the existing,
SHA-pinned Meta readback source; never acquires publisher authority or sends POST.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from lord_god_quote_windows_runner_20261113 import read_dedicated_token, validate_deployed_bytes

ROOT = Path(__file__).resolve().parents[2]
READBACK_PATH = ROOT / "scripts/instagram/lord_god_quote_receipt_readonly_20261112.py"
REGISTRY = ROOT / "scripts/wave-executors.json"
PLAN = ROOT / "content/instagram/lord-god-strength-quote-cloud-20261111.json"
PLAN_SHA256 = "529afa8711bc3fd5c071fb322bea90d13d85b2c3e49fc188cd34a62761e352b3"
APPROVED_DATES = frozenset({"2026-11-13", "2026-11-14", "2026-11-15"})
MOSCOW = ZoneInfo("Europe/Moscow")


def validate_readback_source() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf8"))
    entries = [
        entry
        for entry in registry.get("executors", [])
        if entry.get("path") == "scripts/instagram/lord_god_quote_receipt_readonly_20261112.py"
    ]
    if len(entries) != 1 or entries[0]["provider_write_capable"] is not False:
        raise RuntimeError("GET-only Meta IMAGE readback source is not approved")
    if hashlib.sha256(READBACK_PATH.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise RuntimeError("Meta IMAGE readback source SHA-256 mismatch")
    if hashlib.sha256(PLAN.read_bytes()).hexdigest() != PLAN_SHA256:
        raise RuntimeError("Frozen approved quote plan SHA-256 mismatch")


def execute(*, preflight: bool = False) -> int:
    if os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("GITHUB_EVENT_NAME"):
        raise RuntimeError("Native IMAGE readback is forbidden from GitHub Actions")
    now = dt.datetime.now(MOSCOW)
    if not preflight:
        if now.strftime("%Y-%m-%d") not in APPROVED_DATES:
            raise RuntimeError("Outside the three approved IMAGE readback dates")
        if now.time() < dt.time(14, 0):
            raise RuntimeError("Independent IMAGE readback cannot run before 14:00 Moscow")
    validate_deployed_bytes()
    validate_readback_source()
    token = read_dedicated_token()
    os.environ["LORD_GOD_PAGE_TOKEN"] = token
    os.environ["LORD_GOD_QUOTE_RECEIPT_MODE"] = "preflight" if preflight else "scheduled"

    from lord_god_quote_receipt_readonly_20261112 import main as original_readback

    return int(original_readback())


def main() -> int:
    preflight = sys.argv[1:] == ["--preflight"]
    if sys.argv[1:] and not preflight:
        raise RuntimeError("Only --preflight is permitted; scheduled readback takes no arguments")
    now = dt.datetime.now(MOSCOW)
    logs = ROOT / "operator-logs"
    logs.mkdir(parents=True, exist_ok=True)
    prefix = "quote-readback-preflight-" if preflight else "quote-readback-"
    path = logs / (prefix + now.strftime("%Y-%m-%d") + ".log")
    with path.open("a", encoding="utf8", buffering=1) as output:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            print("INDEPENDENT_IMAGE_READBACK_START", now.isoformat(), flush=True)
            try:
                result = execute(preflight=preflight)
            except Exception as exc:
                print("INDEPENDENT_IMAGE_READBACK_ERROR", type(exc).__name__, str(exc)[:160], flush=True)
                result = 2
            print("INDEPENDENT_IMAGE_READBACK_FINISH", result, flush=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
