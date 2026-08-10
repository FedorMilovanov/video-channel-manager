from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_custom_emoji_catalog import (
    build_capability_canary_html,
    load_custom_emoji_catalog,
)
from video_channel_manager.telegram_models import ProviderEffect
from video_channel_manager.telegram_multichannel_transport import (
    GenericMessagePayload,
    GenericTargetProof,
    TelegramApiError,
    render_message_payload,
    send_message_once,
)

EXPECTED_CHAT_ID = -1003527567039
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
EXPECTED_CHANNEL_USERNAME = "@deep_info_life"
PUBLICATION_ID = "svodka-custom-emoji-capability-canary"


class CustomEmojiCanaryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-custom-emoji-capability-canary"]
    schema_version: Literal[1]
    state: Literal["intent", "verified", "unknown", "not_dispatched"]
    provider_effect: Literal["impossible", "verified", "may_exist", "not_dispatched"]
    project_key: Literal["svodka"]
    channel_username: Literal["@deep_info_life"]
    chat_id: Literal[-1003527567039]
    bot_id: Literal[8716602202]
    bot_username: Literal["preaching_mp3_bot"]
    catalog_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_verified_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    publication_id: Literal["svodka-custom-emoji-capability-canary"]
    workflow_run_id: str = Field(pattern=r"^[0-9]+$")
    workflow_run_attempt: str = Field(pattern=r"^[0-9]+$")
    github_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    github_workflow_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    created_at_utc: datetime
    updated_at_utc: datetime
    message_id: int | None = Field(default=None, gt=0)
    message_url: str | None = None
    error: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_state_shape(self) -> "CustomEmojiCanaryRecord":
        if self.created_at_utc.tzinfo is None or self.updated_at_utc.tzinfo is None:
            raise ValueError("canary timestamps must be timezone-aware")
        if self.updated_at_utc < self.created_at_utc:
            raise ValueError("canary updated_at_utc cannot precede created_at_utc")
        if self.state == "intent":
            if self.provider_effect != "impossible" or self.message_id is not None or self.message_url is not None:
                raise ValueError("intent state must prove no provider effect yet")
            if self.error is not None:
                raise ValueError("intent state must not include an error")
        elif self.state == "verified":
            if self.provider_effect != "verified" or self.message_id is None or not self.message_url:
                raise ValueError("verified state requires exact Telegram receipt")
            if self.error is not None:
                raise ValueError("verified state must not include an error")
        else:
            if self.message_id is not None or self.message_url is not None:
                raise ValueError("unverified canary state must not claim a Telegram message id")
            if not self.error:
                raise ValueError("unverified canary state requires an error")
        return self


def _load_target_proof(path: Path) -> GenericTargetProof:
    try:
        return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid custom emoji canary target proof {path}: {exc}") from exc


def _load_record(path: Path) -> CustomEmojiCanaryRecord:
    try:
        return CustomEmojiCanaryRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid custom emoji canary record {path}: {exc}") from exc


