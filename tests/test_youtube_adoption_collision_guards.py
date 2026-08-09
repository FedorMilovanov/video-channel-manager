from __future__ import annotations

import pytest

from video_channel_manager.youtube_release_cli import _verify_existing_journal_for_adoption
from video_channel_manager.youtube_upload_plan import UploadPlanError


def _journal(*, alias: str = "legendary-poet", evidence_sha: str = "sha256:" + "a" * 64) -> dict:
    return {
        "account_alias": alias,
        "state": "verified",
        "provider_effect": "verified",
        "adopted_existing_target": True,
        "remote_video_id": "VID1",
        "adoption_evidence_sha256": evidence_sha,
    }


def test_adoption_refuses_different_oauth_alias_even_for_same_video() -> None:
    current = _journal(alias="wrong-alias")
    proposed = _journal()

    with pytest.raises(UploadPlanError, match="OAuth alias conflicts"):
        _verify_existing_journal_for_adoption(current, proposed=proposed)


def test_adoption_refuses_silent_rebinding_to_different_immutable_evidence() -> None:
    current = _journal(evidence_sha="sha256:" + "a" * 64)
    proposed = _journal(evidence_sha="sha256:" + "b" * 64)

    with pytest.raises(UploadPlanError, match="different immutable evidence"):
        _verify_existing_journal_for_adoption(current, proposed=proposed)


def test_same_exact_adoption_identity_is_allowed() -> None:
    current = _journal()
    proposed = _journal()

    _verify_existing_journal_for_adoption(current, proposed=proposed)
