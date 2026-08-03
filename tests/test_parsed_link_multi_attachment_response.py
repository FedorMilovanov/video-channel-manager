from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lord_god_article_wave_v3 import parsed_link_contract as contract  # noqa: E402
from lord_god_article_wave_v3 import parsed_link_preview as preview  # noqa: E402


def _load_operation() -> tuple[dict[str, Any], dict[str, str]]:
    policy, _ = contract.load_parsed_policy(ROOT)
    operation = policy["operations"][0]
    metadata = {
        "title": str(operation["title"]),
        "description": ("Проверенное полное описание статьи для карточки ВКонтакте длиной более сорока символов."),
    }
    return operation, metadata


def _link_attachment(
    operation: dict[str, Any],
    metadata: dict[str, str],
) -> dict[str, Any]:
    return {
        "type": "link",
        "link": {
            "url": operation["url"],
            "title": metadata["title"],
            "description": metadata["description"],
            "photo": {
                "owner_id": -60805374,
                "id": 991,
                "sizes": [{"width": 1200, "height": 630}],
            },
        },
    }


def test_matching_link_is_selected_from_multi_attachment_response() -> None:
    operation, metadata = _load_operation()
    response = {
        "data": [
            {"type": "photo", "photo": {"owner_id": -1, "id": 10}},
            _link_attachment(operation, metadata),
            {"type": "video", "video": {"owner_id": -1, "id": 20}},
        ]
    }

    parsed = preview.parse_link_response(
        response,
        article_url=operation["url"],
        expected_metadata=metadata,
    )

    assert parsed["article_url"] == operation["url"]
    assert parsed["link_photo_id"] == "-60805374_991"
    assert parsed["response_attachment_count"] == 3
    assert parsed["ignored_attachment_types"] == ["photo", "video"]


def test_multiple_matching_links_are_rejected() -> None:
    operation, metadata = _load_operation()
    link = _link_attachment(operation, metadata)
    response = {"data": [link, _link_attachment(operation, metadata)]}

    with pytest.raises(RuntimeError, match="multiple matching link attachments"):
        preview.parse_link_response(
            response,
            article_url=operation["url"],
            expected_metadata=metadata,
        )


def test_no_matching_link_reports_returned_attachment_shape() -> None:
    operation, metadata = _load_operation()
    response = {
        "data": [
            {"type": "photo", "photo": {"owner_id": -1, "id": 10}},
            {"type": "video", "video": {"owner_id": -1, "id": 20}},
        ]
    }

    with pytest.raises(RuntimeError, match="attachment_types=.*photo.*video"):
        preview.parse_link_response(
            response,
            article_url=operation["url"],
            expected_metadata=metadata,
        )
