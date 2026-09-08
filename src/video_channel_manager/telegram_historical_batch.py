from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalPost, HistoricalSource, TheologyProfile
from video_channel_manager.telegram_historical_revision import (
    HistoricalRevisionGitBlobRef,
    load_historical_revision_git_blob_json,
    validate_historical_claim_evidence,
    validate_historical_topic_verification,
)
from video_channel_manager.telegram_research import sha256_json

_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_TOPIC_KEY_RE = r"^[a-z0-9][a-z0-9_]{2,50}$"
_REQUIRED_RED_TEAM_FIELDS = {
    "independence_group",
    "unsupported_popular_claims",
    "claim_upgrade_conditions",
    "visual_plan",
    "historical_description_separated_from_editorial_evaluation",
}
_ALLOWED_VISUAL_STATES = {"planned_unmaterialized", "planned_locator_required"}


class HistoricalV3BatchTopicV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(pattern=_PUBLICATION_RE)
    red_team_topic: str = Field(pattern=_TOPIC_KEY_RE)
    post: HistoricalRevisionGitBlobRef
    verification: HistoricalRevisionGitBlobRef
    source_shards: tuple[HistoricalRevisionGitBlobRef, ...] = Field(min_length=2, max_length=12)
    expected_visual_slots: Literal[2]

    @model_validator(mode="after")
    def topic_contract(self) -> "HistoricalV3BatchTopicV1":
        if not self.publication_id.endswith("-v3"):
            raise ValueError("historical v3 batch publication ids must end in -v3")
        paths = [self.post.path, self.verification.path]
        paths.extend(ref.path for ref in self.source_shards)
        if len(paths) != len(set(paths)):
            raise ValueError("historical v3 batch topic Git blob paths must be unique")
        return self


class HistoricalV3BatchManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-v3-batch-manifest"]
    schema_version: Literal[1]
    batch_id: str = Field(pattern=r"^historical-v3-batch-[a-z0-9][a-z0-9-]{4,100}$")
    owning_issue: Literal[561]
    checked_on: date
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    state: Literal["provider_inert"]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    theology_profile: HistoricalRevisionGitBlobRef
    red_team: HistoricalRevisionGitBlobRef
    topics: tuple[HistoricalV3BatchTopicV1, ...] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def manifest_contract(self) -> "HistoricalV3BatchManifestV1":
        publication_ids = [topic.publication_id for topic in self.topics]
        red_team_topics = [topic.red_team_topic for topic in self.topics]
        post_paths = [topic.post.path for topic in self.topics]
        verification_paths = [topic.verification.path for topic in self.topics]
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("historical v3 batch publication ids must be unique")
        if len(red_team_topics) != len(set(red_team_topics)):
            raise ValueError("historical v3 batch red-team topic keys must be unique")
        if len(post_paths) != len(set(post_paths)):
            raise ValueError("historical v3 batch post paths must be unique")
        if len(verification_paths) != len(set(verification_paths)):
            raise ValueError("historical v3 batch verification paths must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalV3BatchPreflightV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-v3-batch-preflight"]
    schema_version: Literal[1]
    status: Literal["PASS"]
    batch_id: str
    batch_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    topic_count: Literal[8]
    source_binding_count: int = Field(ge=16)
    unique_source_count: int = Field(ge=1)
    claim_count: int = Field(ge=8)
    visual_slot_count: Literal[16]
    materialized_media_count: Literal[0]
    red_team_url_count: int = Field(ge=40)
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical v3 batch JSON {path}: {exc}") from exc


def _resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("historical v3 batch paths must be repository-relative")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("historical v3 batch path escapes repository root")
    return resolved


