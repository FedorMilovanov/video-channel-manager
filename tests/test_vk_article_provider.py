from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot
from video_channel_manager.wave_engine.engine import UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import (
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
)
from video_channel_manager.wave_engine.vk_article_provider import (
    VK_ARTICLE_ACCOUNT_ALIAS,
    VK_ARTICLE_COMMUNITY_ID,
    VK_ARTICLE_OPERATION_KIND,
    VK_ARTICLE_OWNER_ID,
    ArticleOperation,
    VkArticleWallError,
    VkArticleWallWriter,
    VkPostponedArticlePhotoAdapter,
    WallCapture,
    jpeg_dimensions,
    parse_article_operation,
)

ARTICLE_URL = "https://thelegendarypoet.ru/essays/test-article"
MESSAGE = f"Историческая заметка.\n\nЧитайте полную статью:\n{ARTICLE_URL}"
PUBLISH_DATE = 1_800_000_000


def _jpeg(width: int = 1200, height: int = 630) -> bytes:
    return (
        b"\xff\xd8"
        b"\xff\xc0"
        b"\x00\x11"
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def _operation(*, asset_path: str = "asset.jpg") -> WaveOperation:
    message_sha256 = "sha256:" + hashlib.sha256(MESSAGE.encode("utf-8")).hexdigest()
    spec = WaveOperationSpec(
        order_key="01-test",
        operation_kind=VK_ARTICLE_OPERATION_KIND,
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload={
            "editorial_operation_id": "approved-01",
            "account_alias": VK_ARTICLE_ACCOUNT_ALIAS,
            "article_url": ARTICLE_URL,
            "image_source_url": "https://thelegendarypoet.ru/images/test.webp",
            "message": MESSAGE,
            "message_sha256": message_sha256,
            "publish_date": PUBLISH_DATE,
            "publish_at": "2027-01-15T11:00:00+03:00",
            "guid": "vcm-art-0123456789abcdef0123456789ab",
            "asset_path": asset_path,
            "asset_sha256": hashlib.sha256(_jpeg()).hexdigest(),
            "asset_width": 1200,
            "asset_height": 630,
            "policy_sha256": "sha256:" + "a" * 64,
            "required_canary": None,
        },
    )
    return WaveOperation.build(
        sequence=0,
        project=ProjectBinding(
            project_key="legendary-poet",
            community_id=VK_ARTICLE_COMMUNITY_ID,
            owner_id=VK_ARTICLE_OWNER_ID,
        ),
        source_snapshot_id="b" * 64,
        policy_version="test-v1",
        spec=spec,
    )


def _article(*, message: str = MESSAGE, publish_date: int = PUBLISH_DATE) -> ArticleOperation:
    return ArticleOperation(
        editorial_operation_id="approved-01",
        account_alias=VK_ARTICLE_ACCOUNT_ALIAS,
        article_url=ARTICLE_URL,
        image_source_url="https://thelegendarypoet.ru/images/test.webp",
        message=message,
        message_sha256="sha256:" + hashlib.sha256(message.encode("utf-8")).hexdigest(),
        publish_date=publish_date,
        guid="vcm-art-0123456789abcdef0123456789ab",
        asset_path="asset.jpg",
        asset_sha256=hashlib.sha256(_jpeg()).hexdigest(),
        asset_width=1200,
        asset_height=630,
        required_canary=None,
    )


def _post(*, post_id: int, text: str, publish_date: int, photo_id: int = 10) -> dict[str, object]:
    return {
        "owner_id": VK_ARTICLE_OWNER_ID,
        "id": post_id,
        "date": publish_date,
        "text": text,
        "attachments": [
            {
                "type": "photo",
                "photo": {"owner_id": VK_ARTICLE_OWNER_ID, "id": photo_id},
            }
        ],
    }


def _capture(
    *,
    published: list[dict[str, object]] | None = None,
    postponed: list[dict[str, object]] | None = None,
) -> WallCapture:
    published_items = published or []
    postponed_items = postponed or []
    snapshot = build_wall_snapshot(
        community_id=VK_ARTICLE_COMMUNITY_ID,
        published_items=published_items,
        postponed_items=postponed_items,
        published_pages=1,
        postponed_pages=1,
        complete=True,
    )
    return WallCapture(
        published=tuple(published_items),
        postponed=tuple(postponed_items),
        snapshot=snapshot,
    )


def test_parse_article_operation_and_jpeg_dimensions() -> None:
    parsed = parse_article_operation(_operation())
    assert parsed.article_url == ARTICLE_URL
    assert parsed.message == MESSAGE
    assert parsed.publish_date == PUBLISH_DATE
    assert jpeg_dimensions(_jpeg()) == (1200, 630)


def test_invalid_message_digest_fails_closed() -> None:
    operation = _operation()
    payload = dict(operation.payload)
    payload["message_sha256"] = "sha256:" + "0" * 64
    tampered = operation.model_copy(update={"payload": payload})
    with pytest.raises(VkArticleWallError, match="message_sha256 mismatch"):
        parse_article_operation(tampered)


def test_same_article_url_can_have_distinct_approved_posts() -> None:
    earlier_message = f"Другой самостоятельный анонс.\n\n{ARTICLE_URL}"
    capture = _capture(
        postponed=[
            _post(
                post_id=11,
                text=earlier_message,
                publish_date=PUBLISH_DATE - 172_800,
            )
        ]
    )
    assert VkArticleWallWriter._preflight_conflicts(capture, _article()) is None


def test_exact_existing_post_is_adopted_but_schedule_collision_is_blocked() -> None:
    exact_capture = _capture(postponed=[_post(post_id=12, text=MESSAGE, publish_date=PUBLISH_DATE)])
    existing = VkArticleWallWriter._preflight_conflicts(exact_capture, _article())
    assert existing is not None
    assert existing.remote_id == f"{VK_ARTICLE_OWNER_ID}_12"

    collision_capture = _capture(
        postponed=[
            _post(
                post_id=13,
                text="Другая публикация.\n\nhttps://thelegendarypoet.ru/essays/other",
                publish_date=PUBLISH_DATE,
            )
        ]
    )
    with pytest.raises(VkArticleWallError, match="schedule slot"):
        VkArticleWallWriter._preflight_conflicts(collision_capture, _article())


class _FakeWriter:
    def __init__(self, *, unknown: bool = False) -> None:
        self.unknown = unknown
        self.calls = 0

    def schedule(self, *, article: ArticleOperation, jpeg: bytes) -> dict[str, object]:
        self.calls += 1
        assert article.article_url == ARTICLE_URL
        assert jpeg_dimensions(jpeg) == (1200, 630)
        if self.unknown:
            raise UnknownProviderOutcomeError("provider response lost")
        return {"status": "scheduled", "remote_id": f"{VK_ARTICLE_OWNER_ID}_101"}


def _adapter(tmp_path: Path, writer: _FakeWriter) -> VkPostponedArticlePhotoAdapter:
    adapter = object.__new__(VkPostponedArticlePhotoAdapter)
    adapter.repository_root = tmp_path.resolve()
    adapter.account_alias = VK_ARTICLE_ACCOUNT_ALIAS
    adapter.settings = SimpleNamespace(data_dir=tmp_path / "data")
    adapter.writer = writer
    return adapter


def test_adapter_verifies_exact_asset_before_single_dispatch(tmp_path: Path) -> None:
    asset = tmp_path / "asset.jpg"
    asset.write_bytes(_jpeg())
    writer = _FakeWriter()
    adapter = _adapter(tmp_path, writer)

    evidence = adapter.execute(_operation())
    assert evidence["status"] == "scheduled"
    assert writer.calls == 1


def test_adapter_preserves_unknown_outcome_and_does_not_retry(tmp_path: Path) -> None:
    asset = tmp_path / "asset.jpg"
    asset.write_bytes(_jpeg())
    writer = _FakeWriter(unknown=True)
    adapter = _adapter(tmp_path, writer)

    with pytest.raises(UnknownProviderOutcomeError):
        adapter.execute(_operation())
    assert writer.calls == 1
