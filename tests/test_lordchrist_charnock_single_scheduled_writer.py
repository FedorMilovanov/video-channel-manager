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
    assert _cron_triggers("lordchrist-charnock-scheduled-reissue.yml") == ["0 9 * * 2,5"]
    assert _cron_triggers("lordchrist-telegraph-poster.yml") == []
    assert _cron_triggers("lordchrist-telegram-poster.yml") == ["17 16 * * 1,3,6"]
    all_midday_owners = {
        workflow.name
        for workflow in WORKFLOWS.glob("lordchrist-*.yml")
        if "0 9 * * 2,5" in _cron_triggers(workflow.name)
    }
    assert all_midday_owners == {"lordchrist-charnock-scheduled-reissue.yml"}


def test_sole_scheduled_reissue_preserves_immutable_approval_and_no_backfill() -> None:
    data = (WORKFLOWS / "lordchrist-charnock-scheduled-reissue.yml").read_text(encoding="utf-8")
    assert "LORDCHRIST_CHARNOCK_RECOVERY_ENABLED" in data
    assert "LORDCHRIST_CHARNOCK_RECOVERY_MANIFEST_SHA256" in data
    assert 'now.hour not in (12,13)' in data
    assert "bash scripts/lordchrist_charnock_reschedule.sh" in data
    assert 'cancel-in-progress: false' in data


def test_retired_rich_and_telegraph_jobs_do_not_resolve_scheduled_articles() -> None:
    rich = (WORKFLOWS / "lordchrist-telegram-poster.yml").read_text(encoding="utf-8")
    rich_job = rich.split("\n  charnock-rich:", 1)[1]
    assert "github.event.schedule == '0 9 * * 2,5'" not in rich_job
    assert "github.event_name == 'workflow_dispatch'" in rich_job
    telegraph = (WORKFLOWS / "lordchrist-telegraph-poster.yml").read_text(encoding="utf-8")
    assert "steps.resolve.outputs" not in telegraph
    assert "github.event_name == 'schedule'" not in telegraph
    assert "if: inputs.action == 'publish'" in telegraph
