from __future__ import annotations

from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile import (
    ANOMALY_CREATED_AT,
    ANOMALY_CREATED_BY,
    IDENTITY_CONTRACT,
    _record_observed_projection,
    _validate_wall475_identity,
)
from video_channel_manager.platforms.vk.milovi_issue323_finalize import MiloviFinalizerBlocked

_UNSET = object()


def _post(
    *,
    text: str = "provider-rendered text",
    post_source: object = _UNSET,
) -> dict[str, Any]:
    if post_source is _UNSET:
        post_source = {"type": "api"}
    return {
        "owner_id": -68859909,
        "id": 475,
        "date": ANOMALY_CREATED_AT,
        "from_id": -68859909,
        "created_by": ANOMALY_CREATED_BY,
        "post_type": "post",
        "post_source": post_source,
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


@pytest.mark.parametrize(
    ("text", "post_source"),
    [
        ("", {"type": "vk"}),
        ("provider later rendered this text", {"type": "api"}),
        ("another provider projection", {}),
        ("non-empty provider projection", None),
    ],
)
def test_wall475_identity_ignores_mutable_provider_projection(
    text: str,
    post_source: object,
) -> None:
    _validate_wall475_identity(_post(text=text, post_source=post_source), "o1WXIMupuws")


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
def test_wall475_identity_rejects_stable_identity_drift(field: str, value: object) -> None:
    post = _post()
    post[field] = value
    with pytest.raises(MiloviFinalizerBlocked):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_allows_missing_optional_created_by() -> None:
    post = _post()
    post.pop("created_by")
    _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["id"] = 456239999
    with pytest.raises(MiloviFinalizerBlocked, match="456239232"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_type_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["type"] = "video"
    with pytest.raises(MiloviFinalizerBlocked, match="short_video"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_source_marker_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["description"] = "different source"
    with pytest.raises(MiloviFinalizerBlocked, match="source marker"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_projection_is_recorded_as_evidence_without_becoming_identity() -> None:
    state: dict[str, Any] = {}
    post = _post(text="provider-rendered text", post_source={"type": "api", "platform": "iphone"})

    _record_observed_projection(state, post)

    assert state["identity_contract"] == IDENTITY_CONTRACT
    assert state["observed_provider_text_nonempty"] is True
    assert state["observed_post_source_type"] == "api"
    assert state["mutable_projection_fields"] == ["text", "post_source"]
    assert len(state["observed_provider_text_sha256"]) == 64
    assert len(state["observed_post_source_sha256"]) == 64
    assert len(state["observed_raw_post_sha256"]) == 64
