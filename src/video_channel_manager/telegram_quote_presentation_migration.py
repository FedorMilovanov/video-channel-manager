from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import (
    DEPTH_QUEUE_DIGEST,
    DEPTH_RELEASE_ID,
    DEPTH_V3_QUEUE_DIGEST,
    DEPTH_V3_RELEASE_ID,
    build_depth_runtime_queue,
    build_depth_v3_runtime_queue,
)
from video_channel_manager.telegram_quote_progress import validate_quote_progress

MIGRATION_FILENAME = "successor-depth-presentation-migration-v1.json"
MIGRATION_V2_FILENAME = "successor-depth-presentation-migration-v2.json"
EXPECTED_BOUNDARY = 15
EXPECTED_V2_BOUNDARY = 16
EXPECTED_TOTAL = 60


class QuotePresentationMigration(BaseModel):
    """Immutable v3 -> v4 presentation migration boundary (historical)."""

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


class QuotePresentationMigrationV2(BaseModel):
    """Immutable v4 -> v5 presentation migration boundary.

    Sequences 16 and 17 are the only cards ever published under quote-v4 (17
    went out on 2026-10-17 as durable Telegram message 1567). The v5 policy
    renders the pending suffix quote-first with no leading title at all; the
    depth-v3 restore release guarantees that every pending quotation opens as
    a complete, self-contained thought, so no title is ever needed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-presentation-migration"]
    schema_version: Literal[2]
    release_id: Literal["lordchrist-successor-depth-v3"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[17]
    from_policy_id: Literal["lordchrist-quote-v4"]
    from_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    to_policy_id: Literal["lordchrist-quote-v5"]
    to_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_writes_authorized: Literal[False]
    reason: str = Field(min_length=80, max_length=1000)

    @model_validator(mode="after")
    def exact_release_identity(self) -> "QuotePresentationMigrationV2":
        if self.release_id != DEPTH_V3_RELEASE_ID or self.queue_digest != DEPTH_V3_QUEUE_DIGEST:
            raise ValueError("presentation migration differs from the sealed depth-v3 restore release identity")
        if self.from_policy_sha256 == self.to_policy_sha256:
            raise ValueError("presentation migration must change the presentation policy digest")
        return self


MigrationContract = QuotePresentationMigration | QuotePresentationMigrationV2


def load_migration(path: Path) -> MigrationContract:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
        if schema_version == 1:
            return QuotePresentationMigration.model_validate(payload)
        if schema_version == 2:
            return QuotePresentationMigrationV2.model_validate(payload)
        raise ValueError(f"unsupported quote presentation migration schema version: {schema_version!r}")
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid LordChrist quote presentation migration {path}: {exc}") from exc


def load_ledger(path: Path) -> TelegramLedger:
    try:
        return TelegramLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist publication ledger {path}: {exc}") from exc


def validate_migration(
    *,
    migration_path: Path,
    from_policy_path: Path,
    to_policy_path: Path,
    ledger_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    allow_verified_progress: bool = False,
) -> dict[str, object]:
    migration = load_migration(migration_path)
    from_policy = load_presentation_policy(from_policy_path)
    to_policy = load_presentation_policy(to_policy_path)
    if migration.from_policy_id != from_policy.policy_id or migration.from_policy_sha256 != from_policy.digest:
        raise ValueError("migration source presentation identity differs from the reviewed source policy")
    if migration.to_policy_id != to_policy.policy_id or migration.to_policy_sha256 != to_policy.digest:
        raise ValueError("migration target presentation identity differs from the reviewed target policy")

    if migration.schema_version == 2:
        queue = build_depth_v3_runtime_queue(
            candidate_path=candidate_path,
            translation_ledger_path=translation_ledger_path,
            integrity_amendment_path=integrity_amendment_path,
        )
    else:
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

    boundary = validate_quote_progress(
        queue,
        ledger,
        minimum_published=migration.published_boundary,
        allow_progress=allow_verified_progress,
        policy=to_policy,
        evidence_root=ledger_path.parent / "dispatches",
    )

    return {
        "migration_schema_version": migration.schema_version,
        "release_id": migration.release_id,
        "queue_digest": migration.queue_digest,
        "published_boundary": migration.published_boundary,
        "published_verified": boundary,
        "pending_pristine": EXPECTED_TOTAL - boundary,
        "from_policy_id": migration.from_policy_id,
        "to_policy_id": migration.to_policy_id,
        "provider_writes_authorized": migration.provider_writes_authorized,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an immutable quote presentation migration boundary.")
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--from-policy", type=Path, required=True)
    parser.add_argument("--to-policy", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--translation-ledger", type=Path, required=True)
    parser.add_argument("--integrity-amendment", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = validate_migration(
        migration_path=args.migration,
        from_policy_path=args.from_policy,
        to_policy_path=args.to_policy,
        ledger_path=args.ledger,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
