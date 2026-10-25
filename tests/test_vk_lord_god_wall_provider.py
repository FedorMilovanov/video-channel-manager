from __future__ import annotations

import hashlib
from typing import Any

import pytest

from video_channel_manager.platforms.vk.wall_safety import (
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
)
from video_channel_manager.platforms.vk.writer import VkWriteError
from video_channel_manager.wave_engine.engine import UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import (
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
)
from video_channel_manager.wave_engine.vk_lord_god_wall_provider import (
    LORD_GOD_ACCOUNT_ALIAS,
    LORD_GOD_WALL_OPERATION_KIND,
    LORD_GOD_WALL_POLICY_VERSION,
    LordGodPostponedWallAdapter,
    LordGodWallError,
    LordGodWallWriter,
    parse_lord_god_wall_operation,
)


def sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def operation(payload: dict[str, Any]) -> WaveOperation:
    project = ProjectBinding(
        project_key="lord-god-strength",
        community_id=60805374,
        owner_id=-60805374,
    )
    spec = WaveOperationSpec(
        order_key="2026-09-13T12:00:00+03:00",
        operation_kind=LORD_GOD_WALL_OPERATION_KIND,
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload=payload,
    )
    return WaveOperation.build(
        sequence=0,
        project=project,
        source_snapshot_id="0" * 64,
        policy_version=LORD_GOD_WALL_POLICY_VERSION,
        spec=spec,
    )


def text_payload() -> dict[str, Any]:
    message = "Умерщвляй грех — иначе грех будет умерщвлять тебя."
    return {
        "content_kind": "text",
        "account_alias": LORD_GOD_ACCOUNT_ALIAS,
        "message": message,
        "message_sha256": sha(message),
        "publish_date": 2_000_000_000,
        "guid": "vcm-lgw-text-0001",
        "source_id": "lordchrist-bunyan-cross-burden",
    }


def video_payload() -> dict[str, Any]:
    message = "Джон МакАртур — Богодухновенность Библии."
    description = "Точное описание"
    return {
        "content_kind": "video",
        "account_alias": LORD_GOD_ACCOUNT_ALIAS,
        "message": message,
        "message_sha256": sha(message),
        "publish_date": 2_000_000_100,
        "guid": "vcm-lgw-video-0001",
        "source_id": "-60805374_170994532",
        "video_owner_id": -60805374,
        "video_id": 170994532,
        "video_remote_id": "-60805374_170994532",
        "expected_video_title": "Джон МакАртур. Богодухновенность Библии",
        "expected_video_description_sha256": sha(description),
    }


def snapshot(*posts: VkWallPostFingerprint) -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=60805374,
        captured_at="2026-09-12T07:00:00+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=tuple(posts),
    )


class _CircuitClosedWriter(LordGodWallWriter):
    def assert_method_circuit_closed(self, method: str) -> None:
        assert method in {"wall.get", "wall.post"}


def test_parse_text_operation_is_bound_to_lord_god_project() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    assert wall.content_kind == "text"
    assert wall.source_id == "lordchrist-bunyan-cross-burden"
    assert wall.video_remote_id is None
    assert wall.message_sha256 == sha(wall.message)


@pytest.mark.parametrize("quarantined_alias", ["legendary-poet", "default"])
def test_parse_rejects_quarantined_legacy_credential(quarantined_alias: str) -> None:
    payload = text_payload()
    payload["account_alias"] = quarantined_alias
    with pytest.raises(LordGodWallError, match="quarantined legacy VK credential"):
        parse_lord_god_wall_operation(operation(payload))


def test_adapter_refuses_quarantined_legacy_credential_before_settings() -> None:
    with pytest.raises(ValueError, match="quarantined legacy VK credential"):
        LordGodPostponedWallAdapter(account_alias="legendary-poet")


def test_verify_video_checks_exact_title_description_and_playability() -> None:
    wall = parse_lord_god_wall_operation(operation(video_payload()))

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            pass

        def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
            assert owner_id == -60805374
            assert video_id == 170994532
            return {
                "title": "Джон МакАртур. Богодухновенность Библии",
                "description": "Точное описание",
                "files": {"external": "https://example.invalid/video"},
            }

    item = FakeWriter().verify_video(wall)
    assert item["title"].startswith("Джон МакАртур")


