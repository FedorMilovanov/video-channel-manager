from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.platforms.youtube.comments import comment_text_sha256
from video_channel_manager.wave_engine.cli import _youtube_comment_plan
from video_channel_manager.wave_engine.engine import OperationRejectedError, UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import (
    EvidenceArtifact,
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
    WaveSourceEvidence,
)
from video_channel_manager.wave_engine.youtube_comment_provider import (
    LordGodYouTubeCommentAdapter,
    YOUTUBE_COMMENT_OPERATION_KIND,
    YOUTUBE_COMMENT_OWNER,
    YOUTUBE_COMMENT_POLICY_VERSION,
)

VIDEO_ID = "Bs9QO484MO4"
TITLE = "Панорама Библии - 3 | Алексей Коломийцев | Книга Исход"
SOURCE_URL = "https://www.slovo.org/resursy/propovedi/panorama-biblii-3-kniga-iskhod/"
TEXT = "*Пасха и искупление*\n\nВ Исх. 12 спасение по Божьей милости.\n\n" + SOURCE_URL


def _operation(
    *,
    payload_patch: dict[str, object] | None = None,
    kind: str = YOUTUBE_COMMENT_OPERATION_KIND,
    policy: str = YOUTUBE_COMMENT_POLICY_VERSION,
    mutation: MutationClass = MutationClass.AMBIGUOUS_MUTATION,
) -> WaveOperation:
    payload = {
        "video_id": VIDEO_ID,
        "channel_id": YOUTUBE_COMMENT_OWNER,
        "video_title": TITLE,
        "comment_text": TEXT,
        "comment_sha256": comment_text_sha256(TEXT),
        "source_url": SOURCE_URL,
        "review_status": "approved",
        "reviewed_at": "2026-11-23T18:00:00+03:00",
    }
    payload.update(payload_patch or {})
    return WaveOperation.build(
        sequence=0,
        project=ProjectBinding(
            project_key="lord-god-strength",
            community_id=60805374,
            owner_id=-60805374,
        ),
        source_snapshot_id="a" * 64,
        policy_version=policy,
        spec=WaveOperationSpec(
            order_key="0003-comment",
            operation_kind=kind,
            mutation_class=mutation,
            payload=payload,
        ),
    )


class FakeCommentWriter:
    def __init__(
        self,
        *,
        channel: str = YOUTUBE_COMMENT_OWNER,
        title: str = TITLE,
        status: str = "public",
        owned: list[object] | None = None,
    ) -> None:
        self.channel = channel
        self.auth_owner = YOUTUBE_COMMENT_OWNER
        self.title = title
        self.status = status
        self.owned = owned or []
        self.creates = 0
        self.reads = 0
        self.error: Exception | None = None

    def _request(self, method: str, resource: str, *, params: dict[str, str | int]) -> dict[str, object]:
        assert method == "GET" and resource == "channels" and params["mine"] == "true"
        return {"items": [{"id": self.auth_owner}]}

    def read_video_identity(self, video_id: str) -> SimpleNamespace:
        self.reads += 1
        return SimpleNamespace(video_id=video_id, channel_id=self.channel, title=self.title, privacy_status=self.status)

    def list_top_level_comments(self, video_id: str, *, strict_moderation: bool = False) -> list[object]:
        assert strict_moderation, "Guarded publisher must require complete moderation inventory"
        return list(self.owned)

    def create_top_level_comment(self, *, video_id: str, expected_channel_id: str, text: str) -> SimpleNamespace:
        self.creates += 1
        if self.error is not None:
            raise self.error
        result = SimpleNamespace(
            video_id=video_id,
            channel_id=expected_channel_id,
            author_channel_id=expected_channel_id,
            comment_id="Ugxyz123",
            text=text,
        )
        self.owned.append(result)
        return result


def _adapter(
    tmp_path: Path, writer: FakeCommentWriter | None = None
) -> tuple[LordGodYouTubeCommentAdapter, FakeCommentWriter]:
    fake = writer or FakeCommentWriter()
    return LordGodYouTubeCommentAdapter(writer=fake, data_dir=tmp_path), fake


