from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile as reconcile
from video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile import (
    ANOMALY_CREATED_AT,
    ANOMALY_CREATED_BY,
    IDENTITY_CONTRACT,
    _cleanup_exact_wall475,
    _record_observed_projection,
    _record_read_observation,
    _validate_deleted_wall475_tombstone,
    _validate_wall475_identity,
    _wall475_is_absent,
)
from video_channel_manager.platforms.vk.milovi_issue323_anomaly_state import (
    ANOMALY_CLIP_REMOTE_ID,
    ANOMALY_STATE_SCHEMA,
    ANOMALY_WALL_REMOTE_ID,
    MiloviIssue323AnomalyBlocked,
)

_UNSET = object()


def _video_attachment(*, video_id: int = 456239232) -> dict[str, Any]:
    return {
        "type": "video",
        "video": {
            "owner_id": -68859909,
            "id": video_id,
            "type": "short_video",
            "description": (
                "#Торт на День Рождения от #Milovi_Cake #ВикторияМилованова\n\n"
                "Источник YouTube Shorts: https://www.youtube.com/shorts/o1WXIMupuws"
            ),
        },
    }


def _post(
    *,
    text: str = "provider-rendered text",
    post_source: object = _UNSET,
) -> dict[str, Any]:
    if post_source is _UNSET:
        post_source = {"type": "api"}
    return {
        "owner_id": -68859909,
        "id": 475,
        "date": ANOMALY_CREATED_AT,
        "from_id": -68859909,
        "created_by": ANOMALY_CREATED_BY,
        "post_type": "post",
        "post_source": post_source,
        "text": text,
        "attachments": [_video_attachment()],
    }


def _deleted_tombstone(*, owner_id: int = -68859909, post_id: int = 475) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "id": post_id,
        "is_deleted": True,
    }


@pytest.mark.parametrize(
    ("text", "post_source"),
    [
        ("", {"type": "vk"}),
        ("provider later rendered this text", {"type": "api"}),
        ("another provider projection", {}),
        ("non-empty provider projection", None),
    ],
)
def test_wall475_identity_ignores_mutable_provider_projection(
    text: str,
    post_source: object,
) -> None:
    _validate_wall475_identity(_post(text=text, post_source=post_source), "o1WXIMupuws")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner_id", -1),
        ("id", 999),
        ("date", ANOMALY_CREATED_AT + 1),
        ("from_id", -1),
        ("created_by", ANOMALY_CREATED_BY + 1),
        ("post_type", "reply"),
    ],
)
def test_wall475_identity_rejects_stable_identity_drift(field: str, value: object) -> None:
    post = _post()
    post[field] = value
    with pytest.raises(MiloviIssue323AnomalyBlocked):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_allows_missing_optional_created_by() -> None:
    post = _post()
    post.pop("created_by")
    _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_deleted_tombstone_as_live_identity() -> None:
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="deleted tombstone"):
        _validate_wall475_identity(_deleted_tombstone(), "o1WXIMupuws")


def test_exact_deleted_tombstone_is_absence_without_attachments() -> None:
    tombstone = _deleted_tombstone()

    _validate_deleted_wall475_tombstone(tombstone)
    assert _wall475_is_absent(tombstone) is True


@pytest.mark.parametrize(
    ("owner_id", "post_id"),
    [(-1, 475), (-68859909, 999)],
)
def test_deleted_tombstone_requires_exact_owner_and_post(owner_id: int, post_id: int) -> None:
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="tombstone identity"):
        _validate_deleted_wall475_tombstone(_deleted_tombstone(owner_id=owner_id, post_id=post_id))