def load_historical_v3_batch_manifest(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalV3BatchManifestV1:
    resolved = manifest_path if manifest_path.is_absolute() else _resolve_repo_path(repo_root, manifest_path)
    return HistoricalV3BatchManifestV1.model_validate(_read_json(resolved))


def validate_historical_v3_red_team(
    value: object,
    *,
    manifest: HistoricalV3BatchManifestV1,
) -> int:
    if not isinstance(value, dict):
        raise ValueError("historical v3 red-team dossier must be an object")
    if (
        value.get("schema_name") != "video-channel-manager.telegram-historical-v3-red-team-dossier"
        or value.get("schema_version") != 1
        or value.get("owning_issue") != manifest.owning_issue
        or value.get("project_key") != manifest.project_key
        or value.get("channel_username") != manifest.channel_username
        or value.get("provider_write_performed") is not False
    ):
        raise ValueError("historical v3 red-team dossier header differs from the batch manifest")
    checked_on = date.fromisoformat(str(value.get("checked_on") or ""))
    if checked_on > manifest.checked_on:
        raise ValueError("historical v3 red-team dossier is newer than the batch manifest")

    required_fields = value.get("required_v3_fields")
    if (
        not isinstance(required_fields, list)
        or any(not isinstance(item, str) for item in required_fields)
        or not _REQUIRED_RED_TEAM_FIELDS.issubset(set(required_fields))
    ):
        raise ValueError("historical v3 red-team dossier omits required v3 controls")

    reviewed_urls = value.get("reviewed_urls")
    reviewed = value.get("reviewed")
    if (
        not isinstance(reviewed_urls, int)
        or isinstance(reviewed_urls, bool)
        or reviewed_urls < 40
        or not isinstance(reviewed, list)
        or len(reviewed) != reviewed_urls
    ):
        raise ValueError("historical v3 red-team dossier must bind at least 40 reviewed URLs")

    urls: list[str] = []
    reviewed_topics: set[str] = set()
    for item in reviewed:
        if not isinstance(item, dict):
            raise ValueError("historical v3 red-team reviewed entries must be objects")
        url = item.get("url")
        topic = item.get("topic")
        family = item.get("family")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("historical v3 red-team reviewed entries require url/topic/family")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("historical v3 red-team reviewed entries require url/topic/family")
        if not isinstance(family, str) or not family.strip():
            raise ValueError("historical v3 red-team reviewed entries require url/topic/family")
        urls.append(url)
        reviewed_topics.add(topic)
    if len(urls) != len(set(urls)):
        raise ValueError("historical v3 red-team reviewed URLs must be unique")

    topic_findings = value.get("topic_findings")
    if not isinstance(topic_findings, dict):
        raise ValueError("historical v3 red-team topic_findings must be an object")
    required_topics = {topic.red_team_topic for topic in manifest.topics}
    if not required_topics.issubset(topic_findings) or not required_topics.issubset(reviewed_topics):
        raise ValueError("historical v3 red-team dossier does not cover every batch topic")
    return reviewed_urls


def validate_historical_v3_topic_controls(
    value: object,
    *,
    sources: tuple[HistoricalSource, ...],
    expected_visual_slots: int,
) -> int:
    if not isinstance(value, dict):
        raise ValueError("historical v3 topic verification must be an object")

    unsupported = value.get("unsupported_popular_claims")
    upgrades = value.get("claim_upgrade_conditions")
    if not isinstance(unsupported, list) or not unsupported:
        raise ValueError("historical v3 topic verification requires unsupported_popular_claims")
    if not isinstance(upgrades, list) or not upgrades:
        raise ValueError("historical v3 topic verification requires claim_upgrade_conditions")
    for item in unsupported:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("claim"), str)
            or not item["claim"].strip()
            or not isinstance(item.get("status"), str)
            or not item["status"].strip()
        ):
            raise ValueError("historical v3 unsupported_popular_claims entries are invalid")
    for item in upgrades:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("claim"), str)
            or not item["claim"].strip()
            or not isinstance(item.get("upgrade_requires"), str)
            or not item["upgrade_requires"].strip()
        ):
            raise ValueError("historical v3 claim_upgrade_conditions entries are invalid")

    source_ids = {source.source_id for source in sources}
    evidence_groups = {source.independence_group for source in sources}
    declared_groups = value.get("independent_evidence_groups_used_in_reader_claims")
    if (
        not isinstance(declared_groups, list)
        or len(declared_groups) < 2
        or any(not isinstance(item, str) or not item.strip() for item in declared_groups)
        or len(declared_groups) != len(set(declared_groups))
        or not set(declared_groups).issubset(evidence_groups)
    ):
        raise ValueError("historical v3 declared evidence groups are invalid or unbound")

    visual_plan = value.get("visual_plan")
    if not isinstance(visual_plan, list) or len(visual_plan) != expected_visual_slots:
        raise ValueError(f"historical v3 topic verification requires exactly {expected_visual_slots} visual slots")
    slots: list[str] = []
    for item in visual_plan:
        if not isinstance(item, dict):
            raise ValueError("historical v3 visual plan entries must be objects")
        slot = item.get("slot")
        source_id = item.get("source_id")
        state = item.get("state")
        if (
            not isinstance(slot, str)
            or not slot.strip()
            or not isinstance(source_id, str)
            or source_id not in source_ids
            or state not in _ALLOWED_VISUAL_STATES
            or item.get("production_ready") is not False
        ):
            raise ValueError("historical v3 visual plan entry is invalid or prematurely materialized")
        slots.append(slot)
    if len(slots) != len(set(slots)):
        raise ValueError("historical v3 visual plan slots must be unique")
    return len(visual_plan)