def test_one_reviewed_exact_comment_posts_once_and_reconciles_read_only(tmp_path: Path) -> None:
    adapter, fake = _adapter(tmp_path)
    result = adapter.execute(_operation())
    assert result["comment_id"] == "Ugxyz123"
    assert result["publication_verified"] is True
    assert fake.creates == 1
    reconciliation = adapter.reconcile(_operation())
    assert reconciliation["reconciled_read_only"] is True
    assert fake.creates == 1


def test_second_mutation_does_not_replay_completed_comment(tmp_path: Path) -> None:
    adapter, fake = _adapter(tmp_path)
    adapter.execute(_operation())
    with pytest.raises(OperationRejectedError, match="Existing owner-authored"):
        adapter.execute(_operation())
    assert fake.creates == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"review_status": "REVIEW_ONLY"},
        {"channel_id": "wrong-owner"},
        {"source_url": "https://example.com/video"},
        {"comment_sha256": "sha256:deadbeef"},
        {"comment_text": "Text omits original source"},
        {"extra": "unexpected"},
    ],
)
def test_bad_review_is_rejected_before_write(tmp_path: Path, patch: dict[str, object]) -> None:
    adapter, fake = _adapter(tmp_path)
    with pytest.raises(OperationRejectedError):
        adapter.execute(_operation(payload_patch=patch))
    assert fake.creates == 0


@pytest.mark.parametrize(
    "fake",
    [
        FakeCommentWriter(channel="wrong-owner"),
        FakeCommentWriter(title="Wrong Title"),
        FakeCommentWriter(status="private"),
    ],
)
def test_live_identity_drift_blocks_write(tmp_path: Path, fake: FakeCommentWriter) -> None:
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(OperationRejectedError):
        adapter.execute(_operation())
    assert fake.creates == 0


def test_existing_different_comment_blocks_write(tmp_path: Path) -> None:
    fake = FakeCommentWriter(
        owned=[SimpleNamespace(author_channel_id=YOUTUBE_COMMENT_OWNER, comment_id="Ugold", text="old")]
    )
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(OperationRejectedError, match="Existing owner-authored"):
        adapter.execute(_operation())
    assert fake.creates == 0


def test_unclassified_dispatch_failure_is_unknown_not_retry_safe(tmp_path: Path) -> None:
    fake = FakeCommentWriter()
    fake.error = RuntimeError("POST returned empty after success")
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(UnknownProviderOutcomeError, match="never blind retry"):
        adapter.execute(_operation())
    assert fake.creates == 1


def test_read_only_reconciliation_rejects_absent_or_duplicate(tmp_path: Path) -> None:
    adapter, fake = _adapter(tmp_path)
    with pytest.raises(ValueError, match="conclusively reconcile"):
        adapter.reconcile(_operation())
    assert fake.creates == 0
    fake.owned.extend(
        [
            SimpleNamespace(author_channel_id=YOUTUBE_COMMENT_OWNER, comment_id="1", text=TEXT),
            SimpleNamespace(author_channel_id=YOUTUBE_COMMENT_OWNER, comment_id="2", text=TEXT),
        ]
    )
    with pytest.raises(ValueError, match="conclusively reconcile"):
        adapter.reconcile(_operation())
    assert fake.creates == 0


def test_wrong_policy_or_mutation_cannot_publish(tmp_path: Path) -> None:
    adapter, fake = _adapter(tmp_path)
    for op in [
        _operation(policy="wrong-policy"),
        _operation(kind="vk.wall.post"),
        _operation(mutation=MutationClass.SAFE_READ),
    ]:
        with pytest.raises(OperationRejectedError):
            adapter.execute(op)
    assert fake.creates == 0


