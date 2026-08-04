from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from video_channel_manager.platforms.vk.thumbnail_lifecycle import (
    ThumbnailPostflightUnverified,
    ThumbnailStatus,
    execute_thumbnail_operation,
    read_thumbnail_record,
)

OWNER_ID = -235216998
VIDEO_ID = 456239134
PROJECT_KEY = "legendary-poet"


def _png(path: Path) -> Path:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (1280).to_bytes(4, "big") + (720).to_bytes(4, "big")
    )
    return path


class _UploadCrashWriter:
    def get_upload_url(self, *, owner_id: int) -> str:
        assert owner_id == OWNER_ID
        return "https://upload.example/thumb"

    def upload_image(self, *, upload_url: str, path: Path) -> dict[str, Any]:
        assert upload_url == "https://upload.example/thumb"
        assert path.is_file()
        raise SystemExit("simulated process crash after upload intent")


class _SaveCrashWriter:
    def get_upload_url(self, *, owner_id: int) -> str:
        assert owner_id == OWNER_ID
        return "https://upload.example/thumb"

    def upload_image(self, *, upload_url: str, path: Path) -> dict[str, Any]:
        return {"thumb_json": '{"photo":"payload"}'}

    def save_uploaded_thumbnail(
        self,
        *,
        owner_id: int,
        video_id: int,
        upload_payload: dict[str, Any],
    ) -> dict[str, Any]:
        assert owner_id == OWNER_ID
        assert video_id == VIDEO_ID
        assert upload_payload["thumb_json"]
        raise SystemExit("simulated process crash after save intent")


class _NoNetworkWriter:
    def __init__(self) -> None:
        self.calls = 0

    def __getattr__(self, name: str) -> Any:
        self.calls += 1
        raise AssertionError(f"network method must not be called after crash intent: {name}")


@pytest.mark.parametrize(
    ("writer", "expected_status"),
    [
        (_UploadCrashWriter(), ThumbnailStatus.UPLOAD_INTENT_RECORDED),
        (_SaveCrashWriter(), ThumbnailStatus.SAVE_INTENT_RECORDED),
    ],
)
def test_restart_after_dispatch_intent_never_replays_mutation(
    tmp_path: Path,
    writer: object,
    expected_status: ThumbnailStatus,
) -> None:
    image = _png(tmp_path / "thumb.png")
    journal = tmp_path / "thumb.json"

    with pytest.raises(SystemExit):
        execute_thumbnail_operation(
            writer=writer,  # type: ignore[arg-type]
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )

    assert read_thumbnail_record(journal).status == expected_status.value

    no_network = _NoNetworkWriter()
    with pytest.raises(ThumbnailPostflightUnverified, match="must not be replayed") as error:
        execute_thumbnail_operation(
            writer=no_network,  # type: ignore[arg-type]
            project_key=PROJECT_KEY,
            owner_id=OWNER_ID,
            video_id=VIDEO_ID,
            image_path=image,
            journal_path=journal,
            postflight_delays=(0.0,),
        )

    assert error.value.record.status == ThumbnailStatus.UNKNOWN_REQUIRES_RECONCILIATION.value
    assert no_network.calls == 0
