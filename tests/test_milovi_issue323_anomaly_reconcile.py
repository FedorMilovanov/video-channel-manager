from __future__ import annotations

from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile import (
    ANOMALY_CREATED_AT,
    ANOMALY_CREATED_BY,
    _TextNormalizedAnomalyWriter,
    _strict_raw_anomaly,
)
from video_channel_manager.platforms.vk.milovi_issue323_finalize import MiloviFinalizerBlocked


def _post(*, text: str = "provider-rendered text") -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 475,
        "date": ANOMALY_CREATED_AT,
        "from_id": -68859909,
        "created_by": ANOMALY_CREATED_BY,
        "post_type": "post",
        "post_source": {"type": "vk"},
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239232,
                    "type": "short_video",
                    "description": (
                        "#Торт на День Рождения от #Milovi_Cake #ВикторияМилованова\n\n"
                        "Источник YouTube Shorts: https://www.youtube.com/shorts/o1WXIMupuws"
                    ),
                },
            }
        ],
    }


def test_strict_raw_anomaly_accepts_provider_text_drift() -> None:
    _strict_raw_anomaly(_post(text="provider later rendered this text"), "o1WXIMupuws")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner_id", -1),
        ("id", 999),
        ("date", ANOMALY_CREATED_AT + 1),
        ("from_id", -1),
        ("created_by", ANOMALY_CREATED_BY + 1),
        ("post_type", "reply"),
    ],
)
def test_strict_raw_anomaly_rejects_immutable_identity_drift(field: str, value: object) -> None:
    post = _post()
    post[field] = value
    with pytest.raises(MiloviFinalizerBlocked):
        _strict_raw_anomaly(post, "o1WXIMupuws")


def test_strict_raw_anomaly_rejects_provider_source_drift() -> None:
    post = _post()
    post["post_source"] = {"type": "api"}
    with pytest.raises(MiloviFinalizerBlocked, match="provider source"):
        _strict_raw_anomaly(post, "o1WXIMupuws")


def test_strict_raw_anomaly_rejects_attachment_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["id"] = 456239999
    with pytest.raises(MiloviFinalizerBlocked, match="456239232"):
        _strict_raw_anomaly(post, "o1WXIMupuws")


def test_strict_raw_anomaly_rejects_source_marker_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["description"] = "different source"
    with pytest.raises(MiloviFinalizerBlocked, match="source marker"):
        _strict_raw_anomaly(post, "o1WXIMupuws")


class _Reader:
    def __init__(self, post: dict[str, Any]) -> None:
        self.post = post

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        return self.post

    def sentinel(self) -> str:
        return "delegated"


def test_normalized_writer_changes_only_in_process_text_view() -> None:
    original = _post(text="provider-rendered text")
    delegate = _Reader(original)
    writer = _TextNormalizedAnomalyWriter(delegate, "o1WXIMupuws")  # type: ignore[arg-type]

    observed = writer.read_post(community_id=68859909, post_id=475)

    assert observed is not None
    assert observed["text"] == ""
    assert original["text"] == "provider-rendered text"
    assert writer.sentinel() == "delegated"
