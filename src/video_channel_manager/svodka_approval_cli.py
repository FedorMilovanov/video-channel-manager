from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding


class SvodkaReleaseApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-release-approval"]
    schema_version: Literal[1]
    project_key: Literal["svodka"]
    release_id: str = Field(pattern=r"^svodka-[a-z0-9][a-z0-9-]{4,90}$")
    candidate_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approved_release_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reviewed_by: str = Field(min_length=3, max_length=200)
    reviewed_at: datetime
    owning_issue: int = Field(ge=1)
    provider_write_scope: Literal["exact manual canary then canary-gated scheduled pilot only"]

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value


def load_svodka_release_approval(path: Path) -> SvodkaReleaseApproval:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SvodkaReleaseApproval.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Svodka release approval {path}: {exc}") from exc


def materialize_svodka_approved_release(
    *,
    profile_path: Path,
    queue_path: Path,
    binding_path: Path,
    approval_path: Path,
    output_path: Path,
) -> tuple[str, str]:
    profile = load_channel_profile(profile_path)
    draft = load_svodka_draft(queue_path, profile)
    binding = load_target_binding(binding_path, profile)
    approval = load_svodka_release_approval(approval_path)

    if approval.project_key != profile.project_key:
        raise ValueError("Svodka approval project differs from selected profile")

    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id=approval.release_id,
        binding=binding,
    )
    if candidate.digest != approval.candidate_sha256:
        raise ValueError(
            "current Svodka candidate differs from reviewed approval: "
            f"current={candidate.digest} reviewed={approval.candidate_sha256}"
        )

    release = authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=approval.candidate_sha256,
        reviewed_by=approval.reviewed_by,
        reviewed_at=approval.reviewed_at,
    )
    if release.digest != approval.approved_release_sha256:
        raise ValueError(
            "materialized Svodka approved release digest mismatch: "
            f"current={release.digest} reviewed={approval.approved_release_sha256}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(release.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return candidate.digest, release.digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize an exact reviewed Svodka release without provider access.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidate_digest, release_digest = materialize_svodka_approved_release(
        profile_path=args.profile,
        queue_path=args.queue,
        binding_path=args.binding,
        approval_path=args.approval,
        output_path=args.output,
    )
    print(f"candidate_digest={candidate_digest}")
    print(f"approved_release_digest={release_digest}")
    print("provider_write_performed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
