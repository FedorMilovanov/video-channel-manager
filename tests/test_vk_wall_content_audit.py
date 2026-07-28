from __future__ import annotations

from video_channel_manager.platforms.vk.catalog import canonical_sha256
from video_channel_manager.platforms.vk.wall_content_audit import (
    build_wall_content_audit,
    extract_video_ids_from_post,
    render_wall_content_audit_markdown,
)


def _video(
    remote_id: str,
    title: str,
    *,
    wall_post_id: int | None = None,
    is_short: bool = False,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "is_short_video": is_short,
        "permalink": f"https://vk.com/video{remote_id}",
    }
    if wall_post_id is not None:
        metadata["wall_post_id"] = wall_post_id
    return {
        "ref": {"remote_id": remote_id},
        "title": title,
        "published_at": "2026-07-28T10:00:00Z",
        "duration_seconds": 120,
        "metadata": metadata,
    }


def _post(
    post_id: int,
    *,
    video_id: str | None = None,
    text: str = "",
    copy_history: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    attachments: list[dict[str, object]] = []
    if video_id is not None:
        owner_text, item_text = video_id.split("_", maxsplit=1)
        attachments.append(
            {
                "type": "video",
                "video": {"owner_id": int(owner_text), "id": int(item_text)},
            }
        )
    payload: dict[str, object] = {
        "owner_id": -235216998,
        "id": post_id,
        "date": 1_753_700_000 + post_id,
        "text": text,
        "attachments": attachments,
    }
    if copy_history is not None:
        payload["copy_history"] = copy_history
    return payload


def test_extract_video_ids_from_attachments_links_and_reposts() -> None:
    post = _post(
        11,
        video_id="-235216998_456239109",
        text=(
            "Смотрите https://vkvideo.ru/video-235216998_456239111 и "
            "https://vk.com/clip-235216998_456239112"
        ),
        copy_history=[_post(10, text="Повтор: video-235216998_456239113")],
    )

    assert extract_video_ids_from_post(post) == {
        "-235216998_456239109",
        "-235216998_456239111",
        "-235216998_456239112",
        "-235216998_456239113",
    }


def test_wall_audit_classifies_every_video_without_guessing() -> None:
    videos = [
        _video("-235216998_1", "Опубликовано"),
        _video("-235216998_2", "Отложено", is_short=True),
        _video("-235216998_3", "Не публиковалось"),
        _video("-235216998_4", "Только старый marker", wall_post_id=44),
        _video("-235216998_5", "Конфликт"),
    ]
    published = [
        _post(101, video_id="-235216998_1"),
        _post(105, text="https://vk.com/video-235216998_5"),
    ]
    postponed = [
        _post(202, video_id="-235216998_2"),
        _post(205, video_id="-235216998_5"),
    ]

    audit = build_wall_content_audit(
        community_id=235216998,
        videos=videos,
        published_posts=published,
        postponed_posts=postponed,
    )
    states = {item["video_id"]: item["state"] for item in audit["videos"]}

    assert states == {
        "-235216998_1": "published",
        "-235216998_2": "scheduled",
        "-235216998_3": "unposted",
        "-235216998_4": "wall_marker_only_review",
        "-235216998_5": "published_and_scheduled_conflict",
    }
    assert audit["status"] == "review_required"
    assert audit["summary"] == {
        "videos": 5,
        "published_wall_posts": 2,
        "postponed_wall_posts": 2,
        "published_videos": 1,
        "scheduled_videos": 1,
        "unposted_videos": 1,
        "wall_marker_only_review": 1,
        "published_and_scheduled_conflicts": 1,
        "duplicate_post_references": 1,
    }
    assert audit["audit_sha256"] == canonical_sha256(
        {key: value for key, value in audit.items() if key != "audit_sha256"}
    )


def test_duplicate_published_references_are_reported() -> None:
    video_id = "-235216998_456239109"
    audit = build_wall_content_audit(
        community_id=235216998,
        videos=[_video(video_id, "Дубликат")],
        published_posts=[_post(1, video_id=video_id), _post(2, text=f"video{video_id}")],
        postponed_posts=[],
    )

    assert audit["status"] == "review_required"
    assert audit["summary"]["duplicate_post_references"] == 1
    assert audit["duplicate_post_references"][0]["video_id"] == video_id
    assert len(audit["duplicate_post_references"][0]["published_posts"]) == 2


def test_clean_audit_lists_only_confirmed_unposted_videos() -> None:
    audit = build_wall_content_audit(
        community_id=235216998,
        videos=[
            _video("-235216998_1", "Уже было"),
            _video("-235216998_2", "Новая публикация", is_short=True),
        ],
        published_posts=[_post(1, video_id="-235216998_1")],
        postponed_posts=[],
    )
    markdown = render_wall_content_audit_markdown(audit)

    assert audit["status"] == "completed"
    assert audit["summary"]["unposted_videos"] == 1
    assert "`-235216998_2` · short · Новая публикация" in markdown
    assert "`-235216998_1` ·" not in markdown
