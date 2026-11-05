"""Provider-inert, exact-owner tests for public Milovi School wall comparison."""

from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_school_public_wall_audit import (
    MILOVI_COMMUNITY_ID,
    MILOVI_OWNER_ID,
    classify_editorial_wall_posts,
    collect_exact_public_wall,
    source_ids_from_editorial,
)

SOURCE_IDS = (
    "herme-ispahan-deep",
    "tech-mirror-glaze",
    "grolet-lemon-yuzu",
    "mercotte-entremets-system",
    "recipe-madeleines",
    "recipe-fondant-chocolat",
    "tech-tempering-chocolate",
    "tech-creme-pat",
    "recipe-macarons-herme",
    "tech-mousse-stability",
)


class FakeClient:
    def __init__(self, posts: list[dict], *, declared_count: int | None = None) -> None:
        self.posts = posts
        self.declared_count = len(posts) if declared_count is None else declared_count
        self.calls: list[dict] = []

    def _call(self, method: str, *, params: dict) -> dict:
        assert method == "wall.get"
        assert params["owner_id"] == MILOVI_OWNER_ID
        assert params["filter"] == "owner"
        assert params["count"] == 100
        self.calls.append(params)
        offset = params["offset"]
        return {"count": self.declared_count, "items": self.posts[offset : offset + 100]}


def _post(post_id: int, text: str = "") -> dict:
    return {"id": post_id, "owner_id": MILOVI_OWNER_ID, "text": text}


def test_single_complete_public_read_and_exact_source_matches() -> None:
    posts = [
        _post(1, "Patisserie Russe: https://french.milovicake.ru/articles/tech-mirror-glaze/"),
        _post(2, "Video about cake"),
        {
            **_post(3),
            "copy_history": [_post(400, "https://french.milovicake.ru/articles/herme-ispahan-deep/")],
            "attachments": [{"type": "link", "link": {"url": "https://french.milovicake.ru/articles/tech-creme-pat/"}}],
        },
    ]
    client = FakeClient(posts)
    readback = collect_exact_public_wall(client)
    assert len(readback) == 3
    assert len(client.calls) == 1
    report = classify_editorial_wall_posts(readback, SOURCE_IDS)
    statuses = {p["source_id"]: p for p in report["source_classification"]}
    assert report["community_id"] == MILOVI_COMMUNITY_ID
    assert report["public_wall_complete"] is True
    assert report["provider_writes"] == 0
    assert statuses["tech-mirror-glaze"]["matches"][0]["url"] == "https://vk.com/wall-68859909_1"
    assert statuses["herme-ispahan-deep"]["public_wall_presence"] == "found"
    assert statuses["tech-creme-pat"]["public_wall_presence"] == "found"
    assert statuses["recipe-madeleines"]["public_wall_presence"] == "not_found_on_public_wall"
    assert all(not item["automatically_eligible_to_publish"] for item in statuses.values())
    assert report["postponed_state"] == "unverified_user_reported_empty"
    assert report["native_articles_state"] == "unverified"


def test_complete_multiple_pages_only_when_exact_owner_count_stable() -> None:
    client = FakeClient([_post(i) for i in range(1, 103)])
    posts = collect_exact_public_wall(client)
    assert len(posts) == 102
    assert [v["offset"] for v in client.calls] == [0, 100]


def test_read_rejects_truncated_wrong_owner_duplicates_and_unbounded_scan() -> None:
    with pytest.raises(ValueError, match="truncated"):
        collect_exact_public_wall(FakeClient([_post(1)], declared_count=2))
    with pytest.raises(ValueError, match="wrong-owner"):
        collect_exact_public_wall(FakeClient([{**_post(1), "owner_id": -123}]))
    with pytest.raises(ValueError, match="duplicate"):
        collect_exact_public_wall(FakeClient([_post(1), _post(1)]))
    with pytest.raises(ValueError, match="ceiling"):
        collect_exact_public_wall(FakeClient([]), max_posts=3001)


def test_editorial_source_parser_rejects_duplicates_or_unapproved_state() -> None:
    draft = "project_key=milovi-cake community `68859909` execution_authorized=false\n" + "".join(
        "Source ID: " + chr(96) + slug + chr(96) + "\n" + 2 * f"https://french.milovicake.ru/articles/{slug}/\n"
        for slug in SOURCE_IDS
    )
    assert source_ids_from_editorial(draft) == SOURCE_IDS
    with pytest.raises(ValueError, match="10 distinct"):
        source_ids_from_editorial(draft.replace("tech-mousse-stability", "tech-creme-pat"))
    with pytest.raises(ValueError, match="provider-inert"):
        source_ids_from_editorial(draft.replace("execution_authorized=false", "execution_authorized=true"))
