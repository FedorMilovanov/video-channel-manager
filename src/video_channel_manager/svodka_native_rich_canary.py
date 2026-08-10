from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpOperationClass,
    RetryPolicy,
    execute_http_request,
)
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_rich_models import RichArticleDocument
from video_channel_manager.telegram_rich_provider import (
    ArchivedTelegramRichOutcome,
    HttpxTelegramRichMutationProvider,
    RichProviderEffect,
    TelegramRichMessageDocument,
    TelegramRichMutationProvider,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichOutcomeArchiver,
    TelegramRichProviderOutcome,
    TelegramRichRequestTimeout,
    TelegramRichTargetBinding,
    publish_rich_once,
)
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

CONFIRMATION = "RICH-CANARY:@deep_info_life:ONE-ARTICLE"
EXPECTED_REPOSITORY = "FedorMilovanov/video-channel-manager"
EXPECTED_GITHUB_REF = "refs/heads/main"
EXPECTED_PROJECT_KEY = "svodka"
EXPECTED_CHANNEL_USERNAME = "@deep_info_life"
EXPECTED_CHAT_ID = -1003527567039
EXPECTED_CHAT_USERNAME = "deep_info_life"
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
PUBLICATION_ID = "svodka-native-rich-message-canary"
TARGET_PROOF_MAX_AGE = timedelta(minutes=15)
QUALITY_WORKFLOWS = ("svodka-quality.yml", "svodka-approved-release-quality.yml")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RUN_NUMBER_RE = re.compile(r"^[1-9][0-9]*$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


class NativeRichRegistryAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(min_length=10, max_length=120)
    entry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    direct_media_url: str = Field(pattern=r"^https://")
    expected_mime: Literal["image/png", "image/jpeg"]
    caption: str = Field(min_length=10, max_length=500)
    credit: str = Field(min_length=5, max_length=300)


class NativeRichMediaRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_pr: Literal[293]
    article_id: Literal["svodka-rich-2026-august-total-solar-eclipse"]
    assets: tuple[NativeRichRegistryAsset, NativeRichRegistryAsset]

    @model_validator(mode="after")
    def exact_two_distinct_assets(self) -> "NativeRichMediaRegistry":
        if len({asset.asset_id for asset in self.assets}) != 2:
            raise ValueError("native rich canary requires two distinct reviewed registry assets")
        return self


class NativeRichRemoteMediaEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(min_length=10, max_length=120)
    direct_media_url: str = Field(pattern=r"^https://")
    content_type: Literal["image/jpeg", "image/png"]
    content_length: int = Field(gt=0, le=10_000_000)
    content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class NativeRichRemoteMediaProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-native-rich-media-proof"]
    schema_version: Literal[1]
    media_registry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    items: tuple[NativeRichRemoteMediaEvidence, NativeRichRemoteMediaEvidence]
    checked_at_utc: datetime
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def exact_distinct_evidence(self) -> "NativeRichRemoteMediaProof":
        if self.checked_at_utc.tzinfo is None:
            raise ValueError("native rich media proof timestamp must be timezone-aware")
        if len({item.asset_id for item in self.items}) != 2:
            raise ValueError("native rich media proof requires two distinct assets")
        return self

    @property
    def digest(self) -> str:
        return _sha256_json(self.model_dump(mode="json"))

    @property
    def content_identity(self) -> tuple[tuple[str, str, str, int, str], ...]:
        return tuple(
            (item.asset_id, item.direct_media_url, item.content_type, item.content_length, item.content_sha256)
            for item in self.items
        )


class NativeRichFutureEditSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_method: Literal["editMessageText"]
    provider_writes_authorized: Literal[False]
    wired_to_workflow: Literal[False]
    requires_verified_canary_message_id: Literal[True]
    replacement_details_summary: str = Field(min_length=5, max_length=100)


class NativeRichCanarySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-native-rich-canary-spec"]
    schema_version: Literal[1]
    project_key: Literal["svodka"]
    channel_username: Literal["@deep_info_life"]
    publication_id: Literal["svodka-native-rich-message-canary"]
    provider_writes_authorized_by_artifact: Literal[False]
    counts_as_pilot_post: Literal[False]
    publication_ledger_consumed: Literal[False]
    legacy_scheduler_unlocked: Literal[False]
    media_registry: NativeRichMediaRegistry
    provider_assigned_media_paths: tuple[str, ...]
    input_rich_message: dict[str, Any]
    expected_returned_rich_message: dict[str, Any]
    future_edit_test: NativeRichFutureEditSpec

    @model_validator(mode="after")
    def validate_editorial_shape(self) -> "NativeRichCanarySpec":
        input_blocks = self.input_rich_message.get("blocks")
        expected_blocks = self.expected_returned_rich_message.get("blocks")
        if not isinstance(input_blocks, list) or not isinstance(expected_blocks, list):
            raise ValueError("native rich canary must use explicit block-form input and expected output")
        block_types = [block.get("type") for block in input_blocks if isinstance(block, dict)]
        required = {
            "heading",
            "paragraph",
            "list",
            "divider",
            "blockquote",
            "table",
            "mathematical_expression",
            "details",
            "photo",
        }
        if not required.issubset(block_types):
            raise ValueError("native rich canary is missing a reviewed useful rich-message feature")
        if block_types.count("photo") != 2 or self.provider_assigned_media_paths != (
            "$/blocks/2",
            "$/blocks/6",
        ):
            raise ValueError("native rich canary must contain both reviewed inline registry photos")
        if self.input_rich_message.get("skip_entity_detection") is not True:
            raise ValueError("native rich canary must disable unreviewed automatic entity detection")
        return self

    @property
    def digest(self) -> str:
        return _sha256_json(self.model_dump(mode="json"))


class NativeRichCanaryIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-native-rich-canary-state"]
    schema_version: Literal[1]
    state: Literal["intent"]
    provider_effect: Literal["impossible"]
    project_key: Literal["svodka"]
    channel_username: Literal["@deep_info_life"]
    chat_id: Literal[-1003527567039]
    bot_id: Literal[8716602202]
    bot_username: Literal["preaching_mp3_bot"]
    publication_id: Literal["svodka-native-rich-message-canary"]
    confirmation: Literal["RICH-CANARY:@deep_info_life:ONE-ARTICLE"]
    github_repository: Literal["FedorMilovanov/video-channel-manager"]
    github_ref: Literal["refs/heads/main"]
    github_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    github_workflow_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    workflow_run_id: str = Field(pattern=r"^[1-9][0-9]*$")
    workflow_run_attempt: str = Field(pattern=r"^[1-9][0-9]*$")
    exact_quality_workflows: tuple[Literal["svodka-quality.yml", "svodka-approved-release-quality.yml"], ...]
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_proof_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    spec_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_registry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_asset_entry_sha256: tuple[str, str]
    media_proof_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_proof: NativeRichRemoteMediaProof
    rich_article_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rich_render_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    document_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_rich_structure_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_proof: GenericTargetProof
    document: TelegramRichMessageDocument
    mutation_request_limit: Literal[1]
    automatic_retry_allowed: Literal[False]
    blind_retry_allowed: Literal[False]
    may_exist_requires_stop: Literal[True]
    publication_ledger_consumed: Literal[False]
    counts_as_pilot_post: Literal[False]
    pilot_release_modified: Literal[False]
    legacy_scheduler_unlocked: Literal[False]
    automatic_delete_allowed: Literal[False]
    automatic_edit_allowed: Literal[False]
    created_at_utc: datetime

    @model_validator(mode="after")
    def validate_exact_intent(self) -> "NativeRichCanaryIntent":
        if self.created_at_utc.tzinfo is None:
            raise ValueError("native rich canary intent timestamp must be timezone-aware")
        if self.github_workflow_sha != self.github_sha:
            raise ValueError("native rich canary workflow source must be the exact current main SHA")
        if self.exact_quality_workflows != QUALITY_WORKFLOWS:
            raise ValueError("native rich canary must require both exact current-main quality workflows")
        if self.profile_sha256 != self.document.target.profile_sha256:
            raise ValueError("native rich canary profile digest differs from the exact rich document")
        if self.target_binding_sha256 != self.document.target.target_binding_sha256:
            raise ValueError("native rich canary binding digest differs from the exact rich document")
        if self.document_sha256 != self.document.document_sha256:
            raise ValueError("native rich canary document digest is invalid")
        if self.expected_rich_structure_sha256 != self.document.expected_rich_structure_sha256:
            raise ValueError("native rich canary expected structure digest is invalid")
        if self.expected_media_sha256 != self.document.expected_media_sha256:
            raise ValueError("native rich canary expected media digest is invalid")
        if self.target_proof_sha256 != _sha256_json(self.target_proof.model_dump(mode="json")):
            raise ValueError("native rich canary target proof digest is invalid")
        if any(_SHA256_RE.fullmatch(value) is None for value in self.media_asset_entry_sha256):
            raise ValueError("native rich canary media registry entry digest is invalid")
        if (
            self.media_proof_sha256 != self.media_proof.digest
            or self.media_proof.media_registry_sha256 != self.media_registry_sha256
        ):
            raise ValueError("native rich canary remote media proof digest is invalid")
        return self


class NativeRichProviderArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_name: str = Field(min_length=10, max_length=200)
    artifact_id: str = Field(pattern=r"^[1-9][0-9]*$")
    artifact_url: str = Field(pattern=r"^https://github\.com/.+/actions/runs/[0-9]+/artifacts/[0-9]+$")
    artifact_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_outcome_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    uploaded_before_durable_outcome: Literal[True]


CanaryTerminalState = Literal["verified", "may_exist", "confirmed_absent", "not_dispatched", "impossible"]


class NativeRichCanaryOutcomeState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-native-rich-canary-state"]
    schema_version: Literal[1]
    state: CanaryTerminalState
    provider_effect: RichProviderEffect
    intent: NativeRichCanaryIntent
    provider_outcome: TelegramRichProviderOutcome
    provider_outcome_artifact: NativeRichProviderArtifact
    automatic_retry_allowed: Literal[False]
    blind_retry_allowed: Literal[False]
    second_run_allowed: Literal[False]
    may_exist_requires_stop: Literal[True]
    publication_ledger_consumed: Literal[False]
    counts_as_pilot_post: Literal[False]
    pilot_release_modified: Literal[False]
    legacy_scheduler_unlocked: Literal[False]
    automatic_delete_allowed: Literal[False]
    automatic_edit_allowed: Literal[False]
    updated_at_utc: datetime

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "NativeRichCanaryOutcomeState":
        if self.updated_at_utc.tzinfo is None or self.updated_at_utc < self.intent.created_at_utc:
            raise ValueError("native rich canary outcome timestamp is invalid")
        if self.state != self.provider_effect:
            raise ValueError("native rich canary terminal state must equal the provider effect")
        outcome = self.provider_outcome
        if outcome.provider_effect != self.provider_effect:
            raise ValueError("native rich canary state differs from its exact provider outcome")
        if outcome.document_sha256 != self.intent.document_sha256:
            raise ValueError("native rich canary outcome differs from the durable intent document")
        if outcome.target_proof_sha256 != self.intent.target_proof_sha256:
            raise ValueError("native rich canary outcome differs from the durable intent target proof")
        if self.provider_outcome_artifact.provider_outcome_sha256 != outcome.outcome_sha256:
            raise ValueError("native rich canary artifact differs from the provider outcome")
        if self.state == "verified" and (
            outcome.expected_chat_id != EXPECTED_CHAT_ID
            or outcome.message_id is None
            or outcome.structure_verification != "exact"
            or outcome.media_verification != "exact"
            or outcome.returned_rich_message is None
        ):
            raise ValueError("verified native rich canary lacks exact target, RichMessage, or media evidence")
        return self


NativeRichCanaryState = NativeRichCanaryIntent | NativeRichCanaryOutcomeState
_STATE_ADAPTER: TypeAdapter[NativeRichCanaryState] = TypeAdapter(NativeRichCanaryState)


class NativeRichFutureEditTestPlan(BaseModel):
    """Provider-disabled review fixture; deliberately has no executable adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-native-rich-future-edit-test"]
    schema_version: Literal[1]
    provider_method: Literal["editMessageText"]
    provider_writes_authorized: Literal[False]
    wired_to_workflow: Literal[False]
    provider_request_count: Literal[0]
    requires_verified_canary_message_id: Literal[True]
    chat_id: Literal[-1003527567039]
    message_id_source: Literal["verified native rich canary durable outcome"]
    base_document_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_parameter_name: Literal["rich_message"]
    replacement_rich_message: dict[str, Any]
    text_parameter_used: Literal[False]
    automatic_retry_allowed: Literal[False]
    automatic_dispatch_allowed: Literal[False]


class ExactFileOutcomeArchiver(TelegramRichOutcomeArchiver):
    """Write exact outcome bytes once; the workflow uploads them before state commit."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> TelegramRichOutcomeArchiveReceipt:
        if self.path.exists():
            raise ValueError("native rich provider outcome path already exists")
        if _sha256_bytes(outcome_bytes) != outcome_sha256:
            raise ValueError("native rich provider outcome bytes differ from the claimed digest")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("xb") as handle:
            handle.write(outcome_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)
        if _sha256_bytes(self.path.read_bytes()) != outcome_sha256:
            raise ValueError("native rich provider outcome changed while archiving")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=f"workflow-artifact-pending:{self.path.name}",
            durable_before_state_mutation=True,
        )


