from __future__ import annotations

import hashlib

import pytest

import video_channel_manager.wave_engine.vk_article_provider as provider_module
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot
from video_channel_manager.wave_engine.engine import UnknownProviderOutcomeError
from video_channel_manager.wave_engine.vk_article_provider import (
    VK_ARTICLE_ACCOUNT_ALIAS,
    VK_ARTICLE_APPROVED_POLICY_SHA256,
    VK_ARTICLE_COMMUNITY_ID,
    VK_ARTICLE_OWNER_ID,
    ArticleOperation,
    VkArticleWallWriter,
    WallCapture,
)

ARTICLE_URL = "https://thelegendarypoet.ru/essays/postflight-test"
MESSAGE = f"Точный исторический анонс.\n\nЧитайте полную статью:\n{ARTICLE_URL}"
PUBLISH_DATE = 1_800_000_000
POST_ID = 77


def _article() -> ArticleOperation:
    return ArticleOperation(
        editorial_operation_id="approved-postflight-01",
        account_alias=VK_ARTICLE_ACCOUNT_ALIAS,
        article_url=ARTICLE_URL,
        image_source_url="https://thelegendarypoet.ru/images/postflight-test.webp",
        message=MESSAGE,
        message_sha256="sha256:" + hashlib.sha256(MESSAGE.encode("utf-8")).hexdigest(),
        publish_date=PUBLISH_DATE,
        guid="vcm-art-0123456789abcdef0123456789ab",
        asset_path="asset.jpg",
        asset_sha256="a" * 64,
        asset_width=1200,
        asset_height=630,
        policy_sha256=VK_ARTICLE_APPROVED_POLICY_SHA256,
        required_canary=None,
    )


def _post(*, text: str) -> dict[str, object]:
    return {
        "owner_id": VK_ARTICLE_OWNER_ID,
        "id": POST_ID,
        "date": PUBLISH_DATE,
        "text": text,
        "attachments": [
            {
                "type": "photo",
                "photo": {"owner_id": VK_ARTICLE_OWNER_ID, "id": 501},
            }
        ],
    }


def _capture(*, postponed: list[dict[str, object]] | None = None) -> WallCapture:
    postponed_items = postponed or []
    snapshot = build_wall_snapshot(
        community_id=VK_ARTICLE_COMMUNITY_ID,
        published_items=[],
        postponed_items=postponed_items,
        published_pages=1,
        postponed_pages=1,
        complete=True,
    )
    return WallCapture(
        published=(),
        postponed=tuple(postponed_items),
        snapshot=snapshot,
    )


class _ScheduleWriter(VkArticleWallWriter):
    def __init__(self, *, after: WallCapture) -> None:
        self._captures = [_capture(), after]
        self._capture_index = 0
        self.wall_post_calls = 0
        self.photo_save_calls = 0

    def capture_complete_wall(self, *, max_posts_per_surface: int = 10_000) -> WallCapture:
        del max_posts_per_surface
        index = min(self._capture_index, len(self._captures) - 1)
        self._capture_index += 1
        return self._captures[index]

    def _wall_upload_url(self) -> str:
        return "https://pu.vk.ru/upload"

    def _upload_jpeg_once(
        self,
        *,
        upload_url: str,
        article: ArticleOperation,
        jpeg: bytes,
    ) -> dict[str, object]:
        assert upload_url == "https://pu.vk.ru/upload"
        assert article.article_url == ARTICLE_URL
        assert jpeg == b"jpeg"
        return {"photo": "payload", "server": 1, "hash": "hash"}

    def _save_wall_photo(self, upload: dict[str, object]) -> tuple[str, int, int]:
        assert upload == {"photo": "payload", "server": 1, "hash": "hash"}
        self.photo_save_calls += 1
        return "photo123_456_key", 123, 456

    def _call(
        self,
        method: str,
        *,
        params: dict[str, object],
        retry_transient: bool = False,
    ) -> object:
        del retry_transient
        assert method == "wall.post"
        assert params["owner_id"] == VK_ARTICLE_OWNER_ID
        assert params["message"] == MESSAGE
        assert params["publish_date"] == PUBLISH_DATE
        assert params["attachments"] == "photo123_456_key"
        self.wall_post_calls += 1
        return {"post_id": POST_ID}


def test_schedule_requires_exact_postflight_before_final_success() -> None:
    writer = _ScheduleWriter(after=_capture(postponed=[_post(text=MESSAGE)]))

    evidence = writer.schedule(article=_article(), jpeg=b"jpeg")

    assert evidence["status"] == "scheduled"
    assert evidence["remote_id"] == f"{VK_ARTICLE_OWNER_ID}_{POST_ID}"
    assert evidence["photo_tokens"] == [f"photo{VK_ARTICLE_OWNER_ID}_501"]
    assert writer.photo_save_calls == 1
    assert writer.wall_post_calls == 1


def test_schedule_postflight_mismatch_is_unknown_and_never_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _ScheduleWriter(after=_capture(postponed=[_post(text="wrong text")]))
    monkeypatch.setattr(provider_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(UnknownProviderOutcomeError, match="not exactly visible"):
        writer.schedule(article=_article(), jpeg=b"jpeg")

    assert writer.photo_save_calls == 1
    assert writer.wall_post_calls == 1
