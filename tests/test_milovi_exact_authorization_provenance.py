from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager import milovi_telegram_feed as milovi

PUBLICATION_ID = "milovi-feed-20260821-001"
LEGACY_UNSCOPED_PUBLICATION_ID = "milovi-feed-20260820-002"
RELEASE_PATH = Path("content/telegram/milovi-cake/releases/milovi-feed-20260821-001-runtime.json")
AUTHORITY_PATH = Path("content/telegram/milovi-cake/releases/milovi-feed-20260821-001-execution-authority.json")
LEGACY_RELEASE_PATH = Path("content/telegram/milovi-cake/releases/milovi-feed-20260820-002-runtime.json")
LEGACY_AUTHORITY_PATH = Path("content/telegram/milovi-cake/releases/milovi-feed-20260820-002-execution-authority.json")
LEGACY_CANDIDATE_DIGEST = "sha256:46cfea48120a395fe6b8dff87c7c7b328f2f0a83ca245ed9d35e591a45c580f6"
LEGACY_RELEASE_DIGEST = "sha256:d507dc58519b9c5ec3bceede9ad1792b7b602c93fa3f13e48e287b6aee9e25dc"


def _release_with_review_identity(publication_id: str):
    release = milovi.load_release(RELEASE_PATH)
    payload = release.model_dump(mode="python")
    payload["reviewed_publication_id"] = publication_id
    return release.__class__.model_validate(payload)


def _authority_with_identity(publication_id: str, *, release_digest: str):
    authority = milovi._load_authority(AUTHORITY_PATH)
    payload = authority.model_dump(mode="python")
    payload["authorized_publication_id"] = publication_id
    payload["release_digest"] = release_digest
    return milovi.MiloviExecutionAuthority.model_validate(payload)


def test_live_release_rejects_unstructured_human_review_provenance() -> None:
    with pytest.raises(
        ValueError,
        match="release review provenance does not bind exact publication_id",
    ):
        milovi.validate_bundle(PUBLICATION_ID, require_release_authorized=True)


def test_live_execution_rejects_unstructured_human_authority_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _release_with_review_identity(PUBLICATION_ID)
    monkeypatch.setattr(milovi, "load_release", lambda _path: release)

    with pytest.raises(
        ValueError,
        match="execution provenance does not bind exact publication_id",
    ):
        milovi.validate_bundle(PUBLICATION_ID, require_execution_authorized=True)


def test_exact_structured_publication_authorization_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _release_with_review_identity(PUBLICATION_ID)
    authority = _authority_with_identity(PUBLICATION_ID, release_digest=release.digest)
    monkeypatch.setattr(milovi, "load_release", lambda _path: release)
    monkeypatch.setattr(milovi, "_load_authority", lambda _path: authority)

    result = milovi.validate_bundle(PUBLICATION_ID, require_execution_authorized=True)

    assert result["valid"] is True
    assert result["release_authorized"] is True
    assert result["execution_authorized"] is True
    assert result["provider_mutation_allowed"] is True
    assert result["provider_access_performed"] is False


def test_mismatched_structured_release_identity_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _release_with_review_identity("milovi-feed-20990101-999")
    monkeypatch.setattr(milovi, "load_release", lambda _path: release)

    with pytest.raises(
        ValueError,
        match="release review provenance does not bind exact publication_id",
    ):
        milovi.validate_bundle(PUBLICATION_ID, require_release_authorized=True)


def test_mismatched_structured_execution_identity_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _release_with_review_identity(PUBLICATION_ID)
    authority = _authority_with_identity("milovi-feed-20990101-999", release_digest=release.digest)
    monkeypatch.setattr(milovi, "load_release", lambda _path: release)
    monkeypatch.setattr(milovi, "_load_authority", lambda _path: authority)

    with pytest.raises(
        ValueError,
        match="execution provenance does not bind exact publication_id",
    ):
        milovi.validate_bundle(PUBLICATION_ID, require_execution_authorized=True)


def test_inactive_authority_accepts_null_structured_provenance() -> None:
    authority = milovi._load_authority(AUTHORITY_PATH)
    payload = authority.model_dump(mode="python")
    payload.update(
        execution_authorized=False,
        provider_mutation_allowed=False,
        release_digest=None,
        authorized_by=None,
        authorized_publication_id=None,
        authorized_at=None,
    )

    inactive = milovi.MiloviExecutionAuthority.model_validate(payload)

    assert inactive.execution_authorized is False
    assert inactive.provider_mutation_allowed is False
    assert inactive.authorized_publication_id is None


def test_legacy_unscoped_evidence_is_unchanged_readable_but_not_live_authority() -> None:
    release = milovi.load_release(LEGACY_RELEASE_PATH)
    authority = milovi._load_authority(LEGACY_AUTHORITY_PATH)

    assert release.release_authorized is True
    assert release.reviewed_candidate_sha256 == LEGACY_CANDIDATE_DIGEST
    assert release.reviewed_publication_id is None
    assert release.candidate_digest() == LEGACY_CANDIDATE_DIGEST
    assert release.digest == LEGACY_RELEASE_DIGEST
    assert authority.execution_authorized is True
    assert authority.provider_mutation_allowed is True
    assert authority.release_digest == LEGACY_RELEASE_DIGEST
    assert authority.authorized_by == "human user via ChatGPT request 2026-08-20"
    assert authority.authorized_publication_id is None

    result = milovi.validate_bundle(LEGACY_UNSCOPED_PUBLICATION_ID)
    assert result["valid"] is True
    assert result["provider_access_performed"] is False

    with pytest.raises(
        ValueError,
        match="release review provenance does not bind exact publication_id",
    ):
        milovi.validate_bundle(LEGACY_UNSCOPED_PUBLICATION_ID, require_release_authorized=True)