def test_schedule_text_requires_exact_single_postflight_delta() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    created = VkWallPostFingerprint(
        owner_id=-60805374,
        post_id=13001,
        surface=VkWallSurface.POSTPONED,
        publish_date=wall.publish_date,
        text_sha256=wall.message_sha256,
        attachments=(),
    )

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            self._snapshots = iter((snapshot(), snapshot(created)))
            self.called: dict[str, Any] | None = None

        def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10_000) -> VkWallSnapshot:
            assert community_id == 60805374
            assert max_posts_per_surface == 10_000
            return next(self._snapshots)

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            assert method == "wall.post"
            self.called = params
            return {"post_id": 13001}

    writer = FakeWriter()
    result = writer.schedule_text(wall)
    assert result["status"] == "scheduled"
    assert result["remote_id"] == "-60805374_13001"
    assert result["surface"] == "postponed"
    assert writer.called is not None
    assert writer.called["owner_id"] == -60805374
    assert "attachments" not in writer.called


def test_text_preflight_collision_blocks_before_dispatch() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    occupied = VkWallPostFingerprint(
        owner_id=-60805374,
        post_id=12999,
        surface=VkWallSurface.POSTPONED,
        publish_date=wall.publish_date,
        text_sha256=sha("другой текст"),
        attachments=(),
    )

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            self.calls = 0

        def capture_wall_snapshot(
            self,
            *,
            community_id: int,
            max_posts_per_surface: int = 10_000,
        ) -> VkWallSnapshot:
            return snapshot(occupied)

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            self.calls += 1
            raise AssertionError("provider mutation must not be dispatched")

    writer = FakeWriter()
    with pytest.raises(LordGodWallError, match="schedule slot is already occupied"):
        writer.schedule_text(wall)
    assert writer.calls == 0


def test_text_lost_provider_response_is_unknown_and_never_replayed() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            self.calls = 0

        def capture_wall_snapshot(
            self,
            *,
            community_id: int,
            max_posts_per_surface: int = 10_000,
        ) -> VkWallSnapshot:
            return snapshot()

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            self.calls += 1
            raise RuntimeError("lost provider response")

    writer = FakeWriter()
    with pytest.raises(UnknownProviderOutcomeError, match="lost provider response"):
        writer.schedule_text(wall)
    assert writer.calls == 1


def test_text_postflight_mismatch_is_unknown_and_never_replayed() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    wrong = VkWallPostFingerprint(
        owner_id=-60805374,
        post_id=13001,
        surface=VkWallSurface.POSTPONED,
        publish_date=wall.publish_date,
        text_sha256=sha("неожиданный текст"),
        attachments=(),
    )

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            self.calls = 0
            self.snapshots = iter((snapshot(), snapshot(wrong)))

        def capture_wall_snapshot(
            self,
            *,
            community_id: int,
            max_posts_per_surface: int = 10_000,
        ) -> VkWallSnapshot:
            return next(self.snapshots)

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            self.calls += 1
            return {"post_id": 13001}

    writer = FakeWriter()
    with pytest.raises(UnknownProviderOutcomeError, match="not exactly visible"):
        writer.schedule_text(wall)
    assert writer.calls == 1


def test_text_open_wall_circuit_fails_before_snapshot_or_dispatch() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))

    class FakeWriter(LordGodWallWriter):
        def __init__(self) -> None:
            self.checked: list[str] = []
            self.snapshots = 0
            self.calls = 0

        def assert_method_circuit_closed(self, method: str) -> None:
            self.checked.append(method)
            raise VkWriteError(
                "VK flood-control circuit is open for wall.get",
                method=method,
                code=9,
                attempts=0,
            )

        def capture_wall_snapshot(
            self,
            *,
            community_id: int,
            max_posts_per_surface: int = 10_000,
        ) -> VkWallSnapshot:
            self.snapshots += 1
            raise AssertionError("wall snapshot must not be requested")

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            self.calls += 1
            raise AssertionError("provider mutation must not be dispatched")

    writer = FakeWriter()
    with pytest.raises(VkWriteError, match="flood-control circuit is open"):
        writer.schedule_text(wall)
    assert writer.checked == ["wall.get"]
    assert writer.snapshots == 0
    assert writer.calls == 0


