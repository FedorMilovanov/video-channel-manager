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


def _post(post_source: object) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 475,
        "date": ANOMALY_CREATED_AT,
        "from_id": -68859909,
        "created_by": ANOMALY_CREATED_BY,
        "post_type": "post",
        "post_source": post_source,
        "text": "provider-rendered text",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239232,
                    "type": "short_video",
                    "description": "https://www.youtube.com/shorts/o1WXIMupuws",
                },
            }
        ],
    }


def test_default_strict_contract_still_rejects_provider_source_drift() -> None:
    with pytest.raises(MiloviFinalizerBlocked, match="provider source"):
        _strict_raw_anomaly(_post({"type": "api"}), "o1WXIMupuws")


@pytest.mark.parametrize("post_source", [{"type": "api"}, {}, None])
def test_exact_reconciler_flag_tolerates_only_provider_source_drift(post_source: object) -> None:
    _strict_raw_anomaly(
        _post(post_source),
        "o1WXIMupuws",
        allow_provider_source_drift=True,
    )


def test_exact_reconciler_flag_does_not_relax_attachment_identity() -> None:
    post = _post({"type": "api"})
    post["attachments"][0]["video"]["id"] = 456239999
    with pytest.raises(MiloviFinalizerBlocked, match="456239232"):
        _strict_raw_anomaly(
            post,
            "o1WXIMupuws",
            allow_provider_source_drift=True,
        )


class _Reader:
    def __init__(self, post: dict[str, Any]) -> None:
        self.post = post

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        return self.post


def test_normalized_writer_requires_explicit_provider_source_drift_flag() -> None:
    post = _post({"type": "api"})
    writer = _TextNormalizedAnomalyWriter(
        _Reader(post),  # type: ignore[arg-type]
        "o1WXIMupuws",
        allow_provider_source_drift=True,
    )

    observed = writer.read_post(community_id=68859909, post_id=475)

    assert observed is not None
    assert observed["text"] == ""
    assert post["text"] == "provider-rendered text"
