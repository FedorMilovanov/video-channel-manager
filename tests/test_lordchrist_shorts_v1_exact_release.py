from __future__ import annotations

import hashlib
import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload, render_video_payload
from video_channel_manager.telegram_target_binding import load_target_binding

PROFILE = Path("content/telegram/channels/lordchrist-shorts-v1.json")
BINDING = Path("content/telegram/channels/lordchrist-shorts-v1-target-binding.json")
RELEASE = Path("content/telegram/lordchrist/shorts-v1-release.json")
MANIFEST = Path("content/telegram/lordchrist/shorts-v1-source-manifest.json")
DRAFT = Path("content/telegram/lordchrist/shorts-piper-macarthur-deferred-review-20261106.json")
EVIDENCE_COMMIT = "85990401e732a22a8a12b390683196264a50ba8c"


def test_four_video_release_is_exact_source_bound() -> None:
    profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, profile)
    release = load_release(RELEASE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    assert profile.channel_username == "@lordchrist"
    assert profile.concurrency_group == "lordchrist-telegram-publisher"
    assert profile.state_branch == "state/lordchrist-telegram"
    assert profile.publication_id_prefix == "lordchrist-short-"
    assert binding.chat_id == release.chat_id == -1001295216957
    assert binding.bot_id == release.bot_id == 8716602202
    assert binding.digest == release.target_binding_sha256
    assert release.profile_sha256 == profile.digest
    assert release.release_authorized is True
    assert manifest["release_digest"] == release.digest
    assert manifest["candidate_digest"] == release.candidate_digest()
    assert len(release.items) == len(manifest["items"]) == len(draft["items"]) == 4
    assert manifest["schedule_activated"] is False
    assert manifest["provider_writes_performed"] is False
    assert manifest["source_evidence_commit"] == EVIDENCE_COMMIT
    ids = ["ba4ZahiY-U0", "_aDIR0D7rSk", "tELrnM71TQA", "VeY1tpoLUJU"]
    for index, (item, original, source) in enumerate(
        zip(release.items, draft["items"], manifest["items"], strict=True)
    ):
        assert source["youtube_video_id"] == original["youtube_video_id"] == ids[index]
        assert item.publication_id == source["publication_id"] == original["publication_id"]
        assert item.scheduled_at.isoformat() == original["proposed_at"]
        assert item.scheduled_at.hour == 16
        assert item.payload.media_sha256 == source["source_sha256"]
        assert item.source_sha256 == source["source_sha256"]
        assert item.payload.media_byte_size == source["source_byte_size"]
        assert item.payload.caption == original["caption"]
        assert item.payload.caption.count("?") < 4
        assert item.payload.provider_payload_sha256 == source["provider_payload_sha256"]
        assert "sha256:" + hashlib.sha256(item.payload.caption.encode("utf-8")).hexdigest() == source["caption_sha256"]
        assert isinstance(item.payload, GenericVideoPayload)
        again = render_video_payload(
            profile,
            publication_id=item.publication_id,
            caption=item.payload.caption,
            media_path=item.payload.media_path,
            media_sha256=item.payload.media_sha256,
            media_byte_size=item.payload.media_byte_size,
            media_filename=item.payload.media_filename,
        )
        assert again == item.payload
    assert len({x.payload.media_sha256 for x in release.items}) == 4


def test_shorts_four_protected_evidence_and_cross_track_guard() -> None:
    data = json.loads(Path("docs/operations/protected-evidence-refs.json").read_text(encoding="utf-8"))
    evidence = next(x for x in data["refs"] if x["ref"] == "agent/lordchrist-shorts4-media-20261106")
    assert evidence["tip_is_stable"] is True
    assert evidence["tip_commit"] == EVIDENCE_COMMIT
    src = Path(".github/workflows/lordchrist-quote-v6-publisher.yml").read_text(encoding="utf-8")
    assert "lordchrist-telegram-publisher" in src
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["separate_quote_v6_lane_unchanged"] is True
    assert manifest["state_initialized"] is False