def test_video_open_wall_circuit_fails_before_video_read_or_wall_snapshot() -> None:
    wall = parse_lord_god_wall_operation(operation(video_payload()))

    class FakeWriter(LordGodWallWriter):
        def __init__(self) -> None:
            self.checked: list[str] = []
            self.video_reads = 0
            self.snapshots = 0

        def assert_method_circuit_closed(self, method: str) -> None:
            self.checked.append(method)
            raise VkWriteError(
                "VK flood-control circuit is open for wall.get",
                method=method,
                code=9,
                attempts=0,
            )

        def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
            self.video_reads += 1
            raise AssertionError("video.get must not be requested")

        def capture_wall_snapshot(
            self,
            *,
            community_id: int,
            max_posts_per_surface: int = 10_000,
        ) -> VkWallSnapshot:
            self.snapshots += 1
            raise AssertionError("wall snapshot must not be requested")

    writer = FakeWriter()
    with pytest.raises(VkWriteError, match="flood-control circuit is open"):
        writer.schedule_video(wall)
    assert writer.checked == ["wall.get"]
    assert writer.video_reads == 0
    assert writer.snapshots == 0


def test_community_key_writer_uses_wall_permission_without_user_video_scope(tmp_path) -> None:
    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(
            access_token="community-secret",
            token_type="community",
            scopes=["photos", "docs", "messages", "wall", "manage", "stories", "market"],
            permission_mask=134623237,
        ),
    )
    writer = LordGodWallWriter(token_store=store, account_alias=LORD_GOD_ACCOUNT_ALIAS)

    assert writer._token_value() == "community-secret"
    assert writer.assert_token_scopes("wall").access_token == "community-secret"
    with pytest.raises(VkWriteError, match="community key does not verify"):
        writer.assert_token_scopes("video")


def test_user_token_writer_still_requires_video_scope(tmp_path) -> None:
    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(access_token="user-secret", token_type="user", scopes=["wall", "groups"]),
    )
    writer = LordGodWallWriter(token_store=store, account_alias=LORD_GOD_ACCOUNT_ALIAS)

    with pytest.raises(VkWriteError, match="does not verify required permission"):
        writer._token_value()


def test_community_key_schedule_text_end_to_end_with_mocked_vk(tmp_path) -> None:
    import urllib.parse

    import httpx

    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(
            access_token="community-secret",
            token_type="community",
            scopes=["photos", "docs", "messages", "wall", "manage", "stories", "market"],
            permission_mask=134623237,
        ),
    )
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    state = {"posted": False, "calls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        form = urllib.parse.parse_qs(request.content.decode("utf-8"))
        state["calls"].append((method, form))
        if method == "wall.getById":
            items = []
            if state["posted"]:
                items = [
                    {
                        "id": 777,
                        "owner_id": -60805374,
                        "date": wall.publish_date,
                        "text": wall.message,
                        "attachments": [],
                    }
                ]
            return httpx.Response(200, json={"response": {"count": len(items), "items": items}})
        if method == "wall.post":
            assert form.get("owner_id") == ["-60805374"]
            assert form.get("publish_date") == [str(wall.publish_date)]
            assert form.get("guid") == [wall.guid]
            state["posted"] = True
            return httpx.Response(200, json={"response": {"post_id": 777}})
        raise AssertionError(f"unexpected VK method: {method}")

    writer = LordGodWallWriter(
        token_store=store,
        account_alias=LORD_GOD_ACCOUNT_ALIAS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    result = writer.schedule_text(wall)

    assert result["status"] == "scheduled_community_key"
    assert result["remote_id"] == "-60805374_777"
    assert result["surface"] == "postponed"
    assert result["readback"] == {"status": "verified"}
    methods = [call[0] for call in state["calls"]]
    assert methods.count("wall.post") == 1
    assert "wall.get" not in methods


def test_community_key_schedule_survives_unavailable_readback(tmp_path) -> None:
    import httpx

    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(
            access_token="community-secret",
            token_type="community",
            scopes=["wall", "manage"],
            permission_mask=134623237,
        ),
    )
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        calls.append(method)
        if method == "wall.post":
            return httpx.Response(200, json={"response": {"post_id": 888}})
        if method == "wall.getById":
            return httpx.Response(
                200,
                json={"error": {"error_code": 27, "error_msg": "Group authorization failed"}},
            )
        raise AssertionError(f"unexpected VK method: {method}")

    writer = LordGodWallWriter(
        token_store=store,
        account_alias=LORD_GOD_ACCOUNT_ALIAS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    result = writer.schedule_text(wall)

    assert result["status"] == "scheduled_community_key"
    assert result["remote_id"] == "-60805374_888"
    assert result["readback"]["status"] == "unavailable"
    assert result["readback"]["code"] == 27
    assert "wall.get" not in calls


def test_community_key_wrong_credential_kind_blocks_before_dispatch(tmp_path) -> None:
    import httpx

    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(access_token="user-secret", token_type="user", scopes=["video", "wall", "groups"]),
    )
    wall = parse_lord_god_wall_operation(operation(text_payload()))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"response": {"post_id": 1}})

    writer = LordGodWallWriter(
        token_store=store,
        account_alias=LORD_GOD_ACCOUNT_ALIAS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    with pytest.raises(LordGodWallError, match="community access key"):
        writer.schedule_text_with_community_key(wall)
    assert calls == []


def _photo_payload(jpeg: bytes) -> dict[str, Any]:
    payload = text_payload()
    payload["photo_path"] = "content/telegram/lordchrist/telegraph-v1/media/lordchrist-telegraph-charnock-07-cover.jpg"
    payload["photo_sha256"] = "sha256:" + hashlib.sha256(jpeg).hexdigest()
    return payload


def _community_store(tmp_path, scopes: list[str]):
    from video_channel_manager.platforms.vk.models import VkAccessToken
    from video_channel_manager.platforms.vk.store import VkTokenStore

    store = VkTokenStore(tmp_path)
    store.save_token(
        LORD_GOD_ACCOUNT_ALIAS,
        VkAccessToken(
            access_token="community-secret",
            token_type="community",
            scopes=scopes,
            permission_mask=134623237,
        ),
    )
    return store


def test_parse_text_operation_accepts_bound_cover_photo() -> None:
    jpeg = b"\xff\xd8cover-bytes"
    wall = parse_lord_god_wall_operation(operation(_photo_payload(jpeg)))
    assert wall.photo_path is not None and wall.photo_path.endswith("charnock-07-cover.jpg")
    assert wall.photo_sha256 == "sha256:" + hashlib.sha256(jpeg).hexdigest()

    broken = _photo_payload(jpeg)
    del broken["photo_sha256"]
    with pytest.raises(LordGodWallError, match="must be supplied together"):
        parse_lord_god_wall_operation(operation(broken))


def test_community_key_photo_operation_is_rejected_before_any_call(tmp_path) -> None:
    # Live-proven in apply run 40197033579: photos.getWallUploadServer is
    # unavailable with group auth (VK error 27), so a cover operation must
    # fail deterministically before any provider call.
    import httpx

    jpeg = b"\xff\xd8fake-jpeg-bytes"
    store = _community_store(tmp_path, ["photos", "wall"])
    wall = parse_lord_god_wall_operation(operation(_photo_payload(jpeg)))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"response": {"post_id": 1}})

    writer = LordGodWallWriter(
        token_store=store,
        account_alias=LORD_GOD_ACCOUNT_ALIAS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_base_url="https://example.test/method",
    )

    with pytest.raises(LordGodWallError, match="cannot be uploaded with the community access key"):
        writer.schedule_text(wall)
    assert calls == []


