from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/telegram-milovi-exact-canary.yml"
PREPARE = REPOSITORY_ROOT / "scripts/milovi_telegram_canary_prepare.py"
SEND = REPOSITORY_ROOT / "scripts/milovi_telegram_canary_send.py"


def test_exact_canary_is_one_file_triggered_and_persists_intent_before_send() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "content/telegram/milovi-cake/live/canary-authorization.json" in workflow
    assert "test \"${GITHUB_RUN_ATTEMPT}\" = \"1\"" in workflow
    assert workflow.index("persist canary dispatch-started barrier") < workflow.index("milovi_telegram_canary_send.py")
    assert "cancel-in-progress: false" in workflow


def test_exact_canary_send_has_zero_mutation_retry_and_no_fallback_operation() -> None:
    sender = SEND.read_text(encoding="utf-8")
    assert 'HTTPTransport(retries=0)' in sender
    assert 'sendPhoto' in sender
    assert 'sendDocument' not in sender
    assert 'sendMessage' not in sender
    assert 'dispatch_started barrier remains' in sender


def test_exact_canary_is_bound_to_recovered_target_and_transport() -> None:
    prepare = PREPARE.read_text(encoding="utf-8")
    assert 'CHAT_ID = -1002215328390' in prepare
    assert 'BOT_ID = 8716602202' in prepare
    assert 'a9730cc62939845c61191f1a375b2bab35800122c968d6cc757f0ae4340771d5' in prepare
    assert 'd712ca06f2503bbb7e483f6c8d0fe3f0067b37b834536f7f7861bb38415fa580' in prepare
    assert 'changed != [AUTH_PATH.as_posix()]' in prepare
    assert 'STATE_PATH.exists()' in prepare