def load_canary_spec(path: Path) -> NativeRichCanarySpec:
    try:
        return NativeRichCanarySpec.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid native rich canary spec {path}: {exc}") from exc


def load_target_proof(path: Path) -> GenericTargetProof:
    try:
        return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid native rich canary target proof {path}: {exc}") from exc


def load_media_proof(path: Path) -> NativeRichRemoteMediaProof:
    try:
        return NativeRichRemoteMediaProof.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid native rich canary remote media proof {path}: {exc}") from exc


def load_canary_state(path: Path) -> NativeRichCanaryState:
    try:
        return _STATE_ADAPTER.validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid native rich canary state {path}: {exc}") from exc


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def require_exact_invocation(*, confirmation: str, github_repository: str, github_ref: str) -> None:
    if confirmation != CONFIRMATION:
        raise ValueError(f"confirmation must be exactly {CONFIRMATION}")
    if github_repository != EXPECTED_REPOSITORY:
        raise ValueError("native rich canary is bound to the exact reviewed GitHub repository")
    if github_ref != EXPECTED_GITHUB_REF:
        raise ValueError("native rich canary can run only from refs/heads/main")


def require_no_prior_state(state_path: Path) -> None:
    if state_path.exists():
        state = load_canary_state(state_path)
        effect = state.provider_effect
        raise ValueError(
            f"native rich canary already has durable state ({state.state}/{effect}); second run and blind retry are forbidden"
        )


