from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_follow_on import (
    EXPECTED_ITEM_COUNT,
    EXPECTED_MESSAGE_COUNT,
    EXPECTED_PHOTO_COUNT,
    build_readiness_template,
    build_release_candidate,
    materialize_exact_photo,
    validate_follow_on_bundle,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload, GenericPhotoPayload

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
CANDIDATES = ROOT / "content/telegram/milovi-cake/follow-on-wave-candidates-2026-08.json"
TRANSPORT = ROOT / "content/telegram/milovi-cake/follow-on-photo-source-manifest-2026-08.json"
POLICY = ROOT / "content/telegram/milovi-cake/follow-on-release-policy-2026-08.json"


def _profile():
    return load_channel_profile(PROFILE)


def _bundle(profile=None):
    return validate_follow_on_bundle(
        profile or _profile(),
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
    )


def _write_ready_receipt(
    tmp_path: Path,
    *,
    bootstrap_verified_at: str = "2026-08-16T20:05:00+03:00",
    source_revalidated_at: str = "2026-08-17T07:50:00+03:00",
) -> Path:
    candidates, transport, policy = _bundle()
    receipt = build_readiness_template(candidates=candidates, transport=transport, policy=policy)
    receipt.update(
        {
            "status": "verified_current_sources",
            "bootstrap_terminal_status": "verified",
            "bootstrap_final_verified_at": bootstrap_verified_at,
            "source_revalidated_at": source_revalidated_at,
        }
    )
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _build(tmp_path: Path, *, now: str = "2026-08-17T08:00:00+03:00"):
    return build_release_candidate(
        _profile(),
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        readiness_receipt_path=_write_ready_receipt(tmp_path),
        now=datetime.fromisoformat(now),
    )


def test_bundle_is_exactly_nine_cake_photos_three_school_messages_and_provider_inert() -> None:
    candidates, transport, policy = _bundle()
    assert len(candidates["items"]) == EXPECTED_ITEM_COUNT == 12
    assert transport["photo_count"] == EXPECTED_PHOTO_COUNT == 9
    assert transport["transport_ready_count"] == 9
    assert policy["required_revalidation_publication_ids"] == [
        "milovi-follow-on-002",
        "milovi-follow-on-003",
        "milovi-follow-on-004",
        "milovi-follow-on-006",
        "milovi-follow-on-007",
        "milovi-follow-on-009",
        "milovi-follow-on-011",
    ]
    assert candidates["execution_authorized"] is False
    assert candidates["provider_mutation_allowed"] is False
    assert transport["provider_mutation_allowed"] is False
    assert policy["provider_mutation_allowed"] is False
    assert policy["compiler_may_access_telegram_provider"] is False


def test_readiness_template_is_explicitly_not_verified_or_authorized() -> None:
    candidates, transport, policy = _bundle()
    template = build_readiness_template(candidates=candidates, transport=transport, policy=policy)
    assert template["status"] == "requires_fresh_external_verification"
    assert template["bootstrap_terminal_status"] == "requires_exact_state_read"
    assert template["bootstrap_final_verified_at"] is None
    assert template["source_revalidated_at"] is None
    assert template["provider_write_performed"] is False
    assert template["telegram_provider_accessed"] is False
    assert template["execution_authorized"] is False
    assert template["provider_mutation_allowed"] is False


def test_release_candidate_starts_on_next_daylight_slot_and_remains_unauthorized(tmp_path: Path) -> None:
    release = _build(tmp_path)
    assert len(release.items) == 12
    assert release.items[0].scheduled_at.isoformat() == "2026-08-17T10:30:00+03:00"
    assert [item.scheduled_at.strftime("%H:%M") for item in release.items] == ["10:30", "20:00"] * 6
    assert all(item.scheduled_at > datetime.fromisoformat("2026-08-17T08:00:00+03:00") for item in release.items)
    assert release.daily_verified_limit == 2
    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert release.chat_id is None
    assert release.bot_id is None
    assert release.bot_username is None


def test_release_candidate_uses_generic_exact_photo_and_message_payloads(tmp_path: Path) -> None:
    release = _build(tmp_path)
    photos = [item.payload for item in release.items if isinstance(item.payload, GenericPhotoPayload)]
    messages = [item.payload for item in release.items if isinstance(item.payload, GenericMessagePayload)]
    assert len(photos) == EXPECTED_PHOTO_COUNT
    assert len(messages) == EXPECTED_MESSAGE_COUNT
    assert photos[0].publication_id == "milovi-follow-on-001"
    assert photos[0].media_path == ".runtime/milovi-telegram-follow-on/media/p06.jpg"
    assert photos[0].media_sha256 == "sha256:e8a48c819550a7e914f81fe7f7f30d27d9412d72744dc1d93c109989ab86770a"
    assert photos[0].media_byte_size == 537768
    assert messages[0].publication_id == "milovi-follow-on-003"
    assert "Читать в нашем проекте Milovi School" in messages[0].expected_plain_text
    assert messages[0].link_preview_disabled is True


def test_exact_twenty_hundred_anchor_never_catches_up_same_slot(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(
        tmp_path,
        bootstrap_verified_at="2026-08-17T19:55:00+03:00",
        source_revalidated_at="2026-08-17T19:58:00+03:00",
    )
    release = build_release_candidate(
        _profile(),
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        readiness_receipt_path=receipt,
        now=datetime.fromisoformat("2026-08-17T20:00:00+03:00"),
    )
    assert release.items[0].scheduled_at.isoformat() == "2026-08-18T10:30:00+03:00"


def test_after_twenty_hundred_anchor_starts_next_morning(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(
        tmp_path,
        bootstrap_verified_at="2026-08-17T20:01:00+03:00",
        source_revalidated_at="2026-08-17T20:02:00+03:00",
    )
    release = build_release_candidate(
        _profile(),
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        readiness_receipt_path=receipt,
        now=datetime.fromisoformat("2026-08-17T20:03:00+03:00"),
    )
    assert release.items[0].scheduled_at.isoformat() == "2026-08-18T10:30:00+03:00"


def test_stale_source_revalidation_receipt_fails_closed(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(tmp_path, source_revalidated_at="2026-08-17T06:59:00+03:00")
    with pytest.raises(ValueError, match="stale"):
        build_release_candidate(
            _profile(),
            candidates_path=CANDIDATES,
            transport_manifest_path=TRANSPORT,
            policy_path=POLICY,
            readiness_receipt_path=receipt,
            now=datetime.fromisoformat("2026-08-17T08:00:00+03:00"),
        )


def test_future_source_revalidation_receipt_fails_closed(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(tmp_path, source_revalidated_at="2026-08-17T08:06:00+03:00")
    with pytest.raises(ValueError, match="future"):
        build_release_candidate(
            _profile(),
            candidates_path=CANDIDATES,
            transport_manifest_path=TRANSPORT,
            policy_path=POLICY,
            readiness_receipt_path=receipt,
            now=datetime.fromisoformat("2026-08-17T08:00:00+03:00"),
        )


def test_unverified_bootstrap_terminal_status_fails_closed(tmp_path: Path) -> None:
    candidates, transport, policy = _bundle()
    receipt = build_readiness_template(candidates=candidates, transport=transport, policy=policy)
    receipt.update(
        {
            "status": "verified_current_sources",
            "bootstrap_terminal_status": "pending",
            "bootstrap_final_verified_at": "2026-08-16T20:05:00+03:00",
            "source_revalidated_at": "2026-08-17T07:50:00+03:00",
        }
    )
    path = tmp_path / "pending-bootstrap.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="bootstrap terminal status"):
        build_release_candidate(
            _profile(),
            candidates_path=CANDIDATES,
            transport_manifest_path=TRANSPORT,
            policy_path=POLICY,
            readiness_receipt_path=path,
            now=datetime.fromisoformat("2026-08-17T08:00:00+03:00"),
        )


def test_candidate_drift_after_readiness_receipt_fails_closed(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(tmp_path)
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    payload["items"][0]["caption"] += " Подмена."
    changed = tmp_path / "changed-candidates.json"
    changed.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="readiness candidate digest"):
        build_release_candidate(
            _profile(),
            candidates_path=changed,
            transport_manifest_path=TRANSPORT,
            policy_path=POLICY,
            readiness_receipt_path=receipt,
            now=datetime.fromisoformat("2026-08-17T08:00:00+03:00"),
        )


def test_transport_drift_after_readiness_receipt_fails_closed(tmp_path: Path) -> None:
    receipt = _write_ready_receipt(tmp_path)
    payload = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    payload["photos"][0]["transport_byte_size"] += 1
    changed = tmp_path / "changed-transport.json"
    changed.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="readiness media manifest digest"):
        build_release_candidate(
            _profile(),
            candidates_path=CANDIDATES,
            transport_manifest_path=changed,
            policy_path=POLICY,
            readiness_receipt_path=receipt,
            now=datetime.fromisoformat("2026-08-17T08:00:00+03:00"),
        )


def test_provider_write_gate_does_not_change_unauthorized_release_identity(tmp_path: Path) -> None:
    inert_profile = _profile()
    active_profile = inert_profile.model_copy(update={"provider_writes_authorized": True})
    receipt = _write_ready_receipt(tmp_path)
    now = datetime.fromisoformat("2026-08-17T08:00:00+03:00")
    inert_release = build_release_candidate(
        inert_profile,
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        readiness_receipt_path=receipt,
        now=now,
    )
    active_release = build_release_candidate(
        active_profile,
        candidates_path=CANDIDATES,
        transport_manifest_path=TRANSPORT,
        policy_path=POLICY,
        readiness_receipt_path=receipt,
        now=now,
    )
    assert inert_profile.digest == active_profile.digest
    assert inert_release.items == active_release.items
    assert inert_release.candidate_digest() == active_release.candidate_digest()
    assert active_release.release_authorized is False


def test_unknown_media_id_is_rejected_before_source_file_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown Milovi follow-on media_id"):
        materialize_exact_photo(
            transport_manifest_path=TRANSPORT,
            media_id="p99",
            source_path=tmp_path / "does-not-exist.webp",
            output_path=tmp_path / "out.jpg",
        )
