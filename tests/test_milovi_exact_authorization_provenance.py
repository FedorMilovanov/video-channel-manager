from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager import milovi_telegram_feed as milovi

PUBLICATION_ID = "milovi-feed-20260821-001"
LEGACY_UNSCOPED_PUBLICATION_ID = "milovi-feed-20260820-002"
RELEASE_PATH = Path("content/telegram/milovi-cake/releases/milovi-feed-20260821-001-runtime.json")
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def _active_authority(authorized_by: str) -> milovi.MiloviExecutionAuthority:
    return milovi.MiloviExecutionAuthority(
        schema_name="video-channel-manager.milovi-telegram-execution-authority",
        schema_version=1,
        project_key="milovi-cake",
        publication_id=PUBLICATION_ID,
        release_id=PUBLICATION_ID,
        release_candidate_sha256=DIGEST_A,
        release_digest=DIGEST_B,
        provider_payload_sha256=DIGEST_C,
        execution_authorized=True,
        provider_mutation_allowed=True,
        authorized_by=authorized_by,
        authorized_at=datetime(2026, 8, 21, 3, 50, tzinfo=UTC),
        authority_source="fresh_exact_human_authorization_only",
        historical_authorization_inherits=False,
        automation_is_execution_authority=False,
        max_provider_attempts=1,
        blind_mutation_retries=0,
    )


def test_active_execution_authority_rejects_generic_human_provenance() -> None:
    with pytest.raises(
        ValidationError,
        match="authorized_by must name exact publication_id",
    ):
        _active_authority("human user requested real posts")


def test_active_execution_authority_accepts_exact_publication_provenance() -> None:
    authority = _active_authority(f"human user explicitly authorized {PUBLICATION_ID} for @MiloviCake")

    assert authority.execution_authorized is True
    assert authority.provider_mutation_allowed is True


def test_authorized_release_rejects_generic_review_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    release = milovi.load_release(RELEASE_PATH)
    generic_release = release.model_copy(update={"reviewed_by": "human user requested real posts"})
    monkeypatch.setattr(milovi, "load_release", lambda _path: generic_release)

    with pytest.raises(
        ValueError,
        match="reviewed_by must name exact release_id",
    ):
        milovi.validate_bundle(PUBLICATION_ID)


def test_historical_exact_release_provenance_remains_valid() -> None:
    result = milovi.validate_bundle(PUBLICATION_ID)

    assert result["valid"] is True
    assert result["publication_id"] == PUBLICATION_ID
    assert result["release_authorized"] is True
    assert result["provider_access_performed"] is False


def test_legacy_unscoped_authorization_is_retired_provider_inert() -> None:
    result = milovi.validate_bundle(LEGACY_UNSCOPED_PUBLICATION_ID)

    assert result["valid"] is True
    assert result["release_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["provider_mutation_allowed"] is False
    assert result["provider_access_performed"] is False
