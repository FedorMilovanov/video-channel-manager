"""Primary-source caption and layered media rights: editorial only, never a release."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/audits/2026-11-04-lord-god-piper-primary-source-caption-rights-inert.json"
QUEUE = ROOT / "content/instagram/lord-god-strength-shorts-sermons-intake-20261104.json"
TECHNICAL = ROOT / "docs/audits/2026-11-04-lord-god-piper-first-reel-meta-v3-technical-evidence.json"
PERMISSIONS_DRAFT = ROOT / "docs/operations/2026-11-04-lord-god-piper-permissions-request-drafts.md"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_verified_2011_original_is_exactly_bound_to_the_russian_short() -> None:
    r = read(EVIDENCE)
    queue = read(QUEUE)
    candidate = next(c for c in queue["candidates"] if c["source_video_id"] == "lTRm2NbnIas")
    proof = read(TECHNICAL)
    assert r["schema_name"] == "video-manager.lord-god-primary-source-caption-rights-inert"
    assert r["schema_version"] == 1
    assert r["project_key"] == queue["project_key"] == candidate["project_key"] == "lord-god-strength"
    assert r["youtube_channel_id"] == queue["youtube_channel_id"] == candidate["youtube_channel_id"]
    assert r["youtube_video_id"] == candidate["source_video_id"] == proof["source_video_id"]
    assert r["youtube_url"] == candidate["source_url"]
    assert r["youtube_title"] == candidate["source_title"]
    assert r["short_duration_seconds"] == proof["source_clip_full_duration_seconds"] == 144
    assert r["original_speaker"] == "John Piper"
    assert r["original_work_title"] == "Ministry Reflections with John Piper and R. C. Sproul"
    assert r["original_event"] == "Ligonier Ministries 2011 National Conference"
    assert r["original_event_date"] == "2011-03-26"
    assert r["original_primary_transcript_url"] == (
        "https://www.desiringgod.org/messages/ministry-reflections-with-john-piper-and-r-c-sproul"
    )
    assert "rose story" in r["original_source_opening_anchor"]
    assert r["original_source_closing_anchor"] == "We glorify the things we value by enjoying them."
    assert len(r["source_verified_claims"]) == 3
    assert "Romans 12:1" in r["source_verified_claims"][-1]
    assert r["russian_caption_track"]["language"] == "ru"
    assert r["russian_caption_track"]["kind"] == "asr"
    assert r["russian_caption_track"]["caption_track_automatically_generated"] is True
    assert r["russian_caption_track"]["caption_entire_text_stored"] is False
    assert r["russian_caption_track"]["translated_audio_voice_owner_verified"] is False
    assert candidate["primary_talk_source_review_file"] == EVIDENCE.relative_to(ROOT).as_posix()
    assert proof["primary_source_editorial_evidence_file"] == EVIDENCE.relative_to(ROOT).as_posix()
    assert candidate["original_talk_transcript_correspondence"] == ("verified_primary_english_excerpt_2011_ligonier")
    assert candidate["english_primary_source_identified"] is True


def test_russian_caption_is_complete_but_not_approved() -> None:
    r = read(EVIDENCE)
    e = r["editorial"]
    q = read(QUEUE)
    c = next(x for x in q["candidates"] if x["source_video_id"] == r["youtube_video_id"])
    caption = e["caption_ru"]
    assert 100 <= len(caption) <= 2200
    assert "??" not in caption and "\ufffd" not in caption
    assert "Пайпер" in caption
    assert "Рим. 12:1" in caption
    assert "Р. Ч. Спроулом" in caption
    assert caption.count(r["original_primary_transcript_url"]) == 1
    assert caption.count(r["youtube_url"]) == 1
    assert caption.count("#ГосподьБогСилаМоя") == 1
    assert len([token for token in caption.split() if token.startswith("#")]) == 6
    assert e["caption_factual_review"] == "primary_source_grounded_draft"
    assert e["caption_final_approval"] is False
    assert e["visual_review_complete"] is False
    assert e["source_translation_rights_checked"] is False
    assert c["caption_review"] == "pending"
    assert c["ready_to_publish"] is False
    assert c["provider_writes_authorized"] is False
    assert q["source_grounded_caption_draft_count"] == 1
    assert q["source_specific_rights_cleared_count"] == 0
    assert q["ready_to_publish_count"] == 0
    assert q["provider_writes_authorized"] is False
    assert len(q["candidates"]) == 20
    assert len([x for x in q["candidates"] if x.get("primary_talk_source_review_file")]) == 1


def test_actual_conference_recording_and_russian_derivative_cannot_be_republished_without_rights() -> None:
    r = read(EVIDENCE)
    rights = r["source_rights"]
    assert rights["desiring_god_policy_url"] == "https://www.desiringgod.org/permissions"
    assert rights["ligonier_policy_url"] == "https://www.ligonier.org/copyright-policy"
    assert rights["desiring_god_writing_authorization_reference"] is None
    assert rights["ligonier_recording_writing_authorization_reference"] is None
    assert rights["russian_translation_and_voice_authorization_reference"] is None
    assert rights["actual_rightsholders_confirmed"] is False
    assert rights["rights_review_complete"] is False
    assert "written permission" in rights["desiring_god_policy_scope"]
    assert "special written permission" in rights["ligonier_policy_scope"]
    card = next(x for x in read(QUEUE)["candidates"] if x["source_video_id"] == "lTRm2NbnIas")
    assert card["desiring_god_av_written_reupload_permission_verified"] is False
    assert card["ligonier_av_written_reupload_permission_verified"] is False
    assert card["russian_dubbing_and_translation_reuse_permission_verified"] is False
    guard = r["publish_guard"]
    assert guard["instagram_professional_account_id"] is None
    assert guard["browser_login_is_not_provider_graph_api_authorization"] is True
    assert guard["provider_write_authorization"] is False
    assert guard["editorial_approval"] is False
    assert guard["rights_approval"] is False
    assert guard["publication_release_id"] is None
    assert guard["ready_to_publish"] is False
    assert guard["do_not_request_or_store_otp"] is True
    text = PERMISSIONS_DRAFT.read_text(encoding="utf-8")
    assert "permission" in text.casefold()
    assert r["original_primary_transcript_url"] in text
    assert r["youtube_url"] in text
    assert rights["desiring_god_policy_url"] in text
    assert rights["ligonier_policy_url"] in text
    assert "forms.cloud.microsoft" in text
    assert "ничего не отправлено" in text
    assert r["technical_reel"]["render_sha256"] == read(TECHNICAL)["render_sha256"]
    assert r["technical_reel"]["output_readiness"] == "tech_verified_nonpublishing"
