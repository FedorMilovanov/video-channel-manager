from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CANONICAL = "milovi-telegram-feed-publisher.yml"
MUTATION_MARKER = "python -m video_channel_manager.telegram_multichannel_cli " + "send-once"
RETIRED = {
    "milovi-telegram-bootstrap-activation-package.yml",
    "milovi-telegram-bootstrap-media-proof.yml",
    "milovi-telegram-bootstrap-publisher.yml",
    "milovi-telegram-bootstrap-quality.yml",
    "milovi-telegram-bootstrap-review-ready.yml",
    "milovi-telegram-ledger-init.yml",
    "milovi-telegram-live-canary-v2-dispatch.yml",
    "milovi-telegram-live-canary-v2-quality.yml",
    "milovi-telegram-live-canary-v2.yml",
    "milovi-telegram-oneoff-canary-dispatch.yml",
    "milovi-telegram-oneoff-canary-quality.yml",
    "milovi-telegram-oneoff-canary.yml",
    "milovi-feed-20260819-001-controller.yml",
    "milovi-feed-20260819-001-media-proof.yml",
    "milovi-feed-20260819-001-quality.yml",
    "milovi-telegram-follow-on-media-proof.yml",
    "milovi-telegram-follow-on-readiness.yml",
}


def test_retired_milovi_operational_surfaces_are_physically_absent() -> None:
    assert all(not (WORKFLOWS / name).exists() for name in RETIRED)


def test_discovery_finds_exactly_one_milovi_provider_mutation_workflow() -> None:
    mutation_paths: list[str] = []
    for path in sorted(WORKFLOWS.glob("*milovi*.yml")):
        text = path.read_text(encoding="utf-8")
        if MUTATION_MARKER in text:
            mutation_paths.append(path.name)
    assert mutation_paths == [CANONICAL]


def test_canonical_writer_owns_one_state_and_concurrency_namespace() -> None:
    text = (WORKFLOWS / CANONICAL).read_text(encoding="utf-8")

    assert "group: milovi-cake-telegram-publisher" in text
    assert "state/milovi-cake-telegram" in text
    assert "content/telegram/milovi-cake/feed/index.json" in text
    assert "require-execution-authorized" in text
    assert "telegram_multichannel_cli prepare" in text
    assert "sync-index" in text
    assert MUTATION_MARKER in text
    assert text.index("telegram_multichannel_cli prepare") < text.index("telegram_multichannel_cli send-once")
    assert "schedule:" not in text
    assert "cron:" not in text


def test_read_only_target_discovery_does_not_become_a_second_writer() -> None:
    discovery = WORKFLOWS / "milovi-telegram-target-discovery.yml"
    assert discovery.is_file()
    text = discovery.read_text(encoding="utf-8")
    assert "discover-target" in text
    assert "provider_writes_authorized" not in text
    assert MUTATION_MARKER not in text

    implementation = (
        ROOT / "src" / "video_channel_manager" / "telegram_channel_discovery.py"
    ).read_text(encoding="utf-8")
    assert 'method="getMe"' in implementation
    assert implementation.count('method="getChat"') == 4
    assert 'method="getChatMember"' in implementation
    assert implementation.count("mutation=False") == 4
    assert "mutation=True" not in implementation
    for forbidden_method in (
        "sendMessage",
        "sendPhoto",
        "sendMediaGroup",
        "editMessage",
        "deleteMessage",
    ):
        assert forbidden_method not in implementation