def test_wrong_alias_or_missing_lock_directory_refuses(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="owner account alias"):
        LordGodYouTubeCommentAdapter(writer=FakeCommentWriter(), data_dir=tmp_path, account_alias="other")
    adapter = LordGodYouTubeCommentAdapter(writer=FakeCommentWriter(), data_dir=None)
    with pytest.raises(OperationRejectedError, match="durable"):
        adapter.execute(_operation())


def test_youtube_plan_requires_exactly_one_op() -> None:
    from video_channel_manager.wave_engine.models import WavePlan
    from video_channel_manager.wave_engine.models import WaveSourceEvidence, EvidenceArtifact

    source = WaveSourceEvidence.build(
        project=ProjectBinding(project_key="lord-god-strength", community_id=60805374, owner_id=-60805374),
        policy_version=YOUTUBE_COMMENT_POLICY_VERSION,
        artifacts=(EvidenceArtifact(path="content/test-source.json", sha256="a" * 64),),
    )
    plan = WavePlan.build(
        source=source,
        specs=(
            WaveOperationSpec(
                order_key="03",
                operation_kind=YOUTUBE_COMMENT_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=_operation().payload,
            ),
        ),
    )
    assert _youtube_comment_plan(plan)
    multi = WavePlan.build(
        source=source,
        specs=(
            WaveOperationSpec(
                order_key="03",
                operation_kind=YOUTUBE_COMMENT_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=_operation().payload,
            ),
            WaveOperationSpec(
                order_key="04",
                operation_kind=YOUTUBE_COMMENT_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=_operation().payload,
            ),
        ),
    )
    assert not _youtube_comment_plan(multi)


def test_wrong_oauth_channel_grant_blocks_write_and_reconciliation(tmp_path: Path) -> None:
    fake = FakeCommentWriter()
    fake.auth_owner = "another-youtube-owner"
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(OperationRejectedError, match="OAuth grant"):
        adapter.execute(_operation())
    with pytest.raises(OperationRejectedError, match="OAuth grant"):
        adapter.reconcile(_operation())
    assert fake.creates == 0


def test_strict_moderation_inventory_rejects_unreadable_held_comments() -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            assert method == "GET" and resource == "commentThreads"
            if params["moderationStatus"] == "published":
                return {"items": []}
            raise YouTubeCommentError("Owner cannot read held-for-review or likely-spam")

    stub = StubCommentsAPI()
    assert stub.list_top_level_comments(VIDEO_ID) == []
    with pytest.raises(YouTubeCommentError, match="Owner cannot read"):
        stub.list_top_level_comments(VIDEO_ID, strict_moderation=True)


def test_incomplete_comment_inventory_blocks_before_post(tmp_path: Path) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError

    class IncompleteWriter(FakeCommentWriter):
        def list_top_level_comments(self, video_id: str, *, strict_moderation: bool = False) -> list[object]:
            assert strict_moderation
            raise YouTubeCommentError("moderation inventory incomplete")

    fake = IncompleteWriter()
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(OperationRejectedError, match="inventory is incomplete"):
        adapter.execute(_operation())
    assert fake.creates == 0


def test_original_link_must_match_video_episode_number(tmp_path: Path) -> None:
    wrong = "https://www.slovo.org/resursy/propovedi/panorama-biblii-4-kniga-levit/"
    comment = TEXT.replace(SOURCE_URL, wrong)
    adapter, fake = _adapter(tmp_path)
    with pytest.raises(OperationRejectedError, match="episode number"):
        adapter.execute(
            _operation(
                payload_patch={
                    "source_url": wrong,
                    "comment_text": comment,
                    "comment_sha256": comment_text_sha256(comment),
                }
            )
        )
    assert fake.creates == 0


@pytest.mark.parametrize("payload", [{}, {"items": {}}, {"items": [None]}, {"items": [], "nextPageToken": 123}])
def test_strict_inventory_rejects_malformed_success_response(payload: dict[str, object]) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            return payload

    with pytest.raises(YouTubeCommentError, match="malformed moderation inventory|invalid moderation page token"):
        StubCommentsAPI().list_top_level_comments(VIDEO_ID, strict_moderation=True)