def _require_hex_identity(value: str, *, name: str, pattern: re.Pattern[str]) -> None:
    if pattern.fullmatch(value) is None:
        raise ValueError(f"native rich canary {name} is invalid")


def _require_exact_target(
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    proof: GenericTargetProof,
    *,
    now: datetime,
) -> None:
    if now.tzinfo is None:
        raise ValueError("native rich canary current timestamp must be timezone-aware")
    expected = (
        EXPECTED_PROJECT_KEY,
        EXPECTED_CHANNEL_USERNAME.casefold(),
        profile.digest,
        EXPECTED_CHAT_ID,
        EXPECTED_CHAT_USERNAME.casefold(),
        EXPECTED_BOT_ID,
        EXPECTED_BOT_USERNAME.casefold(),
    )
    binding_actual = (
        binding.project_key,
        binding.channel_username.casefold(),
        binding.profile_sha256,
        binding.chat_id,
        binding.chat_username.casefold(),
        binding.bot_id,
        binding.bot_username.casefold(),
    )
    proof_actual = (
        proof.project_key,
        proof.channel_username.casefold(),
        proof.profile_sha256,
        proof.chat_id,
        proof.chat_username.casefold(),
        proof.bot_id,
        proof.bot_username.casefold(),
    )
    if profile.project_key != EXPECTED_PROJECT_KEY or profile.channel_username.casefold() != (
        EXPECTED_CHANNEL_USERNAME.casefold()
    ):
        raise ValueError("native rich canary profile differs from project svodka / @deep_info_life")
    if binding_actual != expected or proof_actual != expected:
        raise ValueError("native rich canary binding or preflight differs from the exact reviewed target")
    if proof.chat_type != "channel" or proof.can_post_messages is not True:
        raise ValueError("native rich canary preflight does not prove channel posting permission")
    age = now - proof.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > TARGET_PROOF_MAX_AGE:
        raise ValueError("native rich canary target proof is stale or has an invalid future timestamp")


