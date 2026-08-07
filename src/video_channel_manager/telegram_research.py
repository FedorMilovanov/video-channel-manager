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

MAX_TELEGRAM_TEXT_LENGTH = 4096
PUB_ID_RE = r"^lordchrist-research-[a-z0-9][a-z0-9-]{4,80}$"

EvidenceType = Literal["primary", "institutional", "scholarly"]
Certainty = Literal["exact", "estimate", "lower_bound", "archive_count", "interpretation"]
ClaimKind = Literal["numeric", "historical", "influence", "method", "interpretation"]
ContentKind = Literal["comparison", "historical_analysis", "biography"]


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


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


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_id: str = Field(pattern=r"^claim-[a-z0-9][a-z0-9-]{2,100}$")
    claim_text: str = Field(min_length=20, max_length=600)
    claim_kind: ClaimKind
    certainty: Certainty
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    measurement_scope: str | None = Field(default=None, min_length=3, max_length=180)
    evidence_note: str | None = Field(default=None, max_length=500)

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


class Post(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int = Field(ge=1, le=5)
    publication_id: str = Field(pattern=PUB_ID_RE)
    content_kind: ContentKind
    title: str = Field(min_length=5, max_length=120)
    body: str = Field(min_length=600, max_length=MAX_TELEGRAM_TEXT_LENGTH)
    release_offset_days: int = Field(ge=0, le=60)
    as_of_date: date
    freshness_class: Literal["historical"] = "historical"
    editorial_status: Literal["ready"] = "ready"
    fact_check_status: Literal["accepted"] = "accepted"
    rights_status: Literal["original_editorial_no_long_quotes"] = "original_editorial_no_long_quotes"
    claims: tuple[Claim, ...] = Field(min_length=3, max_length=12)

    @field_validator("body")
    @classmethod
    def public_copy_only(cls, value: str) -> str:
        text = value.replace("\r\n", "\n").strip()
        internal = ("fact-check anchors", "research-post", "certainty =", "source_ids", "нейросеть", "как ии")
        if any(marker in text.casefold() for marker in internal):
            raise ValueError("public research copy contains internal editorial or machine language")
        if "**" in text or "`" in text or "http://" in text or "https://" in text:
            raise ValueError("research queue body must be final Telegram plain text, not Markdown source or raw URLs")
        return text

    @model_validator(mode="after")
    def claim_ids(self) -> "Post":
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)) or not any(c.claim_kind == "historical" for c in self.claims):
            raise ValueError("post requires unique claims and at least one historical claim")
        return self

    @property
    def payload_sha256(self) -> str:
        return _digest({"sequence": self.sequence, "publication_id": self.publication_id, "content_kind": self.content_kind, "title": self.title, "body": self.body, "release_offset_days": self.release_offset_days, "as_of_date": self.as_of_date.isoformat(), "claims": [c.model_dump(mode="json") for c in self.claims]})


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: Literal["staged", "armed"] = "staged"
    activation_policy: Literal["manual_after_verified_research_canary"] = "manual_after_verified_research_canary"
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    cadence_days: Literal[2] = 2
    activation_at_utc: datetime | None = None
    canary_publication_id: str | None = None
    canary_message_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def activation_evidence(self) -> "Schedule":
        evidence = (self.activation_at_utc, self.canary_publication_id, self.canary_message_id)
        if self.state == "staged":
            if any(v is not None for v in evidence):
                raise ValueError("staged research schedule cannot claim canary evidence")
            return self
        if any(v is None for v in evidence):
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
    sources: tuple[Source, ...] = Field(min_length=12, max_length=100)
    posts: tuple[Post, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def contract(self) -> "ResearchQueueV2":
        source_ids = [s.source_id for s in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        if [p.sequence for p in self.posts] != [1, 2, 3, 4, 5]:
            raise ValueError("research post sequences must be exactly 1..5")
        if [p.release_offset_days for p in self.posts] != [0, 2, 4, 6, 8]:
            raise ValueError("release offsets must be exactly T+0/T+2/T+4/T+6/T+8")
        if len({p.publication_id for p in self.posts}) != 5:
            raise ValueError("publication_id values must be unique")
        known = set(source_ids)
        claim_ids: list[str] = []
        for post in self.posts:
            for claim in post.claims:
                claim_ids.append(claim.claim_id)
                missing = set(claim.source_ids) - known
                if missing:
                    raise ValueError(f"claim {claim.claim_id} references unknown sources: {sorted(missing)}")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique across the research queue")
        if self.verification.reviewed_pages < len(self.sources):
            raise ValueError("reviewed_pages cannot be smaller than bound sources")
        if any(s.checked_on > self.verification.checked_on for s in self.sources):
            raise ValueError("verification date cannot predate a bound source check")
        if {"primary", "institutional", "scholarly"} - {s.evidence_type for s in self.sources}:
            raise ValueError("source register must include primary, institutional, and scholarly evidence")
        self._locked_numbers()
        return self

    def _locked_numbers(self) -> None:
        claims = [c for p in self.posts for c in p.claims]
        def one(fragment: str) -> Claim:
            found = [c for c in claims if fragment.casefold() in c.claim_text.casefold()]
            if len(found) != 1:
                raise ValueError(f"expected one locked claim containing {fragment!r}")
            return found[0]
        calvin, spurgeon, macarthur = one("4–5 тысяч"), one("3 563"), one("3 600")
        if (calvin.certainty, calvin.measurement_scope) != ("estimate", "оценка общего числа произнесённых проповедей"):
            raise ValueError("Calvin 4–5k must remain an estimate of sermons preached")
        if (spurgeon.certainty, spurgeon.measurement_scope) != ("exact", "опубликованные проповеди в 63-томном корпусе"):
            raise ValueError("Spurgeon 3,563 must remain an exact published-corpus count")
        if (macarthur.certainty, macarthur.measurement_scope) != ("lower_bound", "записанные проповеди в современном архиве Grace to You"):
            raise ValueError("MacArthur 3,600+ must remain a lower-bound archive count")

    @property
    def digest(self) -> str:
        return _digest({"schema_version": self.schema_version, "series_id": self.series_id, "verification": self.verification.model_dump(mode="json"), "schedule": self.schedule.model_dump(mode="json"), "sources": [s.model_dump(mode="json") for s in self.sources], "posts": [{"sequence": p.sequence, "publication_id": p.publication_id, "release_offset_days": p.release_offset_days, "payload_sha256": p.payload_sha256} for p in self.posts]})

    @property
    def live_eligible(self) -> bool:
        return self.schedule.state == "armed"


def load_research_queue(path: Path) -> ResearchQueueV2:
    return ResearchQueueV2.model_validate(json.loads(path.read_text(encoding="utf-8")))


def preview_research_queue(queue: ResearchQueueV2) -> dict[str, object]:
    return {"valid": True, "live_eligible": queue.live_eligible, "schedule_state": queue.schedule.state, "queue_digest": queue.digest, "posts": [{"sequence": p.sequence, "publication_id": p.publication_id, "release_offset_days": p.release_offset_days, "payload_sha256": p.payload_sha256, "title": p.title, "body": p.body} for p in queue.posts]}


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
    output: dict[str, object]
    if args.command == "validate":
        output = {"valid": True, "live_eligible": queue.live_eligible, "schedule_state": queue.schedule.state, "count": len(queue.posts), "sources": len(queue.sources), "reviewed_pages": queue.verification.reviewed_pages, "queue_digest": queue.digest}
    elif args.command == "preview":
        output = preview_research_queue(queue)
    else:
        raise AssertionError(f"unhandled command: {args.command}")
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.command == "preview" else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
