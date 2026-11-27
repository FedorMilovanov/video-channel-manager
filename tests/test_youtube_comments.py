from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.platforms.youtube.comments import (
    YouTubeCommentConflictError,
    YouTubeCommentError,
    YouTubeCommentWriter,
    YouTubeCommentsDisabledError,
    comments_equivalent,
    validate_comment_text,
)
from video_channel_manager.platforms.http import RetryPolicy
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore


def _token(*scopes: str) -> OAuthToken:
    return OAuthToken(
        access_token="access",
        refresh_token="refresh",
        scopes=list(scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _writer(
    tmp_path: Path,
    handler: httpx.MockTransport,
    *,
    verify_delays_seconds: tuple[float, ...] = (0.0,),
    retry_policy: RetryPolicy | None = None,
    sleep: Any = lambda _: None,
) -> YouTubeCommentWriter:
    store = TokenStore(tmp_path)
    store.save_token("account", _token(YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE))
    return YouTubeCommentWriter(
        client_config=InstalledClientConfig(client_id="client", client_secret="secret"),
        token_store=store,
        account_alias="account",
        http_client=httpx.Client(transport=handler),
        api_base_url="https://youtube.test",
        verify_delays_seconds=verify_delays_seconds,
        retry_policy=retry_policy,
        sleep=sleep,
    )


def _video() -> dict[str, Any]:
    return {
        "id": "video-1",
        "snippet": {"channelId": "channel-1", "title": "Title"},
        "status": {"privacyStatus": "public"},
    }


def _comment(
    comment_id: str,
    text: str,
    *,
    author_channel_id: str = "channel-1",
    include_target: bool = True,
    moderation_status: str = "published",
) -> dict[str, Any]:
    snippet: dict[str, Any] = {
        "textOriginal": text,
        "authorChannelId": {"value": author_channel_id},
        "authorDisplayName": "The Legendary Poet",
        "publishedAt": "2026-07-25T12:00:00Z",
        "updatedAt": "2026-07-25T12:00:00Z",
        "moderationStatus": moderation_status,
    }
    if include_target:
        snippet.update({"channelId": "channel-1", "videoId": "video-1"})
    return {"id": comment_id, "snippet": snippet}


def _thread(
    comment_id: str,
    text: str,
    *,
    author_channel_id: str = "channel-1",
    moderation_status: str = "published",
) -> dict[str, Any]:
    return {
        "id": f"thread-{comment_id}",
        "snippet": {
            "channelId": "channel-1",
            "videoId": "video-1",
            "topLevelComment": _comment(
                comment_id,
                text,
                author_channel_id=author_channel_id,
                moderation_status=moderation_status,
            ),
        },
    }


@pytest.mark.parametrize(
    "damaged",
    [
        "?????? ?????: https://www.youtube.com/watch?v=jys4x8T_sYg",
        "broken\ufffdtext",
    ],
)
def test_validate_comment_text_rejects_damaged_unicode(damaged: str) -> None:
    with pytest.raises(ValueError, match="Unicode encoding damage"):
        validate_comment_text(damaged)


def test_validate_comment_text_keeps_normal_question_marks_and_cyrillic() -> None:
    label = "".join(chr(c) for c in (0x41F, 0x43E, 0x43B, 0x43D, 0x43E, 0x435))
    assert validate_comment_text(label + "???") == label + "???"


@pytest.mark.parametrize(
    ("invalid", "valid"),
    [
        (
            "МакАртур: _греческий текст сохранился_, но перевод отличается.",
            "МакАртур: _греческий текст сохранился,_ но перевод отличается.",
        ),
        (
            "Он старается _не оправдывать себя_, однако защищает сотрудников.",
            "Он старается _не оправдывать себя,_ однако защищает сотрудников.",
        ),
        ("*Telegram*: https://t.me/lordchrist", "*Telegram:* https://t.me/lordchrist"),
        ("_Источник_: https://www.gty.org/sermons/70-26", "_Источник:_ https://www.gty.org/sermons/70-26"),
        ("*Фраза*.", "*Фраза.*"),
    ],
)
def test_validate_comment_text_rejects_punctuation_after_emphasis(invalid: str, valid: str) -> None:
    with pytest.raises(ValueError, match="native emphasis punctuation is invalid"):
        validate_comment_text(invalid)
    assert validate_comment_text(valid) == valid


def test_validate_comment_text_preserves_external_dash_and_urls() -> None:
    text = "📌 *Полная встреча:* https://www.youtube.com/watch?v=a_123\n_Суть фразы,_ а не абзаца.\n*Поэт* — название."
    assert validate_comment_text(text) == text


def test_comment_create_and_update_fail_before_http_on_encoding_damage(tmp_path: Path) -> None:
    def no_http(request: httpx.Request) -> httpx.Response:
        pytest.fail("Damaged Unicode must not reach the YouTube HTTP client.")

    writer = _writer(tmp_path, httpx.MockTransport(no_http))
    damaged = "?????? ?????: https://www.youtube.com/watch?v=jys4x8T_sYg"
    with pytest.raises(ValueError, match="Unicode encoding damage"):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text=damaged,
        )
    with pytest.raises(ValueError, match="Unicode encoding damage"):
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text="previous text",
            new_text=damaged,
        )


