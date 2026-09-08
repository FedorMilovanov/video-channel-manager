from __future__ import annotations

import copy
from pathlib import Path

import httpx
import pytest

from video_channel_manager.telegram_historical_media_release import (
    MEDIA_POLICY,
    build_media_document,
    load_media_release,
    verify_transport_media_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "content/telegram/lordchrist/historical-editorial/v1/production-release-spurgeon-v3-media-canary.json"


def _loaded():
    return load_media_release(RELEASE, ROOT)


def _remote_client(release: dict[str, object], *, mime: str = "image/jpeg") -> httpx.Client:
    by_url = {str(item["raw_url"]): item for item in release["media"]}  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        record = by_url[str(request.url)]
        body = (ROOT / str(record["path"])).read_bytes()
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": mime, "content-length": str(len(body))},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_spurgeon_v3_media_release_binds_exact_revision_target_and_two_git_media() -> None:
    release, queue, sources, profile_path, aux = _loaded()

    assert release["release_id"] == "lordchrist-history-spurgeon-down-grade-1887-v3-media-live-v1"
    assert release["canary_publication_id"] == "lordchrist-history-spurgeon-down-grade-1887-v3"
    assert release["publication_ids"] == ["lordchrist-history-spurgeon-down-grade-1887-v3"]
    assert release["media_policy"] == MEDIA_POLICY
    assert release["recurring_publication_ids"] == []
    assert release["recurring_scheduled_dates_moscow"] == []
    assert len(queue.posts) == 1
    assert queue.posts[0].publication_id == release["canary_publication_id"]
    assert len(sources) == 48
    assert profile_path.name == "lordchrist-rich.json"
    assert aux["revision_preflight"].status == "PASS"
    assert aux["revision_preflight"].editorial_media_count == 2

    hero, portrait = release["media"]
    assert hero["git_blob_sha"] == "32742cb1c1701ab861d1b4adff6349cabc78ddef"
    assert hero["byte_length"] == 131308
    assert hero["sha256"] == "sha256:9ccb4ff08042b3cf996164653c0b26759f870c853da12518b4f673b4daa9d2f1"
    assert portrait["git_blob_sha"] == "1769058538105671ec042ecc296fa6737565df10"
    assert portrait["byte_length"] == 89046
    assert portrait["sha256"] == "sha256:d257d13b6fa1ecf060b7540960d5e1c49c4a655c827f348f551b282778aff23f"


def test_spurgeon_v3_rich_document_has_two_provider_assigned_photos_in_reviewed_positions() -> None:
    release, queue, sources, profile_path, aux = _loaded()
    document, render = build_media_document(
        ROOT,
        release,
        queue,
        sources,
        profile_path,
        aux["target_binding_path"],
        release["canary_publication_id"],
    )

    assert document.publication_id == "lordchrist-history-spurgeon-down-grade-1887-v3"
    assert document.target.chat_id == -1001295216957
    assert document.target.bot_id == 8716602202
    assert document.expected_media_sha256 is not None
    assert len(document.provider_assigned_media_paths) == 2
    assert render.media_placeholders == ()
    assert render.provider_assigned_media == ("img-spurgeon-v3-hero", "img-spurgeon-v3-portrait")

    blocks = document.input_rich_message["blocks"]
    media_indexes = [index for index, block in enumerate(blocks) if block["type"] == "photo"]
    assert len(media_indexes) == 2
    assert blocks[media_indexes[0] - 1]["type"] == "paragraph"
    assert "Осенью 1887 года" in str(blocks[media_indexes[0] - 1])
    assert "Январь–апрель 1888-го" in str(blocks[media_indexes[1] - 3 : media_indexes[1]])


def test_transport_media_preflight_reproves_remote_mime_size_sha_and_exact_git_bytes() -> None:
    release, _queue, _sources, _profile, _aux = _loaded()
    with _remote_client(release) as client:
        proofs = verify_transport_media_bytes(ROOT, release, client=client)

    assert [proof["asset_id"] for proof in proofs] == ["img-spurgeon-v3-hero", "img-spurgeon-v3-portrait"]
    assert all(proof["provider_write_performed"] is False for proof in proofs)


def test_transport_media_preflight_fails_closed_on_wrong_remote_mime_before_provider_write() -> None:
    release, _queue, _sources, _profile, _aux = _loaded()
    with _remote_client(release, mime="text/plain") as client:
        with pytest.raises(ValueError, match="MIME differs"):
            verify_transport_media_bytes(ROOT, release, client=client)


def test_transport_media_preflight_fails_closed_on_bound_sha_drift_before_http() -> None:
    release, _queue, _sources, _profile, _aux = _loaded()
    drifted = copy.deepcopy(release)
    drifted["media"][0]["sha256"] = "sha256:" + "0" * 64
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="local byte identity differs"):
            verify_transport_media_bytes(ROOT, drifted, client=client)
    assert calls == 0


def test_media_release_rejects_wrong_target_or_revision_binding() -> None:
    release, _queue, _sources, _profile, _aux = _loaded()
    assert release["chat_id"] == -1001295216957
    assert release["revision"]["git_blob_sha"] == "579832fc57170d10e8356c8d0facc217ddf760bf"
