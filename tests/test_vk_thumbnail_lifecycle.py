from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.vk.models import VkAccessToken
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.thumbnail_lifecycle import (
    THUMBNAIL_EVIDENCE_SCHEMA,
    ThumbnailEvidenceError,
    ThumbnailPostflightUnverified,
    ThumbnailStatus,
    execute_thumbnail_operation,
    read_thumbnail_record,
)
from video_channel_manager.platforms.vk.thumbnail_writer import VerifiedVkThumbnailWriter

OWNER_ID = -235216998
VIDEO_ID = 456239134
PROJECT_KEY = "legendary-poet"


def _png(path: Path, *, width: int = 1280, height: int = 720) -> Path:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )
    return path


def _writer(tmp_path: Path, respond: httpx.MockTransport) -> VerifiedVkThumbnailWriter:
    store = VkTokenStore(tmp_path / "tokens")
    store.save_token("legendary-poet", VkAccessToken(access_token="secret", scopes=["video", "groups"]))
    return VerifiedVkThumbnailWriter(
        token_store=store,
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=respond),
        api_base_url="https://api.example/method",
        max_attempts=1,
    )


def _images(*, query: str = "saved") -> list[dict[str, object]]:
    return [
        {
            "url": f"https://cdn.example/video/thumb-320.jpg?token={query}",
            "width": 320,
            "height": 180,
        },
        {
            "url": f"https://cdn.example/video/thumb-1280.jpg?token={query}",
            "width": 1280,
            "height": 720,
        },
    ]


def test_thumbnail_operation_requires_delayed_exact_readback(tmp_path: Path) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"
    calls: list[str] = []
    readbacks = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal readbacks
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            return httpx.Response(200, json={"thumb_json": '{"photo":"payload"}'})
        if request.url.path.endswith("/video.saveUploadedThumb"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "photo_id": 77,
                        "photo_owner_id": OWNER_ID,
                        "photo_hash": "hash-1",
                        "image": _images(query="save"),
                    }
                },
            )
        if request.url.path.endswith("/video.get"):
            readbacks += 1
            images = _images(query="other") if readbacks == 1 else _images(query="readback")
            if readbacks == 1:
                images[1] = {
                    "url": "https://cdn.example/video/different.jpg?token=other",
                    "width": 1280,
                    "height": 720,
                }
            return httpx.Response(
                200,
                json={"response": {"count": 1, "items": [{"owner_id": OWNER_ID, "id": VIDEO_ID, "image": images}]}},
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    record = execute_thumbnail_operation(
        writer=writer,
        project_key=PROJECT_KEY,
        owner_id=OWNER_ID,
        video_id=VIDEO_ID,
        image_path=image,
        journal_path=journal,
        postflight_delays=(0.0, 0.0),
    )

    assert record.schema_name == THUMBNAIL_EVIDENCE_SCHEMA
    assert record.status == ThumbnailStatus.VERIFIED.value
    assert record.saved_receipt is not None
    assert record.readback is not None
    assert readbacks == 2
    assert calls.count("/method/video.saveUploadedThumb") == 1
    assert read_thumbnail_record(journal).status == ThumbnailStatus.VERIFIED.value


def test_unverified_readback_never_replays_save_and_can_reconcile(tmp_path: Path) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"
    save_calls = 0

    def first_respond(request: httpx.Request) -> httpx.Response:
        nonlocal save_calls
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            return httpx.Response(200, json={"thumb_json": '{"photo":"payload"}'})
        if request.url.path.endswith("/video.saveUploadedThumb"):
            save_calls += 1
            return httpx.Response(
                200,
                json={
                    "response": {
                        "photo_id": 77,
                        "photo_owner_id": OWNER_ID,
                        "photo_hash": "hash-1",
                        "image": _images(query="save"),
                    }
                },
            )
        if request.url.path.endswith("/video.get"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "owner_id": OWNER_ID,
                                "id": VIDEO_ID,
                                "image": [
                                    {
                                        "url": "https://cdn.example/video/not-selected.jpg",
                                        "width": 1280,
                                        "height": 720,
                                    }
                                ],
                            }
                        ],
                    }
                },
            )
        raise AssertionError(request.url)

    with pytest.raises(ThumbnailPostflightUnverified) as error:
        execute_thumbnail_operation(
            writer=_writer(tmp_path, httpx.MockTransport(first_respond)),
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )

    assert error.value.record.status == ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION.value
    assert save_calls == 1

    reconcile_calls: list[str] = []

    def reconcile_respond(request: httpx.Request) -> httpx.Response:
        reconcile_calls.append(request.url.path)
        assert request.url.path.endswith("/video.get")
        return httpx.Response(
            200,
            json={
                "response": {
                    "count": 1,
                    "items": [{"owner_id": OWNER_ID, "id": VIDEO_ID, "image": _images(query="later")}],
                }
            },
        )

    reconciled = execute_thumbnail_operation(
        writer=_writer(tmp_path, httpx.MockTransport(reconcile_respond)),
        project_key=PROJECT_KEY,
        owner_id=OWNER_ID,
        video_id=VIDEO_ID,
        image_path=image,
        journal_path=journal,
        postflight_delays=(0.0,),
    )

    assert reconciled.status == ThumbnailStatus.VERIFIED.value
    assert reconcile_calls == ["/method/video.get"]
    assert save_calls == 1


