from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericPhotoPayload, render_photo_payload
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
RELEASE = ROOT / "content/telegram/milovi-cake/oneoff-canary-authorized-release-2026-08-18-v2.json"
AUTH = ROOT / "content/telegram/milovi-cake/oneoff-canary-execution-authorization-2026-08-18-v2.json"
HISTORICAL_AUTH = ROOT / "content/telegram/milovi-cake/oneoff-canary-execution-authorization-2026-08-18.json"


def test_live_canary_v2_release_is_exact_and_recomputed() -> None:
    profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, profile)
    release = load_release(RELEASE)

    assert release.release_id == "milovi-oneoff-canary-2026-08-18-v2"
    assert release.digest == "sha256:7d85bad0c335a4c6a8dd745226661aba8867cc103b5e16bf9ffe4c063b7e2eae"
    assert release.reviewed_candidate_sha256 == (
        "sha256:357fad009dbeedebc4af61390d3603bb9fd959a5617e9e367b3a0ee0b2d77f08"
    )
    assert release.release_authorized is True
    assert release.target_binding_sha256 == binding.digest
    assert len(release.items) == 1

    item = release.items[0]
    assert item.publication_id == "milovi-canary-20260818-002"
    assert item.scheduled_at.isoformat() == "2026-08-18T21:50:00+03:00"
    assert isinstance(item.payload, GenericPhotoPayload)
    assert item.payload.provider_payload_sha256 == (
        "sha256:d60f503934fb209429606b235622ab0d27a1179978c9fa78574cf517d321b07a"
    )
    assert item.payload.media_sha256 == "sha256:8bb0956e44084265d7a3a14ce01f96eb1e4a9c327c780448de34e068f6cf6f10"

    recomputed = render_photo_payload(
        profile,
        publication_id=item.publication_id,
        caption=item.payload.caption,
        media_path=item.payload.media_path,
        media_sha256=item.payload.media_sha256,
        media_byte_size=item.payload.media_byte_size,
        media_filename=item.payload.media_filename,
    )
    assert recomputed.provider_payload_sha256 == item.payload.provider_payload_sha256


def test_live_canary_v2_authorization_is_one_operation_zero_retries() -> None:
    release = load_release(RELEASE)
    auth = json.loads(AUTH.read_text(encoding="utf-8"))

    assert auth["release_digest"] == release.digest
    assert auth["publication_id"] == release.items[0].publication_id
    assert auth["execution_authorized"] is True
    assert auth["automatic_dispatch_authorized"] is True
    assert auth["max_provider_attempts"] == 1
    assert auth["blind_mutation_retries"] == 0
    assert auth["supersedes_publication_id"] == "milovi-canary-20260818-001"
    assert auth["supersedes_only_if_prior_intent_absent"] is True
    assert auth["execute_not_before"] == "2026-08-18T21:50:00+03:00"
    assert auth["execute_not_after"] == "2026-08-18T23:50:00+03:00"
    assert "controller_dispatch_window_end" not in auth


def test_historical_v1_authorization_remains_expired_and_immutable() -> None:
    historical = json.loads(HISTORICAL_AUTH.read_text(encoding="utf-8"))
    assert historical["publication_id"] == "milovi-canary-20260818-001"
    assert historical["execute_not_before"] == "2026-08-18T16:10:00+03:00"
    assert historical["execute_not_after"] == "2026-08-18T18:10:00+03:00"
    assert historical["controller_dispatch_window_end"] == "2026-08-18T17:05:00+03:00"
