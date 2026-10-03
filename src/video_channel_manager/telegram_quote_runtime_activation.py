from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN, TelegramLedger
from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_publisher import load_ledger
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, DEPTH_RELEASE_ID, build_depth_runtime_queue
from video_channel_manager.telegram_quote_presentation_migration import validate_migration
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue
from video_channel_manager.telegram_quote_source_audit import (
    assert_future_exact_source_coverage,
    load_source_web_audit,
)

RUNTIME_ACTIVATION_FILENAME = "successor-depth-runtime-activation-v4.json"
EXPECTED_TOTAL = 60
SEALED_HANDOFF_PREFIX = 14


class RuntimeActivation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-runtime-activation"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    sealed_handoff_published_prefix: Literal[14]
    required_published_prefix: int = Field(ge=SEALED_HANDOFF_PREFIX, le=EXPECTED_TOTAL)
    required_pending_suffix: int = Field(ge=0, le=EXPECTED_TOTAL)
    presentation_policy_id: Literal["lordchrist-quote-v4"]
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    state_ledger_relative_path: Literal["content/telegram/lordchrist/successor-depth-v2-publication-ledger.json"]
    source_web_audit: Literal["quote-source-web-audit-v2.json"]
    source_live_probe: Literal["quote-source-live-probe-v1.json"]
    presentation_migration: Literal["successor-depth-presentation-migration-v1.json"]
    provider_writes_authorized: bool
    note: str = Field(min_length=120, max_length=1200)

    @model_validator(mode="after")
    def exact_runtime_identity(self) -> "RuntimeActivation":
        if self.release_id != DEPTH_RELEASE_ID or self.queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("runtime activation differs from the sealed depth-v2 queue identity")
        if self.required_published_prefix + self.required_pending_suffix != EXPECTED_TOTAL:
            raise ValueError("runtime activation checkpoint must cover all 60 positional slots")
        if self.required_published_prefix < self.sealed_handoff_published_prefix:
            raise ValueError("runtime activation cannot move behind the sealed 14/46 handoff")
        return self


def load_runtime_activation(path: Path) -> RuntimeActivation:
    try:
        return RuntimeActivation.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist runtime activation {path}: {exc}") from exc


def _validate_live_probe(path: Path, *, audit_page_count: int) -> dict[str, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid LordChrist quote source live probe {path}: {exc}") from exc

    if payload.get("schema_name") != "video-channel-manager.telegram-quote-source-live-probe":
        raise ValueError("live source probe schema identity is invalid")
    if payload.get("schema_version") != 1:
        raise ValueError("live source probe schema version is invalid")
    if payload.get("release_id") != DEPTH_RELEASE_ID or payload.get("queue_digest") != DEPTH_QUEUE_DIGEST:
        raise ValueError("live source probe differs from the exact depth-v2 release identity")
    if payload.get("web_audit_file") != "quote-source-web-audit-v2.json":
        raise ValueError("live source probe is not bound to the reviewed web-audit inventory")

    attempted = int(payload.get("urls_attempted", -1))
    succeeded = int(payload.get("urls_fetched_successfully", -1))
    failed = int(payload.get("fetch_failures", -1))
    failed_urls = payload.get("failed_urls")
    if attempted != audit_page_count:
        raise ValueError("live source probe URL count differs from the reviewed web-audit inventory")
    if succeeded + failed != attempted:
        raise ValueError("live source probe success/failure accounting is inconsistent")
    if succeeded < 50:
        raise ValueError("live source probe did not independently fetch at least 50 reviewed source URLs")
    if not isinstance(failed_urls, list) or len(failed_urls) != failed or len(failed_urls) != len(set(failed_urls)):
        raise ValueError("live source probe failure inventory is inconsistent")
    semantics = str(payload.get("failure_semantics", ""))
    if "not evidence that the source URL is dead" not in semantics:
        raise ValueError("live source probe must preserve retrieval-failure semantics")
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}


