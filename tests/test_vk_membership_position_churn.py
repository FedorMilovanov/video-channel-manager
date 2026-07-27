from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType


def _load_verifier() -> ModuleType:
    scripts = Path("scripts").resolve()
    sys.path.insert(0, str(scripts))
    try:
        path = scripts / "verify_vk_reviewed_correction_apply_bundle.py"
        spec = importlib.util.spec_from_file_location("vk_correction_apply_verifier", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def _membership(video_id: str, position: int) -> dict[str, object]:
    return {
        "collection_ref": {"remote_id": "-13"},
        "video_ref": {"remote_id": video_id},
        "position": position,
        "membership_id": None,
    }


def test_position_only_churn_does_not_change_membership_identity() -> None:
    verifier = _load_verifier()
    source = {
        "memberships": [
            _membership("video-a", 37),
            _membership("video-b", 38),
        ]
    }
    final = {
        "memberships": [
            _membership("video-a", 38),
            _membership("video-b", 37),
        ]
    }

    assert Counter(verifier._membership_identity_rows(source)) == Counter(
        verifier._membership_identity_rows(final)
    )
    assert verifier._membership_sha256(source) == verifier._membership_sha256(final)
    assert verifier._membership_position_changes(source, final) == [
        {
            "collection_id": "-13",
            "video_id": "video-a",
            "before_position": 37,
            "after_position": 38,
        },
        {
            "collection_id": "-13",
            "video_id": "video-b",
            "before_position": 38,
            "after_position": 37,
        },
    ]


def test_real_membership_change_still_changes_identity() -> None:
    verifier = _load_verifier()
    source = {"memberships": [_membership("video-a", 37)]}
    final = {"memberships": [_membership("video-c", 37)]}

    assert Counter(verifier._membership_identity_rows(source)) != Counter(
        verifier._membership_identity_rows(final)
    )
    assert verifier._membership_sha256(source) != verifier._membership_sha256(final)
