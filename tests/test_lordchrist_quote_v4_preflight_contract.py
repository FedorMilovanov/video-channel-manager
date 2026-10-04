from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lordchrist-quote-v4-preflight.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_quote_v4_preflight_binds_the_exact_predecessor_effect_track() -> None:
    """The channel-wide barrier must read the immutable predecessor artifacts.

    A generated successor runtime queue must never be treated as the legacy
    predecessor queue; the workflow binds the same exact paths the guarded
    production publisher binds.
    """

    workflow = _workflow()

    assert "LORDCHRIST_PREDECESSOR_QUEUE_PATH: content/telegram/lordchrist/verified-30-posts.json" in workflow
    assert (
        "LORDCHRIST_PREDECESSOR_LEDGER_PATH: .state/lordchrist/content/telegram/lordchrist/publication-ledger.json"
        in workflow
    )
    assert (
        "the immutable predecessor\n  # track even while the active queue is a generated successor runtime artifact"
        in workflow
    )


def test_quote_v4_preflight_binds_the_exact_approved_queue_digest_before_provider_access() -> None:
    workflow = _workflow()

    digest_step = workflow.index("LORDCHRIST_APPROVED_QUEUE_DIGEST={digest}")
    live_preflight = workflow.index("Read-only live bot and channel identity preflight")
    assert digest_step < live_preflight
    assert 'selection["queue_digest"]' in workflow
    assert 'activation["queue_digest"]' in workflow
    assert 'schedule["successor_queue_digest"]' in workflow


def test_quote_v4_preflight_keeps_the_exact_step_order() -> None:
    workflow = _workflow()

    ordered = [
        "Build exact depth-v2 runtime queue without provider authorization",
        "Bind the exact reviewed queue digest for the read-only preflight",
        "Validate rolling v4 checkpoint and evidence",
        "Re-run standalone quality gate for exact future suffix 16 through 60",
        "Validate queue and ledger through quote-v4 renderer",
        "Prove quote-v4 reading unit for the exact next pending publication",
        "Prove exact Telegram target configuration",
        "Read-only live bot and channel identity preflight",
        "Assert preflight remained provider-inert",
    ]
    positions = [workflow.index(name) for name in ordered]
    assert positions == sorted(positions)


def test_quote_v4_preflight_automatic_trigger_still_requires_successful_main_ci() -> None:
    workflow = _workflow()

    assert "- CI" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert "refusing stale activation proof" in workflow


def test_quote_v4_preflight_dispatch_is_explicit_read_only_staging_only() -> None:
    workflow = _workflow()

    assert "workflow_dispatch:" in workflow
    assert "READ-ONLY-STAGING-PREFLIGHT" in workflow
    assert "never authorizes a provider write" in workflow
    assert "staging_sha" in workflow
    assert "current_main" in workflow


def test_quote_v4_preflight_staging_pull_request_run_requires_the_exact_label() -> None:
    """A staged read-only proof is available only on an explicitly labelled
    same-repository pull request; forks never receive repository secrets."""

    workflow = _workflow()

    assert "pull_request:" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "contains(github.event.pull_request.labels.*.name, 'lordchrist-read-only-preflight')" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "This staged run is verification evidence only" in workflow
    assert "Unsupported preflight event" in workflow


def test_quote_v4_preflight_is_provider_inert_and_never_writes_state() -> None:
    workflow = _workflow()

    assert workflow.count("persist-credentials: false") == 2
    assert "git push" not in workflow
    assert "sendMessage" not in workflow
    assert (
        'telegram_cli \\\n            --queue "$DEPTH_RUNTIME_QUEUE_PATH" \\\n            --ledger "$DEPTH_LEDGER_PATH" \\\n            --presentation-policy "$V4_POLICY_PATH" \\\n            preflight'
        in workflow
    )
    assert 'if target_proof["bot_id"] != int(os.environ["LORDCHRIST_TELEGRAM_BOT_ID"])' in workflow
    assert 'if target_proof["chat_username"] != "lordchrist"' in workflow
    assert "requirements/telegram-publisher.txt" in workflow
    assert 'python-version: "3.11"' in workflow
