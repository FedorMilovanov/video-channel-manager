from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_research_release import build_research_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding

FIRST_CANARY_PUBLICATION_ID = "lordchrist-research-three-preachers-numbers"


class LordchristResearchRolloutApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.lordchrist-research-rollout-approval"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    release_id: str = Field(pattern=r"^lordchrist-research-[a-z0-9][a-z0-9-]{4,80}$")
    start_at: datetime
    candidate_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approved_release_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reviewed_by: str = Field(min_length=3, max_length=200)
    reviewed_at: datetime
    owning_issue: Literal[242]
    first_canary_publication_id: Literal["lordchrist-research-three-preachers-numbers"]
    provider_write_scope: Literal["exact research-v2 canary then canary-gated scheduled pilot only"]

    @field_validator("start_at", "reviewed_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("rollout timestamps must be timezone-aware")
        return value


def load_lordchrist_research_rollout_approval(path: Path) -> LordchristResearchRolloutApproval:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return LordchristResearchRolloutApproval.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist research rollout approval {path}: {exc}") from exc


def _runtime_profile(base_profile: TelegramChannelProfile) -> TelegramChannelProfile:
    if base_profile.provider_writes_authorized:
        raise ValueError("canonical Lordchrist generic profile must remain provider-write-disabled")
    runtime = base_profile.model_copy(update={"provider_writes_authorized": True})
    if runtime.digest != base_profile.digest:
        raise ValueError("execution-only write gate unexpectedly changed channel identity digest")
    return runtime


def materialize_lordchrist_research_rollout(
    *,
    profile_path: Path,
    queue_path: Path,
    binding_path: Path,
    approval_path: Path,
    release_output_path: Path,
    runtime_profile_output_path: Path,
) -> tuple[GenericReleaseQueue, TelegramChannelProfile]:
    base_profile = load_channel_profile(profile_path)
    if base_profile.provider_writes_authorized:
        raise ValueError("canonical Lordchrist generic profile must remain provider-write-disabled")
    research = load_research_queue(queue_path)
    binding = load_target_binding(binding_path, base_profile)
    approval = load_lordchrist_research_rollout_approval(approval_path)

    if approval.project_key != base_profile.project_key:
        raise ValueError("research rollout approval project differs from selected profile")
    if research.schedule.state != "staged" or research.live_eligible:
        raise ValueError("canonical research evidence queue must remain staged/provider-inert")

    candidate = build_research_release_candidate(
        base_profile,
        research,
        release_id=approval.release_id,
        start_at=approval.start_at,
        binding=binding,
    )
    if candidate.items[0].publication_id != approval.first_canary_publication_id:
        raise ValueError("reviewed first research canary is not the strict first immutable release item")

    current_candidate_sha256 = candidate.candidate_digest()
    release = authorize_release_candidate(
        candidate,
        profile=base_profile,
        binding=binding,
        expected_candidate_sha256=current_candidate_sha256,
        reviewed_by=approval.reviewed_by,
        reviewed_at=approval.reviewed_at,
    )
    current_release_sha256 = release.digest
    if (
        current_candidate_sha256 != approval.candidate_sha256
        or current_release_sha256 != approval.approved_release_sha256
    ):
        raise ValueError(
            "current Lordchrist research release differs from exact rollout approval: "
            f"current_candidate={current_candidate_sha256} reviewed_candidate={approval.candidate_sha256} "
            f"current_release={current_release_sha256} reviewed_release={approval.approved_release_sha256}"
        )

    runtime_profile = _runtime_profile(base_profile)
    release_output_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_profile_output_path.parent.mkdir(parents=True, exist_ok=True)
    release_output_path.write_text(release.model_dump_json(indent=2) + "\n", encoding="utf-8")
    runtime_profile_output_path.write_text(runtime_profile.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return release, runtime_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize one exact approved Lordchrist research-v2 rollout without provider access."
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--release-output", type=Path, required=True)
    parser.add_argument("--runtime-profile-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    release, runtime_profile = materialize_lordchrist_research_rollout(
        profile_path=args.profile,
        queue_path=args.queue,
        binding_path=args.binding,
        approval_path=args.approval,
        release_output_path=args.release_output,
        runtime_profile_output_path=args.runtime_profile_output,
    )
    print(f"release_id={release.release_id}")
    print(f"candidate_digest={release.candidate_digest()}")
    print(f"approved_release_digest={release.digest}")
    print(f"first_canary={FIRST_CANARY_PUBLICATION_ID}")
    print(f"runtime_profile_provider_writes_authorized={runtime_profile.provider_writes_authorized}")
    print("provider_write_performed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
