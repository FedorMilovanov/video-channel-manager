from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.platforms.youtube.comments import comment_text_sha256
from video_channel_manager.wave_engine.cli import _youtube_comment_plan
from video_channel_manager.wave_engine.engine import OperationRejectedError, UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import (
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
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
