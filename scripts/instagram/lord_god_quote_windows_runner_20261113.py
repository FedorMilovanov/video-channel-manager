"""Single-authority Windows Task Scheduler entrypoint for approved Nov 13?15 quote photos.

Reuses the protected GitHub publisher, with an atomic SQLite one-attempt claim.
No arbitrary captions/dates and no retry of an ambiguous provider write.
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

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/instagram/lord_god_quote_cloud_20261111.py"
REGISTRY = ROOT / "scripts/wave-executors.json"
DATABASE = Path(r"C:\Users\Fedor\Projects\video-channel-manager\data\video_manager.db")
ENV_FILE = Path(r"C:\Users\Fedor\Projects\video-channel-manager\.env")
APPROVED_DATES = frozenset({"2026-11-13", "2026-11-14", "2026-11-15"})
MOSCOW = ZoneInfo("Europe/Moscow")


def validate_deployed_bytes() -> None:
    info = json.loads(REGISTRY.read_text(encoding="utf8"))
    entries = [
        entry
        for entry in info.get("executors", [])
        if entry.get("path") == "scripts/instagram/lord_god_quote_cloud_20261111.py"
    ]
    if len(entries) != 1 or not entries[0].get("provider_write_capable"):
        raise RuntimeError("No approved photo publisher entry in execution registry")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise RuntimeError("Deployed photo publisher SHA-256 differs from protected source")
    if not DATABASE.is_file() or not ENV_FILE.is_file():
        raise RuntimeError("Owner's durable SQLite database or credential source unavailable")


def read_dedicated_token() -> str:
    values = [
        line.partition("=")[2].strip().strip('"').strip("'")
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("VCM_INSTAGRAM_ACCESS_TOKEN_LORD_GOD_STRENGTH=")
    ]
    if len(values) != 1 or len(values[0]) < 35:
        raise RuntimeError("Exactly one valid dedicated Lord God Page token is required")
    return values[0]


def execute(*, preflight: bool = False) -> int:
    if os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("GITHUB_EVENT_NAME"):
        raise RuntimeError("Windows photo writer cannot run inside GitHub Actions")
    now = dt.datetime.now(MOSCOW)
    day = now.strftime("%Y-%m-%d")
    if not preflight and day not in APPROVED_DATES:
        raise RuntimeError("Outside remaining approved 13?15 November photo dates")
    if not preflight and not (dt.time(12, 45) <= now.time() < dt.time(14, 0)):
        raise RuntimeError("Outside approved 12:45?14:00 Moscow photo window")
    validate_deployed_bytes()
    os.environ["LORD_GOD_CLOUD_MODE"] = "preflight" if preflight else "local_scheduled"
    os.environ["LORD_GOD_PAGE_TOKEN"] = read_dedicated_token()
    os.environ["LORD_GOD_LOCAL_LEDGER_DB"] = str(DATABASE)
    from lord_god_quote_cloud_20261111 import main

    main()
    return 0


def main() -> int:
    preflight = sys.argv[1:] == ["--preflight"]
    if sys.argv[1:] and not preflight:
        raise RuntimeError("Only --preflight may be supplied; scheduled mode needs no args")
    stamp = dt.datetime.now(MOSCOW)
    logs = ROOT / "operator-logs"
    logs.mkdir(parents=True, exist_ok=True)
    report = logs / (("quote-preflight-" if preflight else "quote-") + stamp.strftime("%Y-%m-%d") + ".log")
    with report.open("a", encoding="utf8", buffering=1) as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            print("QUOTE_SCHEDULER_START", stamp.isoformat(), flush=True)
            try:
                result = execute(preflight=preflight)
            except Exception as exc:
                print("QUOTE_SCHEDULER_FAILED_NO_BLIND_RETRY", type(exc).__name__, str(exc)[:160], flush=True)
                result = 2
            print("QUOTE_SCHEDULER_FINISH", result, flush=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
