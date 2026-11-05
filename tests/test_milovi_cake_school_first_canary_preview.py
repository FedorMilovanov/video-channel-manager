"""A Milovi School canary preview must never masquerade as VK posting authority."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "content/editorial/milovi-cake/vk-school-first-canary-preview-20261105.json"
EDITORIAL_PATH = ROOT / "content/editorial/milovi-cake/vk-school-wave-20261105.md"


def test_canary_is_exact_milovi_source_and_plain_text_only() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    editorial = EDITORIAL_PATH.read_text(encoding="utf-8")
    source_id = "tech-mirror-glaze"
    canonical_url = f"https://french.milovicake.ru/articles/{source_id}/"
    marker = f"Source ID: `{source_id}`"
    assert editorial.count(marker) == 1
    excerpt = editorial.split(marker, 1)[1].split("\n---", 1)[0]
    assert excerpt.count("**") == 2
    reviewed_message = excerpt.split("**", 2)[2].strip()

    assert plan["schema_name"] == "video-manager.milovi-school-vk-wall-canary-preview"
    assert plan["schema_version"] == 1
    assert plan["package_kind"] == "editorial_bundle"
    assert plan["truth_level"] == "editorial_prepared"
    assert plan["owner_issue"] == 792
    assert plan["project_key"] == "milovi-cake"
    assert plan["community_id"] == 68859909
    assert plan["owner_id"] == -68859909
    assert plan["credential_alias_for_later_execution"] == "vk-milovi-cake-community-key"
    assert plan["source_article_id"] == source_id
    assert plan["source_article_url"] == canonical_url
    assert plan["message"] == reviewed_message
    assert plan["message"].count(canonical_url) == 1
    assert plan["message"].endswith("#MiloviSchool")
    assert plan["attachment_tokens"] == []
    assert plan["message_sha256"] == hashlib.sha256(reviewed_message.encode("utf-8")).hexdigest()
    assert plan["editorial_source_sha256"] == hashlib.sha256(editorial.encode("utf-8")).hexdigest()


def test_canary_slot_and_guid_are_stable_and_not_dispatched() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    intended = datetime(2026, 11, 7, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    source = plan["source_article_id"]
    unix = int(intended.timestamp())
    expected_guid = (
        "vcm-milovi-school-" + hashlib.sha256(f"milovi-cake:school:{source}:{unix}".encode("utf-8")).hexdigest()[:20]
    )

    assert plan["publication_surface"] == "vk_wall_postponed"
    assert plan["publish_at_msk"] == intended.isoformat()
    assert datetime.fromisoformat(plan["publish_at_utc"].replace("Z", "+00:00")) == intended
    assert plan["publish_date_unix"] == unix
    assert plan["guid"] == expected_guid
    assert plan["preflight_evidence"]["public_wall_post_count"] == 162
    assert plan["preflight_evidence"]["exact_school_urls_found"] == 0
    assert plan["preflight_evidence"]["public_wall_audit_sha256"] == (
        "7204742b1b7888c9bbf3fb702290bdfc180beac254ab9246c9e0c05f276d8815"
    )
    assert plan["preflight_evidence"]["native_vk_articles_public_catalog"].startswith("empty_observed_")
    assert plan["preflight_evidence"]["native_vk_articles_drafts"] == "not_checked"
    assert plan["preflight_evidence"]["postponed_posts"] == "owner_reported_empty_not_machine_verified"
    assert len(plan["required_execution_gates"]) >= 7
    assert plan["provider_adapter_connected"] is False
    assert plan["provider_writes_authorized"] is False
    assert plan["automatic_execution"] is False
    assert plan["operator_execution_approval"] == "not_granted"
    assert plan["provider_effect_state"] == "not_dispatched"
    assert plan["release_eligible"] is False