def test_comment_create_rejects_punctuation_scope_before_http(tmp_path: Path) -> None:
    def no_http(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid comment formatting must be rejected before the HTTP call.")

    writer = _writer(tmp_path, httpx.MockTransport(no_http))
    broken = "МакАртур различил: _греческий текст сохранился_, но перевод может отличаться."
    with pytest.raises(ValueError, match="native emphasis punctuation"):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text=broken,
        )
    with pytest.raises(ValueError, match="native emphasis punctuation"):
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text="previous text",
            new_text=broken,
        )


def test_list_comments_paginates_reads_moderation_views_and_deduplicates(tmp_path: Path) -> None:
    calls: list[tuple[str, str | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/commentThreads"
        status = request.url.params["moderationStatus"]
        page = request.url.params.get("pageToken")
        calls.append((status, page))
        if status == "published" and page is None:
            return httpx.Response(200, json={"items": [_thread("comment-1", "One")], "nextPageToken": "next"})
        if status == "published" and page == "next":
            return httpx.Response(
                200,
                json={"items": [_thread("comment-2", "Two", author_channel_id="viewer-2")]},
            )
        if status == "heldForReview":
            return httpx.Response(
                200,
                json={
                    "items": [
                        _thread("comment-1", "One"),
                        _thread("comment-3", "Held", moderation_status="heldForReview"),
                    ]
                },
            )
        assert status == "likelySpam"
        return httpx.Response(200, json={"items": []})

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    comments = writer.list_top_level_comments("video-1")
    assert [item.comment_id for item in comments] == ["comment-1", "comment-2", "comment-3"]
    assert comments[0].author_channel_id == "channel-1"
    assert comments[1].author_channel_id == "viewer-2"
    assert comments[2].moderation_status == "heldForReview"
    assert calls == [
        ("published", None),
        ("published", "next"),
        ("heldForReview", None),
        ("likelySpam", None),
    ]


def test_unsupported_non_published_moderation_views_are_tolerated(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        status = request.url.params["moderationStatus"]
        if status == "published":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(400, json={"error": {"message": "unsupported moderation view"}})

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    assert writer.list_top_level_comments("video-1") == []


def test_comments_disabled_is_classified_separately(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "The video has disabled comments.",
                    "errors": [{"reason": "commentsDisabled"}],
                }
            },
        )

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentsDisabledError):
        writer.list_top_level_comments("video-1")


