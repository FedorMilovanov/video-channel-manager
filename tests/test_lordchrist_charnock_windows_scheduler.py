"""Guardrails for the independent Windows Charnock backup clock.

These are static contract checks. The real publishing workflow remains the
same guarded GitHub Actions job; this local tool only dispatches it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "scripts" / "lordchrist_charnock_external_dispatch.ps1"
INSTALL = ROOT / "scripts" / "install_lordchrist_charnock_windows_backup.ps1"


def _dispatch() -> str:
    return DISPATCH.read_text(encoding="utf-8")


def _install() -> str:
    return INSTALL.read_text(encoding="utf-8")


def test_only_approved_dates_and_publications() -> None:
    content = _dispatch()
    assert "'2026-11-20' = 'lordchrist-telegraph-charnock-09'" in content
    assert "'2026-11-24' = 'lordchrist-telegraph-charnock-10'" in content
    assert "'2026-11-27' = 'lordchrist-telegraph-charnock-11'" in content
    assert "'2026-12-01' = 'lordchrist-telegraph-charnock-12'" in content
    for num in ("06", "07", "08", "13"):
        assert f"lordchrist-telegraph-charnock-{num}" not in content
    assert "$local.Hour -notin @(12, 13)" in content
    assert "NO_DUE" in content
    assert "OUTSIDE_APPROVED_WINDOW" in content


def test_no_forged_clock_can_dispatch() -> None:
    content = _dispatch()
    assert "if ($Dispatch -and $ProbeAt)" in content
    assert "Simulated time forbidden in execution mode" in content
    assert "[DateTimeOffset]::UtcNow" in content
    assert "ConvertTime($instant, $moscow)" in content
    assert "Russian Standard Time" in content
    assert "WOULD_DISPATCH" in content


def test_verified_git_actor_and_immutable_artifacts() -> None:
    content = _dispatch()
    assert "repo = 'FedorMilovanov/video-channel-manager'" in content
    assert "actor -cne 'FedorMilovanov'" in content
    assert "approvedManifestSha256 = '13f3716d5dffc32291ac3c9ee12f82591389bcb5154e7ecf0a534741c6b960fd'" in content
    assert "approvedWorkflowBlob = '3cd700040228cd6b6ba2227ad22cd87e7d7e9c32'" in content
    assert "workflowFile.Blob -cne $approvedWorkflowBlob" in content
    assert "hash -cne $approvedManifestSha256" in content
    assert "'state/lordchrist-telegram'" in content
    assert "ALREADY_CLAIMED" in content
    assert "Original verified receipt missing" in content
    assert "Original receipt mismatch" in content


def test_only_git_workflow_dispatch_can_mutate_remotely() -> None:
    content = _dispatch()
    assert "if (-not $Dispatch)" in content
    assert "Invoke-CheckedGh -Arguments @('workflow','run',$workflow" in content
    assert "RUN_APPROVED_CHARNOCK_SLOT_ONCE" in content
    assert "DISPATCH_REQUESTED" in content
    assert "sendMessage" not in content
    assert "editPage" not in content
    assert "createPage" not in content
    assert "gh auth login" not in content
    assert "GH_TOKEN" not in content
    assert "GITHUB_TOKEN" not in content


def test_four_one_date_tasks_with_wake_and_no_catchup() -> None:
    content = _install()
    for number, day in (("09", "2026-11-20"), ("10", "2026-11-24"), ("11", "2026-11-27"), ("12", "2026-12-01")):
        assert f"'{number}' = '{day}T12:05:00'" in content
    assert "New-ScheduledTaskTrigger -Once -At" in content
    assert "New-TimeSpan -Minutes 30" in content
    assert "New-TimeSpan -Minutes 95" in content
    assert "-WakeToRun" in content
    assert "-LogonType Interactive" in content
    assert "-RunLevel Limited" in content
    assert "-MultipleInstances IgnoreNew" in content
    assert "Windows Task Scheduler must use Europe/Moscow local clock" in content
    assert "Pre-existing Charnock backup task(s) require explicit reconciliation" in content
    assert "SourceHash" not in content or "$sourceHash" in content
    assert "Get-FileHash -LiteralPath $target" in content
    assert "Register-ScheduledTask" in content
    assert "Start-ScheduledTask" not in content


def test_installer_is_opt_in_and_requires_readonly_proof() -> None:
    content = _install()
    assert "param([switch]$Install)" in content
    assert "if (-not $Install)" in content
    assert "READ_ONLY_PLAN" in content
    assert "-ProbeAt $probe" in content
    assert "WOULD_DISPATCH lordchrist-telegraph-charnock-$num " in content
    assert "Register-ScheduledTask" in content
    assert "secrets." not in content
