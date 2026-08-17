from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / ".github/workflows/milovi-telegram-bootstrap-publisher.yml"
QUALITY = ROOT / ".github/workflows/milovi-telegram-bootstrap-quality.yml"
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
QUEUE = ROOT / "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
HISTORICAL_ROLLOUT = "content/telegram/milovi-cake/bootstrap-rollout-candidate-2026-08.json"
OPERATIONAL_QUEUE = "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
AUTHORIZED_RELEASE = ROOT / "content/telegram/milovi-cake/bootstrap-authorized-release-2026-08.json"
TARGET_BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"


def test_publisher_and_quality_compile_the_same_operational_queue() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    quality = QUALITY.read_text(encoding="utf-8")

    assert publisher.count(f"ROLLOUT_PATH: {OPERATIONAL_QUEUE}") == 1
    assert quality.count(f"ROLLOUT_PATH: {OPERATIONAL_QUEUE}") == 1
    assert HISTORICAL_ROLLOUT not in publisher
    assert HISTORICAL_ROLLOUT not in quality


def test_operational_queue_stays_inert_while_separate_release_gate_is_exact() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    binding = json.loads(TARGET_BINDING.read_text(encoding="utf-8"))
    release = json.loads(AUTHORIZED_RELEASE.read_text(encoding="utf-8"))

    assert profile["provider_writes_authorized"] is True
    assert queue["execution_authorized"] is False
    assert queue["provider_mutation_allowed"] is False
    assert binding["provider_write_performed"] is False
    assert release["release_authorized"] is True
    assert release["target_binding_sha256"] == (
        "sha256:741a8b4b54d785976236c6f15ed5d82cc9ad46aeb96a80cf372f22c421ba047c"
    )
    assert release["reviewed_candidate_sha256"] == (
        "sha256:d2d574e7480d6e5d76c9e5fad15bc00cdd0af04703d0039059f7705a828cf9dc"
    )


def test_publisher_still_gates_before_telegram_secret_usage() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    activation = publisher.index("Resolve fail-closed activation and daylight gate")
    inactive_report = publisher.index("Report inactive bootstrap scheduler")
    telegram_secret = publisher.index("MILOVI_CAKE_TELEGRAM_BOT_TOKEN")
    preflight = publisher.index("Fresh exact target preflight")
    send_once = publisher.index("Send exactly once through generic Telegram runtime")

    assert activation < inactive_report < preflight < telegram_secret < send_once
    assert "outside_09_00_21_00_moscow_window" in publisher
    assert "profile_write_gate_disabled" in publisher
