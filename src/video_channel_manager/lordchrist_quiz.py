"""Reviewed one-off Bible-quiz lane for the @lordchrist channel.

A human-authored quiz spec (``content/telegram/lordchrist/quiz/<id>.json``)
is built into an immutable generic Telegram release whose single item is a
native ``sendPoll`` quiz payload. The committed ``<id>-runtime.json`` release
is the only execution authority: it must be review-authorized against the
exact channel profile and target binding, and the GitHub workflow drives the
canonical multichannel runtime (initialize -> prepare -> send-once ->
apply-outcome) against the durable ``state/lordchrist-telegram`` ledger.
This module never talks to the Telegram provider itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_state import (
    GenericPublicationLedger,
    initialize_ledger,
    load_ledger,
)
from video_channel_manager.telegram_multichannel_transport import render_poll_payload
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "content/telegram/lordchrist/quiz"
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist-rich.json"
BINDING_PATH = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
STATE_LEDGER_PREFIX = "content/telegram/lordchrist/quiz"


class LordchristQuizSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.lordchrist-quiz-spec"]
    schema_version: Literal[1]
    publication_id: str = Field(pattern=r"^lordchrist-quiz-[a-z0-9][a-z0-9-]{3,80}$")
    title: str = Field(min_length=3, max_length=120)
    question: str = Field(min_length=10, max_length=300)
    options: tuple[str, ...] = Field(min_length=2, max_length=10)
    correct_option_index: int = Field(ge=0)
    explanation: str = Field(min_length=10, max_length=200)
    scripture_references: tuple[str, ...] = Field(min_length=1, max_length=8)
    scheduled_at: datetime
    hashtags: str = Field(default="", max_length=120)
    layout: Literal["v1", "v2"] = "v1"

    @model_validator(mode="after")
    def validate_quiz(self) -> "LordchristQuizSpec":
        if self.scheduled_at.tzinfo is None:
            raise ValueError("quiz scheduled_at must be timezone-aware")
        if self.layout == "v1" and not self.hashtags.strip():
            raise ValueError("layout v1 quiz specs require hashtags")
        if self.layout == "v2" and not any(reference in self.explanation for reference in self.scripture_references):
            raise ValueError(
                "layout v2 quiz specs must cite at least one scripture reference in the "
                "post-vote explanation (references are never shown before voting)"
            )
        if any(not option.strip() or len(option) > 100 for option in self.options):
            raise ValueError("quiz options must contain 1..100 visible characters")
        if len({option.casefold() for option in self.options}) != len(self.options):
            raise ValueError("quiz options must be unique")
        if self.correct_option_index >= len(self.options):
            raise ValueError("quiz correct_option_index is outside the options list")
        if any(not reference.strip() for reference in self.scripture_references):
            raise ValueError("quiz scripture references must be non-empty")
        return self


def spec_path(publication_id: str) -> Path:
    return QUIZ_DIR / f"{publication_id}.json"


def runtime_path(publication_id: str) -> Path:
    return QUIZ_DIR / f"{publication_id}-runtime.json"


def ledger_relative_path(publication_id: str) -> str:
    return f"{STATE_LEDGER_PREFIX}/{publication_id}-ledger.json"


def load_quiz_spec(path: Path) -> LordchristQuizSpec:
    try:
        return LordchristQuizSpec.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid lordchrist quiz spec {path}: {exc}") from exc


def load_quiz_release(path: Path) -> GenericReleaseQueue:
    try:
        return GenericReleaseQueue.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid lordchrist quiz release {path}: {exc}") from exc


def spec_source_sha256(spec: LordchristQuizSpec) -> str:
    # exclude_defaults keeps the digest of already-published v1 specs stable
    # when new optional spec fields (e.g. layout) are introduced.
    canonical = json.dumps(
        spec.model_dump(mode="json", exclude_defaults=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_poll_description(spec: LordchristQuizSpec) -> str | None:
    if spec.layout == "v2":
        # Clean format: nothing before voting — no intro, no hashtags, and no
        # scripture references that would hint at the answer in advance.
        return None
    description = (
        "🧠 Викторина по Библии\n\n"
        "Ответ и объяснение — сразу после голосования.\n\n"
        f"📖 {', '.join(spec.scripture_references)}\n\n"
        f"{spec.hashtags}"
    )
    if len(description) > 1024:
        raise ValueError("quiz poll description exceeds the Telegram limit")
    return description


def build_quiz_candidate(
    profile: TelegramChannelProfile,
    spec: LordchristQuizSpec,
    binding: TelegramTargetBinding,
) -> GenericReleaseQueue:
    if binding.project_key != profile.project_key or binding.profile_sha256 != profile.digest:
        raise ValueError("quiz target binding differs from the selected channel profile")
    if binding.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("quiz target binding channel differs from the selected channel profile")
    payload = render_poll_payload(
        profile,
        publication_id=spec.publication_id,
        question=spec.question,
        options=spec.options,
        poll_type="quiz",
        correct_option_ids=(spec.correct_option_index,),
        explanation=spec.explanation,
        description=build_poll_description(spec),
    )
    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=f"{spec.publication_id}-v1",
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        target_binding_sha256=binding.digest,
        chat_id=binding.chat_id,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
        release_authorized=False,
        items=(
            GenericReleaseItem(
                sequence=1,
                publication_id=spec.publication_id,
                scheduled_at=spec.scheduled_at,
                source_sha256=spec_source_sha256(spec),
                payload=payload,
            ),
        ),
    )


def build_quiz_runtime(
    profile: TelegramChannelProfile,
    spec: LordchristQuizSpec,
    binding: TelegramTargetBinding,
    *,
    reviewed_by: str,
    reviewed_at: datetime,
) -> GenericReleaseQueue:
    candidate = build_quiz_candidate(profile, spec, binding)
    return authorize_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
    )


def _load_bundle(publication_id: str) -> tuple[LordchristQuizSpec, GenericReleaseQueue]:
    spec = load_quiz_spec(spec_path(publication_id))
    if spec.publication_id != publication_id:
        raise ValueError("quiz spec publication_id differs from the requested publication")
    return spec, load_quiz_release(runtime_path(publication_id))


def _require_bundle_consistency(
    spec: LordchristQuizSpec,
    release: GenericReleaseQueue,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
) -> None:
    candidate = build_quiz_candidate(profile, spec, binding)
    if len(release.items) != 1:
        raise ValueError("quiz runtime release must contain exactly one item")
    item = release.items[0]
    expected = candidate.items[0]
    if item.publication_id != spec.publication_id or item.source_sha256 != expected.source_sha256:
        raise ValueError("quiz runtime item differs from the reviewed spec")
    if item.payload.model_dump(mode="json") != expected.payload.model_dump(mode="json"):
        raise ValueError("quiz runtime payload differs from the payload rebuilt from the spec")
    if release.profile_sha256 != profile.digest or release.target_binding_sha256 != binding.digest:
        raise ValueError("quiz runtime release is not bound to the exact profile and target binding")
    if (release.chat_id, release.bot_id, release.bot_username) != (
        binding.chat_id,
        binding.bot_id,
        binding.bot_username,
    ):
        raise ValueError("quiz runtime release target fields differ from the target binding")


def validate_quiz(
    publication_id: str,
    *,
    require_release_authorized: bool = False,
    require_execution_authorized: bool = False,
) -> dict[str, object]:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    spec, release = _load_bundle(publication_id)
    _require_bundle_consistency(spec, release, profile, binding)
    if require_release_authorized or require_execution_authorized:
        candidate = build_quiz_candidate(profile, spec, binding)
        if not release.release_authorized or release.reviewed_candidate_sha256 != candidate.candidate_digest():
            raise ValueError("quiz runtime release is not authorized for the exact reviewed candidate")
    if require_execution_authorized and not profile.provider_writes_authorized:
        raise ValueError("quiz channel profile is write-disabled")
    payload = release.items[0].payload
    return {
        "publication_id": publication_id,
        "payload_kind": getattr(payload, "poll_type", "poll"),
        "question": spec.question,
        "options": list(spec.options),
        "release_id": release.release_id,
        "release_authorized": release.release_authorized,
        "profile_sha256": release.profile_sha256,
    }


def _ledger_is_untouched(ledger: GenericPublicationLedger) -> bool:
    """True only when the ledger proves no provider effect ever happened."""
    return bool(ledger.entries) and all(
        entry.state == "pending"
        and entry.provider_effect == "impossible"
        and entry.intent_id is None
        and entry.message_id is None
        for entry in ledger.entries.values()
    )


def state_init(publication_id: str, state_checkout: Path) -> Path:
    _, release = _load_bundle(publication_id)
    ledger_path = state_checkout / ledger_relative_path(publication_id)
    if ledger_path.exists():
        try:
            load_ledger(ledger_path, release)
            return ledger_path
        except ValueError:
            # A reviewed release correction (e.g. moving the scheduled time
            # before any dispatch) invalidates the initialized ledger digest.
            # Re-initialization is safe only when the stale ledger proves
            # that nothing was ever dispatched or published.
            existing = GenericPublicationLedger.model_validate_json(ledger_path.read_text(encoding="utf-8"))
            if not _ledger_is_untouched(existing):
                raise ValueError(
                    "quiz publication ledger belongs to a different release and is not "
                    "provably untouched; refusing to re-initialize state"
                ) from None
    ledger: GenericPublicationLedger = initialize_ledger(release)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return ledger_path


def state_check(publication_id: str, state_checkout: Path, *, require_publishable: bool = False) -> None:
    _, release = _load_bundle(publication_id)
    ledger_path = state_checkout / ledger_relative_path(publication_id)
    if not ledger_path.exists():
        raise ValueError("quiz publication ledger is not initialized")
    ledger = load_ledger(ledger_path, release)
    if require_publishable:
        entry = ledger.entries.get(publication_id)
        if entry is not None and entry.state == "published":
            raise ValueError("quiz publication is already published; replay is forbidden")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reviewed one-off Bible-quiz lane for @lordchrist")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-runtime")
    build.add_argument("--publication-id", required=True)
    build.add_argument("--reviewed-by", required=True)
    build.add_argument("--reviewed-at", required=True)
    build.add_argument("--output", type=Path)

    validate = sub.add_parser("validate")
    validate.add_argument("--publication-id", required=True)
    validate.add_argument("--require-release-authorized", action="store_true")
    validate.add_argument("--require-execution-authorized", action="store_true")

    init = sub.add_parser("state-init")
    init.add_argument("--publication-id", required=True)
    init.add_argument("--state-checkout", type=Path, required=True)

    check = sub.add_parser("state-check")
    check.add_argument("--publication-id", required=True)
    check.add_argument("--state-checkout", type=Path, required=True)
    check.add_argument("--require-publishable", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "build-runtime":
        profile = load_channel_profile(PROFILE_PATH)
        binding = load_target_binding(BINDING_PATH, profile)
        spec = load_quiz_spec(spec_path(args.publication_id))
        reviewed_at = datetime.fromisoformat(args.reviewed_at)
        runtime = build_quiz_runtime(profile, spec, binding, reviewed_by=args.reviewed_by, reviewed_at=reviewed_at)
        output = args.output or runtime_path(args.publication_id)
        output.write_text(runtime.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"runtime": str(output), "candidate_sha256": runtime.reviewed_candidate_sha256}))
    elif args.command == "validate":
        result = validate_quiz(
            args.publication_id,
            require_release_authorized=args.require_release_authorized,
            require_execution_authorized=args.require_execution_authorized,
        )
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "state-init":
        print(state_init(args.publication_id, args.state_checkout))
    elif args.command == "state-check":
        state_check(args.publication_id, args.state_checkout, require_publishable=args.require_publishable)
        print("quiz state is initialized and publishable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
