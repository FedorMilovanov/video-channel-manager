from __future__ import annotations

from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalizer


def _video_attachment(video_id: int = 456239225) -> dict[str, Any]:
    return {
        "type": "video",
        "video": {
            "owner_id": -68859909,
            "id": video_id,
            "type": "short_video",
        },
    }


def _post() -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 468,
        "date": 1786723200,
        "attachments": [_video_attachment()],
    }


def test_rollout_wall_shape_allows_provider_projected_non_video_attachment() -> None:
    post = _post()
    post["attachments"].append(
        {
            "type": "link",
            "link": {
                "url": "https://milovicake.ru/",
                "title": "provider projection",
            },
        }
    )

    finalizer._assert_post_shape(
        post,
        clip_remote_id="-68859909_456239225",
        publish_date=1786723200,
    )


def test_rollout_wall_shape_rejects_second_video_even_with_non_video_projection() -> None:
    post = _post()
    post["attachments"].extend(
        [
            {"type": "link", "link": {"url": "https://milovicake.ru/"}},
            _video_attachment(456239999),
        ]
    )

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="exactly one video attachment; observed 2"):
        finalizer._assert_post_shape(
            post,
            clip_remote_id="-68859909_456239225",
            publish_date=1786723200,
        )


def test_rollout_wall_shape_rejects_missing_video() -> None:
    post = _post()
    post["attachments"] = [{"type": "link", "link": {"url": "https://milovicake.ru/"}}]

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="exactly one video attachment; observed 0"):
        finalizer._assert_post_shape(
            post,
            clip_remote_id="-68859909_456239225",
            publish_date=1786723200,
        )


def test_rollout_wall_shape_rejects_malformed_non_video_projection() -> None:
    post = _post()
    post["attachments"].append("not-an-object")

    with pytest.raises(finalizer.MiloviFinalizerBlocked, match="attachment 1 is not an object"):
        finalizer._assert_post_shape(
            post,
            clip_remote_id="-68859909_456239225",
            publish_date=1786723200,
        )