def test_strict_inventory_rejects_repeated_page_token() -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            self.calls = 0

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            self.calls += 1
            assert self.calls <= 2
            return {"items": [], "nextPageToken": "repeat"}

    with pytest.raises(YouTubeCommentError, match="repeated a moderation page token"):
        StubCommentsAPI().list_top_level_comments(VIDEO_ID, strict_moderation=True)


@pytest.mark.parametrize("video_id, author_id", [("wrong-video", YOUTUBE_COMMENT_OWNER), (VIDEO_ID, None)])
def test_strict_inventory_rejects_unverified_target_or_author(video_id: str, author_id: str | None) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            return {
                "items": [
                    {
                        "id": "thread-id",
                        "snippet": {
                            "videoId": video_id,
                            "channelId": YOUTUBE_COMMENT_OWNER,
                            "topLevelComment": {
                                "id": "comment-id",
                                "snippet": {"authorChannelId": {"value": author_id}, "textOriginal": TEXT},
                            },
                        },
                    }
                ]
            }

    with pytest.raises(YouTubeCommentError, match="unverified target or author"):
        StubCommentsAPI().list_top_level_comments(VIDEO_ID, strict_moderation=True)


@pytest.mark.parametrize("outcome", ["missing", "different_id", "different_text", "duplicate", "error"])
def test_post_receipt_alone_never_verifies_publication(tmp_path: Path, outcome: str) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError

    class ReceiptOnlyWriter(FakeCommentWriter):
        def list_top_level_comments(self, video_id: str, *, strict_moderation: bool = False) -> list[object]:
            assert strict_moderation
            if not self.creates:
                return []
            if outcome == "error":
                raise YouTubeCommentError("readback unavailable")
            if outcome == "missing":
                return []
            observed = SimpleNamespace(
                author_channel_id=YOUTUBE_COMMENT_OWNER,
                comment_id="other" if outcome == "different_id" else "Ugxyz123",
                text="different" if outcome == "different_text" else TEXT,
            )
            return [observed, observed] if outcome == "duplicate" else [observed]

    fake = ReceiptOnlyWriter()
    adapter, _ = _adapter(tmp_path, fake)
    with pytest.raises(UnknownProviderOutcomeError, match="independent readback uncertain"):
        adapter.execute(_operation())
    assert fake.creates == 1


def test_ambiguous_create_blocks_fresh_adapter_and_changed_operation(tmp_path: Path) -> None:
    first, first_writer = _adapter(tmp_path)
    first_writer.error = RuntimeError("provider may have accepted the comment")
    with pytest.raises(UnknownProviderOutcomeError):
        first.execute(_operation())
    assert first_writer.creates == 1

    # A different journal/plan may have a new operation ID and no visible comment yet.
    changed_text = TEXT + "\nДополнительная мысль."
    changed = _operation(
        payload_patch={"comment_text": changed_text, "comment_sha256": comment_text_sha256(changed_text)}
    )
    assert changed.operation_id != _operation().operation_id
    restarted, fresh_writer = _adapter(tmp_path)
    for operation in (_operation(), changed):
        with pytest.raises(OperationRejectedError, match="prior first-comment dispatch reservation"):
            restarted.execute(operation)
    assert fresh_writer.creates == 0


def test_verified_comment_cannot_be_recreated_after_disappearance(tmp_path: Path) -> None:
    first, writer = _adapter(tmp_path)
    first.execute(_operation())
    assert writer.creates == 1
    restarted, fresh_writer = _adapter(tmp_path)
    with pytest.raises(OperationRejectedError, match="prior first-comment dispatch reservation"):
        restarted.execute(_operation())
    assert fresh_writer.creates == 0


def test_reservation_storage_failure_blocks_before_dispatch(tmp_path: Path) -> None:
    directory = tmp_path / "youtube"
    directory.mkdir()
    (directory / "panorama-first-comment-reservations.sqlite3").write_bytes(b"not a SQLite database")
    adapter, writer = _adapter(tmp_path)
    with pytest.raises(OperationRejectedError, match="Cannot durably reserve"):
        adapter.execute(_operation())
    assert writer.creates == 0


