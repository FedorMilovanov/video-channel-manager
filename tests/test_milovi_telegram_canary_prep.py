from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content/telegram/milovi-cake"
MEDIA_MAP = MILOVI / "media-source-map-2026-08.json"
READINESS = MILOVI / "media-delivery-readiness-2026-08.json"
CANDIDATE = MILOVI / "canary-candidate-2026-08.json"
REVIEW_LOCK = MILOVI / "canary-review-lock-2026-08.json"
RUNBOOK = MILOVI / "canary-preparation-2026-08.md"


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def test_milovi_canary_is_exact_photo_candidate_but_not_executable() -> None:
    candidate = _load_json(CANDIDATE)

    assert candidate["schema_name"] == "video-channel-manager.milovi-telegram-canary-candidate"
    assert candidate["project_key"] == "milovi-cake"
    assert candidate["owning_issue"] == 353
    assert candidate["publication_id"] == "milovi-cake-canary-001"
    assert candidate["status"] == "provider_inert_candidate"
    assert candidate["operation"] == "sendPhoto"
    assert candidate["publication_authorized"] is False
    assert candidate["execution_ready"] is False
    assert candidate["provider_mutation_allowed"] is False

    target = candidate["target"]
    assert target["channel_username"] == "@MiloviCake"
    assert target["chat_id"] is None
    assert target["discovery_proof_sha256"] is None
    assert target["target_binding_sha256"] is None
    assert target["expected_bot_id"] == 8716602202
    assert target["expected_bot_username"] == "preaching_mp3_bot"

    actions = candidate["post_actions"]
    assert actions == {
        "pin_after_send": False,
        "schedule": None,
        "follow_up_post": None,
        "invite_link_creation": False,
    }


def test_milovi_canary_media_matches_exact_gallery_source_and_readiness_contract() -> None:
    media_map = _load_json(MEDIA_MAP)
    readiness = _load_json(READINESS)
    candidate = _load_json(CANDIDATE)

    media_items = media_map["items"]
    p18 = next(item for item in media_items if item["id"] == "p18")
    candidate_media = candidate["media"]
    readiness_media = readiness["candidate_media"]

    assert p18["type"] == "photo"
    assert p18["full"] == "/img/gallery/gallery-18-hd.webp"
    assert p18["title"] == "Премиальный торт с золотом"

    assert candidate_media["media_id"] == readiness_media["media_id"] == "p18"
    assert candidate_media["source_repository"] == "FedorMilovanov/Milovi_Cake"
    assert candidate_media["source_commit"] == "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370"
    assert candidate_media["source_path"] == "img/gallery/gallery-18-hd.webp"
    assert candidate_media["source_blob_sha"] == "3574f726b233583a77b8a6db885f91b49e5189d8"
    assert candidate_media["byte_size"] == 195742
    assert candidate_media["delivery_mode"] == "multipart_exact_bytes"
    assert candidate_media["materialized_sha256"] is None
    assert candidate_media["pixel_width"] is None
    assert candidate_media["pixel_height"] is None

    for key in ("source_repository", "source_commit", "source_path", "source_blob_sha", "byte_size"):
        assert readiness_media[key] == candidate_media[key]

    assert readiness_media["pixel_dimensions_verified"] is False
    assert readiness_media["photo_size_limit_verified"] is True
    assert readiness_media["transport_ready"] is False
    assert readiness["provider_write_authorized"] is False


def test_milovi_photo_contract_and_candidate_caption_are_within_reviewed_limits() -> None:
    readiness = _load_json(READINESS)
    candidate = _load_json(CANDIDATE)
    contract = readiness["telegram_contract"]
    caption = candidate["caption"]

    assert contract["photo_multipart_max_bytes"] == 10 * 1024 * 1024
    assert contract["photo_url_max_bytes"] == 5 * 1024 * 1024
    assert contract["photo_width_plus_height_max"] == 10000
    assert contract["photo_aspect_ratio_max"] == 20
    assert contract["photo_caption_max_characters_after_entities"] == 1024
    assert candidate["media"]["byte_size"] < contract["photo_multipart_max_bytes"]

    text = caption["text"]
    assert len(text) <= contract["photo_caption_max_characters_after_entities"]
    assert text.startswith("Milovi Cake — торты и десерты в Санкт-Петербурге.")
    assert "реальные работы Milovi Cake, красивые детали и подборки" in text
    assert "Основатель и кондитер — Виктория Милованова." in text
    assert text.endswith("https://milovicake.ru/")
    assert "закулис" not in text.casefold()
    assert "процесс" not in text.casefold()
    assert "последн" not in text.casefold()
    assert "₽" not in text
    assert caption["parse_mode"] is None
    assert caption["source_repository"] == "FedorMilovanov/Milovi_Cake"
    assert caption["source_path"] == "llms.txt"
    assert caption["source_blob_sha"] == "a6ce3340bb0459657870605f0db09d9f99ac72a8"


