from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_channel_manager.telegram_research import Certainty, ClaimKind, EvidenceType, sha256_json
from video_channel_manager.telegram_rich_models import (
    RICH_ARTICLE_SCHEMA_NAME,
    RICH_ARTICLE_SCHEMA_VERSION,
    RichArticleDocument,
    RichArticleMetadata,
    RichArticleSource,
    RichBlockDetails,
    RichBlockHeading,
    RichBlockParagraph,
    RichMediaSlot,
    RichTextBold,
    RichTextUrl,
)

SHA_RE = r"^sha256:[0-9a-f]{64}$"
SOURCE_ID_RE = r"^src-[a-z0-9][a-z0-9-]{2,80}$"
CLAIM_ID_RE = r"^claim-[a-z0-9][a-z0-9-]{2,100}$"
PUB_ID_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"

SourceGrade = Literal["A", "B+"]
SourceBindingKind = Literal["registry", "catalog"]
EvidenceRole = Literal[
    "primary_document",
    "critical_edition",
    "official_archive",
    "university_archive",
    "peer_reviewed",
    "academic_monograph",
    "institutional_collection",
]
ClaimVoice = Literal["historical_fact", "participant_position", "editorial_evaluation"]
TestimonyProximity = Literal["contemporary", "near_contemporary", "later_tradition", "not_applicable"]
ControversySide = Literal["none", "side_a", "side_b", "synthesis"]
TopicKind = Literal["biography", "martyrdom", "controversy", "historical_fact", "mission_history"]
TheologyAlignment = Literal["aligned", "mixed", "not_applicable"]


def _public_https(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL must be public HTTPS without embedded credentials")
    return value


class HistoricalSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=SOURCE_ID_RE)
    title: str = Field(min_length=3, max_length=300)
    publisher: str = Field(min_length=2, max_length=180)
    url: str = Field(max_length=2048)
    evidence_type: EvidenceType
    grade: SourceGrade
    evidence_role: EvidenceRole
    checked_on: date
    topic_tags: tuple[str, ...] = Field(min_length=1, max_length=12)
    independence_group: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,100}$")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _public_https(value)

    @model_validator(mode="after")
    def grade_role_contract(self) -> "HistoricalSource":
        if self.grade == "A" and self.evidence_role == "institutional_collection" and self.evidence_type != "primary":
            raise ValueError("grade A institutional collection must expose primary evidence")
        if len(set(self.topic_tags)) != len(self.topic_tags):
            raise ValueError("source topic_tags must be unique")
        return self


class HistoricalSourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-source-registry"]
    schema_version: Literal[1]
    checked_on: date
    sources: tuple[HistoricalSource, ...] = Field(min_length=50, max_length=200)

    @model_validator(mode="after")
    def registry_contract(self) -> "HistoricalSourceRegistry":
        ids = [source.source_id for source in self.sources]
        urls = [source.url for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("historical source ids must be unique")
        if len(urls) != len(set(urls)):
            raise ValueError("historical source URLs must be unique")
        if any(source.checked_on > self.checked_on for source in self.sources):
            raise ValueError("registry checked_on cannot predate source checks")
        if not any(source.grade == "A" and source.evidence_type == "primary" for source in self.sources):
            raise ValueError("registry requires at least one grade A primary source")
        if not any(source.evidence_role == "peer_reviewed" for source in self.sources):
            raise ValueError("registry requires peer-reviewed scholarship")
        if not any(source.evidence_role in {"official_archive", "university_archive"} for source in self.sources):
            raise ValueError("registry requires archive evidence")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(pattern=CLAIM_ID_RE)
    claim_text: str = Field(min_length=20, max_length=900)
    claim_kind: ClaimKind
    certainty: Certainty
    voice: ClaimVoice
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    direct_quote: bool = False
    locator: str | None = Field(default=None, min_length=2, max_length=220)
    testimony_proximity: TestimonyProximity = "not_applicable"
    controversy_side: ControversySide = "none"

    @model_validator(mode="after")
    def claim_contract(self) -> "HistoricalClaim":
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("claim source_ids must be unique")
        if self.direct_quote:
            if self.locator is None or self.certainty != "exact":
                raise ValueError("direct quotation requires exact certainty and an exact locator")
            if self.voice == "editorial_evaluation":
                raise ValueError("editorial evaluation cannot masquerade as a direct historical quotation")
        elif self.locator is not None:
            raise ValueError("locator is reserved for direct quotations")
        if self.voice == "editorial_evaluation" and self.controversy_side != "none":
            raise ValueError("editorial evaluation must remain separate from controversy participant evidence")
        if self.controversy_side in {"side_a", "side_b"} and self.voice != "participant_position":
            raise ValueError("controversy side evidence must be participant_position")
        if self.claim_kind == "numeric" and self.certainty == "interpretation":
            raise ValueError("numeric historical claims cannot use interpretation certainty")
        return self


class HistoricalSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")
    heading: str = Field(min_length=3, max_length=120)
    paragraphs: tuple[str, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def visible_text(self) -> "HistoricalSection":
        if any(not paragraph.strip() or len(paragraph) > 1200 for paragraph in self.paragraphs):
            raise ValueError("historical section paragraphs must be compact visible text")
        return self


class HistoricalImagePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=r"^img-[a-z0-9][a-z0-9-]{2,80}$")
    source_id: str = Field(pattern=SOURCE_ID_RE)
    source_page_url: str
    direct_media_url: str | None = None
    depicts: str = Field(min_length=5, max_length=240)
    purpose: str = Field(min_length=5, max_length=240)
    rights_basis: str = Field(min_length=5, max_length=300)
    license_label: str = Field(min_length=2, max_length=120)
    attribution_text: str = Field(min_length=2, max_length=300)
    expected_mime: Literal["image/jpeg", "image/png"] | None = None
    expected_sha256: str | None = Field(default=None, pattern=SHA_RE)
    production_ready: bool = False
    checked_on: date

    @field_validator("source_page_url")
    @classmethod
    def source_page_public(cls, value: str) -> str:
        return _public_https(value)

    @field_validator("direct_media_url")
    @classmethod
    def direct_media_public(cls, value: str | None) -> str | None:
        return None if value is None else _public_https(value)

    @model_validator(mode="after")
    def production_contract(self) -> "HistoricalImagePlan":
        if self.production_ready and (
            self.direct_media_url is None or self.expected_mime is None or self.expected_sha256 is None
        ):
            raise ValueError("production-ready image requires direct URL, MIME and SHA-256")
        return self


class TheologyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-theology-profile"]
    schema_version: Literal[1]
    profile_id: Literal["lordchrist-historical-editorial-v1"]
    source_repository: Literal["FedorMilovanov/gb-is-my-strength"]
    source_path: Literal["about/index.html"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    checked_on: date
    commitments: tuple[str, ...] = Field(min_length=6, max_length=12)

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class TheologyReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    historical_description: str = Field(min_length=30, max_length=1000)
    participant_position: str = Field(min_length=20, max_length=1000)
    editorial_evaluation: str = Field(min_length=30, max_length=1200)
    scripture_refs: tuple[str, ...] = Field(min_length=1, max_length=12)
    alignment: TheologyAlignment
    description_separated_from_evaluation: Literal[True]
    review_status: Literal["accepted"]

    @model_validator(mode="after")
    def review_contract(self) -> "TheologyReview":
        if len(set(self.scripture_refs)) != len(self.scripture_refs):
            raise ValueError("theology scripture references must be unique")
        return self


class HistoricalPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=9)
    publication_id: str = Field(pattern=PUB_ID_RE)
    topic_kind: TopicKind
    title: str = Field(min_length=8, max_length=140)
    lead: str = Field(min_length=80, max_length=900)
    sections: tuple[HistoricalSection, ...] = Field(min_length=2, max_length=5)
    evidence_boundary: str = Field(min_length=50, max_length=1000)
    claims: tuple[HistoricalClaim, ...] = Field(min_length=3, max_length=16)
    theology_review: TheologyReview
    images: tuple[HistoricalImagePlan, ...] = Field(default=(), max_length=3)
    release_offset_days: int = Field(ge=0, le=30)
    opposing_primary_bound: bool = False
    no_opposing_primary_note: str | None = Field(default=None, min_length=20, max_length=500)
    editorial_status: Literal["ready"]
    fact_check_status: Literal["accepted"]
    rights_status: Literal["reviewed"]

    @model_validator(mode="after")
    def post_shape(self) -> "HistoricalPost":
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claim ids must be unique inside a historical post")
        if self.topic_kind == "controversy":
            sides = {claim.controversy_side for claim in self.claims}
            if "side_a" not in sides or "synthesis" not in sides:
                raise ValueError("controversy requires side_a and scholarly synthesis evidence")
            if self.opposing_primary_bound and "side_b" not in sides:
                raise ValueError("bound opposing primary evidence must be represented as side_b")
            if not self.opposing_primary_bound and self.no_opposing_primary_note is None:
                raise ValueError(
                    "controversy without bound opposing primary evidence requires an explicit limitation note"
                )
        elif self.opposing_primary_bound or self.no_opposing_primary_note is not None:
            raise ValueError("opposing-primary fields are reserved for controversy posts")
        if self.topic_kind == "martyrdom" and not any(
            claim.testimony_proximity in {"contemporary", "near_contemporary", "later_tradition"}
            for claim in self.claims
        ):
            raise ValueError("martyrdom post requires explicit testimony proximity")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewed_urls: int = Field(ge=50, le=500)
    checked_on: date
    method: Literal["a_bplus_primary_archive_scholarly_crosscheck"]
    production_threshold: Literal["A_or_B_plus_only"]
    editorial_language: Literal["ru"]
    anti_ranking: Literal[True]


class HistoricalSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["staged"]
    provider_writes_authorized: Literal[False]
    activation_policy: Literal["manual_after_verified_historical_rich_canary"]
    timezone: Literal["Europe/Moscow"]
    local_time: Literal["19:17"]
    iso_weekdays: tuple[int, int, int]
    posts_per_week: Literal[3]
    max_verified_per_day: Literal[2]
    backfill_policy: Literal["none"]

    @model_validator(mode="after")
    def schedule_contract(self) -> "HistoricalSchedule":
        if self.iso_weekdays != (1, 3, 6):
            raise ValueError("historical cadence must be Monday/Wednesday/Saturday")
        return self


class HistoricalEditorialQueueV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-editorial-queue"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    series_id: str = Field(pattern=r"^series-history-[a-z0-9][a-z0-9-]{3,80}$")
    purpose: Literal["evidence_backed_historical_edification"]
    state: Literal["provider_inert"]
    verification: HistoricalVerification
    schedule: HistoricalSchedule
    source_binding_kind: SourceBindingKind
    source_binding_path: str = Field(min_length=5, max_length=300)
    source_binding_sha256: str = Field(pattern=SHA_RE)
    source_registry_sha256: str = Field(pattern=SHA_RE)
    theology_profile_path: str
    theology_profile_sha256: str = Field(pattern=SHA_RE)
    posts: tuple[HistoricalPost, ...] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def queue_shape(self) -> "HistoricalEditorialQueueV1":
        if [post.sequence for post in self.posts] != list(range(1, 10)):
            raise ValueError("historical queue sequences must be exactly 1..9")
        if [post.release_offset_days for post in self.posts] != [0, 2, 5, 7, 9, 12, 14, 16, 19]:
            raise ValueError("historical queue must encode three Monday/Wednesday/Saturday weeks")
        if len({post.publication_id for post in self.posts}) != 9:
            raise ValueError("historical publication ids must be unique")
        claim_ids = [claim.claim_id for post in self.posts for claim in post.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("historical claim ids must be unique across the queue")
        if self.source_binding_kind == "registry" and self.source_binding_sha256 != self.source_registry_sha256:
            raise ValueError("direct registry binding digest must equal materialized registry digest")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))

    @property
    def live_eligible(self) -> bool:
        return False


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical editorial JSON {path}: {exc}") from exc


