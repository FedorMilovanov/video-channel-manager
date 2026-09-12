from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import video_channel_manager.wave_engine.vk_video_wall_provider as provider_module
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot
from video_channel_manager.platforms.vk.writer import VkWriteError
from video_channel_manager.wave_engine.engine import KnownProviderRejectionError, UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import MutationClass, ProjectBinding, WaveOperation, WaveOperationSpec
from video_channel_manager.wave_engine.vk_video_wall_provider import (
    VK_VIDEO_WALL_COMMUNITY_ID,
    VK_VIDEO_WALL_OPERATION_KIND,
    VK_VIDEO_WALL_OWNER_ID,
    VideoWallCapture,
    VkPostponedVideoWallAdapter,
    VkVideoWallError,
    VkVideoWallWriter,
    parse_video_wall_operation,
)

SOURCE_ID = "NgvWlaMqTnI"
VIDEO_ID = 456239215
REMOTE_ID = f"{VK_VIDEO_WALL_OWNER_ID}_{VIDEO_ID}"
MESSAGE = "Зимний вечер — Александр Пушкин\n\nhttps://thelegendarypoet.ru/"
PUBLISH_DATE = 1_800_000_000
TITLE = "Зимний вечер ⚡ VERSION 2 ⚡ Пушкин"
DESCRIPTION = f"Описание\n\nhttps://www.youtube.com/watch?v={SOURCE_ID}"


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _guid() -> str:
    seed = f"{SOURCE_ID}:{REMOTE_ID}:{PUBLISH_DATE}:{_sha(MESSAGE)}"
    return "vcm-vwall-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:28]


def _operation() -> WaveOperation:
    spec = WaveOperationSpec(
        order_key="001",
        operation_kind=VK_VIDEO_WALL_OPERATION_KIND,
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload={
            "source_video_id": SOURCE_ID,
            "account_alias": "legendary-poet",
            "video_owner_id": VK_VIDEO_WALL_OWNER_ID,
            "video_id": VIDEO_ID,
            "video_remote_id": REMOTE_ID,
            "message": MESSAGE,
            "message_sha256": _sha(MESSAGE),
            "publish_date": PUBLISH_DATE,
            "guid": _guid(),
            "expected_video_title": TITLE,
            "expected_video_description_sha256": _sha(DESCRIPTION),
        },
    )

    return WaveOperation.build(
        sequence=0,
        project=ProjectBinding(
            project_key="legendary-poet",
            community_id=VK_VIDEO_WALL_COMMUNITY_ID,
            owner_id=VK_VIDEO_WALL_OWNER_ID,
        ),
        source_snapshot_id="a" * 64,
        policy_version="test-video-wall-v1",
        spec=spec,
    )


def _post(*, post_id: int, message: str = MESSAGE, publish_date: int = PUBLISH_DATE) -> dict[str, object]:
    return {
        "owner_id": VK_VIDEO_WALL_OWNER_ID,
        "id": post_id,
        "date": publish_date,
        "text": message,
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": VK_VIDEO_WALL_OWNER_ID, "id": VIDEO_ID},
            }
        ],
    }


def _capture(
    *,
    published: list[dict[str, object]] | None = None,
    postponed: list[dict[str, object]] | None = None,
) -> VideoWallCapture:

    published_items = published or []
    postponed_items = postponed or []
    snapshot = build_wall_snapshot(
        community_id=VK_VIDEO_WALL_COMMUNITY_ID,
        published_items=published_items,
        postponed_items=postponed_items,
        published_pages=1,
        postponed_pages=1,
        complete=True,
    )
    return VideoWallCapture(
        published=tuple(published_items),
        postponed=tuple(postponed_items),
        snapshot=snapshot,
    )


def test_parse_video_wall_operation_binds_exact_identity() -> None:
    parsed = parse_video_wall_operation(_operation())
    assert parsed.video_remote_id == REMOTE_ID
    assert parsed.attachment == f"video{REMOTE_ID}"
    assert parsed.message_sha256 == _sha(MESSAGE)


def test_parse_rejects_non_deterministic_guid() -> None:
    operation = _operation()
    payload = dict(operation.payload)
    payload["guid"] = "vcm-vwall-" + "0" * 28
    tampered = operation.model_copy(update={"payload": payload})
    with pytest.raises(VkVideoWallError, match="deterministic"):
        parse_video_wall_operation(tampered)


