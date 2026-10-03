from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, DEPTH_RELEASE_ID, build_depth_runtime_queue

MIGRATION_FILENAME = "successor-depth-presentation-migration-v1.json"
EXPECTED_BOUNDARY = 15
EXPECTED_TOTAL = 60


class QuotePresentationMigration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-presentation-migration"]
    schema_version: Literal[1]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    from_policy_id: Literal["lordchrist-quote-v3"]
    from_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    to_policy_id: Literal["lordchrist-quote-v4"]
    to_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_writes_authorized: Literal[False]
    reason: str = Field(min_length=80, max_length=1000)

    @model_validator(mode="after")
    def exact_release_identity(self) -> "QuotePresentationMigration":
        if self.release_id != DEPTH_RELEASE_ID or self.queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("presentation migration differs from the sealed depth-v2 release identity")
        if self.from_policy_sha256 == self.to_policy_sha256:
            raise ValueError("presentation migration must change the presentation policy digest")
        return self


def load_migration(path: Path) -> QuotePresentationMigration:
    try:
        return QuotePresentationMigration.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist quote presentation migration {path}: {exc}") from exc


def load_ledger(path: Path) -> TelegramLedger:
    try:
        return TelegramLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist publication ledger {path}: {exc}") from exc


def validate_migration(
    *,
    migration_path: Path,
    v3_policy_path: Path,
    v4_policy_path: Path,
    ledger_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
) -> dict[str, object]:
    migration = load_migration(migration_path)
    v3 = load_presentation_policy(v3_policy_path)
    v4 = load_presentation_policy(v4_policy_path)
    if migration.from_policy_id != v3.policy_id or migration.from_policy_sha256 != v3.digest:
        raise ValueError("migration source presentation identity differs from reviewed quote-v3")
    if migration.to_policy_id != v4.policy_id or migration.to_policy_sha256 != v4.digest:
        raise ValueError("migration target presentation identity differs from reviewed quote-v4")

    queue = build_depth_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    if queue.release_id != migration.release_id or queue.digest != migration.queue_digest:
        raise ValueError("runtime queue differs from the migration release identity")
    if len(queue.posts) != EXPECTED_TOTAL:
        raise ValueError("migration requires the exact 60-card depth-v2 runtime queue")

    ledger = load_ledger(ledger_path)
    if ledger.queue_digest != migration.queue_digest:
        raise ValueError("durable state ledger differs from migration queue digest")

    expected_ids = [post.publication_id for post in queue.posts]
    if set(ledger.entries) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(ledger.entries))
        extra = sorted(set(ledger.entries) - set(expected_ids))
        raise ValueError(f"durable ledger inventory differs from runtime queue: missing={missing}, extra={extra}")

    for post in queue.posts[: migration.published_boundary]:
        entry = ledger.entries[post.publication_id]
        if entry.state != "published" or entry.provider_effect != "verified":
            raise ValueError(f"published migration prefix is not immutable provider-verified history: {post.publication_id}")
        if entry.payload_sha256 != post.source_payload_sha256:
            raise ValueError(f"published migration prefix payload differs from runtime identity: {post.publication_id}")

    for post in queue.posts[migration.published_boundary :]:
        entry = ledger.entries[post.publication_id]
        if entry.state != "pending" or entry.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}:
            raise ValueError(f"future migration suffix is not pristine pending state: {post.publication_id}")
        if entry.intent_id is not None or entry.message_id is not None:
            raise ValueError(f"future migration suffix already has dispatch/provider identity: {post.publication_id}")
        if entry.payload_sha256 != post.source_payload_sha256:
            raise ValueError(f"future migration suffix payload differs from runtime identity: {post.publication_id}")

    return {
        "release_id": migration.release_id,
        "queue_digest": migration.queue_digest,
        "published_boundary": migration.published_boundary,
        "published_verified": migration.published_boundary,
        "pending_pristine": EXPECTED_TOTAL - migration.published_boundary,
        "from_policy_id": migration.from_policy_id,
        "to_policy_id": migration.to_policy_id,
        "provider_writes_authorized": migration.provider_writes_authorized,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the immutable quote-v3 to quote-v4 migration boundary.")
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--v3-policy", type=Path, required=True)
    parser.add_argument("--v4-policy", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = validate_migration(
        migration_path=args.migration,
        v3_policy_path=args.v3_policy,
        v4_policy_path=args.v4_policy,
        ledger_path=args.ledger,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