def test_create_comment_is_verified_and_idempotent_with_contextual_direct_read(tmp_path: Path) -> None:
    created: dict[str, Any] | None = None
    posted_bodies: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal created
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads" and request.method == "GET":
            status = request.url.params["moderationStatus"]
            return httpx.Response(200, json={"items": [created] if created and status == "published" else []})
        if request.url.path == "/commentThreads" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            posted_bodies.append(body)
            text = body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            created = _thread("comment-1", text)
            return httpx.Response(200, json=created)
        if request.url.path == "/comments":
            assert created is not None
            direct = _comment(
                "comment-1", created["snippet"]["topLevelComment"]["snippet"]["textOriginal"], include_target=False
            )
            return httpx.Response(200, json={"items": [direct]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    first = writer.create_top_level_comment(
        video_id="video-1",
        expected_channel_id="channel-1",
        text="Первая строка.  \n\nВторая строка.",
    )
    second = writer.create_top_level_comment(
        video_id="video-1",
        expected_channel_id="channel-1",
        text="Первая строка.\n\nВторая строка.",
    )
    assert first.comment_id == second.comment_id == "comment-1"
    assert len(posted_bodies) == 1
    assert posted_bodies[0]["snippet"]["videoId"] == "video-1"
    assert comments_equivalent(first.text, "Первая строка.\n\nВторая строка.")


def test_successful_create_response_is_safe_fallback_during_indexing_delay(tmp_path: Path) -> None:
    created: dict[str, Any] | None = None

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal created
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads" and request.method == "GET":
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/commentThreads" and request.method == "POST":
            created = _thread("comment-1", "Approved")
            return httpx.Response(200, json=created)
        if request.url.path == "/comments":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle), verify_delays_seconds=(0.0, 0.0))
    result = writer.create_top_level_comment(
        video_id="video-1",
        expected_channel_id="channel-1",
        text="Approved",
    )
    assert result.comment_id == "comment-1"
    assert result.author_channel_id == "channel-1"


def test_create_refuses_a_different_existing_channel_comment(tmp_path: Path) -> None:
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads":
            status = request.url.params["moderationStatus"]
            return httpx.Response(
                200,
                json={"items": [_thread("comment-1", "Older channel comment")] if status == "published" else []},
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="New approved comment",
        )
    assert methods == ["GET", "GET", "GET", "GET"]


def test_add_independent_comment_preserves_prior_comments_and_is_idempotent(tmp_path: Path) -> None:
    existing = [_thread("comment-1", "First historical subject")]
    posts = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads" and request.method == "GET":
            return httpx.Response(
                200, json={"items": existing if request.url.params["moderationStatus"] == "published" else []}
            )
        if request.url.path == "/commentThreads" and request.method == "POST":
            posts.append(request)
            text = json.loads(request.content)["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            created = _thread("comment-2", text)
            existing.append(created)
            return httpx.Response(200, json=created)
        if request.url.path == "/comments":
            return httpx.Response(200, json={"items": [_comment("comment-2", "Second historical subject")]})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    reviewed = {item.comment_id: item.text_sha256 for item in writer.list_top_level_comments("video-1")}
    for _ in range(2):
        result = writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="Second historical subject",
            expected_owned_comments=reviewed,
        )
        assert result.comment_id == "comment-2"
    assert len(posts) == 1
    assert len(existing) == 2


@pytest.mark.parametrize("reviewed", [{}, {"comment-1": "sha256:" + "0" * 64}, {"other-id": "sha256:" + "1" * 64}])
def test_add_rejects_stale_reviewed_owner_state_before_post(tmp_path: Path, reviewed: dict[str, str]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads":
            return httpx.Response(
                200,
                json={
                    "items": [_thread("comment-1", "Older channel comment")]
                    if request.url.params["moderationStatus"] == "published"
                    else []
                },
            )
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError, match="Reviewed owner comment state changed"):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="New approved comment",
            expected_owned_comments=reviewed,
        )


def test_update_requires_exact_reviewed_before_text(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/comments":
            return httpx.Response(200, json={"items": [_comment("comment-1", "Manually changed")]})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError):
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text="Reviewed before",
            new_text="Approved after",
        )


def test_update_accepts_write_response_without_target_fields_and_verifies(tmp_path: Path) -> None:
    current_text = "Reviewed before"

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal current_text
        if request.url.path == "/comments" and request.method == "GET":
            return httpx.Response(200, json={"items": [_comment("comment-1", current_text, include_target=False)]})
        if request.url.path == "/comments" and request.method == "PUT":
            body = json.loads(request.content.decode("utf-8"))
            current_text = body["snippet"]["textOriginal"]
            return httpx.Response(200, json=_comment("comment-1", current_text, include_target=False))
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    result = writer.update_top_level_comment(
        comment_id="comment-1",
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_text="Reviewed before",
        new_text="Approved after",
    )
    assert result.comment_id == "comment-1"
    assert result.video_id == "video-1"
    assert result.channel_id == "channel-1"
    assert result.text == "Approved after"


