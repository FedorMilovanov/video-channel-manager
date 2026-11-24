"""One-comment-per-video guarded YouTube adapter for the versioned Wave engine.

No provider write is possible without an exact reviewed source/plan/apply
intent, the wave journal, a matching owner, and two operator write gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from video_channel_manager.platforms.youtube.comments import (
    YouTubeCommentError,
    YouTubeCommentWriter,
    comment_text_sha256,
    comments_equivalent,
    validate_comment_text,
)
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock
from video_channel_manager.wave_engine.canonical import is_ci_environment, resolve_repository_relative_path
from video_channel_manager.wave_engine.engine import OperationRejectedError, UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import MutationClass, WaveOperation, WaveSourceEvidence

YOUTUBE_COMMENT_OPERATION_KIND = "youtube.comment.create"
YOUTUBE_COMMENT_POLICY_VERSION = "lord-god-panorama-comment-wave-v1"
YOUTUBE_COMMENT_OWNER = "UCeSJsC6go2c9pdJCuUI1BYA"
YOUTUBE_COMMENT_ACCOUNT = "fedor-milovanov"
REVIEWED_COMMENT_ARTIFACT = "panorama-reviewed-comment.json"
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_APPROVED_FIELDS = frozenset(
    {
        "video_id",
        "channel_id",
        "video_title",
        "comment_text",
        "comment_sha256",
        "source_url",
        "review_status",
        "reviewed_at",
    }
)


class LordGodYouTubeCommentAdapter:
    """Fail-closed Wave adapter; never retries a potentially dispatched POST."""

    reconciliation_replay_safe = True

    def __init__(
        self,
        *,
        account_alias: str = YOUTUBE_COMMENT_ACCOUNT,
        writer: YouTubeCommentWriter | None = None,
        data_dir: Path | None = None,
        review_source: WaveSourceEvidence | None = None,
        repository_root: Path | None = None,
    ) -> None:
        if account_alias != YOUTUBE_COMMENT_ACCOUNT:
            raise ValueError("YouTube comment wave requires exact approved owner account alias")
        self.account_alias = account_alias
        self._owns_writer = writer is None
        self.review_source = review_source
        self.repository_root = repository_root
        if writer is None:
            from video_channel_manager.config import get_settings
            from video_channel_manager.platforms.youtube.models import InstalledClientConfig
            from video_channel_manager.platforms.youtube.store import ProjectQuotaGuard, TokenStore

            settings = get_settings()
            if not settings.data_dir.is_absolute():
                raise ValueError("YouTube comment wave requires the canonical absolute VCM_DATA_DIR")
            config = InstalledClientConfig.from_file(settings.youtube_client_secret_file)
            if ProjectQuotaGuard.for_client(settings.data_dir, config.client_id, account_alias) is None:
                raise ValueError("YouTube comment wave requires an identifiable Google Cloud quota project")
            writer = YouTubeCommentWriter(
                client_config=config,
                token_store=TokenStore(settings.data_dir),
                account_alias=account_alias,
            )
            data_dir = settings.data_dir
        self.writer = writer
        self.data_dir = data_dir.resolve() if data_dir is not None else None

    @staticmethod
    def _validated_payload(operation: WaveOperation) -> dict[str, str]:
        if operation.operation_kind != YOUTUBE_COMMENT_OPERATION_KIND:
            raise OperationRejectedError("YouTube comment operation kind differs from reviewed adapter")
        if operation.policy_version != YOUTUBE_COMMENT_POLICY_VERSION:
            raise OperationRejectedError("YouTube comment policy_version differs from current contract")
        if operation.mutation_class is not MutationClass.AMBIGUOUS_MUTATION:
            raise OperationRejectedError("YouTube comment publication must be an ambiguous mutation")
        if operation.project.project_key != "lord-god-strength":
            raise OperationRejectedError("YouTube comment project differs from Lord God")
        if (operation.project.community_id, operation.project.owner_id) != (60805374, -60805374):
            raise OperationRejectedError("YouTube comment project owner binding mismatch")
        p = operation.payload
        if set(p) != _APPROVED_FIELDS or not all(isinstance(v, str) for v in p.values()):
            raise OperationRejectedError("YouTube comment payload fields are not exactly reviewed")
        if p["channel_id"] != YOUTUBE_COMMENT_OWNER:
            raise OperationRejectedError("YouTube comment destination owner does not match approved account")
        if not _VIDEO_ID_RE.fullmatch(p["video_id"]):
            raise OperationRejectedError("YouTube video ID must be an exact 11-character ID")
        if not p["video_title"].strip() or p["video_title"] != p["video_title"].strip():
            raise OperationRejectedError("YouTube comment title is not an exact normalized title")
        if p["review_status"] != "approved" or not p["reviewed_at"].strip():
            raise OperationRejectedError("YouTube comment must have a record-specific editorial approval")
        try:
            reviewed_at = datetime.fromisoformat(p["reviewed_at"])
        except ValueError as exc:
            raise OperationRejectedError("YouTube comment review timestamp must be timezone-aware ISO 8601") from exc
        if reviewed_at.utcoffset() is None:
            raise OperationRejectedError("YouTube comment review timestamp must include a timezone")
        episode_title = re.search(r"Панорама Библии\s*-\s*(\d+)\s*\|", p["video_title"])
        episode_source = re.fullmatch(
            r"https://www\.slovo\.org/resursy/propovedi/panorama-biblii-(\d+)-[a-z0-9-]+/?", p["source_url"]
        )
        if not episode_title or not episode_source or episode_title.group(1) != episode_source.group(1):
            raise OperationRejectedError("YouTube comment source page does not match the exact episode number")
        try:
            normalized = validate_comment_text(p["comment_text"])
        except ValueError as exc:
            raise OperationRejectedError(f"Invalid YouTube comment formatting: {exc}") from exc
        if normalized != p["comment_text"]:
            raise OperationRejectedError("YouTube comment has unexpected whitespace normalization")
        if p["source_url"] not in normalized.split():
            raise OperationRejectedError("YouTube comment must link the exact primary sermon source")
        if comment_text_sha256(normalized) != p["comment_sha256"]:
            raise OperationRejectedError("YouTube comment SHA256 differs from reviewed copy")
        return p

    def _assert_reviewed_source(self, operation: WaveOperation, payload: dict[str, str]) -> None:
        source = self.review_source
        if source is None or self.repository_root is None:
            raise OperationRejectedError("Exact reviewed comment source and repository root are required")
        if (
            source.project != operation.project
            or source.policy_version != operation.policy_version
            or source.source_snapshot_id != operation.source_snapshot_id
        ):
            raise OperationRejectedError("Reviewed comment source identity differs from the operation")
        matches = [
            artifact for artifact in source.artifacts if PurePosixPath(artifact.path).name == REVIEWED_COMMENT_ARTIFACT
        ]
        if len(matches) != 1:
            raise OperationRejectedError("Source must bind exactly one panorama-reviewed-comment.json artifact")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate reviewed comment JSON key")
                result[key] = value
            return result

        try:
            artifact = matches[0]
            path = resolve_repository_relative_path(self.repository_root, artifact.path, require_file=True)
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact.sha256:
                raise ValueError("Reviewed artifact SHA-256 drift")
            reviewed = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        except (OSError, ValueError) as exc:
            raise OperationRejectedError("Cannot verify exact reviewed comment source artifact") from exc
        if not isinstance(reviewed, dict) or reviewed != payload:
            raise OperationRejectedError("Operation payload differs from exact reviewed comment artifact")

    def _owned(self, *, video_id: str) -> list[Any]:
        try:
            all_comments = self.writer.list_top_level_comments(video_id, strict_moderation=True)
        except YouTubeCommentError as exc:
            raise OperationRejectedError(
                "YouTube moderation inventory is incomplete; comment publication prohibited"
            ) from exc
        return [c for c in all_comments if c.author_channel_id == YOUTUBE_COMMENT_OWNER]

    def _assert_authenticated_owner(self) -> None:
        mine = self.writer._request("GET", "channels", params={"part": "id", "mine": "true", "maxResults": 5})
        items = mine.get("items")
        if (
            not isinstance(items, list)
            or len(items) != 1
            or not isinstance(items[0], dict)
            or items[0].get("id") != YOUTUBE_COMMENT_OWNER
            or mine.get("nextPageToken") is not None
        ):
            raise OperationRejectedError("OAuth grant belongs to a different YouTube channel")

    def _reserve_first_comment(self, operation: WaveOperation, payload: dict[str, str]) -> None:
        """Commit an irreversible target reservation before any possible POST.

        Unlike the caller-selected wave journal, this index is shared by all
        plans and journals on the canonical owner data store. Neither changed
        copy nor a new operation ID permits a second dispatch. The wave journal
        remains the receipt/result authority; this index is only a write barrier.
        """
        if self.data_dir is None:
            raise OperationRejectedError("No durable local owner lock directory was supplied")
        database = self.data_dir / "youtube" / "panorama-first-comment-reservations.sqlite3"
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(database, timeout=5.0)) as connection:
                connection.execute("PRAGMA synchronous=FULL")
                with connection:
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS first_comment_reservations ("
                        "channel_id TEXT NOT NULL, video_id TEXT NOT NULL, "
                        "operation_id TEXT NOT NULL, comment_sha256 TEXT NOT NULL, "
                        "PRIMARY KEY (channel_id, video_id))"
                    )
                    connection.execute(
                        "INSERT INTO first_comment_reservations "
                        "(channel_id, video_id, operation_id, comment_sha256) VALUES (?, ?, ?, ?)",
                        (YOUTUBE_COMMENT_OWNER, payload["video_id"], operation.operation_id, payload["comment_sha256"]),
                    )
        except sqlite3.IntegrityError as exc:
            raise OperationRejectedError(
                "A prior first-comment dispatch reservation exists; reconcile its original journal, never replay"
            ) from exc
        except (OSError, sqlite3.Error) as exc:
            raise OperationRejectedError("Cannot durably reserve the first-comment target; no POST allowed") from exc

    def execute(self, operation: WaveOperation) -> Mapping[str, Any]:
        p = self._validated_payload(operation)
        if (self._owns_writer or isinstance(self.writer, YouTubeCommentWriter)) and is_ci_environment():
            raise OperationRejectedError("YouTube comment writes require the persistent owner runtime, not CI")
        if self._owns_writer or isinstance(self.writer, YouTubeCommentWriter) or self.review_source is not None:
            self._assert_reviewed_source(operation, p)
        if self.data_dir is None:
            raise OperationRejectedError("No durable local owner lock directory was supplied")
        lock = self.data_dir / "locks" / (f"youtube-{self.account_alias}-{YOUTUBE_COMMENT_OWNER}.lock")
        with local_youtube_write_lock(lock, account=self.account_alias, channel_id=YOUTUBE_COMMENT_OWNER):
            self._assert_authenticated_owner()
            identity = self.writer.read_video_identity(p["video_id"])
            if identity.video_id != p["video_id"] or identity.channel_id != YOUTUBE_COMMENT_OWNER:
                raise OperationRejectedError("YouTube video identity or owner differs from the reviewed target")
            if identity.title != p["video_title"]:
                raise OperationRejectedError("YouTube title drifted after editorial review")
            if identity.privacy_status != "public":
                raise OperationRejectedError("YouTube target video must remain public")
            owned = self._owned(video_id=p["video_id"])
            if owned:
                raise OperationRejectedError(
                    "Existing owner-authored top-level comment: no unreviewed overwrite or second comment"
                )
            self._reserve_first_comment(operation, p)
            # Never clear the reservation, even after a rejected or uncertain POST.
            try:
                created = self.writer.create_top_level_comment(
                    video_id=p["video_id"],
                    expected_channel_id=YOUTUBE_COMMENT_OWNER,
                    text=p["comment_text"],
                )
            except Exception as exc:
                raise UnknownProviderOutcomeError(
                    f"YouTube comment dispatch or postflight uncertain ({type(exc).__name__}); "
                    "reconcile with read-only checks, never blind retry"
                ) from exc
            if (
                created.video_id != p["video_id"]
                or created.author_channel_id != YOUTUBE_COMMENT_OWNER
                or not comments_equivalent(created.text, p["comment_text"])
                or not created.comment_id
            ):
                raise UnknownProviderOutcomeError(
                    "YouTube reported a mismatched comment after dispatch; manual reconciliation required"
                )
            # The shared writer may fall back to the POST receipt after unsuccessful GETs.
            # This wave requires an independent, complete owner-inventory readback.
            try:
                observed = self._owned(video_id=p["video_id"])
                if (
                    len(observed) != 1
                    or observed[0].comment_id != created.comment_id
                    or not comments_equivalent(observed[0].text, p["comment_text"])
                ):
                    raise ValueError("Independent comment inventory does not match the create receipt")
            except Exception as exc:
                raise UnknownProviderOutcomeError(
                    "YouTube comment independent readback uncertain; reconcile with GET only, never blind retry"
                ) from exc
            return {
                "video_id": p["video_id"],
                "channel_id": YOUTUBE_COMMENT_OWNER,
                "comment_id": created.comment_id,
                "comment_sha256": p["comment_sha256"],
                "publication_verified": True,
            }

    def reconcile(self, operation: WaveOperation) -> Mapping[str, Any]:
        """GET-only outcome reconciliation; never creates or edits a comment."""
        p = self._validated_payload(operation)
        self._assert_authenticated_owner()
        identity = self.writer.read_video_identity(p["video_id"])
        if identity.video_id != p["video_id"] or identity.channel_id != YOUTUBE_COMMENT_OWNER:
            raise ValueError("YouTube reconciliation video or channel mismatch")
        owned = self._owned(video_id=p["video_id"])
        matching = [comment for comment in owned if comments_equivalent(comment.text, p["comment_text"])]
        if len(matching) != 1:
            raise ValueError(
                f"Cannot conclusively reconcile YouTube comment: {len(matching)} exact matching owner comments"
            )
        if len(owned) != 1:
            raise ValueError("YouTube reconciliation found unexpected second owner comment")
        return {
            "video_id": p["video_id"],
            "channel_id": YOUTUBE_COMMENT_OWNER,
            "comment_id": matching[0].comment_id,
            "comment_sha256": p["comment_sha256"],
            "reconciled_read_only": True,
        }

    def close(self) -> None:
        close = getattr(self.writer, "close", None)
        if callable(close):
            close()
