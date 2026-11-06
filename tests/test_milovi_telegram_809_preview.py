from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release

ID = "milovi-feed-20261107-001"
BASE = Path("content/telegram/milovi-cake")


def test_november_v12_corrupt_cyrillic_bundle_is_permanently_retired() -> None:
    # Before launch, a Windows code-page error replaced the Russian caption
    # with literal '?' characters. Never revive this digest-bound identity.
    from video_channel_manager.milovi_telegram_feed import validate_retired_bundle

    proof = validate_retired_bundle(ID)
    assert proof["status"] == "retired_proven_never_send"
    assert proof["provider_access_performed"] is False
    assert proof["provider_write_performed"] is False
    with pytest.raises(ValueError, match="permanently retired"):
        validate_bundle(ID)
    with pytest.raises(ValueError, match="permanently retired"):
        validate_bundle(ID, require_execution_authorized=True)


def test_november_v12_identity_and_media_provenance_remain_pinned() -> None:
    release = load_release(BASE / "releases" / f"{ID}-runtime.json")
    candidate = json.loads((BASE / "november-first-video-candidate-20261107.json").read_text(encoding="utf-8"))
    video = json.loads((BASE / "releases" / f"{ID}-video.json").read_text(encoding="utf-8"))
    authority = json.loads((BASE / "releases" / f"{ID}-execution-authority.json").read_text(encoding="utf-8"))
    reservoir = json.loads((BASE / "accepted-video-reservoir-2026-08.json").read_text(encoding="utf-8"))
    accepted = next(item for item in reservoir["artifacts"] if item["media_id"] == "v12")

    assert candidate["publication_id"] == ID
    assert candidate["operation"] == "sendVideo"
    assert candidate["media_id"] == "v12"
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False
    assert candidate["editorial_guards"]["copyright_music_or_audio_review_required"] is True
    assert video["artifact_sha256"] == accepted["sha256"]
    assert video["artifact_git_blob_sha1"] == accepted["git_blob_sha1"]
    assert video["artifact_byte_size"] == accepted["byte_size"]
    assert video["artifact_ref"] == reservoir["artifact_ref"]
    assert video["evidence_sha256"] == reservoir["evidence_sha256"]
    assert video["provider_write_performed"] is False
    assert release.items[0].publication_id == ID
    assert authority["release_candidate_sha256"] == release.candidate_digest()
    assert authority["provider_payload_sha256"] == release.items[0].payload.provider_payload_sha256
    assert authority["execution_authorized"] is False
    assert authority["provider_mutation_allowed"] is False
