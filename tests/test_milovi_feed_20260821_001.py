from __future__ import annotations

import hashlib
import json
from pathlib import Path

from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
PUBLICATION_ID = "milovi-feed-20260821-001"
TRANSPORT_SHA256 = "sha256:e8a48c819550a7e914f81fe7f7f30d27d9412d72744dc1d93c109989ab86770a"
SOURCE_SHA256 = "sha256:6ca82d87ab4c4ac869e1363df7758bef47aa8eccbcc5e2f5be70a402ce459fcc"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_20260821_is_fresh_identity_not_catchup_of_002() -> None:
    candidate = _json(CONTENT / "marathon-publication-candidate-2026-08-21-001.json")
    stale = _json(CONTENT / "marathon-publication-candidate-2026-08-20-002.json")

    assert candidate["publication_id"] == PUBLICATION_ID
    assert candidate["scheduled_at"] == "2026-08-21T10:30:00+03:00"
    assert stale["publication_id"] == "milovi-feed-20260820-002"
    assert candidate["publication_id"] != stale["publication_id"]
    assert candidate["media"]["media_id"] == stale["media"]["media_id"] == "p06"
    assert candidate["media"]["transport_sha256"] == stale["media"]["transport_sha256"] == TRANSPORT_SHA256
    assert candidate["caption"] != stale["caption"]
    assert "зафиксирован" not in candidate["caption"]
    assert "https://milovicake.ru/gallery/" in candidate["caption"]
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False
    assert candidate["marathon_source"]["stale_predecessor_publication_id"] == "milovi-feed-20260820-002"


def test_20260821_caption_digest_and_authorized_runtime_match() -> None:
    candidate = _json(CONTENT / "marathon-publication-candidate-2026-08-21-001.json")
    runtime = load_release(CONTENT / "releases" / f"{PUBLICATION_ID}-runtime.json")
    media = _json(CONTENT / "releases" / f"{PUBLICATION_ID}-media.json")
    authority = _json(CONTENT / "releases" / f"{PUBLICATION_ID}-execution-authority.json")

    digest = "sha256:" + hashlib.sha256(candidate["caption"].encode("utf-8")).hexdigest()
    assert candidate["caption_sha256"] == digest == media["caption_sha256"]
    assert candidate["publication_authorized"] is False
    assert runtime.release_authorized is True
    assert runtime.reviewed_candidate_sha256 == runtime.candidate_digest()
    assert runtime.items[0].payload.caption == candidate["caption"]
    assert runtime.items[0].source_sha256 == SOURCE_SHA256
    assert media["transport"]["sha256"] == TRANSPORT_SHA256
    assert authority["execution_authorized"] is True
    assert authority["provider_mutation_allowed"] is True
    assert authority["release_digest"] == runtime.digest
    assert authority["historical_authorization_inherits"] is False
    assert authority["max_provider_attempts"] == 1
    assert authority["blind_mutation_retries"] == 0
    assert "да, публикуем milovi-feed-20260821-001" in str(authority["authorized_by"])


def test_20260821_bundle_validates_authorized_without_provider_access() -> None:
    result = validate_bundle(
        PUBLICATION_ID,
        require_release_authorized=True,
        require_execution_authorized=True,
    )

    assert result["valid"] is True
    assert result["payload_kind"] == "photo"
    assert result["release_authorized"] is True
    assert result["execution_authorized"] is True
    assert result["provider_mutation_allowed"] is True
    assert result["provider_access_performed"] is False
    assert result["blockers"] == []
