from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_editorial import (
    HistoricalEditorialQueueV1,
    HistoricalSourceRegistry,
    SourceBindingKind,
    load_theology_profile,
)
from video_channel_manager.telegram_research import sha256_json

DEFAULT_WEEKDAYS: tuple[int, int, int] = (1, 3, 6)
DEFAULT_LOCAL_TIME = "19:17"
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_SLOT_COUNT = 9


class HistoricalScaffoldSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=99)
    scheduled_date: date
    release_offset_days: int = Field(ge=0, le=366)
    topic_brief: str = ""
    publication_id: str = ""


class HistoricalCycleScaffoldV1(BaseModel):
    """Provider-inert planning envelope for a future historical cycle.

    The scaffold is intentionally not a publishable queue. It gives editors
    deterministic dates and immutable source/profile bindings while leaving
    topic and publication identity blank until research is complete.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-cycle-scaffold"]
    schema_version: Literal[1]
    cycle_id: str = Field(pattern=r"^history-cycle-[a-z0-9][a-z0-9-]{3,80}$")
    state: Literal["draft_scaffold"]
    provider_writes_authorized: Literal[False]
    timezone: Literal["Europe/Moscow"]
    local_time: Literal["19:17"]
    iso_weekdays: tuple[int, int, int]
    source_binding_kind: SourceBindingKind
    source_binding_path: str = Field(min_length=5, max_length=300)
    source_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_registry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    theology_profile_path: str = Field(min_length=5)
    theology_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    slots: tuple[HistoricalScaffoldSlot, ...] = Field(min_length=1, max_length=99)

    @model_validator(mode="after")
    def scaffold_contract(self) -> "HistoricalCycleScaffoldV1":
        if self.iso_weekdays != DEFAULT_WEEKDAYS:
            raise ValueError("historical scaffold cadence must be Monday/Wednesday/Saturday")
        if [slot.sequence for slot in self.slots] != list(range(1, len(self.slots) + 1)):
            raise ValueError("historical scaffold slot sequence must be contiguous from 1")
        if any(slot.scheduled_date.isoweekday() not in self.iso_weekdays for slot in self.slots):
            raise ValueError("historical scaffold contains a date outside cadence")
        if self.slots[0].release_offset_days != 0:
            raise ValueError("historical scaffold first slot must have release_offset_days=0")
        first = self.slots[0].scheduled_date
        for slot in self.slots:
            if slot.release_offset_days != (slot.scheduled_date - first).days:
                raise ValueError("historical scaffold offsets must match scheduled dates")
        if self.source_binding_kind == "registry" and self.source_binding_sha256 != self.source_registry_sha256:
            raise ValueError("direct registry binding digest must equal materialized registry digest")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalBundlePreflightV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-bundle-preflight"]
    schema_version: Literal[1]
    status: Literal["PASS"]
    queue_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_registry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    theology_profile_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_count: int = Field(ge=50)
    grade_a_count: int = Field(ge=1)
    grade_bplus_count: int = Field(ge=1)
    independent_evidence_groups: int = Field(ge=2)
    claim_count: int = Field(ge=1)
    direct_quote_count: int = Field(ge=0)
    controversy_post_count: int = Field(ge=0)
    martyrdom_post_count: int = Field(ge=0)
    image_plan_count: int = Field(ge=0)
    production_ready_image_count: int = Field(ge=0)
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    backfill_policy: Literal["none"]


def next_cadence_dates(
    start_on: date,
    *,
    count: int = DEFAULT_SLOT_COUNT,
    iso_weekdays: tuple[int, int, int] = DEFAULT_WEEKDAYS,
) -> tuple[date, ...]:
    if count < 1 or count > 99:
        raise ValueError("historical cadence count must be in 1..99")
    if iso_weekdays != tuple(sorted(set(iso_weekdays))) or any(day < 1 or day > 7 for day in iso_weekdays):
        raise ValueError("historical cadence weekdays must be unique sorted ISO weekdays")

    dates: list[date] = []
    cursor = start_on
    while len(dates) < count:
        if cursor.isoweekday() in iso_weekdays:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return tuple(dates)


def build_cycle_scaffold(
    *,
    cycle_id: str,
    start_on: date,
    source_binding_kind: SourceBindingKind,
    source_binding_path: str,
    source_binding_sha256: str,
    source_registry_sha256: str,
    theology_profile_path: str,
    theology_profile_sha256: str,
    slot_count: int = DEFAULT_SLOT_COUNT,
) -> HistoricalCycleScaffoldV1:
    dates = next_cadence_dates(start_on, count=slot_count)
    first = dates[0]
    slots = tuple(
        HistoricalScaffoldSlot(
            sequence=index,
            scheduled_date=scheduled,
            release_offset_days=(scheduled - first).days,
        )
        for index, scheduled in enumerate(dates, start=1)
    )
    return HistoricalCycleScaffoldV1(
        schema_name="video-channel-manager.telegram-historical-cycle-scaffold",
        schema_version=1,
        cycle_id=cycle_id,
        state="draft_scaffold",
        provider_writes_authorized=False,
        timezone=DEFAULT_TIMEZONE,
        local_time=DEFAULT_LOCAL_TIME,
        iso_weekdays=DEFAULT_WEEKDAYS,
        source_binding_kind=source_binding_kind,
        source_binding_path=source_binding_path,
        source_binding_sha256=source_binding_sha256,
        source_registry_sha256=source_registry_sha256,
        theology_profile_path=theology_profile_path,
        theology_profile_sha256=theology_profile_sha256,
        slots=slots,
    )


def _resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError("historical bundle paths must be repository-relative")
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("historical bundle path escapes repository root")
    return resolved


def preflight_historical_bundle(queue_path: Path, *, repo_root: Path = Path(".")) -> HistoricalBundlePreflightV1:
    """Validate a direct-registry queue and return a compact proof report."""

    resolved_queue = queue_path if queue_path.is_absolute() else _resolve_repo_path(repo_root, str(queue_path))
    raw = json.loads(resolved_queue.read_text(encoding="utf-8"))
    queue = HistoricalEditorialQueueV1.model_validate(raw)
    if queue.source_binding_kind != "registry":
        raise ValueError("catalog-bound historical queues require manifest preflight")

    binding_path = _resolve_repo_path(repo_root, queue.source_binding_path)
    binding_payload = json.loads(binding_path.read_text(encoding="utf-8"))
    if sha256_json(binding_payload) != queue.source_binding_sha256:
        raise ValueError("historical source binding digest mismatch")
    registry = HistoricalSourceRegistry.model_validate(binding_payload)

    theology_path = _resolve_repo_path(repo_root, queue.theology_profile_path)
    theology = load_theology_profile(theology_path)

    if registry.digest != queue.source_registry_sha256:
        raise ValueError("historical source registry digest mismatch")
    if theology.digest != queue.theology_profile_sha256:
        raise ValueError("historical theology profile digest mismatch")
    if queue.verification.reviewed_urls < len(registry.sources):
        raise ValueError("reviewed_urls cannot be lower than persisted source registry size")
    if queue.verification.checked_on < registry.checked_on or queue.verification.checked_on < theology.checked_on:
        raise ValueError("historical verification cannot predate bound evidence")

    by_id = {source.source_id: source for source in registry.sources}
    for post in queue.posts:
        for claim in post.claims:
            unknown = set(claim.source_ids) - set(by_id)
            if unknown:
                raise ValueError(f"historical claim {claim.claim_id} uses unknown sources: {sorted(unknown)}")
            bound = [by_id[source_id] for source_id in claim.source_ids]
            if claim.direct_quote:
                if not any(
                    source.grade == "A"
                    and source.evidence_role
                    in {"primary_document", "critical_edition", "official_archive", "university_archive"}
                    for source in bound
                ):
                    raise ValueError(
                        f"direct quotation {claim.claim_id} requires grade A primary/critical/archive evidence"
                    )
            elif claim.voice != "editorial_evaluation":
                groups = {source.independence_group for source in bound}
                if len(groups) < 2:
                    raise ValueError(
                        f"material historical claim {claim.claim_id} requires two independent evidence groups"
                    )
                if not any(source.grade == "A" for source in bound):
                    raise ValueError(f"material historical claim {claim.claim_id} requires at least one grade A source")
        for image in post.images:
            if image.source_id not in by_id:
                raise ValueError(f"historical image {image.asset_id} uses unknown provenance source")
            if image.checked_on > queue.verification.checked_on:
                raise ValueError(f"historical image {image.asset_id} check is newer than queue verification")

    return HistoricalBundlePreflightV1(
        schema_name="video-channel-manager.telegram-historical-bundle-preflight",
        schema_version=1,
        status="PASS",
        queue_digest=queue.digest,
        source_registry_digest=registry.digest,
        theology_profile_digest=theology.digest,
        source_count=len(registry.sources),
        grade_a_count=sum(source.grade == "A" for source in registry.sources),
        grade_bplus_count=sum(source.grade == "B+" for source in registry.sources),
        independent_evidence_groups=len({source.independence_group for source in registry.sources}),
        claim_count=sum(len(post.claims) for post in queue.posts),
        direct_quote_count=sum(claim.direct_quote for post in queue.posts for claim in post.claims),
        controversy_post_count=sum(post.topic_kind == "controversy" for post in queue.posts),
        martyrdom_post_count=sum(post.topic_kind == "martyrdom" for post in queue.posts),
        image_plan_count=sum(len(post.images) for post in queue.posts),
        production_ready_image_count=sum(image.production_ready for post in queue.posts for image in post.images),
        provider_writes_authorized=False,
        live_eligible=False,
        backfill_policy=queue.schedule.backfill_policy,
    )


def write_scaffold(path: Path, scaffold: HistoricalCycleScaffoldV1) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing historical scaffold: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scaffold.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LordChrist historical editorial workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight", help="validate one direct-registry historical editorial bundle")
    preflight.add_argument("queue", type=Path)
    preflight.add_argument("--repo-root", type=Path, default=Path("."))

    scaffold = sub.add_parser("scaffold", help="create a provider-inert future-cycle scaffold")
    scaffold.add_argument("--cycle-id", required=True)
    scaffold.add_argument("--start-on", required=True, type=date.fromisoformat)
    scaffold.add_argument("--source-binding-kind", required=True, choices=("registry", "catalog"))
    scaffold.add_argument("--source-binding-path", required=True)
    scaffold.add_argument("--source-binding-sha256", required=True)
    scaffold.add_argument("--source-registry-sha256", required=True)
    scaffold.add_argument("--theology-profile-path", required=True)
    scaffold.add_argument("--theology-profile-sha256", required=True)
    scaffold.add_argument("--slot-count", type=int, default=DEFAULT_SLOT_COUNT)
    scaffold.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "preflight":
        report = preflight_historical_bundle(args.queue, repo_root=args.repo_root)
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    scaffold = build_cycle_scaffold(
        cycle_id=args.cycle_id,
        start_on=args.start_on,
        source_binding_kind=args.source_binding_kind,
        source_binding_path=args.source_binding_path,
        source_binding_sha256=args.source_binding_sha256,
        source_registry_sha256=args.source_registry_sha256,
        theology_profile_path=args.theology_profile_path,
        theology_profile_sha256=args.theology_profile_sha256,
        slot_count=args.slot_count,
    )
    write_scaffold(args.output, scaffold)
    print(json.dumps({"status": "CREATED", "path": str(args.output), "digest": scaffold.digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_LOCAL_TIME",
    "DEFAULT_SLOT_COUNT",
    "DEFAULT_TIMEZONE",
    "DEFAULT_WEEKDAYS",
    "HistoricalBundlePreflightV1",
    "HistoricalCycleScaffoldV1",
    "HistoricalScaffoldSlot",
    "build_cycle_scaffold",
    "next_cadence_dates",
    "preflight_historical_bundle",
    "write_scaffold",
]