def _load_and_verify_media_registry(
    spec: NativeRichCanarySpec, *, repository_root: Path
) -> dict[str, NativeRichRegistryAsset]:
    registry_path = repository_root / spec.media_registry.path
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"native rich canary media registry is unavailable: {registry_path}") from exc
    if not isinstance(registry, dict) or _sha256_json(registry) != spec.media_registry.sha256:
        raise ValueError("native rich canary media registry differs from its reviewed SHA-256")
    write_authorization = registry.get("telegram_write_authorization")
    canary = registry.get("canary")
    assets = registry.get("assets")
    expected_asset_ids = [asset.asset_id for asset in spec.media_registry.assets]
    if (
        registry.get("schema_name") != "video-channel-manager.svodka-rich-v1-media-registry"
        or registry.get("project_key") != EXPECTED_PROJECT_KEY
        or not isinstance(write_authorization, dict)
        or write_authorization.get("provider_writes_authorized") is not False
        or not isinstance(canary, dict)
        or canary.get("article_id") != spec.media_registry.article_id
        or canary.get("assets") != expected_asset_ids
        or not isinstance(assets, list)
    ):
        raise ValueError("native rich canary media registry safety or exact canary binding is invalid")
    registry_assets = {
        entry.get("asset_id"): entry
        for entry in assets
        if isinstance(entry, dict) and isinstance(entry.get("asset_id"), str)
    }
    verified: dict[str, NativeRichRegistryAsset] = {}
    for expected in spec.media_registry.assets:
        entry = registry_assets.get(expected.asset_id)
        if not isinstance(entry, dict) or _sha256_json(entry) != expected.entry_sha256:
            raise ValueError("native rich canary media registry entry differs from its reviewed SHA-256")
        if (
            entry.get("article_id") != spec.media_registry.article_id
            or entry.get("direct_media_url") != expected.direct_media_url
            or entry.get("expected_mime") != expected.expected_mime
            or entry.get("caption") != f"{expected.caption} {expected.credit}."
            or entry.get("provider_upload_status") != "not_uploaded"
            or entry.get("remote_ready") is not True
            or entry.get("acquisition_status") != "ready"
            or entry.get("canary_member") is not True
        ):
            raise ValueError("native rich canary media registry entry is not exact and remote-ready")
        verified[expected.asset_id] = expected
    return verified