def test_preflight_rejection_does_not_consume_first_comment_target(tmp_path: Path) -> None:
    rejected, writer = _adapter(tmp_path, FakeCommentWriter(title="wrong title"))
    with pytest.raises(OperationRejectedError, match="title drifted"):
        rejected.execute(_operation())
    assert writer.creates == 0
    accepted, fresh_writer = _adapter(tmp_path)
    assert accepted.execute(_operation())["publication_verified"] is True
    assert fresh_writer.creates == 1


def test_panorama_cli_rejects_ci_even_with_operator_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    from video_channel_manager.wave_engine import cli

    plan = SimpleNamespace(policy_version=YOUTUBE_COMMENT_POLICY_VERSION, operations=[_operation()])
    monkeypatch.setattr(cli, "_validated_apply_documents", lambda **kwargs: (None, plan, None))
    monkeypatch.setattr(cli, "_article_plan", lambda _: False)
    monkeypatch.setattr(cli, "_video_plan", lambda _: False)
    monkeypatch.setattr(cli, "_video_wall_plan", lambda _: False)
    monkeypatch.setattr(cli, "_lord_god_wall_plan", lambda _: False)
    monkeypatch.setattr(cli, "is_ci_environment", lambda: True)

    def unexpected_adapter(**kwargs: object) -> None:
        pytest.fail("CI must not construct a provider writer")

    monkeypatch.setattr(cli, "LordGodYouTubeCommentAdapter", unexpected_adapter)
    with pytest.raises(typer.Exit) as exc:
        cli.apply(
            source_path=tmp_path / "source.json",
            plan_path=tmp_path / "plan.json",
            intent_path=tmp_path / "intent.json",
            journal_directory=tmp_path / "journal",
            enable_provider_writes=True,
            ci_operator_confirmation="operator-supplied-token",
        )
    assert exc.value.exit_code == 3
    assert not (tmp_path / "journal").exists()


def test_strict_inventory_cannot_be_bounded() -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

    with pytest.raises(ValueError, match="Strict moderation inventory cannot be bounded"):
        StubCommentsAPI()._list_top_level_comments(VIDEO_ID, strict_moderation=True, max_pages_per_status=1)


@pytest.mark.parametrize("bounded", [False, True])
def test_quota_block_never_returns_partial_inventory(bounded: bool) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter
    from video_channel_manager.platforms.youtube.store import YouTubeQuotaBlocked

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            if params["moderationStatus"] == "published":
                return {"items": []}
            raise YouTubeCommentError("quota blocked") from YouTubeQuotaBlocked("terminal")

    with pytest.raises(YouTubeCommentError, match="quota blocked"):
        StubCommentsAPI()._list_top_level_comments(VIDEO_ID, max_pages_per_status=1 if bounded else None)


def test_strict_inventory_rejects_conflicting_duplicate_identity() -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentError, YouTubeCommentWriter

    class StubCommentsAPI(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, method: str, resource: str, *, params: dict[str, object]) -> dict[str, object]:
            author = "other-channel" if params["moderationStatus"] == "published" else YOUTUBE_COMMENT_OWNER
            return {
                "items": [
                    {
                        "id": "thread-id",
                        "snippet": {
                            "videoId": VIDEO_ID,
                            "channelId": YOUTUBE_COMMENT_OWNER,
                            "topLevelComment": {
                                "id": "comment-id",
                                "snippet": {"authorChannelId": {"value": author}, "textOriginal": TEXT},
                            },
                        },
                    }
                ]
            }

    with pytest.raises(YouTubeCommentError, match="conflicting duplicate comments"):
        StubCommentsAPI().list_top_level_comments(VIDEO_ID, strict_moderation=True)


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-11-23", "2026-11-23T18:00:00"])
def test_invalid_review_timestamp_blocks_before_provider(tmp_path: Path, timestamp: str) -> None:
    adapter, fake = _adapter(tmp_path)
    with pytest.raises(OperationRejectedError, match="review timestamp"):
        adapter.execute(_operation(payload_patch={"reviewed_at": timestamp}))
    assert fake.reads == fake.creates == 0