def load_historical_source_registry(path: Path) -> HistoricalSourceRegistry:
    return HistoricalSourceRegistry.model_validate(_load_json(path))


def load_theology_profile(path: Path) -> TheologyProfile:
    return TheologyProfile.model_validate(_load_json(path))


def _validate_post_evidence(
    post: HistoricalPost,
    registry: HistoricalSourceRegistry,
    theology: TheologyProfile,
    checked_on: date,
) -> None:
    by_id = {source.source_id: source for source in registry.sources}
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
                raise ValueError(f"material historical claim {claim.claim_id} requires two independent evidence groups")
            if not any(source.grade == "A" for source in bound):
                raise ValueError(f"material historical claim {claim.claim_id} requires at least one grade A source")
        if claim.voice == "editorial_evaluation" and not post.theology_review.scripture_refs:
            raise ValueError("editorial theological evaluation requires Scripture references")

    for image in post.images:
        source = by_id.get(image.source_id)
        if source is None:
            raise ValueError(f"historical image {image.asset_id} uses unknown provenance source")
        if image.checked_on > checked_on:
            raise ValueError(f"historical image {image.asset_id} check is newer than queue verification")
        if image.production_ready and image.direct_media_url is None:
            raise ValueError(f"historical image {image.asset_id} falsely claims production readiness")

    if theology.checked_on > checked_on:
        raise ValueError("theology profile is newer than queue verification")


