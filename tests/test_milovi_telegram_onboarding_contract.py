from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
WORKFLOW = ROOT / ".github/workflows/milovi-telegram-target-discovery.yml"
RETIRED_GENERIC_WORKFLOW = ROOT / ".github/workflows/telegram-generic-target-discovery.yml"
LAUNCH_PACK = ROOT / "content/telegram/milovi-cake/launch-pack-2026-08.md"
ASSET_CONTRACT = ROOT / "content/telegram/milovi-cake/editorial-asset-contract-2026-08.md"


def test_milovi_discovery_profile_is_exact_and_write_disabled() -> None:
    profile = load_channel_profile(PROFILE)

    assert profile.project_key == "milovi-cake"
    assert profile.channel_username == "@MiloviCake"
    assert profile.provider_writes_authorized is False
    assert profile.bot_token_env == "MILOVI_CAKE_TELEGRAM_BOT_TOKEN"
    assert profile.target_chat_id_env == "MILOVI_CAKE_TELEGRAM_CHAT_ID"
    assert profile.state_branch == "state/milovi-cake-telegram"
    assert profile.concurrency_group == "milovi-cake-telegram-publisher"


def test_milovi_target_discovery_workflow_is_narrow_and_read_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "PROFILE_PATH: content/telegram/channels/milovi-cake.json" in workflow
    assert "EXPECTED_CHAT_ID: -1002215328390" in workflow
    assert "EXPECTED_BOT_ID: 8716602202" in workflow
    assert "EXPECTED_BOT_USERNAME: preaching_mp3_bot" in workflow
    assert "Require write-disabled exact Milovi profile" in workflow
    assert "Milovi profile must remain provider-write-disabled during target discovery" in workflow
    assert "discover-target" in workflow
    assert "telegram_target_binding_cli" in workflow

    # Provider mutations are intentionally absent from the onboarding workflow.
    for forbidden in (
        "sendMessage",
        "sendPoll",
        "editMessage",
        "deleteMessage",
        "provider_writes_authorized=true",
        "provider_writes_authorized: true",
    ):
        assert forbidden not in workflow

    # The shared bot token is exposed only to the single provider-read step,
    # never to checkout/setup/install/profile-validation steps or job-wide env.
    discovery_marker = "- name: Discover exact target without provider mutation"
    before_discovery, discovery_and_after = workflow.split(discovery_marker, maxsplit=1)
    assert "MILOVI_CAKE_TELEGRAM_BOT_TOKEN" not in before_discovery
    assert discovery_and_after.count("MILOVI_CAKE_TELEGRAM_BOT_TOKEN") == 1

    # Milovi onboarding must not expose unrelated channel choices.
    assert "@lord_god_strength" not in workflow
    assert "deep_info_life" not in workflow
    assert "lordchrist.json" not in workflow
    assert "svodka.json" not in workflow
    assert not RETIRED_GENERIC_WORKFLOW.exists()


def test_launch_pack_has_no_known_rejected_review_placeholders() -> None:
    launch_pack = LAUNCH_PACK.read_text(encoding="utf-8")

    for rejected_name in ("Мария К.", "Ольга Н.", "Екатерина С.", "Анна П.", "Светлана Р."):
        assert rejected_name not in launch_pack

    for verified_name in (
        "Евгения Монтихо",
        "Жанель",
        "Ирина Силантьева",
        "Екатерина Гарсес Еникеева",
        "Татьяна",
    ):
        assert verified_name in launch_pack

    assert "no first-person Victoria copy" in launch_pack
    assert "provider-inert / review only" in launch_pack


def test_milovi_asset_contract_uses_finished_media_and_prohibits_fake_bts() -> None:
    contract = ASSET_CONTRACT.read_text(encoding="utf-8")

    assert "finished cake photographs" in contract
    assert "finished cake videos" in contract
    assert "Production BTS / kitchen share: **0%**" in contract
    assert "do **not** plan, promise, stage or publish" in contract
    assert "kitchen footage" in contract
    assert "behind-the-scenes / BTS production footage" in contract
    assert "The current kitchen is not an editorial asset" in contract
    assert "45% finished-work showcase" in contract
    assert "20% finished-work detail/design breakdowns" in contract
