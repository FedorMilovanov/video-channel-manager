from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_custom_emoji_canary import (
    EXPECTED_BOT_ID,
    EXPECTED_BOT_USERNAME,
    EXPECTED_CHAT_ID,
    PUBLICATION_ID,
    prepare_intent,
    send_canary_once,
)
from video_channel_manager.telegram_custom_emoji_catalog import (
    build_capability_canary_html,
    load_custom_emoji_catalog,
    render_digit,
    render_role,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof
from video_channel_manager.telegram_transport import TelegramApiError

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
CATALOG_PATH = ROOT / "content/telegram/svodka/custom-emoji-catalog.json"


def _target_proof(profile_sha256: str) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="svodka",
        channel_username="@deep_info_life",
        profile_sha256=profile_sha256,
        bot_id=EXPECTED_BOT_ID,
        bot_username=EXPECTED_BOT_USERNAME,
        chat_id=EXPECTED_CHAT_ID,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 8, 10, 17, 55, tzinfo=UTC),
    )


def _write_target(path: Path, profile_sha256: str) -> None:
    path.write_text(_target_proof(profile_sha256).model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_catalog_preserves_all_verified_ids_and_curated_number_sets() -> None:
    catalog = load_custom_emoji_catalog(CATALOG_PATH)

    assert len(catalog.items) == 67
    assert catalog.source_message_ids == (12, 17, 20, 23)
    assert catalog.verification_comment_id == 5243872092
    assert catalog.provider_write_performed is False
    assert catalog.item_for_digit(1).custom_emoji_id == "5426972640587853090"
    assert catalog.item_for_digit(1, style="alternate").custom_emoji_id == "5305763715692377402"
    assert catalog.item_for_digit(1, style="compact").custom_emoji_id == "5280847291853326996"
    assert catalog.item_for_role("science.microscope").custom_emoji_id == "5379679518740978720"
    assert catalog.item_for_role("history.scroll").custom_emoji_id == "5458834606365092343"
    assert len(catalog.check_variants) == 4


def test_catalog_renders_exact_tg_emoji_fallbacks() -> None:
    catalog = load_custom_emoji_catalog(CATALOG_PATH)

    assert render_digit(catalog, 1) == (
        '<tg-emoji emoji-id="5426972640587853090">1️⃣</tg-emoji>'
    )
    assert render_role(catalog, "science.microscope") == (
        '<tg-emoji emoji-id="5379679518740978720">🔬</tg-emoji>'
    )
    html = build_capability_canary_html(catalog)
    assert html.count("<tg-emoji ") == 3
    assert "<b>СВОДКА — проверка оформления</b>" in html
    assert "<i>Исторический акцент</i>" in html


def test_prepare_intent_binds_exact_catalog_payload_and_target(tmp_path: Path) -> None:
    from video_channel_manager.telegram_channel_profile import load_channel_profile

    profile = load_channel_profile(PROFILE_PATH)
    target_path = tmp_path / "target.json"
    _write_target(target_path, profile.digest)

    intent, payload = prepare_intent(
        profile_path=PROFILE_PATH,
        catalog_path=CATALOG_PATH,
        target_proof_path=target_path,
        run_id="12345",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        now=datetime(2026, 8, 10, 17, 56, tzinfo=UTC),
    )

    assert intent.state == "intent"
    assert intent.provider_effect == "impossible"
    assert intent.chat_id == EXPECTED_CHAT_ID
    assert intent.bot_id == EXPECTED_BOT_ID
    assert intent.provider_payload_sha256 == payload.provider_payload_sha256
    assert payload.publication_id == PUBLICATION_ID
    assert [entity.custom_emoji_id for entity in payload.expected_entities if entity.type == "custom_emoji"] == [
        "5379679518740978720",
        "5426972640587853090",
        "5458834606365092343",
    ]


def test_send_canary_records_verified_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from video_channel_manager.telegram_channel_profile import load_channel_profile
    import video_channel_manager.telegram_custom_emoji_canary as module

    profile = load_channel_profile(PROFILE_PATH)
    target_path = tmp_path / "target.json"
    intent_path = tmp_path / "intent.json"
    _write_target(target_path, profile.digest)
    intent, payload = prepare_intent(
        profile_path=PROFILE_PATH,
        catalog_path=CATALOG_PATH,
        target_proof_path=target_path,
        run_id="12345",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        now=datetime(2026, 8, 10, 17, 56, tzinfo=UTC),
    )
    intent_path.write_text(intent.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def fake_send(*args: object, **kwargs: object) -> GenericSendReceipt:
        return GenericSendReceipt(
            schema_name="video-channel-manager.telegram-generic-send-receipt",
            schema_version=1,
            project_key="svodka",
            publication_id=PUBLICATION_ID,
            provider_payload_sha256=payload.provider_payload_sha256,
            chat_id=EXPECTED_CHAT_ID,
            chat_username="deep_info_life",
            message_id=777,
            message_url="https://t.me/deep_info_life/777",
            verified_at_utc=datetime(2026, 8, 10, 17, 57, tzinfo=UTC),
        )

    monkeypatch.setattr(module, "send_message_once", fake_send)
    outcome = send_canary_once(
        profile_path=PROFILE_PATH,
        catalog_path=CATALOG_PATH,
        target_proof_path=target_path,
        intent_path=intent_path,
        token="test-token",
        now=datetime(2026, 8, 10, 17, 57, tzinfo=UTC),
    )

    assert outcome.state == "verified"
    assert outcome.provider_effect == "verified"
    assert outcome.message_id == 777
    assert outcome.message_url == "https://t.me/deep_info_life/777"


def test_send_canary_fail_closes_ambiguous_provider_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from video_channel_manager.telegram_channel_profile import load_channel_profile
    import video_channel_manager.telegram_custom_emoji_canary as module

    profile = load_channel_profile(PROFILE_PATH)
    target_path = tmp_path / "target.json"
    intent_path = tmp_path / "intent.json"
    _write_target(target_path, profile.digest)
    intent, _ = prepare_intent(
        profile_path=PROFILE_PATH,
        catalog_path=CATALOG_PATH,
        target_proof_path=target_path,
        run_id="12345",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        now=datetime(2026, 8, 10, 17, 56, tzinfo=UTC),
    )
    intent_path.write_text(intent.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def fake_send(*args: object, **kwargs: object) -> GenericSendReceipt:
        raise TelegramApiError("response verification failed", provider_effect="may_exist")

    monkeypatch.setattr(module, "send_message_once", fake_send)
    outcome = send_canary_once(
        profile_path=PROFILE_PATH,
        catalog_path=CATALOG_PATH,
        target_proof_path=target_path,
        intent_path=intent_path,
        token="test-token",
        now=datetime(2026, 8, 10, 17, 57, tzinfo=UTC),
    )

    assert outcome.state == "unknown"
    assert outcome.provider_effect == "may_exist"
    assert outcome.message_id is None
    assert outcome.message_url is None
    assert outcome.error == "response verification failed"