def test_photo_text_post_is_reconcilable_by_exact_text_date_and_one_photo() -> None:
    jpeg = b"\xff\xd8fake-jpeg-bytes"
    wall = parse_lord_god_wall_operation(operation(_photo_payload(jpeg)))
    created = VkWallPostFingerprint(
        owner_id=-60805374,
        post_id=13002,
        surface=VkWallSurface.POSTPONED,
        publish_date=wall.publish_date,
        text_sha256=wall.message_sha256,
        attachments=("photo-60805374_555",),
    )

    class FakeWriter(_CircuitClosedWriter):
        def __init__(self) -> None:
            pass

        def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10_000) -> VkWallSnapshot:
            assert community_id == 60805374
            return snapshot(created)

    result = FakeWriter().reconcile_exact(wall)
    assert result["status"] == "reconciled_exact_post"
    assert result["remote_id"] == "-60805374_13002"


def test_community_key_lost_response_is_unknown_after_one_dispatch() -> None:
    wall = parse_lord_god_wall_operation(operation(text_payload()))

    class FakeWriter(LordGodWallWriter):
        def __init__(self) -> None:
            self.calls = 0

        def credential_token_type(self) -> str:
            return "community"

        def assert_token_scopes(self, *required_scopes: str):  # type: ignore[override]
            return None

        def assert_method_circuit_closed(self, method: str) -> None:
            return None

        def _call(self, method: str, *, params: dict[str, Any] | None = None, **_: Any) -> object:
            self.calls += 1
            raise RuntimeError("lost provider response")

    writer = FakeWriter()
    with pytest.raises(UnknownProviderOutcomeError, match="lost provider response"):
        writer.schedule_text_with_community_key(wall)
    assert writer.calls == 1
