from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-follow-on-readiness.yml"


def test_follow_on_readiness_runs_on_current_main_relevant_changes_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "  workflow_dispatch:" in text
    assert "  push:" in text
    assert "    branches:\n      - main" in text
    assert '      - ".github/workflows/milovi-telegram-follow-on-readiness.yml"' in text
    assert '      - "src/video_channel_manager/milovi_telegram_follow_on_readiness.py"' in text
    assert '      - "content/telegram/channels/milovi-cake.json"' in text
    assert '      - "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"' in text
    assert '      - "content/telegram/milovi-cake/follow-on-wave-candidates-2026-08.json"' in text
    assert '      - "content/telegram/milovi-cake/follow-on-photo-source-manifest-2026-08.json"' in text
    assert '      - "content/telegram/milovi-cake/follow-on-release-policy-2026-08.json"' in text
    assert '      - "content/telegram/milovi-cake/school-interest-reading-candidates-2026-08.json"' in text
    assert "schedule:" not in text


def test_follow_on_readiness_push_trigger_stays_provider_inert() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in text
    assert "persist-credentials: false" in text
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "api.telegram.org" not in text
    assert "sendPhoto" not in text
    assert "sendMessage" not in text
    assert "git push" not in text
    assert "contents: write" not in text
