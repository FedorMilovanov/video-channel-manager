from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/operations"
REGISTRY = DOCS / "milovi-cake-telegram-acquisition-registry-2026-08-15.json"
LEDGER = DOCS / "milovi-cake-telegram-acquisition-experiments-2026-08-15.json"
PLAYBOOK = DOCS / "milovi-cake-telegram-growth-2026-08-15.md"

EXPECTED_FIXED_SOURCE_IDS = {
    "tg-site-gallery",
    "tg-site-footer",
    "tg-vk-organic",
    "tg-youtube-organic",
    "tg-dzen-organic",
    "tg-box",
    "tg-client",
}


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_acquisition_registry_is_provider_inert_and_has_unique_fixed_sources() -> None:
    registry = _load_json(REGISTRY)
    sources = registry["fixed_sources"]

    assert registry["schema_name"] == "video-channel-manager.milovi-telegram-acquisition-registry"
    assert registry["project_key"] == "milovi-cake"
    assert registry["owning_issue"] == 353
    assert registry["status"] == "provider_inert"
    assert registry["channel_username"] == "@MiloviCake"
    assert registry["public_route"] == "https://t.me/MiloviCake"
    assert registry["provider_write_authorized"] is False
    assert registry["invite_link_creation_authorized"] is False

    source_ids = [source["source_id"] for source in sources]
    assert len(source_ids) == len(set(source_ids))
    assert set(source_ids) == EXPECTED_FIXED_SOURCE_IDS

    for source in sources:
        assert source["invite_url"] is None
        assert source["invite_link_fingerprint"] is None
        assert source["provider_state"] == "not_created"
        assert source["activation_authorized"] is False
        assert source["measurement_method"] is None
        assert source["purpose"]


def test_acquisition_registry_separates_publishing_rights_from_invite_link_rights() -> None:
    registry = _load_json(REGISTRY)
    policy = registry["provider_rights_policy"]

    assert policy["shared_posting_bot_id"] == 8716602202
    assert policy["shared_posting_bot_username"] == "preaching_mp3_bot"
    assert policy["automatic_invite_rights_escalation_allowed"] is False
    assert policy["preferred_invite_creation_actor"].startswith("manual_channel_admin")
    assert "can_invite_users" in policy["rule"]
    assert "separate provider mutation" in policy["rule"]


def test_acquisition_registry_has_exact_dynamic_namespaces_without_fake_partners() -> None:
    registry = _load_json(REGISTRY)
    namespaces = registry["dynamic_source_namespaces"]

    assert namespaces == [
        {
            "pattern": "tg-partner-<slug>",
            "source_class": "partner",
            "rule": "Instantiate one source only for a named, reviewed partner. Never use one generic partner link across unrelated partners.",
        },
        {
            "pattern": "tg-placement-<slug>-<yyyymm>",
            "source_class": "paid_placement",
            "rule": "Instantiate one source for one paid placement test and period. Preserve it after closure; never recycle it for another channel or later buy.",
        },
    ]

    serialized = json.dumps(registry, ensure_ascii=False)
    assert "example-partner" not in serialized
    assert "example-channel" not in serialized


def test_acquisition_experiment_ledger_starts_empty_without_invented_baseline() -> None:
    ledger = _load_json(LEDGER)
    baseline = ledger["baseline"]
    rules = ledger["measurement_rules"]

    assert ledger["schema_name"] == "video-channel-manager.milovi-telegram-acquisition-experiments"
    assert ledger["project_key"] == "milovi-cake"
    assert ledger["owning_issue"] == 353
    assert ledger["status"] == "provider_inert_empty_ledger"
    assert ledger["provider_write_authorized"] is False
    assert ledger["experiments"] == []

    assert baseline["captured_at"] is None
    assert baseline["subscriber_count"] is None
    assert baseline["evidence_ref"] is None
    assert "remembered or approximate" in baseline["rule"]

    assert rules["raw_join_count_is_success"] is False
    assert rules["measurement_method_required_before_activation"] is True
    assert "missing data to zero" in rules["nullable_metric_rule"]
    assert "timing alone" in rules["attribution_rule"]
    assert rules["decision_values"] == ["keep", "iterate", "stop", "inconclusive"]
    assert rules["decision_requires_evidence"] is True


def test_growth_playbook_matches_current_no_bts_exact_member_discovery_state() -> None:
    playbook = PLAYBOOK.read_text(encoding="utf-8")

    assert "getChatMember(chat_id, user_id=<proved bot id>)" in playbook
    assert "`getMe`, `getChat`, `getChatMember`" in playbook
    assert "getChatAdministrators" not in playbook

    assert "Production/kitchen/BTS footage is currently unavailable" in playbook
    assert "production BTS/kitchen share = 0%" in playbook
    assert "Новые работы и подборки — в Telegram" in playbook
    assert "Новые работы и идеи Milovi Cake" in playbook
    assert "Новые работы и процесс — в Telegram" not in playbook
    assert "Новые работы и закулисье Milovi Cake" not in playbook

    assert "milovi-cake-telegram-acquisition-registry-2026-08-15.json" in playbook
    assert "milovi-cake-telegram-acquisition-experiments-2026-08-15.json" in playbook
    assert "accepted native-video outputs remain **0 / 16**" in playbook

    for merged_pr in ("#354", "#356", "#358", "#360", "#361"):
        assert merged_pr in playbook

    assert "Do not rerun the historical failed workflow run" in playbook
    assert "no invite links are created by this playbook" in playbook


def test_growth_control_plane_requires_evidence_before_source_activation() -> None:
    registry = _load_json(REGISTRY)
    ledger = _load_json(LEDGER)
    prerequisites = registry["activation_prerequisites"]
    required_fields = set(registry["required_measurement_fields"])

    assert any("canary" in gate and "provider-verified" in gate for gate in prerequisites)
    assert any("measurement method" in gate for gate in prerequisites)
    assert {
        "experiment_id",
        "source_id",
        "measurement_method",
        "started_at",
        "ended_at",
        "spend_rub",
        "attributed_joins",
        "evidence_refs",
        "decision",
    } <= required_fields

    schema = ledger["experiment_schema"]
    assert "must exist in the source registry" in schema["source_id"]
    assert "required before active" in schema["measurement_method"]
    assert "exact post/page/QR/partner placement identifier" in schema["content_or_placement_ref"]
    assert "keep | iterate | stop | inconclusive" in schema["decision"]
