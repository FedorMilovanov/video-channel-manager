from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "operations" / "mutation-boundary-register.json"
GOLDEN_PATH = ROOT / "docs" / "operations" / "vk-native-clip-golden-path.md"


def _boundaries() -> list[dict[str, object]]:
    payload = json.loads(REGISTER.read_text(encoding="utf-8"))
    boundaries = payload["boundaries"]
    assert isinstance(boundaries, list)
    return boundaries


def test_vk_upload_reservation_has_one_generic_provider_owner() -> None:
    matches = [item for item in _boundaries() if item.get("scanner_marker") == "vk_api:video.save"]

    assert len(matches) == 1
    boundary = matches[0]
    assert boundary["boundary_id"] == "vk.video.upload.reserve"
    assert boundary["source_file"] == "src/video_channel_manager/platforms/vk/writer.py"
    assert boundary["callable"] == "VkVideoWriter.begin_upload"
    assert boundary["retry_policy"] == "never_replay"
    assert boundary["attempt_limit"] == 1


def test_vk_binary_transfer_has_one_generic_provider_owner() -> None:
    matches = [item for item in _boundaries() if item.get("scanner_marker") == "http:video.upload"]

    assert len(matches) == 1
    boundary = matches[0]
    assert boundary["boundary_id"] == "vk.video.upload.transfer"
    assert boundary["source_file"] == "src/video_channel_manager/platforms/vk/writer.py"
    assert boundary["callable"] == "VkVideoWriter.upload_file"
    assert boundary["retry_policy"] == "never_replay"
    assert boundary["attempt_limit"] == 1


def test_golden_path_forbids_project_specific_upload_semantics() -> None:
    text = GOLDEN_PATH.read_text(encoding="utf-8")

    for required in (
        "Direct provider reservation/transfer primitives remain centralized",
        "a project-specific direct `video.save` owner",
        "a second binary-transfer lifecycle",
        "duplicated existing-Clip reconciliation semantics",
        "community-scoped writer serialization",
        "Do not refactor an in-progress provider rollout",
    ):
        assert required in text
