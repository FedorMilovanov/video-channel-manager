from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github/workflows"
WORKFLOW = WORKFLOWS_DIR / "lordchrist-telegram-poster.yml"
RECOVERY_WORKFLOW = WORKFLOWS_DIR / "lordchrist-reconcile-provider-outcome.yml"
RICH_CANARY_WORKFLOW = WORKFLOWS_DIR / "lordchrist-rich-live-canary.yml"
RICH_CONTROLLER_WORKFLOW = WORKFLOWS_DIR / "lordchrist-rich-live-controller.yml"
RESEARCH_WORKFLOW = WORKFLOWS_DIR / "lordchrist-research-v2-publisher.yml"
WRITER_GROUP = "group: lordchrist-telegram-publisher"
EXPECTED_WRITERS = {WORKFLOW, RECOVERY_WORKFLOW}


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_complete_lordchrist_writer_surface_uses_lossless_serialization_contract() -> None:
    discovered = {path for path in WORKFLOWS_DIR.glob("*.yml") if WRITER_GROUP in path.read_text(encoding="utf-8")}

    assert not RESEARCH_WORKFLOW.exists()
    assert not RICH_CANARY_WORKFLOW.exists()
    assert not RICH_CONTROLLER_WORKFLOW.exists()
    assert discovered == EXPECTED_WRITERS
    for path in discovered:
        text = path.read_text(encoding="utf-8")
        assert "cancel-in-progress: false" in text, path.name
        assert "queue: max" in text, path.name
        assert "queue: single" not in text, path.name
        assert "runs-on: ubuntu-24.04" in text, path.name
        assert "runs-on: ubuntu-latest" not in text, path.name


def test_lordchrist_scheduler_queues_pending_runs_without_cancelling_active_run() -> None:
    text = workflow_text()
    assert WRITER_GROUP in text
    assert "cancel-in-progress: false" in text
    assert "queue: max" in text
    assert "queue: single" not in text


def test_lordchrist_scheduler_preserves_two_moscow_windows_and_pins_runner() -> None:
    text = workflow_text()
    assert 'cron: "17 9 * * *"' in text
    assert 'cron: "17 21 * * 0,2,5"' in text
    assert 'cron: "17 21 * * *"' not in text
    assert text.count("timezone: Europe/Moscow") >= 2
    assert "runs-on: ubuntu-24.04" in text
    assert "runs-on: ubuntu-latest" not in text


def test_lordchrist_provider_path_requires_exact_current_main_ci_before_preflight_and_send() -> None:
    text = workflow_text()
    assert "actions: read" in text
    assert "Require current-main exact-SHA repository CI proof" in text
    assert "Re-prove current-main CI immediately before Telegram mutation" in text
    assert text.count("telegram_github_quality_gate") == 2
    assert text.count("--workflow ci.yml") == 2
    assert text.count('--sha "$GITHUB_SHA"') == 2

    initial_quality = text.index("Require current-main exact-SHA repository CI proof")
    preflight = text.index("Read-only bot and channel preflight")
    persist = text.index("Persist intent and rendered payload before sendMessage")
    pre_send_quality = text.index("Re-prove current-main CI immediately before Telegram mutation")
    send = text.index("Send exactly one prepared message")
    assert initial_quality < preflight < persist < pre_send_quality < send


def test_lordchrist_failed_final_ci_reproof_is_provider_free_and_durably_resolved() -> None:
    text = workflow_text()
    resolve = text.index("Resolve blocked pre-send intent as confirmed absent")
    send = text.index("Send exactly one prepared message")
    final_state = text.index("Persist exact Telegram result")
    assert resolve < send < final_state
    assert "steps.pre_send_quality.outcome != 'success'" in text
    assert "--resolution confirmed_absent" in text
    assert "failed before the Telegram send step" in text
    assert "steps.pre_send_quality.outcome == 'success'" in text


def test_lordchrist_archives_exact_provider_outcome_before_final_state_persistence() -> None:
    text = workflow_text()
    send = text.index("Send exactly one prepared message")
    capture = text.index("Capture exact Lordchrist provider outcome")
    archive = text.index("Archive exact Lordchrist provider outcome before state mutation")
    final_state = text.index("Persist exact Telegram result")
    assert send < capture < archive < final_state
    assert "telegram_lordchrist_outcome_cli" in text
    assert "lordchrist-provider-outcome-${{ github.run_id }}-${{ github.run_attempt }}" in text
    assert "path: .runtime/lordchrist-outcome.json" in text
    assert "if-no-files-found: error" in text
    assert "retention-days: 30" in text
    assert "include-hidden-files: true" in text


def test_completed_rich_live_surfaces_are_not_replayable_from_main() -> None:
    assert not RICH_CANARY_WORKFLOW.exists()
    assert not RICH_CONTROLLER_WORKFLOW.exists()
