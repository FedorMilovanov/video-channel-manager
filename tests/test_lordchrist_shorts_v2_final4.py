from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import OwnerScheduledCanaryApproval, initialize_ledger
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload, render_video_payload
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/lordchrist-shorts-v1.json"
BINDING = ROOT / "content/telegram/channels/lordchrist-shorts-v1-target-binding.json"
V1 = ROOT / "content/telegram/lordchrist/shorts-v1-release.json"
RELEASE = ROOT / "content/telegram/lordchrist/shorts-v2-release.json"
MANIFEST = ROOT / "content/telegram/lordchrist/shorts-v2-source-manifest.json"
APPROVAL = ROOT / "content/telegram/lordchrist/shorts-v2-scheduled-canary-approval.json"
WORKFLOW = ROOT / ".github/workflows/lordchrist-shorts4-publisher.yml"
EVIDENCE_COMMIT = "d45230ae5ab07b0f2301d01628c04e4fa7a3fb84"
IDS = ("2sapXv78y9Q", "PUlNpw83DFI", "y9a7_3DutWk", "EozlBy39F1c")


def test_four_continuation_shorts_are_exact_and_separate_from_immutable_predecessor() -> None:
    profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, profile)
    predecessor = load_release(V1)
    release = load_release(RELEASE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert predecessor.digest == "sha256:8232f393ef3d1ce001d69776ef1ce810ec6de08fec6bd615cb5c495e07871837"
    assert predecessor.items[-1].scheduled_at.date() == date(2026, 11, 11)
    assert release.release_authorized
    assert release.project_key == predecessor.project_key == "lord-god-strength"
    assert profile.concurrency_group == "lordchrist-telegram-publisher"
    assert release.channel_username == profile.channel_username == "@lordchrist"
    assert release.chat_id == predecessor.chat_id == binding.chat_id == -1001295216957
    assert release.bot_id == predecessor.bot_id == binding.bot_id == 8716602202
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest
    assert release.digest == manifest["release_digest"]
    assert release.candidate_digest() == manifest["candidate_digest"]
    assert manifest["source_evidence_commit"] == EVIDENCE_COMMIT
    assert manifest["require_all_four_predecessor_verified"] is True
    assert manifest["independent_external_licensing_certificate_not_asserted"] is True
    assert manifest["provider_writes_performed"] is False
    assert manifest["state_initialized"] is False
    assert manifest["schedule_activated"] is False
    assert len(release.items) == len(manifest["items"]) == 4
    assert set(x.publication_id for x in predecessor.items).isdisjoint(x.publication_id for x in release.items)

    for i, (item, source) in enumerate(zip(release.items, manifest["items"], strict=True)):
        video_id = IDS[i]
        assert item.sequence == i + 1
        assert item.publication_id == source["publication_id"] == "lordchrist-short-" + video_id
        assert source["youtube_video_id"] == video_id
        assert item.scheduled_at.date() == date(2026, 11, 12 + i)
        assert (item.scheduled_at.hour, item.scheduled_at.minute) == (16, 0)
        assert isinstance(item.payload, GenericVideoPayload)
        assert item.payload.media_sha256 == item.source_sha256 == source["source_sha256"]
        assert item.payload.media_byte_size == source["source_byte_size"]
        assert item.payload.provider_payload_sha256 == source["provider_payload_sha256"]
        assert "????" not in item.payload.caption
        assert "#ГосподьБог #Проповедь" in item.payload.caption
        assert f"https://www.youtube.com/watch?v={video_id}" in item.payload.caption
        assert len(item.payload.caption) <= 1024
        assert source["caption_sha256"] == "sha256:" + hashlib.sha256(item.payload.caption.encode("utf-8")).hexdigest()
        assert item.payload.media_filename == f"lordchrist-short-{video_id}.mp4"
        assert source["artifact_commit"] == EVIDENCE_COMMIT
        assert source["artifact_path"] == f"artifacts/lordchrist-telegram/shorts-extra4-20261106/lordchrist-short-{video_id}.mp4"
        assert len(source["git_blob_sha1"]) == 40
        reconstructed = render_video_payload(
            profile,
            publication_id=item.publication_id,
            caption=item.payload.caption,
            media_path=item.payload.media_path,
            media_sha256=item.payload.media_sha256,
            media_byte_size=item.payload.media_byte_size,
            media_filename=item.payload.media_filename,
        )
        assert reconstructed == item.payload
    ledger = initialize_ledger(release)
    assert len(ledger.entries) == 4
    assert {e.state for e in ledger.entries.values()} == {"pending"}
    assert {e.provider_effect for e in ledger.entries.values()} == {"impossible"}


def test_second_wave_scheduled_canary_binds_exact_immutable_manifest() -> None:
    approval = OwnerScheduledCanaryApproval.model_validate_json(APPROVAL.read_text(encoding="utf-8"))
    release = load_release(RELEASE)
    manifest_bytes = MANIFEST.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(manifest_bytes)).encode("ascii") + b"\0" + manifest_bytes).hexdigest()
    assert approval.source_manifest_git_blob_sha1 == blob
    assert approval.source_manifest_path == "content/telegram/lordchrist/shorts-v2-source-manifest.json"
    assert approval.release_digest == release.digest
    assert approval.first_publication_id == release.items[0].publication_id
    assert approval.scheduled_at == release.items[0].scheduled_at
    assert approval.owner_authorized and approval.maximum_first_send_attempts == 1
    assert approval.require_verified_first_receipt_for_followons


def test_continuation_reuses_one_existing_guarded_writer_and_protected_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert '7 13 8-11 11 *' in workflow
    assert '7 13 12-15 11 *' in workflow
    assert "lordchrist-telegram-publisher" in workflow
    assert "content/telegram/lordchrist/shorts-v2-publication-ledger.json" in workflow
    assert "require all" not in workflow.lower() or "verified" in workflow.lower()
    assert "Final-four wave blocked until all four earlier Shorts have exact verified Telegram receipts" in workflow
    assert 'state.state=="published" and state.provider_effect=="verified"' in workflow
    assert 'state.actual_chat_id==release.chat_id and state.bot_id==release.bot_id' in workflow
    assert 'valid_days=(8,9,10,11) if os.environ["WAVE"]=="v1" else (12,13,14,15)' in workflow
    assert "scripts.lordchrist_quote_v6_publisher import guard_cross_track" in workflow
    assert workflow.count("telegram_multichannel_cli send-once") == 1
    assert workflow.index("Persist pre-send intent") < workflow.index("Exactly one native Telegram sendVideo attempt")
    refs = json.loads((ROOT/"docs/operations/protected-evidence-refs.json").read_text(encoding="utf-8"))
    entries = [x for x in refs["refs"] if x["ref"] == "agent/lordchrist-shorts8-media-20261106"]
    assert len(entries) == 1
    assert entries[0]["tip_commit"] == EVIDENCE_COMMIT
    assert entries[0]["role"] == "content_addressed_evidence" and entries[0]["tip_is_stable"] is True


def test_outcome_archival_follows_selected_wave_not_original_v1() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "path: " + "$" + "{{ env.OUTCOME }}" in workflow
    assert 'echo "OUTCOME=.runtime/lordchrist-shorts-v2-outcome.json" >> "$GITHUB_ENV"' in workflow
    assert 'evidence="content/telegram/lordchrist/dispatches/shorts-$WAVE/' in workflow
