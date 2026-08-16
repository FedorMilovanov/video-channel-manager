from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/telegram-milovi-exact-canary.yml"
RUNTIME = REPOSITORY_ROOT / "src/video_channel_manager/milovi_telegram_live_canary.py"


def test_exact_canary_is_one_file_triggered_and_persists_intent_before_send() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "content/telegram/milovi-cake/live/canary-authorization.json" in workflow
    assert 'test "${GITHUB_RUN_ATTEMPT}" = "1"' in workflow
    assert workflow.index("persist canary dispatch-started barrier") < workflow.index(
        "milovi_telegram_live_canary send"
    )
    assert "cancel-in-progress: false" in workflow


def test_exact_canary_send_has_zero_mutation_retry_and_no_fallback_operation() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"sendPhoto"' in runtime
    assert "retries=0" in runtime
    assert "HTTPTransport(retries=retries)" in runtime
    assert "sendDocument" not in runtime
    assert "sendMessage" not in runtime
    assert '"last_durable_stage": "dispatch_started"' in runtime
    assert '"retry_policy": "never_replay"' in runtime
    assert '"provider_write_may_have_occurred": True' in runtime


def test_canary_import_does_not_require_pillow_before_payload_materialization() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    materialize_offset = runtime.index("def _materialize_payload")
    pillow_offset = runtime.index("from PIL import Image")

    assert pillow_offset > materialize_offset
    assert "from PIL import Image" not in runtime[:materialize_offset]


def test_exact_canary_is_bound_to_recovered_target_transport_and_membership() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "CHAT_ID = -1002215328390" in runtime
    assert "BOT_ID = 8716602202" in runtime
    assert "a9730cc62939845c61191f1a375b2bab35800122c968d6cc757f0ae4340771d5" in runtime
    assert "d712ca06f2503bbb7e483f6c8d0fe3f0067b37b834536f7f7861bb38415fa580" in runtime
    assert "changed != [AUTH_PATH.as_posix()]" in runtime
    assert '"getChatMember"' in runtime
    assert 'membership.get("can_post_messages") is True' in runtime
    assert "fresh membership proof lacks channel posting authority" in runtime


def test_rejected_canary_requires_explicit_new_successor_authorization() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert 'prior.get("status") != "provider_rejected"' in runtime
    assert 'prior.get("provider_effect") != "rejected_before_message_creation"' in runtime
    assert "same canary authorization cannot be replayed" in runtime
    assert "successor authorization must explicitly bind the rejected authorization it supersedes" in runtime
    assert "ATTEMPTS_DIR" in runtime
    assert "prior_state_archive" in runtime


def test_terminal_provider_rejection_and_unknown_outcome_are_both_durably_persisted() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "if: always()" in workflow
    assert "Persist post-barrier Telegram outcome evidence" in workflow
    assert "No post-barrier state change to persist; provider dispatch was not durably marked started." in workflow
    assert "400 <= status < 500" in runtime
    assert '"provider_effect": "rejected_before_message_creation"' in runtime
    assert '"status": "unknown_requires_reconciliation"' in runtime
    assert '"required_next_action": "read_reconcile_exact_message_identity"' in runtime
    assert '"automatic_replay_allowed": False' in runtime