def test_source_url_must_be_an_exact_standalone_link(tmp_path: Path) -> None:
    adapter, fake = _adapter(tmp_path)
    text = TEXT + "not-the-reviewed-link"
    with pytest.raises(OperationRejectedError, match="exact primary sermon source"):
        adapter.execute(_operation(payload_patch={"comment_text": text, "comment_sha256": comment_text_sha256(text)}))
    assert fake.reads == fake.creates == 0


@pytest.mark.parametrize(
    "mine",
    [
        {},
        {"items": {"id": YOUTUBE_COMMENT_OWNER}},
        {"items": [None]},
        {"items": [{"id": YOUTUBE_COMMENT_OWNER}], "nextPageToken": "another-page"},
        {"items": [{"id": YOUTUBE_COMMENT_OWNER}, {"id": "another-channel"}]},
    ],
)
def test_owner_inventory_must_be_complete(tmp_path: Path, mine: dict[str, object]) -> None:
    class IncompleteOwnerWriter(FakeCommentWriter):
        def _request(self, method: str, resource: str, *, params: dict[str, str | int]) -> dict[str, object]:
            return mine

    adapter, fake = _adapter(tmp_path, IncompleteOwnerWriter())
    with pytest.raises(OperationRejectedError, match="OAuth grant"):
        adapter.execute(_operation())
    assert fake.reads == fake.creates == 0


def test_real_writer_cannot_dispatch_via_direct_ci_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter
    from video_channel_manager.wave_engine import youtube_comment_provider

    class OfflineRealWriter(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, *args: object, **kwargs: object) -> dict[str, object]:
            pytest.fail("Direct real-adapter CI must not access the provider")

    monkeypatch.setattr(youtube_comment_provider, "is_ci_environment", lambda: True)
    adapter = LordGodYouTubeCommentAdapter(writer=OfflineRealWriter(), data_dir=tmp_path)
    with pytest.raises(OperationRejectedError, match="persistent owner runtime, not CI"):
        adapter.execute(_operation())
    assert not (tmp_path / "youtube").exists()


def test_actual_owner_video_id_must_match_reviewed_target(tmp_path: Path) -> None:
    class WrongVideoWriter(FakeCommentWriter):
        def read_video_identity(self, video_id: str) -> SimpleNamespace:
            identity = super().read_video_identity(video_id)
            identity.video_id = "another-video"
            return identity

    adapter, fake = _adapter(tmp_path, WrongVideoWriter())
    with pytest.raises(OperationRejectedError, match="video identity or owner"):
        adapter.execute(_operation())
    with pytest.raises(ValueError, match="reconciliation video or channel mismatch"):
        adapter.reconcile(_operation())
    assert fake.creates == 0


def test_panorama_cli_reports_adapter_initialization_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    from video_channel_manager.wave_engine import cli

    plan = SimpleNamespace(policy_version=YOUTUBE_COMMENT_POLICY_VERSION, operations=[_operation()])
    monkeypatch.setattr(cli, "_validated_apply_documents", lambda **kwargs: (None, plan, None))
    monkeypatch.setattr(cli, "_article_plan", lambda _: False)
    monkeypatch.setattr(cli, "_video_plan", lambda _: False)
    monkeypatch.setattr(cli, "_video_wall_plan", lambda _: False)
    monkeypatch.setattr(cli, "_lord_god_wall_plan", lambda _: False)
    monkeypatch.setattr(cli, "is_ci_environment", lambda: False)

    def invalid_config(**kwargs: object) -> None:
        raise ValueError("YouTube comment wave requires the canonical absolute VCM_DATA_DIR")

    monkeypatch.setattr(cli, "LordGodYouTubeCommentAdapter", invalid_config)
    with pytest.raises(typer.Exit) as exc:
        cli.apply(
            source_path=tmp_path / "source.json",
            plan_path=tmp_path / "plan.json",
            intent_path=tmp_path / "intent.json",
            journal_directory=tmp_path / "journal",
            enable_provider_writes=True,
        )
    assert exc.value.exit_code == 3
    assert not (tmp_path / "journal").exists()

