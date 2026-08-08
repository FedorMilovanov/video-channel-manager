from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA_RE = r"^sha256:[0-9a-f]{64}$"
PUB_ID_RE = r"^lordchrist-research-[a-z0-9][a-z0-9-]{4,80}$"
BODY_PATH_RE = r"^content/telegram/lordchrist/research-posts/[a-z0-9-]+\.txt$"
SOURCE_PATH_RE = r"^content/telegram/lordchrist/research-queues/[a-z0-9-]+\.json$"
MAX_TELEGRAM_TEXT_LENGTH = 4096

EvidenceType = Literal["primary", "institutional", "scholarly"]
Certainty = Literal["exact", "estimate", "lower_bound", "archive_count", "interpretation"]
ClaimKind = Literal["numeric", "historical", "influence", "method", "interpretation"]
ContentKind = Literal["comparison", "historical_analysis", "biography"]


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(raw)


def normalize_body(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def validate_public_copy(value: str) -> str:
    text = normalize_body(value)
    if not 600 <= len(text) <= MAX_TELEGRAM_TEXT_LENGTH:
        raise ValueError("research post body must fit Telegram and remain substantive")
    internal = ("fact-check anchors", "research-post", "certainty =", "source_ids", "нейросеть", "как ии")
    if any(marker in text.casefold() for marker in internal):
        raise ValueError("public research copy contains internal editorial or machine language")
    if "**" in text or "`" in text or "http://" in text or "https://" in text:
        raise ValueError("research post must be final Telegram plain text without Markdown or raw URLs")
    return text


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str = Field(pattern=r"^src-[a-z0-9][a-z0-9-]{2,80}$")
    title: str = Field(min_length=3, max_length=240)
    publisher: str = Field(min_length=2, max_length=160)
    url: str = Field(pattern=r"^https://")
    evidence_type: EvidenceType
    checked_on: date

    @field_validator("url")
    @classmethod
    def public_https(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("source URL must be public HTTPS without embedded credentials")
        return value


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_name: Literal["video-channel-manager.telegram-research-source-registry"]
    schema_version: Literal[1]
    checked_on: date
    sources: tuple[Source, ...] = Field(min_length=12, max_length=100)

    @model_validator(mode="after")
    def registry_contract(self) -> "SourceRegistry":
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source_id values must be unique")
        if {"primary", "institutional", "scholarly"} - {source.evidence_type for source in self.sources}:
            raise ValueError("source registry must include primary, institutional, and scholarly evidence")
        if any(source.checked_on > self.checked_on for source in self.sources):
            raise ValueError("registry checked_on cannot predate a source check")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_id: str = Field(pattern=r"^claim-[a-z0-9][a-z0-9-]{2,100}$")
    claim_text: str = Field(min_length=20, max_length=600)
    claim_kind: ClaimKind
    certainty: Certainty
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    measurement_scope: str | None = Field(default=None, min_length=3, max_length=180)

    @model_validator(mode="after")
    def semantics(self) -> "Claim":
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("claim source_ids must be unique")
        if self.claim_kind == "numeric":
            if self.certainty == "interpretation" or self.measurement_scope is None:
                raise ValueError("numeric claims require measurement_scope and non-interpretive certainty")
        elif self.measurement_scope is not None:
            raise ValueError("measurement_scope is reserved for numeric claims")
        if self.claim_kind == "influence" and self.certainty == "exact":
            raise ValueError("influence claims cannot use certainty=exact")
        return self


class PostSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int = Field(ge=1, le=5)
    publication_id: str = Field(pattern=PUB_ID_RE)
    content_kind: ContentKind
    title: str = Field(min_length=5, max_length=120)
    body_path: str = Field(pattern=BODY_PATH_RE)
    body_sha256: str = Field(pattern=SHA_RE)
    release_offset_days: int = Field(ge=0, le=60)
    as_of_date: date
    freshness_class: Literal["historical"] = "historical"
    editorial_status: Literal["ready"] = "ready"
    fact_check_status: Literal["accepted"] = "accepted"
    rights_status: Literal["original_editorial_no_long_quotes"] = "original_editorial_no_long_quotes"
    claims: tuple[Claim, ...] = Field(min_length=3, max_length=12)

    @model_validator(mode="after")
    def claim_contract(self) -> "PostSpec":
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)) or not any(c.claim_kind == "historical" for c in self.claims):
            raise ValueError("post requires unique claims and at least one historical claim")
        return self

    @property
    def payload_sha256(self) -> str:
        return sha256_json(
            {
                "sequence": self.sequence,
                "publication_id": self.publication_id,
                "content_kind": self.content_kind,
                "title": self.title,
                "body_sha256": self.body_sha256,
                "release_offset_days": self.release_offset_days,
                "as_of_date": self.as_of_date.isoformat(),
                "claims": [claim.model_dump(mode="json") for claim in self.claims],
            }
        )


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: Literal["staged", "armed"] = "staged"
    activation_policy: Literal["manual_after_verified_research_canary"]
    timezone: Literal["Europe/Moscow"]
    cadence_days: Literal[2]
    activation_at_utc: datetime | None = None
    canary_publication_id: str | None = None
    canary_message_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def activation_evidence(self) -> "Schedule":
        evidence = (self.activation_at_utc, self.canary_publication_id, self.canary_message_id)
        if self.state == "staged":
            if any(value is not None for value in evidence):
                raise ValueError("staged research schedule cannot claim canary evidence")
            return self
        if any(value is None for value in evidence):
            raise ValueError("armed research schedule requires complete canary evidence")
        assert self.activation_at_utc is not None and self.canary_publication_id is not None
        if self.activation_at_utc.tzinfo is None or not re.fullmatch(PUB_ID_RE, self.canary_publication_id):
            raise ValueError("armed research schedule has invalid activation evidence")
        return self


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reviewed_pages: int = Field(ge=50, le=500)
    checked_on: date
    method: Literal["primary_direct_institutional_scholarly_crosscheck"]
    editorial_language: Literal["ru"]
    anti_ranking: Literal[True]


