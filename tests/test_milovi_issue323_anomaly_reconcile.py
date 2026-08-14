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
    _validate_wall475_identity,
)
from video_channel_manager.platforms.vk.milovi_issue323_finalize import MiloviFinalizerBlocked

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
    with pytest.raises(MiloviFinalizerBlocked):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_allows_missing_optional_created_by() -> None:
    post = _post()
    post.pop("created_by")
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

    with pytest.raises(MiloviFinalizerBlocked, match="exactly one video attachment; observed 2"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_zero_video_attachments() -> None:
    post = _post()
    post["attachments"] = [{"type": "link", "link": {"url": "https://vk.ru/milovi_cake"}}]

    with pytest.raises(MiloviFinalizerBlocked, match="exactly one video attachment; observed 0"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_malformed_non_video_attachment() -> None:
    post = _post()
    post["attachments"].append("not-an-object")

    with pytest.raises(MiloviFinalizerBlocked, match="is not an object"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["id"] = 456239999
    with pytest.raises(MiloviFinalizerBlocked, match="456239232"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_attachment_type_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["type"] = "video"
    with pytest.raises(MiloviFinalizerBlocked, match="short_video"):
        _validate_wall475_identity(post, "o1WXIMupuws")


def test_wall475_identity_rejects_source_marker_drift() -> None:
    post = _post()
    post["attachments"][0]["video"]["description"] = "different source"
    with pytest.raises(MiloviFinalizerBlocked, match="source marker"):
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


class _Writer:
    def __init__(
        self,
        first_post: dict[str, Any],
        *,
        dispatch_post: dict[str, Any] | None = None,
        delete_error: Exception | None = None,
        delete_takes_effect: bool = True,
    ) -> None:
        self._first_post = first_post
        self._dispatch_post = dispatch_post if dispatch_post is not None else deepcopy(first_post)
        self._delete_error = delete_error
        self._delete_takes_effect = delete_takes_effect
        self._deleted = False
        self.read_count = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        self.read_count += 1
        if self._deleted:
            return None
        if self.read_count == 1:
            return deepcopy(self._first_post)
        return deepcopy(self._dispatch_post)

    def _call(self, method: str, *, params: dict[str, Any]) -> None:
        self.calls.append((method, params))
        if self._delete_takes_effect:
            self._deleted = True
        if self._delete_error is not None:
            raise self._delete_error


def _run_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, writer: _Writer) -> dict[str, Any]:
    target_proofs: list[object] = []
    monkeypatch.setattr(reconcile, "_assert_native_clip", lambda *args, **kwargs: {})
    monkeypatch.setattr(reconcile, "_prove_target", lambda client: target_proofs.append(client))
    finalizer: dict[str, Any] = {"cleanup_475": {"status": "pending"}}
    _cleanup_exact_wall475(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        finalizer=finalizer,
        finalizer_path=tmp_path / "finalizer.json",
    )
    assert len(target_proofs) == 1
    return finalizer


def test_cleanup_reproves_wall475_immediately_before_single_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    writer = _Writer(_post())

    finalizer = _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.read_count >= 3
    assert writer.calls == [("wall.delete", {"owner_id": -68859909, "post_id": 475})]
    assert finalizer["cleanup_475"]["status"] == "verified_absent"
    assert finalizer["cleanup_475"]["identity_contract"] == IDENTITY_CONTRACT


def test_cleanup_accepts_non_video_projection_and_still_deletes_only_wall475(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    post = _post()
    post["attachments"].append({"type": "link", "link": {"url": "https://vk.ru/milovi_cake"}})
    writer = _Writer(post)

    finalizer = _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.calls == [("wall.delete", {"owner_id": -68859909, "post_id": 475})]
    assert finalizer["cleanup_475"]["observed_attachment_count"] == 2
    assert finalizer["cleanup_475"]["observed_video_attachment_count"] == 1


def test_cleanup_blocks_if_stable_identity_changes_between_intent_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    changed = _post()
    changed["attachments"][0]["video"]["id"] = 456239999
    writer = _Writer(_post(), dispatch_post=changed)

    with pytest.raises(MiloviFinalizerBlocked, match="456239232"):
        _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.calls == []


def test_cleanup_blocks_if_second_video_appears_between_intent_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    changed = _post()
    changed["attachments"].append(_video_attachment(video_id=456239999))
    writer = _Writer(_post(), dispatch_post=changed)

    with pytest.raises(MiloviFinalizerBlocked, match="exactly one video attachment; observed 2"):
        _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.calls == []


def test_cleanup_reconciles_response_loss_without_blind_delete_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    writer = _Writer(_post(), delete_error=TimeoutError("response lost"), delete_takes_effect=True)

    finalizer = _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.calls == [("wall.delete", {"owner_id": -68859909, "post_id": 475})]
    assert finalizer["cleanup_475"]["status"] == "verified_absent"


def test_cleanup_stops_after_ambiguous_failed_delete_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    writer = _Writer(_post(), delete_error=TimeoutError("response lost"), delete_takes_effect=False)

    with pytest.raises(TimeoutError, match="response lost"):
        _run_cleanup(monkeypatch, tmp_path, writer)

    assert writer.calls == [("wall.delete", {"owner_id": -68859909, "post_id": 475})]