class SvodkaRichMediaProofReader(HttpClientOwner):
    """Own one bounded read-only client for the exact two-asset proof."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._initialize_http_client(
            http_client,
            timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15),
            follow_redirects=False,
            trust_env=False,
        )

    def fetch(self, url: str) -> tuple[int, str, bytes]:
        result = execute_http_request(
            lambda: self._http_client.get(
                url,
                headers={"User-Agent": "video-channel-manager-rich-canary/1"},
            ),
            provider="https-media",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="svodka-native-rich-canary-asset",
            retry_policy=RetryPolicy(max_attempts=2),
        )
        response = result.response
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        return response.status_code, content_type, response.content


def prove_remote_media(
    *,
    spec: NativeRichCanarySpec,
    repository_root: Path,
    expected_proof: NativeRichRemoteMediaProof | None = None,
    fetcher: Callable[[str], tuple[int, str, bytes]] | None = None,
    now: datetime | None = None,
) -> NativeRichRemoteMediaProof:
    registry_assets = _load_and_verify_media_registry(spec, repository_root=repository_root)
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        raise ValueError("native rich media proof timestamp must be timezone-aware")

    reader: SvodkaRichMediaProofReader | None = None
    effective_fetcher: Callable[[str], tuple[int, str, bytes]]
    if fetcher is None:
        reader = SvodkaRichMediaProofReader()
        effective_fetcher = reader.fetch
    else:
        effective_fetcher = fetcher
    evidence: list[NativeRichRemoteMediaEvidence] = []
    try:
        fetched = [
            (registry_assets[expected.asset_id], effective_fetcher(expected.direct_media_url))
            for expected in spec.media_registry.assets
        ]
    finally:
        if reader is not None:
            reader.close()
    for asset, fetch_result in fetched:
        status_code, content_type, content = fetch_result
        if status_code != 200:
            raise ValueError(f"native rich media preflight returned HTTP {status_code} for {asset.asset_id}")
        if content_type != asset.expected_mime:
            raise ValueError("native rich media preflight returned an unexpected exact MIME type")
        if not content or len(content) > 10_000_000:
            raise ValueError("native rich media preflight returned an empty or oversized asset")
        valid_signature = (
            content.startswith(b"\xff\xd8\xff")
            if content_type == "image/jpeg"
            else content.startswith(b"\x89PNG\r\n\x1a\n")
        )
        if not valid_signature:
            raise ValueError("native rich media preflight bytes do not match the exact image MIME signature")
        evidence.append(
            NativeRichRemoteMediaEvidence(
                asset_id=asset.asset_id,
                direct_media_url=asset.direct_media_url,
                content_type=content_type,
                content_length=len(content),
                content_sha256=_sha256_bytes(content),
            )
        )
    proof = NativeRichRemoteMediaProof(
        schema_name="video-channel-manager.svodka-native-rich-media-proof",
        schema_version=1,
        media_registry_sha256=spec.media_registry.sha256,
        items=(evidence[0], evidence[1]),
        checked_at_utc=current,
        provider_write_performed=False,
    )
    if expected_proof is not None and proof.content_identity != expected_proof.content_identity:
        raise ValueError("native rich media bytes changed after durable intent; mutation is forbidden")
    return proof


def _require_fresh_media_proof(
    proof: NativeRichRemoteMediaProof,
    spec: NativeRichCanarySpec,
    *,
    now: datetime,
) -> None:
    expected_identity = tuple(
        (asset.asset_id, asset.direct_media_url, asset.expected_mime) for asset in spec.media_registry.assets
    )
    actual_identity = tuple((item.asset_id, item.direct_media_url, item.content_type) for item in proof.items)
    if proof.media_registry_sha256 != spec.media_registry.sha256 or actual_identity != expected_identity:
        raise ValueError("native rich media proof differs from the exact reviewed registry assets")
    age = now - proof.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > TARGET_PROOF_MAX_AGE:
        raise ValueError("native rich media proof is stale or has an invalid future timestamp")


def _domain_block(
    raw: dict[str, Any],
    *,
    block_id: str,
    media_id_by_url: dict[str, str],
) -> dict[str, Any]:
    block = copy.deepcopy(raw)
    block_type = block.get("type")
    if block_type == "photo":
        photo = block.get("photo")
        media_url = photo.get("media") if isinstance(photo, dict) else None
        media_id = media_id_by_url.get(str(media_url))
        if media_id is None:
            raise ValueError("native rich canary photo is absent from the exact domain media library")
        return {
            "type": "media",
            "block_id": block_id,
            "media_id": media_id,
            **({"caption": block["caption"]} if "caption" in block else {}),
        }
    block["block_id"] = block_id
    if block_type == "list":
        items = block.get("items")
        if not isinstance(items, list):
            raise ValueError("native rich canary domain list has no items")
        for item_index, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get("blocks"), list):
                raise ValueError("native rich canary domain list item is malformed")
            item["blocks"] = [
                _domain_block(
                    child,
                    block_id=f"{block_id}-i-{item_index}-b-{child_index}",
                    media_id_by_url=media_id_by_url,
                )
                for child_index, child in enumerate(item["blocks"])
                if isinstance(child, dict)
            ]
    elif block_type in {"blockquote", "collage", "slideshow", "details"}:
        children = block.get("blocks")
        if not isinstance(children, list):
            raise ValueError(f"native rich canary domain {block_type} has no blocks")
        block["blocks"] = [
            _domain_block(
                child,
                block_id=f"{block_id}-b-{child_index}",
                media_id_by_url=media_id_by_url,
            )
            for child_index, child in enumerate(children)
            if isinstance(child, dict)
        ]
    return block


def _build_domain_article(
    spec: NativeRichCanarySpec,
    *,
    input_rich_message: dict[str, Any],
) -> RichArticleDocument:
    blocks = input_rich_message.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("native rich canary domain source has no blocks")
    media_id_by_url = {asset.direct_media_url: asset.asset_id for asset in spec.media_registry.assets}
    domain_blocks = [
        _domain_block(raw, block_id=f"canary-b-{index}", media_id_by_url=media_id_by_url)
        for index, raw in enumerate(blocks)
        if isinstance(raw, dict)
    ]
    media = [
        {
            "media_id": asset.asset_id,
            "kind": "photo",
            "uri": asset.direct_media_url,
            "alt_text": asset.caption,
            "resolved": None,
        }
        for asset in spec.media_registry.assets
    ]
    return RichArticleDocument.model_validate(
        {
            "schema_name": "video-channel-manager.rich-article-document",
            "schema_version": 1,
            "document_id": PUBLICATION_ID,
            "project_key": EXPECTED_PROJECT_KEY,
            "metadata": {
                "title": "Затмение 12 августа: карта и наука",
                "language": "ru",
                "summary": "Короткий материал СВОДКИ для проверки нативной Rich Message структуры.",
                "author": "Редакция СВОДКИ",
                "created_at": date(2026, 8, 10).isoformat(),
            },
            "blocks": domain_blocks,
            "media": media,
            "revision": "native-canary-v1",
        }
    )


def _render_document(
    *,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    spec: NativeRichCanarySpec,
    github_repository: str,
    github_sha: str,
    repository_root: Path,
) -> tuple[TelegramRichMessageDocument, RichRenderResult, RichArticleDocument]:
    _require_hex_identity(github_sha, name="github_sha", pattern=_GIT_SHA_RE)
    if github_repository != EXPECTED_REPOSITORY:
        raise ValueError("native rich canary document requires the exact reviewed repository")
    registry_assets = _load_and_verify_media_registry(spec, repository_root=repository_root)
    input_rich_message = copy.deepcopy(spec.input_rich_message)
    blocks = input_rich_message.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("native rich canary photo blocks are missing")
    expected_positions = ((2, spec.media_registry.assets[0]), (6, spec.media_registry.assets[1]))
    for index, asset in expected_positions:
        block = blocks[index] if len(blocks) > index else None
        photo = block.get("photo") if isinstance(block, dict) else None
        placeholder = f"{{{{MEDIA_URL:{asset.asset_id}}}}}"
        if not isinstance(photo, dict) or photo.get("media") != placeholder:
            raise ValueError("native rich canary media URL placeholder moved or changed")
        photo["media"] = registry_assets[asset.asset_id].direct_media_url

    rich_target = TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=EXPECTED_PROJECT_KEY,
        channel_username=EXPECTED_CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=EXPECTED_CHAT_ID,
        chat_username=EXPECTED_CHAT_USERNAME,
        bot_id=EXPECTED_BOT_ID,
        bot_username=EXPECTED_BOT_USERNAME,
    )
    article = _build_domain_article(spec, input_rich_message=input_rich_message)
    telegram_document, render_result = render_rich_document(
        article,
        rich_target,
        publication_id=PUBLICATION_ID,
        provider_assigned_media_ids=tuple(asset.asset_id for asset in spec.media_registry.assets),
        skip_entity_detection=True,
    )
    if (
        telegram_document.input_rich_message != input_rich_message
        or telegram_document.expected_returned_rich_message != spec.expected_returned_rich_message
        or telegram_document.provider_assigned_media_paths != spec.provider_assigned_media_paths
        or render_result.media_placeholders
        or render_result.provider_assigned_media != tuple(asset.asset_id for asset in spec.media_registry.assets)
    ):
        raise ValueError("Agent A rich bridge render differs from the exact reviewed native canary document")
    return telegram_document, render_result, article


def build_document(
    *,
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    spec: NativeRichCanarySpec,
    github_repository: str,
    github_sha: str,
    repository_root: Path,
) -> TelegramRichMessageDocument:
    document, _, _ = _render_document(
        profile=profile,
        binding=binding,
        spec=spec,
        github_repository=github_repository,
        github_sha=github_sha,
        repository_root=repository_root,
    )
    return document


def prepare_intent(
    *,
    profile_path: Path,
    binding_path: Path,
    spec_path: Path,
    target_proof_path: Path,
    media_proof_path: Path,
    state_path: Path,
    repository_root: Path,
    confirmation: str,
    github_repository: str,
    github_ref: str,
    github_sha: str,
    github_workflow_sha: str,
    run_id: str,
    run_attempt: str,
    now: datetime | None = None,
) -> NativeRichCanaryIntent:
    require_exact_invocation(
        confirmation=confirmation,
        github_repository=github_repository,
        github_ref=github_ref,
    )
    require_no_prior_state(state_path)
    _require_hex_identity(github_sha, name="github_sha", pattern=_GIT_SHA_RE)
    _require_hex_identity(github_workflow_sha, name="github_workflow_sha", pattern=_GIT_SHA_RE)
    _require_hex_identity(run_id, name="run_id", pattern=_RUN_NUMBER_RE)
    _require_hex_identity(run_attempt, name="run_attempt", pattern=_RUN_NUMBER_RE)
    if github_workflow_sha != github_sha:
        raise ValueError("native rich canary workflow source is not exact current main")

    profile = load_channel_profile(profile_path)
    binding = load_target_binding(binding_path, profile)
    spec = load_canary_spec(spec_path)
    target_proof = load_target_proof(target_proof_path)
    media_proof = load_media_proof(media_proof_path)
    current = now or datetime.now(tz=UTC)
    _require_exact_target(profile, binding, target_proof, now=current)
    _require_fresh_media_proof(media_proof, spec, now=current)
    if not profile.provider_writes_authorized:
        raise ValueError("native rich canary runtime profile is provider-write disabled")
    document, render_result, rich_article = _render_document(
        profile=profile,
        binding=binding,
        spec=spec,
        github_repository=github_repository,
        github_sha=github_sha,
        repository_root=repository_root,
    )
    expected_media_sha256 = document.expected_media_sha256
    if expected_media_sha256 is None:
        raise ValueError("native rich canary document must require exact inline media evidence")

    return NativeRichCanaryIntent(
        schema_name="video-channel-manager.svodka-native-rich-canary-state",
        schema_version=1,
        state="intent",
        provider_effect="impossible",
        project_key=EXPECTED_PROJECT_KEY,
        channel_username=EXPECTED_CHANNEL_USERNAME,
        chat_id=EXPECTED_CHAT_ID,
        bot_id=EXPECTED_BOT_ID,
        bot_username=EXPECTED_BOT_USERNAME,
        publication_id=PUBLICATION_ID,
        confirmation=CONFIRMATION,
        github_repository=EXPECTED_REPOSITORY,
        github_ref=EXPECTED_GITHUB_REF,
        github_sha=github_sha,
        github_workflow_sha=github_workflow_sha,
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        exact_quality_workflows=QUALITY_WORKFLOWS,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        target_proof_sha256=_sha256_json(target_proof.model_dump(mode="json")),
        spec_sha256=spec.digest,
        media_registry_sha256=spec.media_registry.sha256,
        media_asset_entry_sha256=(
            spec.media_registry.assets[0].entry_sha256,
            spec.media_registry.assets[1].entry_sha256,
        ),
        media_proof_sha256=media_proof.digest,
        media_proof=media_proof,
        rich_article_sha256=rich_article.digest,
        rich_render_sha256=render_result.render_sha256,
        document_sha256=document.document_sha256,
        expected_rich_structure_sha256=document.expected_rich_structure_sha256,
        expected_media_sha256=expected_media_sha256,
        target_proof=target_proof,
        document=document,
        mutation_request_limit=1,
        automatic_retry_allowed=False,
        blind_retry_allowed=False,
        may_exist_requires_stop=True,
        publication_ledger_consumed=False,
        counts_as_pilot_post=False,
        pilot_release_modified=False,
        legacy_scheduler_unlocked=False,
        automatic_delete_allowed=False,
        automatic_edit_allowed=False,
        created_at_utc=current,
    )


def _verify_intent_against_runtime(
    intent: NativeRichCanaryIntent,
    *,
    profile_path: Path,
    binding_path: Path,
    spec_path: Path,
    target_proof_path: Path,
    media_proof_path: Path,
    repository_root: Path,
    now: datetime,
) -> tuple[TelegramChannelProfile, GenericTargetProof]:
    profile = load_channel_profile(profile_path)
    binding = load_target_binding(binding_path, profile)
    spec = load_canary_spec(spec_path)
    target_proof = load_target_proof(target_proof_path)
    media_proof = load_media_proof(media_proof_path)
    _require_exact_target(profile, binding, target_proof, now=now)
    _require_fresh_media_proof(media_proof, spec, now=now)
    current_document, current_render, current_article = _render_document(
        profile=profile,
        binding=binding,
        spec=spec,
        github_repository=intent.github_repository,
        github_sha=intent.github_sha,
        repository_root=repository_root,
    )
    if (
        intent.spec_sha256 != spec.digest
        or intent.media_registry_sha256 != spec.media_registry.sha256
        or intent.media_asset_entry_sha256
        != (spec.media_registry.assets[0].entry_sha256, spec.media_registry.assets[1].entry_sha256)
        or intent.media_proof.content_identity != media_proof.content_identity
        or intent.profile_sha256 != profile.digest
        or intent.target_binding_sha256 != binding.digest
        or intent.target_proof_sha256 != _sha256_json(target_proof.model_dump(mode="json"))
        or intent.rich_article_sha256 != current_article.digest
        or intent.rich_render_sha256 != current_render.render_sha256
        or intent.document_sha256 != current_document.document_sha256
        or intent.document != current_document
    ):
        raise ValueError("durable native rich canary intent differs from current exact runtime inputs")
    return profile, target_proof


def dispatch_canary_once(
    *,
    profile_path: Path,
    binding_path: Path,
    spec_path: Path,
    target_proof_path: Path,
    media_proof_path: Path,
    durable_state_path: Path,
    provider_outcome_path: Path,
    repository_root: Path,
    token: str | None = None,
    provider: TelegramRichMutationProvider | None = None,
    archiver: TelegramRichOutcomeArchiver | None = None,
    now: datetime | None = None,
) -> ArchivedTelegramRichOutcome:
    state = load_canary_state(durable_state_path)
    if not isinstance(state, NativeRichCanaryIntent):
        raise ValueError("native rich canary already reached durable terminal state; retry is forbidden")
    current = now or datetime.now(tz=UTC)
    profile, target_proof = _verify_intent_against_runtime(
        state,
        profile_path=profile_path,
        binding_path=binding_path,
        spec_path=spec_path,
        target_proof_path=target_proof_path,
        media_proof_path=media_proof_path,
        repository_root=repository_root,
        now=current,
    )
    effective_archiver = archiver or ExactFileOutcomeArchiver(provider_outcome_path)
    if provider is not None:
        return publish_rich_once(
            state.document,
            target_proof,
            provider,
            effective_archiver,
            profile=profile,
            now=current,
            timeout=TelegramRichRequestTimeout(),
        )
    if not token or not token.strip():
        raise ValueError("SVODKA_TELEGRAM_BOT_TOKEN is required for the explicit native rich canary")
    with HttpxTelegramRichMutationProvider(token=token) as http_provider:
        return publish_rich_once(
            state.document,
            target_proof,
            http_provider,
            effective_archiver,
            profile=profile,
            now=current,
            timeout=TelegramRichRequestTimeout(),
        )


def finalize_outcome_state(
    *,
    durable_intent_path: Path,
    provider_outcome_path: Path,
    artifact_name: str,
    artifact_id: str,
    artifact_url: str,
    artifact_digest: str,
    now: datetime | None = None,
) -> NativeRichCanaryOutcomeState:
    state = load_canary_state(durable_intent_path)
    if not isinstance(state, NativeRichCanaryIntent):
        raise ValueError("native rich canary durable intent was already finalized")
    try:
        outcome_bytes = provider_outcome_path.read_bytes()
        outcome = TelegramRichProviderOutcome.model_validate_json(outcome_bytes)
    except (OSError, ValidationError) as exc:
        raise ValueError("native rich canary provider outcome artifact is missing or malformed") from exc
    if _sha256_bytes(outcome_bytes) != outcome.outcome_sha256:
        raise ValueError("native rich canary provider outcome artifact bytes have changed")
    normalized_artifact_digest = (
        artifact_digest if artifact_digest.startswith("sha256:") else f"sha256:{artifact_digest}"
    )
    if _SHA256_RE.fullmatch(normalized_artifact_digest) is None:
        raise ValueError("native rich canary Actions artifact digest is invalid")
    current = now or datetime.now(tz=UTC)
    artifact = NativeRichProviderArtifact(
        artifact_name=artifact_name,
        artifact_id=artifact_id,
        artifact_url=artifact_url,
        artifact_sha256=normalized_artifact_digest,
        provider_outcome_sha256=outcome.outcome_sha256,
        uploaded_before_durable_outcome=True,
    )
    return NativeRichCanaryOutcomeState(
        schema_name="video-channel-manager.svodka-native-rich-canary-state",
        schema_version=1,
        state=outcome.provider_effect,
        provider_effect=outcome.provider_effect,
        intent=state,
        provider_outcome=outcome,
        provider_outcome_artifact=artifact,
        automatic_retry_allowed=False,
        blind_retry_allowed=False,
        second_run_allowed=False,
        may_exist_requires_stop=True,
        publication_ledger_consumed=False,
        counts_as_pilot_post=False,
        pilot_release_modified=False,
        legacy_scheduler_unlocked=False,
        automatic_delete_allowed=False,
        automatic_edit_allowed=False,
        updated_at_utc=current,
    )


def build_future_edit_test_plan(
    document: TelegramRichMessageDocument, spec: NativeRichCanarySpec
) -> NativeRichFutureEditTestPlan:
    replacement = copy.deepcopy(document.input_rich_message)
    blocks = replacement.get("blocks")
    details = (
        next(
            (block for block in blocks if isinstance(block, dict) and block.get("type") == "details"),
            None,
        )
        if isinstance(blocks, list)
        else None
    )
    if not isinstance(details, dict):
        raise ValueError("native rich future edit fixture has no details block")
    details["summary"] = spec.future_edit_test.replacement_details_summary
    return NativeRichFutureEditTestPlan(
        schema_name="video-channel-manager.svodka-native-rich-future-edit-test",
        schema_version=1,
        provider_method="editMessageText",
        provider_writes_authorized=False,
        wired_to_workflow=False,
        provider_request_count=0,
        requires_verified_canary_message_id=True,
        chat_id=EXPECTED_CHAT_ID,
        message_id_source="verified native rich canary durable outcome",
        base_document_sha256=document.document_sha256,
        request_parameter_name="rich_message",
        replacement_rich_message=replacement,
        text_parameter_used=False,
        automatic_retry_allowed=False,
        automatic_dispatch_allowed=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual-only native sendRichMessage canary for Svodka")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview")
    preview.add_argument("--profile", type=Path, required=True)
    preview.add_argument("--binding", type=Path, required=True)
    preview.add_argument("--spec", type=Path, required=True)
    preview.add_argument("--repository-root", type=Path, default=Path("."))
    preview.add_argument("--github-repository", required=True)
    preview.add_argument("--github-sha", required=True)
    preview.add_argument("--document-output", type=Path, required=True)
    preview.add_argument("--future-edit-output", type=Path, required=True)

    media_proof = subparsers.add_parser("media-proof")
    media_proof.add_argument("--spec", type=Path, required=True)
    media_proof.add_argument("--repository-root", type=Path, default=Path("."))
    media_proof.add_argument("--expected-proof", type=Path)
    media_proof.add_argument("--output", type=Path, required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--profile", type=Path, required=True)
    prepare.add_argument("--binding", type=Path, required=True)
    prepare.add_argument("--spec", type=Path, required=True)
    prepare.add_argument("--target-proof", type=Path, required=True)
    prepare.add_argument("--media-proof", type=Path, required=True)
    prepare.add_argument("--state", type=Path, required=True)
    prepare.add_argument("--repository-root", type=Path, default=Path("."))
    prepare.add_argument("--confirmation", required=True)
    prepare.add_argument("--github-repository", required=True)
    prepare.add_argument("--github-ref", required=True)
    prepare.add_argument("--github-sha", required=True)
    prepare.add_argument("--github-workflow-sha", required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--intent-output", type=Path, required=True)

    dispatch = subparsers.add_parser("dispatch")
    dispatch.add_argument("--profile", type=Path, required=True)
    dispatch.add_argument("--binding", type=Path, required=True)
    dispatch.add_argument("--spec", type=Path, required=True)
    dispatch.add_argument("--target-proof", type=Path, required=True)
    dispatch.add_argument("--media-proof", type=Path, required=True)
    dispatch.add_argument("--durable-state", type=Path, required=True)
    dispatch.add_argument("--provider-outcome", type=Path, required=True)
    dispatch.add_argument("--repository-root", type=Path, default=Path("."))

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--durable-intent", type=Path, required=True)
    finalize.add_argument("--provider-outcome", type=Path, required=True)
    finalize.add_argument("--artifact-name", required=True)
    finalize.add_argument("--artifact-id", required=True)
    finalize.add_argument("--artifact-url", required=True)
    finalize.add_argument("--artifact-digest", required=True)
    finalize.add_argument("--state-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preview":
        profile = load_channel_profile(args.profile)
        binding = load_target_binding(args.binding, profile)
        spec = load_canary_spec(args.spec)
        document, render_result, article = _render_document(
            profile=profile,
            binding=binding,
            spec=spec,
            github_repository=args.github_repository,
            github_sha=args.github_sha,
            repository_root=args.repository_root,
        )
        write_model(args.document_output, document)
        write_model(args.future_edit_output, build_future_edit_test_plan(document, spec))
        print(
            json.dumps(
                {
                    "rich_article_sha256": article.digest,
                    "rich_render_sha256": render_result.render_sha256,
                    "document_sha256": document.document_sha256,
                    "expected_rich_structure_sha256": document.expected_rich_structure_sha256,
                    "expected_media_sha256": document.expected_media_sha256,
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "media-proof":
        spec = load_canary_spec(args.spec)
        expected_proof = load_media_proof(args.expected_proof) if args.expected_proof else None
        proof = prove_remote_media(
            spec=spec,
            repository_root=args.repository_root,
            expected_proof=expected_proof,
        )
        write_model(args.output, proof)
        print(
            json.dumps(
                {
                    "media_proof_sha256": proof.digest,
                    "content_sha256": [item.content_sha256 for item in proof.items],
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "prepare":
        intent = prepare_intent(
            profile_path=args.profile,
            binding_path=args.binding,
            spec_path=args.spec,
            target_proof_path=args.target_proof,
            media_proof_path=args.media_proof,
            state_path=args.state,
            repository_root=args.repository_root,
            confirmation=args.confirmation,
            github_repository=args.github_repository,
            github_ref=args.github_ref,
            github_sha=args.github_sha,
            github_workflow_sha=args.github_workflow_sha,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
        )
        write_model(args.intent_output, intent)
        print(json.dumps({"state": "intent", "document_sha256": intent.document_sha256}, ensure_ascii=False))
        return 0

    if args.command == "dispatch":
        token = os.environ.get("SVODKA_TELEGRAM_BOT_TOKEN", "").strip()
        archived = dispatch_canary_once(
            profile_path=args.profile,
            binding_path=args.binding,
            spec_path=args.spec,
            target_proof_path=args.target_proof,
            media_proof_path=args.media_proof,
            durable_state_path=args.durable_state,
            provider_outcome_path=args.provider_outcome,
            repository_root=args.repository_root,
            token=token,
        )
        print(
            json.dumps(
                {
                    "provider_effect": archived.outcome.provider_effect,
                    "mutation_request_count": archived.outcome.mutation_request_count,
                    "message_id": archived.outcome.message_id,
                    "automatic_retry_allowed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0 if archived.outcome.provider_effect == "verified" else 4

    terminal = finalize_outcome_state(
        durable_intent_path=args.durable_intent,
        provider_outcome_path=args.provider_outcome,
        artifact_name=args.artifact_name,
        artifact_id=args.artifact_id,
        artifact_url=args.artifact_url,
        artifact_digest=args.artifact_digest,
    )
    write_model(args.state_output, terminal)
    print(json.dumps({"state": terminal.state, "provider_effect": terminal.provider_effect}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
