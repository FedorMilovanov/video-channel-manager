"""Bounded independent GET-only proof of approved Instagram Reels on Windows."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from lord_god_quote_windows_runner_20261113 import read_dedicated_token

ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "scripts/instagram/lord_god_reels_readback_cloud_20261112.py"
CREDENTIAL_READER = ROOT / "scripts/instagram/lord_god_quote_windows_runner_20261113.py"
REGISTRY = ROOT / "scripts/wave-executors.json"
PLAN = ROOT / "content/instagram/lord-god-strength-reels-cloud-readback-20261112.json"
PLAN_SHA256 = "7e55a4702d90daaca5e1a346718cca58eddaf0293880fc4439793e6d360f6d63"
LOCAL_POSTFLIGHT = Path(r"E:\VideoChannelManager\Instagram\LordGod\20261110-daily-wave\lord_god_readback_1925_v1.py")
LOCAL_POSTFLIGHT_SHA256 = "f97a85431fc2342b656401c48cc2c7606768debe4cd8afc6a8fb21d2e09d61c9"
DAYS = frozenset(f"2026-11-{day:02d}" for day in range(13, 22))
MOSCOW = ZoneInfo("Europe/Moscow")


def validate_deployment() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf8"))
    for name, file, can_post in (
        ("scripts/instagram/lord_god_reels_readback_cloud_20261112.py", PROOF, False),
        ("scripts/instagram/lord_god_quote_windows_runner_20261113.py", CREDENTIAL_READER, True),
    ):
        items = [entry for entry in registry.get("executors", []) if entry.get("path") == name]
        if len(items) != 1 or items[0].get("provider_write_capable") is not can_post:
            raise RuntimeError("Protected executor identity or capability mismatch")
        if hashlib.sha256(file.read_bytes()).hexdigest() != items[0]["sha256"]:
            raise RuntimeError("Protected executor SHA-256 mismatch")
    if hashlib.sha256(PLAN.read_bytes()).hexdigest() != PLAN_SHA256:
        raise RuntimeError("Frozen Reel readback plan SHA-256 mismatch")


def reconcile_existing_due_slot(today: str) -> str:
    """Use only the hash-pinned local postflight to close an exact ambiguous ledger."""
    if hashlib.sha256(LOCAL_POSTFLIGHT.read_bytes()).hexdigest() != LOCAL_POSTFLIGHT_SHA256:
        raise RuntimeError("Installed 19:25 source SHA-256 mismatch; no ledger reconciliation")
    scope = runpy.run_path(str(LOCAL_POSTFLIGHT), run_name="lordgod_late_ledger_reconcile")
    reconcile = scope.get("reconcile_due_slot")
    if not callable(reconcile):
        raise RuntimeError("Installed 19:25 source lacks canonical reconciliation entrypoint")
    return str(reconcile(today))


def execute(*, preflight: bool = False) -> int:
    if os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("GITHUB_EVENT_NAME"):
        raise RuntimeError("Native Reel receipt prohibited in GitHub Actions")
    now = dt.datetime.now(MOSCOW)
    if not preflight:
        if now.strftime("%Y-%m-%d") not in DAYS:
            raise RuntimeError("Outside approved Reel receipt dates")
        if not dt.time(20, 5) <= now.time() <= dt.time(21, 15):
            raise RuntimeError("Outside 20:05-21:15 Moscow receipt window")
    validate_deployment()
    os.environ["LORD_GOD_PAGE_TOKEN"] = read_dedicated_token()
    os.environ["LORD_GOD_REELS_PROOF_MODE"] = "preflight" if preflight else "scheduled"
    from lord_god_reels_readback_cloud_20261112 import main as get_only_proof

    proof_exit = int(get_only_proof())
    if preflight or proof_exit != 0:
        return proof_exit
    closeout = reconcile_existing_due_slot(now.date().isoformat())
    print("LOCAL_LEDGER_CLOSEOUT=" + closeout, flush=True)
    return 0 if closeout in ("ALREADY_PUBLISHED", "DISCOVERY_SUCCEEDED") else 2


def main() -> int:
    preflight = sys.argv[1:] == ["--preflight"]
    if sys.argv[1:] and not preflight:
        raise RuntimeError("Only --preflight accepted as a manual argument")
    now = dt.datetime.now(MOSCOW)
    directory = ROOT / "operator-logs"
    directory.mkdir(parents=True, exist_ok=True)
    basename = ("reel-readback-preflight-" if preflight else "reel-readback-") + now.strftime("%Y-%m-%d")
    with (directory / (basename + ".log")).open("a", encoding="utf8", buffering=1) as out:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            print("LOCAL_GET_ONLY_REEL_READBACK_START", now.isoformat(), flush=True)
            try:
                code = execute(preflight=preflight)
            except Exception as exc:
                print("LOCAL_GET_ONLY_REEL_READBACK_ERROR", type(exc).__name__, str(exc)[:160], flush=True)
                code = 2
            print("LOCAL_GET_ONLY_REEL_READBACK_FINISH", code, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
