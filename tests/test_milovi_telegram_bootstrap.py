from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_bootstrap import (
    EXPECTED_ITEM_COUNT,
    EXPECTED_MESSAGE_COUNT,
    EXPECTED_PHOTO_COUNT,
    build_release_candidate,
    validate_bootstrap_bundle,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericPhotoPayload,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
ROLLOUT = ROOT / "content/telegram/milovi-cake/bootstrap-rollout-candidate-2026-08.json"
CANDIDATES = ROOT / "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json"
PROOF = ROOT / "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json"
WINDOW = ROOT / "content/telegram/milovi-cake/publishing-window-2026-08.json"


def _profile():
    return load_channel_profile(PROFILE)


def _build(profile=None):
    return build_release_candidate(
        profile or _profile(),
        rollout_path=ROLLOUT,
        candidates_path=CANDIDATES,
        transport_proof_path=PROOF,
        publishing_window_path=WINDOW,
    )


def test_profile_matches_exact_canary_activation_contract() -> None:
    profile = _profile()
    assert profile.publication_id_prefix == "milovi-"
    assert profile.daily_verified_limit == 2
    assert profile.state_branch == "state/milovi-cake-telegram"
    assert profile.concurrency_group == "milovi-cake-telegram-publisher"
    assert profile.provider_writes_authorized is True


def test_provider_write_gate_does_not_change_reviewed_channel_or_payload_identity() -> None:
    active_profile = _profile()
    inert_profile = active_profile.model_copy(update={"provider_writes_authorized": False})

    assert inert_profile.digest == active_profile.digest
    inert_release = _build(inert_profile)
    active_release = _build(active_profile)
    assert inert_release.profile_sha256 == active_release.profile_sha256 == active_profile.digest
    assert inert_release.items == active_release.items
    assert active_release.release_authorized is False


def test_frozen_bundle_validates_exact_two_by_five_daylight_grid() -> None:
    rollout, candidates, proof, window = validate_bootstrap_bundle(
        _profile(),
        rollout_path=ROLLOUT,
        candidates_path=CANDIDATES,
        transport_proof_path=PROOF,
        publishing_window_path=WINDOW,
    )
    assert len(rollout["items"]) == EXPECTED_ITEM_COUNT == 10
    assert len(candidates["candidates"]) == 10
    assert proof["photo_count"] == EXPECTED_PHOTO_COUNT == 9
    assert window["earliest_publication_local"] == "09:00"
    assert window["latest_publication_local"] == "21:00"
    assert window["bootstrap_slots_local"] == ["10:30", "20:00"]
    assert window["max_publication_lag_minutes"] == 120
    assert [item["planned_local"][11:16] for item in rollout["items"]] == ["10:30", "20:00"] * 5
    assert rollout["execution_authorized"] is False
    assert rollout["provider_mutation_allowed"] is False


def test_release_candidate_contains_nine_exact_photos_and_one_message_and_is_unauthorized() -> None:
    release = _build()
    photos = [item.payload for item in release.items if isinstance(item.payload, GenericPhotoPayload)]
    messages = [item.payload for item in release.items if isinstance(item.payload, GenericMessagePayload)]
    assert len(release.items) == 10
    assert len(photos) == EXPECTED_PHOTO_COUNT
    assert len(messages) == EXPECTED_MESSAGE_COUNT
    assert release.daily_verified_limit == 2
    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert release.chat_id is None
    assert release.bot_id is None
    assert release.bot_username is None
    assert photos[0].publication_id == "milovi-bootstrap-001"
    assert photos[0].media_sha256 == "sha256:6243a8a0b12f31b7c8fdf6f4147bff125c27ce69417cec4d54d7016c702c13c1"
    assert photos[0].media_byte_size == 516172
    assert messages[0].publication_id == "milovi-bootstrap-008"


def test_first_screen_has_no_school_or_french_linkage() -> None:
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    joined = "\n".join(item["caption"] for item in payload["candidates"]).casefold()
    assert "milovi school" not in joined
    assert "french.milovicake.ru" not in joined
    assert "француз" not in joined
    assert payload["school_items_in_first_screen"] == 0


def test_caption_drift_is_rejected_before_release_build(tmp_path: Path) -> None:
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    payload["candidates"][0]["caption"] += " Подмена."
    mutated = tmp_path / "candidates.json"
    mutated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="caption digest"):
        validate_bootstrap_bundle(
            _profile(),
            rollout_path=ROLLOUT,
            candidates_path=mutated,
            transport_proof_path=PROOF,
            publishing_window_path=WINDOW,
        )


def test_media_transport_drift_is_rejected_before_release_build(tmp_path: Path) -> None:
    payload = json.loads(PROOF.read_text(encoding="utf-8"))
    payload["photos"][0]["transport_byte_size"] += 1
    mutated = tmp_path / "proof.json"
    mutated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="transport size"):
        validate_bootstrap_bundle(
            _profile(),
            rollout_path=ROLLOUT,
            candidates_path=CANDIDATES,
            transport_proof_path=mutated,
            publishing_window_path=WINDOW,
        )


def test_schedule_drift_off_frozen_slots_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(ROLLOUT.read_text(encoding="utf-8"))
    payload["items"][0]["planned_local"] = "2026-08-16T11:00:00+03:00"
    mutated = tmp_path / "rollout.json"
    mutated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="slot grid"):
        validate_bootstrap_bundle(
            _profile(),
            rollout_path=mutated,
            candidates_path=CANDIDATES,
            transport_proof_path=PROOF,
            publishing_window_path=WINDOW,
        )


def test_historical_canary_is_not_part_of_new_bootstrap_release() -> None:
    release = _build()
    assert "milovi-cake-canary-001" not in {item.publication_id for item in release.items}
