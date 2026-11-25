"""Regression lock: owner-corrected archival Cake Books video, no replay or invented 'new work'."""

from pathlib import Path

from video_channel_manager.milovi_telegram_feed import exact_paths, validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

NEW_ID = "milovi-feed-20261124-001"
OLD_ID = "milovi-feed-20261108-001"
MEDIA_SHA = "sha256:3425e096d2f5d47dc86594f1fde8b47db34e4623ce8ef7badcf338ddd5664ceb"
NEW_CAPTION_SHA = "sha256:da487f157048e4293adda02849222f84e1e0e308064a6c0445e0b2398d21340d"
NEW_RELEASE_SHA = "sha256:67b45480a5a583e2dd4210ff955cd1f117a583d582e2e4f9da2c359356e63050"
NEW_PROVIDER_SHA = "sha256:f30396bb6c71a18b66221923b73ab9ce830c696b271d4685b8335e7b908f736c"


def test_archival_video_has_corrected_copy_and_immutable_source() -> None:
    release = load_release(exact_paths(NEW_ID)["release"])
    assert release.release_id == NEW_ID
    assert release.release_authorized is True
    assert release.reviewed_publication_id == NEW_ID
    assert release.digest == NEW_RELEASE_SHA
    assert release.items[0].scheduled_at.isoformat() == "2026-11-24T19:00:00+03:00"
    assert isinstance(release.items[0].payload, GenericVideoPayload)
    payload = release.items[0].payload
    assert payload.media_sha256 == release.items[0].source_sha256 == MEDIA_SHA
    assert payload.provider_payload_sha256 == NEW_PROVIDER_SHA
    assert payload.media_byte_size == 4_968_773
    assert payload.caption.startswith("🎂 3D-торт «Книги»")
    assert "НОВАЯ РАБОТА" not in payload.caption
    assert "новая работа" not in payload.caption.casefold()


def test_legacy_immutable_release_keeps_its_old_bytes() -> None:
    legacy = load_release(exact_paths(OLD_ID)["release"])
    assert legacy.release_id == OLD_ID
    assert legacy.items[0].scheduled_at.isoformat() == "2026-11-08T19:00:00+03:00"
    assert "НОВАЯ РАБОТА MILOVI CAKE" in legacy.items[0].payload.caption


def test_new_bundle_is_validated_through_canonical_single_writer() -> None:
    out = validate_bundle(NEW_ID, require_execution_authorized=True)
    assert out["valid"] is True
    assert out["payload_kind"] == "video"
    assert out["blockers"] == []
    assert out["release_authorized"] is True
    assert out["execution_authorized"] is True
    assert out["provider_mutation_allowed"] is True
    assert out["provider_access_performed"] is False
    assert out["release_digest"] == NEW_RELEASE_SHA
    assert out["provider_payload_sha256"] == NEW_PROVIDER_SHA


def test_new_candidate_does_not_claim_replayed_provider_effect() -> None:
    import json

    paths = exact_paths(NEW_ID)
    video = json.loads(paths["video"].read_text(encoding="utf-8"))
    candidate = json.loads(Path(video["candidate_path"]).read_text(encoding="utf-8"))
    authority = json.loads(paths["authority"].read_text(encoding="utf-8"))
    assert candidate["caption_sha256"] == video["caption_sha256"] == NEW_CAPTION_SHA
    assert candidate["caption"] == load_release(paths["release"]).items[0].payload.caption
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False
    assert candidate["dispatched_to_provider"] is False
    assert candidate["current_public_duplicate_screen"]["private_or_deleted_history_complete"] is False
    assert authority["max_provider_attempts"] == 1
    assert authority["blind_mutation_retries"] == 0
    assert authority["historical_authorization_inherits"] is False
    assert video["artifact_commit"] == "9331af0c6015404bfda0cd2c6392066b78dc68b3"
    assert video["artifact_sha256"] == MEDIA_SHA
    assert video["artifact_git_blob_sha1"] == "901be04d6a8f33b821015e3413d529876faf1f12"