def test_comment_safe_read_retries_transient_http(tmp_path: Path) -> None:
    calls = 0
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, json={"items": []})

    writer = _writer(
        tmp_path,
        httpx.MockTransport(handle),
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.2, jitter_seconds=0.0),
        sleep=sleeps.append,
    )

    assert writer.list_top_level_comments("video-1") == []
    assert calls == 4
    assert sleeps == [0.2]


def test_comment_mutation_timeout_is_attempted_once(tmp_path: Path) -> None:
    post_calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal post_calls
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.method == "GET" and request.url.path == "/commentThreads":
            return httpx.Response(200, json={"items": []})
        assert request.method == "POST"
        assert request.url.path == "/commentThreads"
        post_calls += 1
        raise httpx.ReadTimeout("response lost for https://upload.example/private", request=request)

    writer = _writer(
        tmp_path,
        httpx.MockTransport(handle),
        retry_policy=RetryPolicy(max_attempts=7),
    )

    with pytest.raises(YouTubeCommentError, match="ambiguous_mutation") as captured:
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="Pinned comment",
        )

    assert "upload.example" not in str(captured.value)
    assert post_calls == 1


def test_terminal_quota_after_accepted_comment_does_not_fallback_or_replay(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads" and request.method == "GET":
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/commentThreads" and request.method == "POST":
            return httpx.Response(200, json=_thread("comment-1", "Approved"))
        if request.url.path == "/comments":
            return httpx.Response(403, json={"error": {"message": "Rejected", "errors": [{"reason": "quotaExceeded"}]}})
        raise AssertionError(request.url)

    writer = _writer(tmp_path, httpx.MockTransport(handle), verify_delays_seconds=(0.0, 0.0))
    with pytest.raises(YouTubeCommentError, match="Comment comment-1 write response accepted"):
        writer.create_top_level_comment(video_id="video-1", expected_channel_id="channel-1", text="Approved")
    assert calls.count(("POST", "/commentThreads")) == 1
    assert calls[-2:] == [("POST", "/commentThreads"), ("GET", "/comments")]


def test_quota_in_moderation_preflight_is_not_treated_as_empty_inventory(tmp_path: Path) -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        assert request.method == "GET"
        if request.url.params["moderationStatus"] == "published":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            403, json={"error": {"message": "Rejected", "errors": [{"reason": "dailyLimitExceeded"}]}}
        )

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentError, match="dailyLimitExceeded"):
        writer.create_top_level_comment(video_id="video-1", expected_channel_id="channel-1", text="Approved")
    assert calls == ["GET", "GET", "GET"]


@pytest.mark.parametrize("late_text", ["Reviewed first comment", "Unreviewed owner comment"])
def test_strict_first_create_refuses_owner_comment_in_held_inventory(tmp_path: Path, late_text: str) -> None:
    statuses: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads":
            status = request.url.params["moderationStatus"]
            statuses.append(status)
            items = [_thread("late-comment", late_text)] if status == "heldForReview" else []
            return httpx.Response(200, json={"items": items})
        raise AssertionError(request.url)

    def unexpected_dispatch() -> None:
        pytest.fail("A new owner comment must block dispatch before intent.")

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentConflictError, match="Owner comment appeared"):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="Reviewed first comment",
            strict_inventory_max_pages=10,
            before_dispatch=unexpected_dispatch,
            expected_video_title="Title",
            expected_privacy_status="public",
        )
    assert statuses == ["published", "heldForReview", "likelySpam"]


