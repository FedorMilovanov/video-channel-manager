from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.milovi_telegram_feed import validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
PUBLICATION_ID = "milovi-feed-20260820-001"
TRANSPORT_SHA256 = "sha256:19ba49ed001ea0c7c79ad9f475be0ad4c4c41b5790ee195e363df7981cfb6b9e"
CAPTION_SHA256 = "sha256:40708552f2899f3c236b5ff63370d556e97701d7495ffe3b753229d69de1f587"
PROVIDER_PAYLOAD_SHA256 = "sha256:e495273ad04ec2b175b056e8bc6676eac23b676a3e3cc866a32da206a4ef26b8"
RELEASE_CANDIDATE_SHA256 = "sha256:99a6b904359a0e3fb82873b69c58319222aa93ad7db1ff0ef2fc1d2308196330"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_20260820_exact_bundle_uses_next_portfolio_first_candidate() -> None:
    continuation = _json(CONTENT / "first-screen-continuation-copy-2026-08.json")
    candidate = _json(CONTENT / "next-publication-candidate-2026-08-20.json")
    item = next(value for value in continuation["items"] if value["publication_id"] == PUBLICATION_ID)

    assert item["position"] == 2
    assert item["media_id"] == candidate["media"]["media_id"] == "p16"
    assert item["caption"] == candidate["caption"]
    assert candidate["caption_sha256"] == CAPTION_SHA256
    assert candidate["scheduled_at"] == "2026-08-20T10:30:00+03:00"
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False


def test_20260820_runtime_transport_and_authority_are_exact_and_inert() -> None:
    runtime = load_release(CONTENT / "releases" / f"{PUBLICATION_ID}-runtime.json")
    media = _json(CONTENT / "releases" / f"{PUBLICATION_ID}-media.json")
    authority = _json(CONTENT / "releases" / f"{PUBLICATION_ID}-execution-authority.json")
    state = _json(CONTENT / "releases" / f"{PUBLICATION_ID}-state-contract.json")

    assert runtime.release_id == PUBLICATION_ID
    assert len(runtime.items) == 1
    assert runtime.items[0].publication_id == PUBLICATION_ID
    assert runtime.items[0].scheduled_at.isoformat() == "2026-08-20T10:30:00+03:00"
    assert runtime.items[0].payload.provider_payload_sha256 == PROVIDER_PAYLOAD_SHA256
    assert runtime.candidate_digest() == authority["release_candidate_sha256"] == RELEASE_CANDIDATE_SHA256
    assert media["transport"]["sha256"] == TRANSPORT_SHA256
    assert media["transport"]["byte_size"] == 506080
    assert state["identity_lock"]["media_id"] == "p16"
    assert authority["execution_authorized"] is False
    assert authority["provider_mutation_allowed"] is False
    assert authority["historical_authorization_inherits"] is False
    assert authority["max_provider_attempts"] == 1
    assert authority["blind_mutation_retries"] == 0


def test_20260820_bundle_validates_without_state_or_provider_access() -> None:
    result = validate_bundle(PUBLICATION_ID)

    assert result["valid"] is True
    assert result["release_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["provider_mutation_allowed"] is False
    assert result["provider_access_performed"] is False
    assert result["blockers"] == [
        "release_authorized=false",
        "execution_authorized=false",
        "provider_mutation_allowed=false",
    ]


def test_stale_20260819_candidate_is_not_reinterpreted_as_20260820() -> None:
    stale = _json(CONTENT / "next-publication-candidate-2026-08-19.json")
    current = _json(CONTENT / "next-publication-candidate-2026-08-20.json")

    assert stale["publication_id"] == "milovi-feed-20260819-001"
    assert stale["scheduled_at"] == "2026-08-19T10:30:00+03:00"
    assert current["publication_id"] == PUBLICATION_ID
    assert current["scheduled_at"] == "2026-08-20T10:30:00+03:00"
    assert stale["publication_id"] != current["publication_id"]
