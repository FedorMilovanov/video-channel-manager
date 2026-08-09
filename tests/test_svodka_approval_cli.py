from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.svodka_approval_cli import (
    load_svodka_release_approval,
    materialize_svodka_approved_release,
)
from video_channel_manager.telegram_multichannel_release import load_release

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
APPROVAL_PATH = REPOSITORY_ROOT / "content/telegram/svodka/release-approval-2026-08.json"


def test_exact_review_receipt_materializes_authorized_release(tmp_path: Path) -> None:
    approval = load_svodka_release_approval(APPROVAL_PATH)
    output = tmp_path / "approved-release.json"

    candidate_digest, release_digest = materialize_svodka_approved_release(
        profile_path=PROFILE_PATH,
        queue_path=QUEUE_PATH,
        binding_path=BINDING_PATH,
        approval_path=APPROVAL_PATH,
        output_path=output,
    )
    release = load_release(output)

    assert candidate_digest == approval.candidate_sha256
    assert release_digest == approval.approved_release_sha256
    assert release.digest == approval.approved_release_sha256
    assert release.reviewed_candidate_sha256 == approval.candidate_sha256
    assert release.release_authorized is True
    assert len(release.items) == 14
    assert release.items[4].publication_id == "svodka-2026-august-total-solar-eclipse"
    assert release.items[4].scheduled_at.isoformat() == "2026-08-12T10:30:00+03:00"
    assert release.items[5].publication_id == "svodka-octopus-three-hearts-blue-blood"


def test_stale_candidate_receipt_fails_closed(tmp_path: Path) -> None:
    approval_payload = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    approval_payload["candidate_sha256"] = "sha256:" + "0" * 64
    stale_approval = tmp_path / "stale-approval.json"
    stale_approval.write_text(json.dumps(approval_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="differs from reviewed approval"):
        materialize_svodka_approved_release(
            profile_path=PROFILE_PATH,
            queue_path=QUEUE_PATH,
            binding_path=BINDING_PATH,
            approval_path=stale_approval,
            output_path=tmp_path / "should-not-exist.json",
        )


def test_wrong_approved_release_digest_fails_closed(tmp_path: Path) -> None:
    approval_payload = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    approval_payload["approved_release_sha256"] = "sha256:" + "f" * 64
    bad_approval = tmp_path / "bad-release-digest.json"
    bad_approval.write_text(json.dumps(approval_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="approved release digest mismatch"):
        materialize_svodka_approved_release(
            profile_path=PROFILE_PATH,
            queue_path=QUEUE_PATH,
            binding_path=BINDING_PATH,
            approval_path=bad_approval,
            output_path=tmp_path / "should-not-exist.json",
        )