def load_historical_editorial_queue(path: Path) -> HistoricalEditorialQueueV1:
    queue = HistoricalEditorialQueueV1.model_validate(_load_json(path))
    if queue.source_binding_kind != "registry":
        raise ValueError("catalog-bound historical queues must be materialized through materialize_historical_bundle")

    binding_path = Path(queue.source_binding_path)
    binding_payload = _load_json(binding_path)
    if sha256_json(binding_payload) != queue.source_binding_sha256:
        raise ValueError("historical source binding digest mismatch")
    registry = HistoricalSourceRegistry.model_validate(binding_payload)
    theology = load_theology_profile(Path(queue.theology_profile_path))
    if registry.digest != queue.source_registry_sha256:
        raise ValueError("historical source registry digest mismatch")
    if theology.digest != queue.theology_profile_sha256:
        raise ValueError("historical theology profile digest mismatch")
    if queue.verification.reviewed_urls < len(registry.sources):
        raise ValueError("reviewed_urls cannot be lower than persisted source registry size")
    if queue.verification.checked_on < registry.checked_on:
        raise ValueError("historical verification cannot predate source registry")
    if queue.verification.checked_on < theology.checked_on:
        raise ValueError("historical verification cannot predate theology profile")
    for post in queue.posts:
        _validate_post_evidence(post, registry, theology, queue.verification.checked_on)
    return queue


def build_historical_rich_document(
    queue: HistoricalEditorialQueueV1,
    post: HistoricalPost,
    registry: HistoricalSourceRegistry,
) -> RichArticleDocument:
    if post not in queue.posts:
        raise ValueError("historical post does not belong to selected queue")

    by_id = {source.source_id: source for source in registry.sources}
    source_ids = tuple(dict.fromkeys(source_id for claim in post.claims for source_id in claim.source_ids))
    sources = tuple(
        RichArticleSource(
            source_id=source_id,
            label=by_id[source_id].title,
            url=by_id[source_id].url,
            verified_on=by_id[source_id].checked_on,
            evidence=f"{by_id[source_id].grade} · {by_id[source_id].evidence_role}",
        )
        for source_id in source_ids
    )

    blocks: list[object] = [
        RichBlockHeading(block_id="h-title", text=post.title, size=1),
        RichBlockParagraph(block_id="p-lead", text=post.lead),
    ]
    for section in post.sections:
        blocks.append(RichBlockHeading(block_id=f"h-{section.section_id}", text=section.heading, size=2))
        for index, paragraph in enumerate(section.paragraphs, start=1):
            blocks.append(RichBlockParagraph(block_id=f"p-{section.section_id}-{index}", text=paragraph))

    blocks.extend(
        [
            RichBlockHeading(block_id="h-evidence", text="Что установлено источниками", size=2),
            RichBlockParagraph(block_id="p-evidence", text=post.evidence_boundary),
            RichBlockHeading(block_id="h-theology", text="Богословская оценка", size=2),
            RichBlockParagraph(
                block_id="p-theology",
                text=(RichTextBold(text="От истории к оценке. "), post.theology_review.editorial_evaluation),
            ),
        ]
    )

    detail_blocks = tuple(
        RichBlockParagraph(
            block_id=f"p-source-{index}",
            text=(
                RichTextUrl(text=by_id[source_id].publisher, url=by_id[source_id].url),
                f" — {by_id[source_id].title} [{by_id[source_id].grade}]",
            ),
        )
        for index, source_id in enumerate(source_ids, start=1)
    )
    blocks.append(
        RichBlockDetails(
            block_id="d-sources",
            summary="Источники и границы уверенности",
            blocks=detail_blocks,
            is_open=False,
        )
    )

    media_slots = tuple(
        RichMediaSlot(
            slot_id=image.asset_id,
            placement={
                "after": "lead" if index == 1 else post.sections[min(index - 2, len(post.sections) - 1)].section_id
            },
            depicts=image.depicts,
            purpose=image.purpose,
            preferred_source_type="reviewed historical image",
            copyright_provenance=(
                f"{image.license_label}; {image.rights_basis}; source={image.source_page_url}; "
                f"attribution={image.attribution_text}"
            ),
            caption=image.depicts,
        )
        for index, image in enumerate(post.images, start=1)
    )

    return RichArticleDocument(
        schema_name=RICH_ARTICLE_SCHEMA_NAME,
        schema_version=RICH_ARTICLE_SCHEMA_VERSION,
        document_id=post.publication_id,
        project_key=queue.project_key,
        metadata=RichArticleMetadata(
            title=post.title,
            language="ru",
            summary=post.lead,
            author="Редакция «Господь Бог — Сила Моя»",
            tags=("история церкви", post.topic_kind),
            created_at=queue.verification.checked_on,
        ),
        blocks=tuple(blocks),
        sources=sources,
        media_slots=media_slots,
        revision="historical-v1",
    )


__all__ = [
    "HistoricalClaim",
    "HistoricalEditorialQueueV1",
    "HistoricalImagePlan",
    "HistoricalPost",
    "HistoricalSchedule",
    "HistoricalSource",
    "HistoricalSourceRegistry",
    "HistoricalVerification",
    "SourceBindingKind",
    "TheologyProfile",
    "TheologyReview",
    "build_historical_rich_document",
    "load_historical_editorial_queue",
    "load_historical_source_registry",
    "load_theology_profile",
]
