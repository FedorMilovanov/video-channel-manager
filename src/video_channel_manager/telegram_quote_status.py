"""Local-only operational summary; never supplies publication authority."""

from __future__ import annotations

import json
import os
from pathlib import Path

from video_channel_manager.telegram_models import TelegramLedger


def publication_status(
    ledger: TelegramLedger | None,
    *,
    job_status: str,
    execution_reason: str,
    run_id: str,
    run_attempt: str,
    durable_result: str,
) -> dict[str, object]:
    published = [] if ledger is None else [e for e in ledger.entries.values() if e.state == "published"]
    pending = [] if ledger is None else [e for e in ledger.entries.values() if e.state == "pending"]
    current = [e for e in published if e.workflow_run_id == run_id and e.workflow_run_attempt == run_attempt]
    ambiguous = ledger is not None and any(
        e.state in {"unknown", "dispatching"} or e.provider_effect == "may_exist" for e in ledger.entries.values()
    )
    url = None
    if job_status != "success" or ledger is None or ambiguous:
        status = "BLOCKED"
        detail = "Publication is not confirmed durably. Inspect the failed step and state; never blindly resend."
    elif current:
        if len(current) == 1 and durable_result == "success" and current[0].provider_effect == "verified":
            status = "PUBLISHED"
            url = current[0].message_url
            detail = "Telegram response verified and exact result persisted to the state branch."
        else:
            status = "BLOCKED"
            detail = "Provider result may exist but durable completion is unconfirmed; reconcile before any retry."
    elif not pending:
        status = "EXHAUSTED"
        detail = "No publication sent: reviewed quote queue is exhausted. A reviewed successor is required."
    elif "production schedule disabled" in execution_reason:
        status = "PAUSED"
        detail = "No publication sent: autonomous posting is disabled. A green preview is not a publication."
    else:
        status = "NO_SEND"
        detail = "No publication sent in this run. Check execution reason and slot/day eligibility."
    return {
        "status": status,
        "detail": detail,
        "execution_reason": execution_reason,
        "published": len(published),
        "pending": len(pending),
        "message_url": url,
        "replenishment_required": ledger is not None and len(pending) <= 7,
    }


def main() -> int:
    path = Path(os.environ["LEDGER_PATH"])
    try:
        ledger = TelegramLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = None
    status = publication_status(
        ledger,
        job_status=os.environ.get("JOB_STATUS", "failure"),
        execution_reason=os.environ.get("EXECUTION_REASON", "unknown"),
        run_id=os.environ["GITHUB_RUN_ID"],
        run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        durable_result=os.environ.get("DURABLE_RESULT", "skipped"),
    )
    payload = json.dumps(status, ensure_ascii=False, sort_keys=True)
    print(payload)
    if status["status"] in {"BLOCKED", "PAUSED", "EXHAUSTED"}:
        print(f"::warning::LordChrist {status['status']}: {status['detail']}")
    if status["replenishment_required"]:
        print(
            f"::warning::LordChrist reviewed quote queue has {status['pending']} pending; prepare a successor release."
        )
    summary = (
        f"## LordChrist quotes: {status['status']}\n\n{status['detail']}\n\n"
        f"Published: {status['published']} · Pending: {status['pending']}\n\n"
        f"Execution reason: `{status['execution_reason']}`\n\n"
    )
    if status["message_url"]:
        summary += f"Verified publication: {status['message_url']}\n"
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
        handle.write(summary)
    output = Path(".runtime/lordchrist-publication-status.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