def test_live_post_without_attachments_is_not_absence_and_still_blocks() -> None:
    post = _post()
    post.pop("attachments")

    assert _wall475_is_absent(post) is False
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="attachments are unavailable"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_accepts_additional_non_video_provider_attachment() -> None:
    post = _post()
    post["attachments"].append(
        {
            "type": "link",
            "link": {
                "url": "https://vk.ru/milovi_cake",
                "title": "provider projection",
            },
        }
    )

    _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_second_video_attachment() -> None:
    post = _post()
    post["attachments"].append(_video_attachment(video_id=456239999))

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="exactly one video attachment; observed 2"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_zero_video_attachments() -> None:
    post = _post()
    post["attachments"] = [{"type": "link", "link": {"url": "https://vk.ru/milovi_cake"}}]

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="exactly one video attachment; observed 0"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_malformed_non_video_attachment() -> None:
    post = _post()
    post["attachments"].append("not-an-object")

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="is not an object"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["id"] = 456239999
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="456239232"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_type_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["type"] = "video"
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="short_video"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_source_marker_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["description"] = "different source"
    with pytest.raises(MiloviIssue323AnomalyBlocked, match="source marker"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_projection_is_recorded_as_evidence_without_becoming_identity() -> None:
    state: dict[str, Any] = {}
    post = _post(text="provider-rendered text", post_source={"type": "api", "platform": "iphone"})
    post["attachments"].append({"type": "link", "link": {"url": "https://vk.ru/milovi_cake"}})

    _record_observed_projection(state, post)

    assert state["identity_contract"] == IDENTITY_CONTRACT
    assert state["observed_provider_text_nonempty"] is True
    assert state["observed_post_source_type"] == "api"
    assert state["observed_attachment_count"] == 2
    assert state["observed_video_attachment_count"] == 1
    assert state["observed_attachment_types"] == ["video", "link"]
    assert state["mutable_projection_fields"] == ["text", "post_source", "non_video_attachments"]
    assert len(state["observed_provider_text_sha256"]) == 64
    assert len(state["observed_post_source_sha256"]) == 64
    assert len(state["observed_attachments_sha256"]) == 64
    assert len(state["observed_raw_post_sha256"]) == 64


def test_read_observation_exposes_shape_without_copying_provider_text() -> None:
    state: dict[str, Any] = {}
    post = _post(text="do not copy this into diagnostics")
    post.pop("attachments")

    _record_read_observation(state, post, stage="initial")

    assert state["last_read_stage"] == "initial"
    assert state["last_read_is_none"] is False
    assert state["last_read_is_deleted"] is False
    assert state["last_read_has_attachments"] is False
    assert state["last_read_owner_id"] == -68859909
    assert state["last_read_post_id"] == 475
    assert "attachments" not in state["last_read_keys"]
    assert "do not copy" not in str(state)
    assert len(state["last_read_raw_post_sha256"]) == 64


class _ReadOnlyWriter:
    def __init__(self, post: dict[str, Any] | None) -> None:
        self.post = deepcopy(post)
        self.read_count = 0

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        self.read_count += 1
        return deepcopy(self.post)


def _cleanup_state(status: str = "uninitialized_no_delete_authority") -> dict[str, Any]:
    return {
        "schema_name": ANOMALY_STATE_SCHEMA,
        "schema_version": 1,
        "community_id": 68859909,
        "owner_id": -68859909,
        "anomaly_wall_remote_id": ANOMALY_WALL_REMOTE_ID,
        "anomaly_clip_remote_id": ANOMALY_CLIP_REMOTE_ID,
        "cleanup_475": {"status": status, "delete_authority": False},
    }


def _run_readonly_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    writer: _ReadOnlyWriter,
    *,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monkeypatch.setattr(reconcile, "_assert_native_clip", lambda *args, **kwargs: {})
    document = state or _cleanup_state()
    _cleanup_exact_wall475(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        finalizer=document,
        finalizer_path=tmp_path / "anomaly-state.json",
    )
    return document


def test_cleanup_reconciles_initial_exact_deleted_tombstone_without_delete_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    writer = _ReadOnlyWriter(_deleted_tombstone())

    state = _run_readonly_cleanup(monkeypatch, tmp_path, writer)

    assert state["cleanup_475"]["status"] == "verified_absent"
    assert state["cleanup_475"]["delete_authority"] is False
    assert state["cleanup_475"]["absence_evidence"] == "wall.getById:is_deleted_true"
    assert writer.read_count == 1


def test_cleanup_reconciles_exact_absence_without_delete_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    state = _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(None))

    assert state["cleanup_475"]["status"] == "verified_absent"
    assert state["cleanup_475"]["delete_authority"] is False
    assert state["cleanup_475"]["absence_evidence"] == "wall.getById:none"


def test_live_wall475_can_never_regrant_retired_cleanup_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    state = _cleanup_state()

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="permanently retired automatic cleanup authority"):
        _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(_post()), state=state)

    assert state["cleanup_475"]["status"] == "live_requires_manual_review"
    assert state["cleanup_475"]["delete_authority"] is False


def test_live_non_video_projection_is_evidence_but_still_grants_no_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    post = _post()
    post["attachments"].append({"type": "link", "link": {"url": "https://vk.ru/milovi_cake"}})
    state = _cleanup_state()

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="no wall.delete is authorized"):
        _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(post), state=state)

    assert state["cleanup_475"]["observed_attachment_count"] == 2
    assert state["cleanup_475"]["observed_video_attachment_count"] == 1
    assert state["cleanup_475"]["delete_authority"] is False


def test_prior_dispatch_live_wall_blocks_blind_retry_forever(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    state = _cleanup_state("delete_dispatch_started")
    state["cleanup_475"]["delete_dispatch_started"] = True

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="blind retry is forbidden"):
        _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(_post()), state=state)

    assert state["cleanup_475"]["status"] == "unknown_requires_reconciliation"
    assert state["cleanup_475"]["delete_authority"] is False


def test_prior_dispatch_exact_tombstone_reconciles_without_second_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    state = _cleanup_state("delete_dispatch_started")
    state["cleanup_475"]["delete_dispatch_started"] = True

    actual = _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(_deleted_tombstone()), state=state)

    assert actual["cleanup_475"]["status"] == "verified_absent"
    assert actual["cleanup_475"]["absence_evidence"] == "wall.getById:is_deleted_true-resume"
    assert actual["cleanup_475"]["delete_authority"] is False


def test_consumed_cleanup_authority_rejects_reappeared_live_post(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    state = _cleanup_state("verified_absent")

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="authority was already consumed"):
        _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(_post()), state=state)

    assert state["cleanup_475"]["delete_authority"] is False


def test_live_wall_without_attachments_blocks_before_any_state_transition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    post = _post()
    post.pop("attachments")
    state = _cleanup_state()

    with pytest.raises(MiloviIssue323AnomalyBlocked, match="attachments are unavailable"):
        _run_readonly_cleanup(monkeypatch, tmp_path, _ReadOnlyWriter(post), state=state)

    assert state["cleanup_475"]["status"] == "uninitialized_no_delete_authority"
