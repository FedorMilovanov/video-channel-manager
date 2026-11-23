"""One scheduled owner for Charnock reissues; old renderers stay manual/inert."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _cron_triggers(filename: str) -> list[str]:
    data = (WORKFLOWS / filename).read_text(encoding="utf-8")
    triggers = data.split("\npermissions:", 1)[0]
    return re.findall(r'^\s*- cron: "([^"]+)"$', triggers, flags=re.MULTILINE)


def test_only_charnock_reissue_owns_tuesday_friday_midday_schedule() -> None:
    approved_triggers = ["0 9 * * 2,5", "11 9 * * 2,5", "37 9 * * 2,5", "11 10 * * 2,5"]
    assert _cron_triggers("lordchrist-charnock-scheduled-reissue.yml") == approved_triggers
    assert _cron_triggers("lordchrist-telegraph-poster.yml") == []
    assert _cron_triggers("lordchrist-telegram-poster.yml") == ["17 16 * * 1,3,6"]
    all_midday_owners = {
        workflow.name
        for workflow in WORKFLOWS.glob("lordchrist-*.yml")
        if set(approved_triggers) & set(_cron_triggers(workflow.name))
    }
    assert all_midday_owners == {"lordchrist-charnock-scheduled-reissue.yml"}


def test_sole_scheduled_reissue_preserves_immutable_approval_and_no_backfill() -> None:
    data = (WORKFLOWS / "lordchrist-charnock-scheduled-reissue.yml").read_text(encoding="utf-8")
    assert "LORDCHRIST_CHARNOCK_RECOVERY_ENABLED" in data
    assert "LORDCHRIST_CHARNOCK_RECOVERY_MANIFEST_SHA256" in data
    assert "now.hour not in (12,13)" in data
    # The v2 source/media binding is resolved read-only before the immutable
    # ledger preflight.  #10 may use only its separately pinned reviewed source,
    # and every other article retains the historic manifest entry unchanged.
    assert "approved=approved_reissue_entry(Path(\".\"),matches[0])" in data
    assert "scheduled_reissue_preflight_status(state,approved)" in data
    assert "APPROVED_MANIFEST_SHA256" in data
    assert '[[ "$(sha256sum "$MANIFEST"' in data
    assert "github.event_name == 'workflow_dispatch'" in data
    assert "github.actor == 'FedorMilovanov'" in data
    assert "inputs.confirm == 'RUN_APPROVED_CHARNOCK_SLOT_ONCE'" in data
    for number in range(9, 13):
        assert f"inputs.publication_id == 'lordchrist-telegraph-charnock-{number:02d}'" in data
    for number in (6, 7, 8, 13):
        assert f"inputs.publication_id == 'lordchrist-telegraph-charnock-{number:02d}'" not in data
    assert 'matches[0]["publication_id"] != os.environ.get("REVIEWED_PUBLICATION_ID")' in data
    assert "bash scripts/lordchrist_charnock_reschedule.sh" in data
    assert "cancel-in-progress: false" in data


def test_retired_rich_and_telegraph_jobs_do_not_resolve_scheduled_articles() -> None:
    rich = (WORKFLOWS / "lordchrist-telegram-poster.yml").read_text(encoding="utf-8")
    rich_job = rich.split("\n  charnock-rich:", 1)[1]
    assert "github.event.schedule == '0 9 * * 2,5'" not in rich_job
    assert "github.event_name == 'workflow_dispatch'" in rich_job
    telegraph = (WORKFLOWS / "lordchrist-telegraph-poster.yml").read_text(encoding="utf-8")
    assert "steps.resolve.outputs" not in telegraph
    assert "github.event_name == 'schedule'" not in telegraph
    assert "if: inputs.action == 'publish'" in telegraph


def test_dispatch_uses_exact_same_protected_writer_and_ledger() -> None:
    workflow = (WORKFLOWS / "lordchrist-charnock-scheduled-reissue.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts/lordchrist_charnock_reschedule.sh").read_text(encoding="utf-8")
    runtime = (ROOT / "src/video_channel_manager/lordchrist_charnock_reschedule.py").read_text(encoding="utf-8")
    assert "concurrency:\n  group: lordchrist-telegram-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "REVIEWED_PUBLICATION_ID:" in workflow
    assert "LORDCHRIST_CHARNOCK_RECOVERY_MANIFEST_SHA256" in workflow
    assert "telegram_github_quality_gate" in workflow
    assert 'if [[ "$GITHUB_EVENT_NAME" == "workflow_dispatch" ]]; then' in script
    assert 'payload=json.loads(Path(os.environ["GITHUB_EVENT_PATH"])' in script
    assert 'os.environ.get("PUBLICATION_ID") not in OWNER_DISPATCH_IDS' in script
    assert all(x in script for x in ("stage prepare", "stage send", "stage verify", "current_main_ci", "persist"))
    assert "CHARNOCK_EDITORIAL_HOLDS" in runtime
    assert "Forged clock forbidden on live recovery" in runtime
    assert "if datetime.now(tz=MOSCOW).hour not in LIVE_WINDOW_HOUR" in runtime
