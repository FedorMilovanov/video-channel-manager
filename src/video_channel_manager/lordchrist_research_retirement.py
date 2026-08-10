from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_multichannel_state import GenericPublicationLedger


class LordchristResearchRetirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.lordchrist-research-retirement"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-research-live-2026-08"]
    release_digest: Literal["sha256:b836f9dc6733cdc922e5aaed97c250d1d46484fe75a216c1f12e586214a2626f"]
    publication_id: Literal["lordchrist-research-three-preachers-numbers"]
    provider_payload_sha256: Literal["sha256:4df54902ef389abb9e577c74ff7ab0c60a989cf4795e731b83e0fdb103d59ba9"]
    intent_id: Literal["9a5e4fc686f8e28c6a3c0d2aedd08402"]
    workflow_run_id: Literal["31390497205"]
    workflow_run_attempt: Literal["1"]
    github_sha: Literal["eb9ccd52b28b957fbf2e1a6b8989880d6e85c43a"]
    github_workflow_sha: Literal["eb9ccd52b28b957fbf2e1a6b8989880d6e85c43a"]
    attempted_at_utc: datetime
    actual_chat_id: Literal[-1001295216957]
    actual_chat_username: Literal["lordchrist"]
    bot_id: Literal[8716602202]
    bot_username: Literal["preaching_mp3_bot"]
    provider_effect: Literal["may_exist"]
    disposition: Literal["retired_no_replay"]
    provider_retry_forbidden: Literal[True]
    successor_activation_authorized: Literal[False]
    evidence_note: str = Field(min_length=20, max_length=2000)
    retired_by: str = Field(min_length=3, max_length=200)
    retired_at_utc: datetime
    owning_issue: Literal[286]

    @model_validator(mode="after")
    def timestamps_are_aware_and_ordered(self) -> "LordchristResearchRetirement":
        if self.attempted_at_utc.tzinfo is None or self.retired_at_utc.tzinfo is None:
            raise ValueError("retirement timestamps must be timezone-aware")
        if self.retired_at_utc < self.attempted_at_utc:
            raise ValueError("retirement cannot predate the historical provider attempt")
        return self


def load_lordchrist_research_retirement(
    path: Path,
    *,
    ledger: GenericPublicationLedger,
) -> LordchristResearchRetirement:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        retirement = LordchristResearchRetirement.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist research retirement evidence {path}: {exc}") from exc

    if (
        retirement.project_key != ledger.project_key
        or retirement.channel_username.casefold() != ledger.channel_username.casefold()
        or retirement.release_id != ledger.release_id
        or retirement.release_digest != ledger.release_digest
    ):
        raise ValueError("research retirement identity differs from durable research ledger")

    entry = ledger.entries.get(retirement.publication_id)
    if entry is None:
        raise ValueError("retired publication is absent from durable research ledger")
    if entry.state != "unknown" or entry.provider_effect != "may_exist":
        raise ValueError("only an unresolved unknown/may_exist research entry can be retired")
    expected = (
        retirement.provider_payload_sha256,
        retirement.intent_id,
        retirement.workflow_run_id,
        retirement.workflow_run_attempt,
        retirement.github_sha,
        retirement.github_workflow_sha,
        retirement.attempted_at_utc,
        retirement.actual_chat_id,
        retirement.actual_chat_username,
        retirement.bot_id,
        retirement.bot_username,
    )
    actual = (
        entry.provider_payload_sha256,
        entry.intent_id,
        entry.workflow_run_id,
        entry.workflow_run_attempt,
        entry.github_sha,
        entry.github_workflow_sha,
        entry.attempted_at_utc,
        entry.actual_chat_id,
        entry.actual_chat_username,
        entry.bot_id,
        entry.bot_username,
    )
    if actual != expected:
        raise ValueError("research retirement evidence differs from exact historical dispatch provenance")
    if entry.message_id is not None or entry.message_url is not None or entry.published_at_utc is not None:
        raise ValueError("retirement cannot override an entry that already claims verified message identity")
    return retirement


__all__ = ["LordchristResearchRetirement", "load_lordchrist_research_retirement"]
