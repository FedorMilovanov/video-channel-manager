from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3.common import OWNER_ID  # noqa: E402
from lord_god_article_wave_v3.photo_wave_v5 import (  # noqa: E402
    build_photo_policy,
    group_wall_photo_identity,
    preflight,
    reference_matches_group_rehost,
)
from lord_god_article_wave_v3.wall import post_reference  # noqa: E402


def raw_post(operation: dict[str, object], *, photo_owner_id: int, photo_id: int) -> dict[str, object]:
    return {
        "owner_id": OWNER_ID,
        "id": 12471,
        "date": operation["publish_date"],
        "text": operation["message"],
        "attachments": [
            {
                "type": "photo",
                "photo": {
                    "owner_id": photo_owner_id,
                    "id": photo_id,
                },
            }
        ],
    }


def test_group_wall_photo_identity_accepts_one_group_owned_photo() -> None:
    reference = {
        "photo_identities": [f"photo{OWNER_ID}_457246560"],
    }

    assert group_wall_photo_identity(reference) == f"photo{OWNER_ID}_457246560"
    assert group_wall_photo_identity({"photo_identities": ["photo631487_457250594"]}) is None
    assert group_wall_photo_identity({"photo_identities": []}) is None
    assert group_wall_photo_identity({"photo_identities": [f"photo{OWNER_ID}_1", f"photo{OWNER_ID}_2"]}) is None


def test_reference_matches_exact_post_with_vk_group_rehost() -> None:
    policy = build_photo_policy(ROOT)
    operation = policy["operations"][0]
    reference = post_reference(
        raw_post(operation, photo_owner_id=OWNER_ID, photo_id=457246560),
        "postponed",
    )

    assert reference_matches_group_rehost(operation, reference) is True


def test_preflight_uses_posted_group_identity_after_rehost() -> None:
    policy = build_photo_policy(ROOT)
    operation = policy["operations"][0]
    posted_identity = f"photo{OWNER_ID}_457246560"
    postponed = [
        raw_post(operation, photo_owner_id=OWNER_ID, photo_id=457246560),
    ]
    journal = {
        "operations": {
            operation["operation_id"]: {
                "stage": "verified",
                "photo_token": "photo631487_457250594",
                "posted_photo_identity": posted_identity,
                "post_id": 12471,
            }
        }
    }

    report = preflight(
        policy,
        [],
        postponed,
        journal,
        minimum_future_seconds=0,
    )

    assert report["already_applied"] == 1
    assert report["ready"] == 9
    assert report["conflicts"] == 0


def test_preflight_rejects_unreconciled_user_photo_identity() -> None:
    policy = build_photo_policy(ROOT)
    operation = policy["operations"][0]
    postponed = [
        raw_post(operation, photo_owner_id=OWNER_ID, photo_id=457246560),
    ]
    journal = {
        "operations": {
            operation["operation_id"]: {
                "stage": "wall_post_accepted_unverified",
                "photo_token": "photo631487_457250594",
                "post_id": 12471,
            }
        }
    }

    report = preflight(
        policy,
        [],
        postponed,
        journal,
        minimum_future_seconds=0,
    )

    assert report["already_applied"] == 0
    assert report["conflicts"] >= 1