def test_strict_first_create_refuses_incomplete_inventory(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if request.url.path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if request.url.path == "/commentThreads":
            return httpx.Response(200, json={"items": [], "nextPageToken": "more"})
        raise AssertionError(request.url)

    def unexpected_dispatch() -> None:
        pytest.fail("An incomplete inventory must block dispatch before intent.")

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    with pytest.raises(YouTubeCommentError, match="exceeds its reserved page limit"):
        writer.create_top_level_comment(
            video_id="video-1",
            expected_channel_id="channel-1",
            text="Reviewed first comment",
            strict_inventory_max_pages=1,
            before_dispatch=unexpected_dispatch,
            expected_video_title="Title",
            expected_privacy_status="public",
        )


@pytest.mark.parametrize("drift", ["none", "text", "extra", "title", "privacy"])
def test_guarded_update_rechecks_full_state_before_intent_and_put(tmp_path: Path, drift: str) -> None:
    from video_channel_manager.platforms.youtube.comments import comment_text_sha256

    before_text = "Reviewed before"
    current_text = "Changed" if drift == "text" else before_text
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal current_text
        if request.url.path == "/videos":
            video = _video()
            if drift == "title":
                video["snippet"]["title"] = "Changed"
            if drift == "privacy":
                video["status"]["privacyStatus"] = "private"
            return httpx.Response(200, json={"items": [video]})
        if request.url.path == "/commentThreads":
            rows = [_thread("comment-1", current_text)]
            if drift == "extra":
                rows.append(_thread("comment-2", "Unexpected comment"))
            return httpx.Response(
                200, json={"items": rows if request.url.params["moderationStatus"] == "published" else []}
            )
        if request.url.path == "/comments" and request.method == "GET":
            return httpx.Response(200, json={"items": [_comment("comment-1", current_text)]})
        assert request.url.path == "/comments" and request.method == "PUT"
        assert calls == ["intent"]
        calls.append("PUT")
        body = json.loads(request.content)
        assert body["id"] == "comment-1"
        current_text = body["snippet"]["textOriginal"]
        return httpx.Response(200, json=_comment("comment-1", current_text))

    writer = _writer(tmp_path, httpx.MockTransport(handle))

    def apply() -> None:
        writer.update_top_level_comment(
            comment_id="comment-1",
            video_id="video-1",
            expected_channel_id="channel-1",
            expected_text=before_text,
            new_text="Reviewed correction",
            expected_owned_comments={"comment-1": comment_text_sha256(before_text)},
            expected_video_title="Title",
            expected_privacy_status="public",
            strict_inventory_max_pages=10,
            before_dispatch=lambda: calls.append("intent"),
        )

    if drift == "none":
        apply()
        assert calls == ["intent", "PUT"]
    else:
        with pytest.raises(YouTubeCommentConflictError):
            apply()
        assert not calls


# Replies use the same canonical HTTP transport, but a different provider
# resource. Every successful write is checked against the exact parent.
def _reply_record(cid: str = "reply-1", text: str = "Спасибо! ❤️", parent: str = "parent-1") -> dict[str, Any]:
    item = _comment(cid, text)
    item["snippet"]["parentId"] = parent
    return item


@pytest.mark.parametrize(
    "case", ["ok", "delay", "wrong-parent", "changed-parent", "cannot-reply", "stale-map", "count", "unknown"]
)
def test_guarded_reply_writes_exact_parent_and_verifies_complete_inventory(tmp_path: Path, case: str) -> None:
    from video_channel_manager.platforms.youtube.comments import comment_text_sha256

    replies: list[dict[str, Any]] = (
        [_reply_record("earlier", "Old reply")] if case in {"ok", "delay", "stale-map"} else []
    )
    posts = []
    intents = []
    listing_calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal listing_calls
        params = request.url.params
        path = request.url.path
        if request.method == "POST":
            assert path == "/comments"
            assert intents == ["intent"]
            body = json.loads(request.content)
            assert body == {"snippet": {"parentId": "parent-1", "textOriginal": "Спасибо! ❤️"}}
            posts.append(body)
            if case == "unknown":
                raise httpx.ReadTimeout("unknown", request=request)
            item = _reply_record()
            replies.append(item)
            return httpx.Response(200, json=item)
        if path == "/videos":
            return httpx.Response(200, json={"items": [_video()]})
        if path == "/commentThreads":
            if params["moderationStatus"] != "published":
                return httpx.Response(200, json={"items": []})
            parent = _thread(
                "parent-1", "Changed" if case == "changed-parent" else "Viewer text", author_channel_id="viewer"
            )
            parent["snippet"].update(
                {
                    "canReply": case != "cannot-reply",
                    "totalReplyCount": len(replies) + (1 if case == "count" else 0),
                }
            )
            return httpx.Response(200, json={"items": [parent]})
        assert path == "/comments"
        if params.get("id") == "parent-1":
            parent = _comment("parent-1", "Viewer text", author_channel_id="viewer")
            if case == "wrong-parent":
                parent["snippet"]["parentId"] = "other"
            return httpx.Response(200, json={"items": [parent]})
        if params.get("id") == "reply-1":
            return httpx.Response(200, json={"items": [_reply_record()]})
        assert params["parentId"] == "parent-1"
        listing_calls += 1
        if case == "delay" and len(posts) == 1 and listing_calls == 2:
            return httpx.Response(200, json={"items": replies[:-1]})
        return httpx.Response(200, json={"items": replies})

    writer = _writer(tmp_path, httpx.MockTransport(handle), verify_delays_seconds=(0.0, 0.0))
    expected = {"earlier": comment_text_sha256("Old reply")} if case in {"ok", "delay"} else {}
    args = dict(
        parent_id="parent-1",
        video_id="video-1",
        expected_channel_id="channel-1",
        expected_video_title="Title",
        expected_parent_author="viewer",
        expected_parent_text="Viewer text",
        expected_owned_replies=expected,
        text="Спасибо! ❤️",
        max_pages=2,
        before_dispatch=lambda: intents.append("intent"),
    )
    if case in {"ok", "delay"}:
        result = writer.create_reply(**args)
        assert result.comment_id == "reply-1"
        assert result.thread_id == "parent-1"
        assert result.text == "Спасибо! ❤️"
        assert len(posts) == len(intents) == 1
        assert replies[0]["id"] == "earlier"
        if case == "delay":
            assert listing_calls == 3
    else:
        with pytest.raises(YouTubeCommentError):
            writer.create_reply(**args)
        assert len(posts) == len(intents) == (1 if case == "unknown" else 0)


@pytest.mark.parametrize("case", ["complete", "cap", "repeated-token", "wrong-parent", "duplicate-id", "malformed"])
def test_reply_inventory_requires_all_pages_and_exact_parent(tmp_path: Path, case: str) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["parentId"] == "parent-1"
        page = request.url.params.get("pageToken")
        if page is None:
            return httpx.Response(200, json={"items": [_reply_record("first")], "nextPageToken": "next"})
        payload = {"items": [_reply_record("second")]}
        if case == "repeated-token":
            payload["nextPageToken"] = "next"
        elif case == "wrong-parent":
            payload["items"] = [_reply_record("second", parent="other")]
        elif case == "duplicate-id":
            payload["items"] = [_reply_record("first")]
        elif case == "malformed":
            payload["items"] = [None]
        return httpx.Response(200, json=payload)

    writer = _writer(tmp_path, httpx.MockTransport(handle))
    kwargs = dict(parent_id="parent-1", video_id="video-1", channel_id="channel-1", max_pages=1 if case == "cap" else 2)
    if case == "complete":
        assert [x.comment_id for x in writer.list_replies(**kwargs)] == ["first", "second"]
    else:
        with pytest.raises(YouTubeCommentError):
            writer.list_replies(**kwargs)


def test_reply_inventory_accepts_viewer_display_but_requires_owner_original(tmp_path: Path) -> None:
    from video_channel_manager.platforms.youtube.store import quota_cost

    assert quota_cost("POST", "comments") == ("shared", 50)
    viewer = _reply_record("viewer-reply")
    viewer["snippet"]["authorChannelId"]["value"] = "viewer"
    viewer["snippet"]["textDisplay"] = viewer["snippet"].pop("textOriginal")
    owner = _reply_record("owner-reply")
    owner["snippet"]["textDisplay"] = owner["snippet"].pop("textOriginal")
    items = [viewer]
    writer = _writer(tmp_path, httpx.MockTransport(lambda _: httpx.Response(200, json={"items": items})))
    args = dict(parent_id="parent-1", video_id="video-1", channel_id="channel-1", max_pages=1)
    assert writer.list_replies(**args)[0].author_channel_id == "viewer"
    items.append(owner)
    with pytest.raises(YouTubeCommentError):
        writer.list_replies(**args)