def _reviewed_artifact(
    tmp_path: Path, *, content: bytes | None = None, filename: str = "panorama-reviewed-comment.json"
) -> tuple[WaveSourceEvidence, WaveOperation, Path]:
    original = _operation()
    path = tmp_path / filename
    raw = content if content is not None else json.dumps(original.payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(raw)
    source = WaveSourceEvidence.build(
        project=original.project,
        policy_version=original.policy_version,
        artifacts=(EvidenceArtifact(path=filename, sha256=hashlib.sha256(raw).hexdigest()),),
    )
    operation = WaveOperation.build(
        sequence=0,
        project=source.project,
        source_snapshot_id=source.source_snapshot_id,
        policy_version=source.policy_version,
        spec=WaveOperationSpec(
            order_key="0003-comment",
            operation_kind=original.operation_kind,
            mutation_class=original.mutation_class,
            payload=original.payload,
        ),
    )
    return source, operation, path


def test_exact_reviewed_artifact_dispatch(tmp_path: Path) -> None:
    source, operation, _ = _reviewed_artifact(tmp_path)
    fake = FakeCommentWriter()
    adapter = LordGodYouTubeCommentAdapter(
        writer=fake, data_dir=tmp_path, review_source=source, repository_root=tmp_path
    )
    assert adapter.execute(operation)["publication_verified"] is True
    assert fake.creates == 1


@pytest.mark.parametrize("defect", ["different-copy", "duplicate-key", "wrong-filename", "changed-bytes", "wrong-snapshot"])
def test_source_binding_rejects_resealed_or_drifted_copy(tmp_path: Path, defect: str) -> None:
    original = _operation()
    kwargs: dict[str, object] = {}
    if defect == "different-copy":
        other = dict(original.payload)
        other["comment_text"] += "\nDifferent."
        other["comment_sha256"] = comment_text_sha256(other["comment_text"])
        kwargs["content"] = json.dumps(other, ensure_ascii=False).encode("utf-8")
    elif defect == "duplicate-key":
        raw = json.dumps(original.payload, ensure_ascii=False)
        kwargs["content"] = (raw[:-1] + ', "review_status": "approved"}').encode("utf-8")
    elif defect == "wrong-filename":
        kwargs["filename"] = "unrelated.json"
    source, operation, path = _reviewed_artifact(tmp_path, **kwargs)
    if defect == "changed-bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    elif defect == "wrong-snapshot":
        operation = original
    fake = FakeCommentWriter()
    adapter = LordGodYouTubeCommentAdapter(
        writer=fake, data_dir=tmp_path, review_source=source, repository_root=tmp_path
    )
    with pytest.raises(OperationRejectedError, match="[Rr]eviewed.comment"):
        adapter.execute(operation)
    assert fake.reads == fake.creates == 0
    assert not (tmp_path / "youtube").exists()


def test_direct_real_writer_requires_review_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter
    from video_channel_manager.wave_engine import youtube_comment_provider

    class OfflineRealWriter(YouTubeCommentWriter):
        def __init__(self) -> None:
            pass

        def _request(self, *args: object, **kwargs: object) -> dict[str, object]:
            pytest.fail("Unbound direct real-adapter call must not contact YouTube")

    monkeypatch.setattr(youtube_comment_provider, "is_ci_environment", lambda: False)
    adapter = LordGodYouTubeCommentAdapter(writer=OfflineRealWriter(), data_dir=tmp_path)
    with pytest.raises(OperationRejectedError, match="Exact reviewed comment source"):
        adapter.execute(_operation())
    assert not (tmp_path / "youtube").exists()