def test_preflight_adopts_exact_and_blocks_other_reference() -> None:
    wall = parse_video_wall_operation(_operation())
    exact = VkVideoWallWriter._preflight_conflicts(
        _capture(postponed=[_post(post_id=10)]),
        wall,
    )
    assert exact is not None
    assert exact.remote_id == f"{VK_VIDEO_WALL_OWNER_ID}_10"

    with pytest.raises(VkVideoWallError, match="different published/postponed"):
        VkVideoWallWriter._preflight_conflicts(
            _capture(published=[_post(post_id=11, message="Другой текст")]),
            wall,
        )


def test_preflight_blocks_occupied_postponed_slot() -> None:
    wall = parse_video_wall_operation(_operation())
    collision = {
        "owner_id": VK_VIDEO_WALL_OWNER_ID,
        "id": 12,
        "date": PUBLISH_DATE,
        "text": "Другая публикация",
        "attachments": [],
    }
    with pytest.raises(VkVideoWallError, match="schedule slot"):
        VkVideoWallWriter._preflight_conflicts(_capture(postponed=[collision]), wall)


@pytest.mark.parametrize("method", ["wall.get", "wall.post"])
def test_schedule_stops_on_open_required_wall_circuit_before_any_provider_call(
    tmp_path: Path,
    method: str,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = VkVideoWallWriter(
        token_store=VkTokenStore(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )
    writer.flood_control.record(method)

    with pytest.raises(VkWriteError, match="circuit is open") as captured:
        writer.schedule(wall=parse_video_wall_operation(_operation()))

    assert captured.value.attempts == 0
    assert captured.value.method == method
    assert calls == 0


def test_reconcile_stops_on_open_wall_get_circuit_before_any_provider_call(tmp_path: Path) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    writer = VkVideoWallWriter(
        token_store=VkTokenStore(tmp_path),
        account_alias="legendary-poet",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )
    writer.flood_control.record("wall.get")

    with pytest.raises(VkWriteError, match="circuit is open for wall.get") as captured:
        writer.reconcile_exact(wall=parse_video_wall_operation(_operation()))

    assert captured.value.attempts == 0
    assert calls == 0


class _ScheduleWriter(VkVideoWallWriter):
    def __init__(self, *, after: VideoWallCapture) -> None:
        self._captures = [_capture(), after]
        self._capture_index = 0
        self.wall_post_calls = 0

    def assert_method_circuit_closed(self, method: str) -> None:
        assert method in {"wall.get", "wall.post"}

    def verify_video(self, wall: object) -> dict[str, object]:
        return {"id": VIDEO_ID}

    def capture_complete_wall(self, *, max_posts_per_surface: int = 10_000) -> VideoWallCapture:
        del max_posts_per_surface
        index = min(self._capture_index, len(self._captures) - 1)
        self._capture_index += 1
        return self._captures[index]

    def _call(
        self,
        method: str,
        *,
        params: dict[str, object],
        retry_transient: bool = False,
    ) -> object:
        del retry_transient
        assert method == "wall.post"
        assert params["owner_id"] == VK_VIDEO_WALL_OWNER_ID
        assert params["attachments"] == f"video{REMOTE_ID}"
        assert params["publish_date"] == PUBLISH_DATE
        assert params["guid"] == _guid()
        self.wall_post_calls += 1
        return {"post_id": 77}


def test_schedule_requires_exact_postflight() -> None:
    writer = _ScheduleWriter(after=_capture(postponed=[_post(post_id=77)]))
    evidence = writer.schedule(wall=parse_video_wall_operation(_operation()))
    assert evidence["status"] == "scheduled"
    assert evidence["remote_id"] == f"{VK_VIDEO_WALL_OWNER_ID}_77"
    assert writer.wall_post_calls == 1


def test_schedule_postflight_mismatch_is_unknown_and_never_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _ScheduleWriter(after=_capture(postponed=[_post(post_id=77, message="Неверный текст")]))
    monkeypatch.setattr(provider_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(UnknownProviderOutcomeError, match="not exactly visible"):
        writer.schedule(wall=parse_video_wall_operation(_operation()))

    assert writer.wall_post_calls == 1


class _ErrorWriter:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def schedule(self, *, wall: object) -> dict[str, object]:
        raise self.error


def test_adapter_classifies_explicit_provider_rejection_as_known(
    tmp_path: Path,
) -> None:
    adapter = object.__new__(VkPostponedVideoWallAdapter)
    adapter.settings = SimpleNamespace(data_dir=tmp_path)
    adapter.account_alias = "legendary-poet"
    adapter.writer = _ErrorWriter(
        VkWriteError(
            "VK API 9 in wall.post: Flood control",
            method="wall.post",
            code=9,
            attempts=1,
        )
    )

    with pytest.raises(KnownProviderRejectionError):
        adapter.execute(_operation())