def _write_record(path: Path, record: CustomEmojiCanaryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _write_payload(path: Path, payload: GenericMessagePayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _require_exact_target(proof: GenericTargetProof) -> None:
    if (
        proof.channel_username.casefold() != EXPECTED_CHANNEL_USERNAME.casefold()
        or proof.chat_id != EXPECTED_CHAT_ID
        or proof.bot_id != EXPECTED_BOT_ID
        or proof.bot_username.casefold() != EXPECTED_BOT_USERNAME.casefold()
    ):
        raise ValueError("custom emoji canary target proof differs from the exact Svodka target")


def build_canary_payload(profile_path: Path, catalog_path: Path) -> GenericMessagePayload:
    profile = load_channel_profile(profile_path)
    catalog = load_custom_emoji_catalog(catalog_path)
    if profile.project_key != "svodka" or profile.channel_username.casefold() != EXPECTED_CHANNEL_USERNAME.casefold():
        raise ValueError("custom emoji canary requires the exact Svodka channel profile")
    return render_message_payload(
        profile,
        publication_id=PUBLICATION_ID,
        html_text=build_capability_canary_html(catalog),
    )


def prepare_intent(
    *,
    profile_path: Path,
    catalog_path: Path,
    target_proof_path: Path,
    run_id: str,
    run_attempt: str,
    github_sha: str,
    github_workflow_sha: str,
    now: datetime | None = None,
) -> tuple[CustomEmojiCanaryRecord, GenericMessagePayload]:
    profile = load_channel_profile(profile_path)
    catalog = load_custom_emoji_catalog(catalog_path)
    target = _load_target_proof(target_proof_path)
    _require_exact_target(target)
    payload = build_canary_payload(profile_path, catalog_path)
    if payload.profile_sha256 != target.profile_sha256 or target.project_key != profile.project_key:
        raise ValueError("custom emoji canary payload and target proof are bound to different profiles")
    current = now or datetime.now(tz=UTC)
    record = CustomEmojiCanaryRecord(
        schema_name="video-channel-manager.svodka-custom-emoji-capability-canary",
        schema_version=1,
        state="intent",
        provider_effect="impossible",
        project_key="svodka",
        channel_username=EXPECTED_CHANNEL_USERNAME,
        chat_id=EXPECTED_CHAT_ID,
        bot_id=EXPECTED_BOT_ID,
        bot_username=EXPECTED_BOT_USERNAME,
        catalog_sha256=catalog.digest,
        catalog_verified_main_sha=catalog.verified_main_sha,
        profile_sha256=profile.digest,
        provider_payload_sha256=payload.provider_payload_sha256,
        publication_id=PUBLICATION_ID,
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
        created_at_utc=current,
        updated_at_utc=current,
    )
    return record, payload


def _record_from_error(
    intent: CustomEmojiCanaryRecord,
    *,
    provider_effect: ProviderEffect,
    error: str,
    now: datetime,
) -> CustomEmojiCanaryRecord:
    state: Literal["unknown", "not_dispatched"] = "not_dispatched" if provider_effect == "not_dispatched" else "unknown"
    effective_effect: Literal["may_exist", "not_dispatched"] = (
        "not_dispatched" if provider_effect == "not_dispatched" else "may_exist"
    )
    return intent.model_copy(
        update={
            "state": state,
            "provider_effect": effective_effect,
            "updated_at_utc": now,
            "error": error[:1000],
        }
    )


def send_canary_once(
    *,
    profile_path: Path,
    catalog_path: Path,
    target_proof_path: Path,
    intent_path: Path,
    token: str,
    now: datetime | None = None,
) -> CustomEmojiCanaryRecord:
    profile = load_channel_profile(profile_path)
    catalog = load_custom_emoji_catalog(catalog_path)
    target = _load_target_proof(target_proof_path)
    intent = _load_record(intent_path)
    _require_exact_target(target)
    if intent.state != "intent" or intent.provider_effect != "impossible":
        raise ValueError("custom emoji canary send requires a pristine durable intent")
    payload = build_canary_payload(profile_path, catalog_path)
    if (
        intent.catalog_sha256 != catalog.digest
        or intent.profile_sha256 != profile.digest
        or intent.provider_payload_sha256 != payload.provider_payload_sha256
    ):
        raise ValueError("custom emoji canary intent does not match current catalog/profile/payload")

    current = now or datetime.now(tz=UTC)
    try:
        receipt = send_message_once(
            profile,
            target,
            payload,
            token=token,
            now=current,
        )
    except TelegramApiError as exc:
        return _record_from_error(
            intent,
            provider_effect=exc.provider_effect,
            error=str(exc),
            now=current,
        )
    except Exception as exc:
        return _record_from_error(
            intent,
            provider_effect="may_exist",
            error=f"unexpected canary failure: {type(exc).__name__}: {exc}",
            now=current,
        )

    return intent.model_copy(
        update={
            "state": "verified",
            "provider_effect": "verified",
            "updated_at_utc": current,
            "message_id": receipt.message_id,
            "message_url": receipt.message_url,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Durable Svodka custom emoji capability canary")
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("--profile", type=Path, required=True)
    preview.add_argument("--catalog", type=Path, required=True)
    preview.add_argument("--payload-output", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--profile", type=Path, required=True)
    prepare.add_argument("--catalog", type=Path, required=True)
    prepare.add_argument("--target-proof", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--github-sha", required=True)
    prepare.add_argument("--github-workflow-sha", required=True)
    prepare.add_argument("--intent-output", type=Path, required=True)
    prepare.add_argument("--payload-output", type=Path, required=True)

    send = sub.add_parser("send")
    send.add_argument("--profile", type=Path, required=True)
    send.add_argument("--catalog", type=Path, required=True)
    send.add_argument("--target-proof", type=Path, required=True)
    send.add_argument("--intent", type=Path, required=True)
    send.add_argument("--outcome-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preview":
        payload = build_canary_payload(args.profile, args.catalog)
        _write_payload(args.payload_output, payload)
        print(
            json.dumps(
                {
                    "publication_id": payload.publication_id,
                    "provider_payload_sha256": payload.provider_payload_sha256,
                    "custom_emoji_ids": [
                        entity.custom_emoji_id for entity in payload.expected_entities if entity.type == "custom_emoji"
                    ],
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "prepare":
        record, payload = prepare_intent(
            profile_path=args.profile,
            catalog_path=args.catalog,
            target_proof_path=args.target_proof,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            github_sha=args.github_sha,
            github_workflow_sha=args.github_workflow_sha,
        )
        _write_record(args.intent_output, record)
        _write_payload(args.payload_output, payload)
        print(
            json.dumps(
                {
                    "state": record.state,
                    "catalog_sha256": record.catalog_sha256,
                    "provider_payload_sha256": record.provider_payload_sha256,
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    token = os.environ.get("SVODKA_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("SVODKA_TELEGRAM_BOT_TOKEN is required")
    outcome = send_canary_once(
        profile_path=args.profile,
        catalog_path=args.catalog,
        target_proof_path=args.target_proof,
        intent_path=args.intent,
        token=token,
    )
    _write_record(args.outcome_output, outcome)
    print(
        json.dumps(
            {
                "state": outcome.state,
                "provider_effect": outcome.provider_effect,
                "message_id": outcome.message_id,
                "message_url": outcome.message_url,
            },
            ensure_ascii=False,
        )
    )
    return 0 if outcome.state == "verified" else 4


if __name__ == "__main__":
    raise SystemExit(main())