def test_milovi_webm_video_lane_stays_blocked_from_native_video_assumption() -> None:
    readiness = _load_json(READINESS)
    policy = readiness["video_policy"]
    contract = readiness["telegram_contract"]

    assert contract["video_max_bytes"] == 50 * 1024 * 1024
    assert contract["native_video_client_format"] == "MPEG4"
    assert policy["current_gallery_extension"] == ".webm"
    assert policy["native_video_ready"] is False
    assert "MP4" in policy["required_next_step"]
    assert "do not silently downgrade" in contract["non_mpeg4_video_policy"].lower()


def test_milovi_canary_review_lock_matches_exact_candidate_and_readiness_bytes() -> None:
    lock = _load_json(REVIEW_LOCK)

    assert lock["schema_name"] == "video-channel-manager.milovi-telegram-canary-review-lock"
    assert lock["project_key"] == "milovi-cake"
    assert lock["publication_id"] == "milovi-cake-canary-001"
    assert lock["status"] == "provider_inert_blocked"
    assert lock["candidate_path"] == "content/telegram/milovi-cake/canary-candidate-2026-08.json"
    assert lock["media_readiness_path"] == "content/telegram/milovi-cake/media-delivery-readiness-2026-08.json"
    assert lock["candidate_git_blob_sha1"] == _git_blob_sha1(CANDIDATE)
    assert lock["media_readiness_git_blob_sha1"] == _git_blob_sha1(READINESS)
    assert lock["source_media"]["git_blob_sha1"] == "3574f726b233583a77b8a6db885f91b49e5189d8"
    assert lock["caption_fact_source"]["git_blob_sha1"] == "a6ce3340bb0459657870605f0db09d9f99ac72a8"
    assert lock["authorization_state"] == "blocked"
    unresolved = lock["unresolved_authorization_inputs"]
    assert unresolved["target_binding_sha256"] is None
    assert unresolved["materialized_media_sha256"] is None
    assert unresolved["explicit_authorization_reference"] is None


def test_milovi_canary_cannot_become_ready_with_unresolved_media_or_target() -> None:
    readiness = _load_json(READINESS)
    candidate = _load_json(CANDIDATE)
    gates = candidate["required_gates_before_authorization"]

    assert candidate["target"]["chat_id"] is None
    assert candidate["target"]["target_binding_sha256"] is None
    assert candidate["media"]["materialized_sha256"] is None
    assert candidate["media"]["pixel_width"] is None
    assert candidate["media"]["pixel_height"] is None
    assert readiness["candidate_media"]["transport_ready"] is False
    assert candidate["execution_ready"] is False
    assert candidate["publication_authorized"] is False
    assert len(gates) >= 8
    assert any("fresh read-only target discovery" in gate for gate in gates)
    assert any("byte SHA-256" in gate for gate in gates)
    assert any("explicitly authorized" in gate for gate in gates)
    assert "Unknown provider outcome blocks replay" in candidate["outcome_rule"]


def test_milovi_canary_runbook_preserves_provider_inert_and_no_bts_boundaries() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "provider-inert / execution blocked" in runbook
    assert "This document prepares one future canary. It does not authorize or perform a Telegram mutation." in runbook
    assert "first canary is a photo" in runbook.lower()
    assert "Username-only sending is not an acceptable replacement." in runbook
    assert "Do not use `sendDocument` as a silent fallback" in runbook
    assert "production footage" in runbook
    assert "one exact canary mutation" in runbook