def test_save_receipt_without_image_descriptors_is_not_success(tmp_path: Path) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            return httpx.Response(200, json={"thumb_json": '{"photo":"payload"}'})
        if request.url.path.endswith("/video.saveUploadedThumb"):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "photo_id": 77,
                        "photo_owner_id": OWNER_ID,
                        "photo_hash": "hash-1",
                        "image": [],
                    }
                },
            )
        raise AssertionError(request.url)

    with pytest.raises(ThumbnailPostflightUnverified, match="no image descriptors"):
        execute_thumbnail_operation(
            writer=_writer(tmp_path, httpx.MockTransport(respond)),
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )

    assert "/method/video.get" not in calls
    assert read_thumbnail_record(journal).status == ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION.value


def test_ambiguous_save_is_persisted_and_never_blindly_replayed(tmp_path: Path) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"
    save_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal save_calls
        if request.url.path.endswith("/video.getThumbUploadUrl"):
            return httpx.Response(200, json={"response": {"upload_url": "https://upload.example/thumb"}})
        if request.url == httpx.URL("https://upload.example/thumb"):
            return httpx.Response(200, json={"thumb_json": '{"photo":"payload"}'})
        if request.url.path.endswith("/video.saveUploadedThumb"):
            save_calls += 1
            return httpx.Response(503, text="ambiguous")
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(ThumbnailPostflightUnverified):
        execute_thumbnail_operation(
            writer=writer,
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )
    assert save_calls == 1

    with pytest.raises(ThumbnailPostflightUnverified, match="no exact save receipt"):
        execute_thumbnail_operation(
            writer=writer,
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )
    assert save_calls == 1


def test_wrong_project_or_tampered_journal_fails_before_network(tmp_path: Path) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"
    network_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(500)

    writer = _writer(tmp_path, httpx.MockTransport(respond))
    with pytest.raises(ThumbnailEvidenceError, match="same registered project"):
        execute_thumbnail_operation(
            writer=writer,
            project_key="lord-god-strength",
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
        )
    assert network_calls == 0

    journal.write_text(
        json.dumps(
            {
                "schema_name": THUMBNAIL_EVIDENCE_SCHEMA,
                "schema_version": "1.0",
                "ruleset": "wave-8e-v1",
                "operation_id": "wrong",
                "project_key": PROJECT_KEY,
                "owner_id": OWNER_ID,
                "video_id": VIDEO_ID,
                "local_thumbnail": {},
                "status": "prepared",
                "saved_receipt": None,
                "readback": None,
                "failure": None,
                "created_at": "2026-08-04T00:00:00+00:00",
                "updated_at": "2026-08-04T00:00:00+00:00",
                "evidence_digest": "tampered",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ThumbnailEvidenceError, match="digest"):
        execute_thumbnail_operation(
            writer=writer,
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
        )
    assert network_calls == 0