class ResearchQueueV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_name: Literal["video-channel-manager.telegram-research-queue"]
    schema_version: Literal[2]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    series_id: str = Field(pattern=r"^series-[a-z0-9][a-z0-9-]{4,100}$")
    purpose: Literal["evidence_backed_historical_edification"]
    verification: Verification
    schedule: Schedule
    source_registry_path: str = Field(pattern=SOURCE_PATH_RE)
    source_registry_sha256: str = Field(pattern=SHA_RE)
    posts: tuple[PostSpec, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def queue_shape(self) -> "ResearchQueueV2":
        if [post.sequence for post in self.posts] != [1, 2, 3, 4, 5]:
            raise ValueError("research post sequences must be exactly 1..5")
        if [post.release_offset_days for post in self.posts] != [0, 2, 4, 6, 8]:
            raise ValueError("release offsets must be exactly T+0/T+2/T+4/T+6/T+8")
        if len({post.publication_id for post in self.posts}) != 5:
            raise ValueError("publication_id values must be unique")
        claim_ids = [claim.claim_id for post in self.posts for claim in post.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique across the research queue")
        self._locked_numbers()
        return self

    def _locked_numbers(self) -> None:
        claims = [claim for post in self.posts for claim in post.claims]

        def one(fragment: str) -> Claim:
            found = [claim for claim in claims if fragment.casefold() in claim.claim_text.casefold()]
            if len(found) != 1:
                raise ValueError(f"expected one locked claim containing {fragment!r}")
            return found[0]

        calvin, spurgeon, macarthur = one("4–5 тысяч"), one("3 563"), one("3 600")
        if (calvin.certainty, calvin.measurement_scope) != ("estimate", "оценка общего числа произнесённых проповедей"):
            raise ValueError("Calvin 4–5k must remain an estimate of sermons preached")
        if (spurgeon.certainty, spurgeon.measurement_scope) != (
            "exact",
            "опубликованные проповеди в 63-томном корпусе",
        ):
            raise ValueError("Spurgeon 3,563 must remain an exact published-corpus count")
        if (macarthur.certainty, macarthur.measurement_scope) != (
            "lower_bound",
            "записанные проповеди в современном архиве Grace to You",
        ):
            raise ValueError("MacArthur 3,600+ must remain a lower-bound archive count")
        if macarthur.source_ids != ("src-gty-sermon-archive-3600",):
            raise ValueError("MacArthur 3,600+ must remain bound to the exact checked Grace to You archive source")

    @property
    def digest(self) -> str:
        return sha256_json(
            {
                "schema_version": self.schema_version,
                "series_id": self.series_id,
                "verification": self.verification.model_dump(mode="json"),
                "schedule": self.schedule.model_dump(mode="json"),
                "source_registry_sha256": self.source_registry_sha256,
                "posts": [
                    {
                        "sequence": post.sequence,
                        "publication_id": post.publication_id,
                        "release_offset_days": post.release_offset_days,
                        "payload_sha256": post.payload_sha256,
                    }
                    for post in self.posts
                ],
            }
        )

    @property
    def live_eligible(self) -> bool:
        return self.schedule.state == "armed"


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_research_queue(path: Path) -> ResearchQueueV2:
    queue = ResearchQueueV2.model_validate(_read_json(path))
    registry = SourceRegistry.model_validate(_read_json(Path(queue.source_registry_path)))
    if registry.digest != queue.source_registry_sha256:
        raise ValueError("source registry digest mismatch")
    if queue.verification.checked_on < registry.checked_on:
        raise ValueError("research verification checked_on cannot predate the bound source registry")
    known = {source.source_id for source in registry.sources}
    if queue.verification.reviewed_pages < len(registry.sources):
        raise ValueError("reviewed_pages cannot be smaller than the bound source registry")
    for post in queue.posts:
        body = validate_public_copy(Path(post.body_path).read_text(encoding="utf-8"))
        if sha256_text(body) != post.body_sha256:
            raise ValueError(f"body digest mismatch: {post.publication_id}")
        for claim in post.claims:
            missing = set(claim.source_ids) - known
            if missing:
                raise ValueError(f"claim {claim.claim_id} references unknown sources: {sorted(missing)}")
    return queue


def preview_research_queue(queue: ResearchQueueV2) -> dict[str, object]:
    return {
        "valid": True,
        "live_eligible": queue.live_eligible,
        "schedule_state": queue.schedule.state,
        "queue_digest": queue.digest,
        "posts": [
            {
                "sequence": post.sequence,
                "publication_id": post.publication_id,
                "release_offset_days": post.release_offset_days,
                "payload_sha256": post.payload_sha256,
                "title": post.title,
                "body": validate_public_copy(Path(post.body_path).read_text(encoding="utf-8")),
            }
            for post in queue.posts
        ],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Validate/preview staged @lordchrist research-post v2 queues")
    root.add_argument("--queue", type=Path, required=True)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("preview")
    return root


def main() -> int:
    args = parser().parse_args()
    queue = load_research_queue(args.queue)
    if args.command == "validate":
        output: dict[str, object] = {
            "valid": True,
            "live_eligible": queue.live_eligible,
            "schedule_state": queue.schedule.state,
            "count": len(queue.posts),
            "reviewed_pages": queue.verification.reviewed_pages,
            "queue_digest": queue.digest,
        }
    elif args.command == "preview":
        output = preview_research_queue(queue)
    else:
        raise AssertionError(f"unhandled command: {args.command}")
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.command == "preview" else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
