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
    assert "dispatch_started barrier remains" in runtime


def test_exact_canary_is_bound_to_recovered_target_and_transport() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "CHAT_ID = -1002215328390" in runtime
    assert "BOT_ID = 8716602202" in runtime
    assert "a9730cc62939845c61191f1a375b2bab35800122c968d6cc757f0ae4340771d5" in runtime
    assert "d712ca06f2503bbb7e483f6c8d0fe3f0067b37b834536f7f7861bb38415fa580" in runtime
    assert "changed != [AUTH_PATH.as_posix()]" in runtime
    assert "STATE_PATH.exists()" in runtime