def validate_runtime_checkpoint(
    *,
    activation_path: Path,
    presentation_policy_path: Path,
    v3_policy_path: Path,
    migration_path: Path,
    source_web_audit_path: Path,
    source_live_probe_path: Path,
    ledger_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    depth_audit_path: Path,
    replacements_path: Path,
    require_provider_writes: bool = False,
) -> dict[str, object]:
    activation = load_runtime_activation(activation_path)
    policy = load_presentation_policy(presentation_policy_path)
    if activation.presentation_policy_id != policy.policy_id:
        raise ValueError("runtime activation presentation policy id differs from quote-v4")
    if activation.presentation_policy_sha256 != policy.digest:
        raise ValueError("runtime activation presentation policy digest differs from quote-v4")
    if require_provider_writes and not activation.provider_writes_authorized:
        raise ValueError("quote-v4 provider writes are not authorized by the rolling runtime activation")

    queue = build_depth_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
        audit_path=depth_audit_path,
        replacements_path=replacements_path,
    )
    if not isinstance(queue, SuccessorRuntimeQueue):
        raise ValueError("runtime activation requires the exact successor runtime queue")
    if queue.release_id != activation.release_id or queue.digest != activation.queue_digest:
        raise ValueError("runtime queue differs from the rolling activation identity")

    ledger: TelegramLedger = load_ledger(ledger_path, queue)
    expected_ids = [post.publication_id for post in queue.posts]
    if list(ledger.entries) != expected_ids:
        raise ValueError("durable ledger ordering/inventory differs from the exact runtime queue")

    boundary = activation.required_published_prefix
    for post in queue.posts[:boundary]:
        entry = ledger.entries[post.publication_id]
        if entry.state != "published" or entry.provider_effect != "verified" or not entry.message_id:
            raise ValueError(f"runtime checkpoint requires verified published prefix: {post.publication_id}")
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"published runtime checkpoint payload differs: {post.publication_id}")

    pristine_effects = {"impossible", "not_dispatched", "confirmed_absent"}
    for post in queue.posts[boundary:]:
        entry = ledger.entries[post.publication_id]
        if entry.state != "pending" or entry.provider_effect not in pristine_effects:
            raise ValueError(f"runtime checkpoint requires pristine pending suffix: {post.publication_id}")
        if any(
            value is not None
            for value in (
                entry.intent_id,
                entry.dispatch_mode,
                entry.scheduled_slot,
                entry.workflow_run_id,
                entry.workflow_run_attempt,
                entry.github_sha,
                entry.github_workflow_sha,
                entry.attempted_at_utc,
                entry.published_at_utc,
                entry.message_id,
                entry.message_url,
            )
        ):
            raise ValueError(f"pending runtime checkpoint retains dispatch/provider identity: {post.publication_id}")
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"pending runtime checkpoint payload differs: {post.publication_id}")

    migration = validate_migration(
        migration_path=migration_path,
        v3_policy_path=v3_policy_path,
        v4_policy_path=presentation_policy_path,
        ledger_path=ledger_path,
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    if migration["published_boundary"] != boundary:
        raise ValueError("presentation migration boundary differs from the rolling activation checkpoint")

    web_audit = load_source_web_audit(source_web_audit_path)
    exact_sources = assert_future_exact_source_coverage(
        web_audit,
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
        depth_audit_path=depth_audit_path,
        replacements_path=replacements_path,
    )
    live_probe = _validate_live_probe(source_live_probe_path, audit_page_count=web_audit.research_pages_reviewed)

    next_post = queue.posts[boundary] if boundary < len(queue.posts) else None
    return {
        "release_id": activation.release_id,
        "queue_digest": activation.queue_digest,
        "presentation_policy_id": policy.policy_id,
        "published_verified": boundary,
        "pending_pristine": activation.required_pending_suffix,
        "next_sequence": next_post.sequence if next_post is not None else None,
        "next_publication_id": next_post.publication_id if next_post is not None else None,
        "exact_future_source_urls": len(set(exact_sources.values())),
        "web_pages_reviewed": web_audit.research_pages_reviewed,
        "live_urls_succeeded": live_probe["succeeded"],
        "provider_writes_authorized": activation.provider_writes_authorized,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Validate the rolling LordChrist quote-v4 runtime activation checkpoint."
    )
    root.add_argument("--activation", type=Path, required=True)
    root.add_argument("--presentation-policy", type=Path, required=True)
    root.add_argument("--v3-policy", type=Path, required=True)
    root.add_argument("--migration", type=Path, required=True)
    root.add_argument("--source-web-audit", type=Path, required=True)
    root.add_argument("--source-live-probe", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    root.add_argument("--candidate", type=Path, required=True)
    root.add_argument("--translation-ledger", type=Path, required=True)
    root.add_argument("--integrity-amendment", type=Path, required=True)
    root.add_argument("--depth-audit", type=Path, required=True)
    root.add_argument("--replacements", type=Path, required=True)
    root.add_argument("--require-provider-writes", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    result = validate_runtime_checkpoint(
        activation_path=args.activation,
        presentation_policy_path=args.presentation_policy,
        v3_policy_path=args.v3_policy,
        migration_path=args.migration,
        source_web_audit_path=args.source_web_audit,
        source_live_probe_path=args.source_live_probe,
        ledger_path=args.ledger,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendment,
        depth_audit_path=args.depth_audit,
        replacements_path=args.replacements,
        require_provider_writes=args.require_provider_writes,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