def preflight_historical_v3_batch(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalV3BatchPreflightV1:
    manifest = load_historical_v3_batch_manifest(manifest_path, repo_root=repo_root)
    theology = TheologyProfile.model_validate(
        load_historical_revision_git_blob_json(repo_root, manifest.theology_profile, label="theology profile")
    )
    if theology.checked_on > manifest.checked_on:
        raise ValueError("historical v3 theology profile is newer than the batch manifest")

    red_team_value = load_historical_revision_git_blob_json(repo_root, manifest.red_team, label="red-team dossier")
    red_team_url_count = validate_historical_v3_red_team(red_team_value, manifest=manifest)

    source_binding_count = 0
    all_source_ids: set[str] = set()
    claim_count = 0
    visual_slot_count = 0

    for topic in manifest.topics:
        post = HistoricalPost.model_validate(
            load_historical_revision_git_blob_json(repo_root, topic.post, label=f"{topic.publication_id} post")
        )
        if post.publication_id != topic.publication_id:
            raise ValueError(f"historical v3 batch publication id differs from bound post: {topic.publication_id}")
        if post.images:
            raise ValueError("historical v3 batch posts must remain media-unmaterialized")

        sources: list[HistoricalSource] = []
        shard_paths: list[str] = []
        for index, ref in enumerate(topic.source_shards, start=1):
            shard = HistoricalSourceShardV1.model_validate(
                load_historical_revision_git_blob_json(
                    repo_root,
                    ref,
                    label=f"{topic.publication_id} source shard {index}",
                )
            )
            if shard.checked_on > manifest.checked_on:
                raise ValueError(f"historical v3 source shard is newer than the batch manifest: {ref.path}")
            shard_paths.append(ref.path)
            sources.extend(shard.sources)

        source_ids = [source.source_id for source in sources]
        source_urls = [source.url for source in sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(f"historical v3 source ids must be unique for {topic.publication_id}")
        if len(source_urls) != len(set(source_urls)):
            raise ValueError(f"historical v3 source URLs must be unique for {topic.publication_id}")
        source_tuple = tuple(sources)
        validate_historical_claim_evidence(post, source_tuple)

        verification = load_historical_revision_git_blob_json(
            repo_root,
            topic.verification,
            label=f"{topic.publication_id} topic verification",
        )
        validate_historical_topic_verification(
            verification,
            publication_id=topic.publication_id,
            checked_on=manifest.checked_on,
            shard_paths=tuple(shard_paths),
        )
        if not isinstance(verification, dict) or set(verification.get("source_shards", ())) != set(shard_paths):
            raise ValueError("historical v3 topic verification must bind exactly the manifest source shards")
        visual_slot_count += validate_historical_v3_topic_controls(
            verification,
            sources=source_tuple,
            expected_visual_slots=topic.expected_visual_slots,
        )

        source_binding_count += len(source_tuple)
        all_source_ids.update(source_ids)
        claim_count += len(post.claims)

    if visual_slot_count != 16:
        raise ValueError("historical v3 batch must contain exactly 16 planned visual slots")

    return HistoricalV3BatchPreflightV1(
        schema_name="video-channel-manager.telegram-historical-v3-batch-preflight",
        schema_version=1,
        status="PASS",
        batch_id=manifest.batch_id,
        batch_sha256=manifest.digest,
        topic_count=8,
        source_binding_count=source_binding_count,
        unique_source_count=len(all_source_ids),
        claim_count=claim_count,
        visual_slot_count=16,
        materialized_media_count=0,
        red_team_url_count=red_team_url_count,
        provider_writes_authorized=False,
        live_eligible=False,
        provider_write_performed=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Validate provider-inert LordChrist historical v3 editorial batches")
    root.add_argument("manifest", type=Path)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = preflight_historical_v3_batch(args.manifest, repo_root=args.repo_root)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
