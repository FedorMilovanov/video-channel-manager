from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, DEPTH_RELEASE_ID

EXPECTED_FUTURE_SEQUENCES = tuple(range(16, 61))
TRUSTED_RESEARCH_HOSTS = frozenset(
    {
        "ccel.org",
        "www.ccel.org",
        "newadvent.org",
        "www.newadvent.org",
        "spurgeon.org",
        "www.spurgeon.org",
        "ligonier.org",
        "www.ligonier.org",
        "learn.ligonier.org",
        "gty.org",
        "www.gty.org",
    }
)


class QuoteSourceWebAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-source-web-audit"]
    schema_version: Literal[2]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    future_sequences_reviewed: tuple[int, ...]
    checked_on: date
    minimum_research_pages: int = Field(ge=50)
    research_pages_reviewed: int = Field(ge=50)
    method: str = Field(min_length=120, max_length=1200)
    research_pages: tuple[str, ...]

    @field_validator("research_pages")
    @classmethod
    def validate_pages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("web-audit research URLs must be unique")
        for raw_url in value:
            parsed = urlparse(raw_url)
            if parsed.scheme != "https" or parsed.hostname not in TRUSTED_RESEARCH_HOSTS:
                raise ValueError(f"web-audit URL is outside the reviewed source allow-list: {raw_url}")
        return value

    @model_validator(mode="after")
    def exact_audit_contract(self) -> "QuoteSourceWebAudit":
        if self.release_id != DEPTH_RELEASE_ID or self.queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("web audit differs from the exact depth-v2 release identity")
        if self.future_sequences_reviewed != EXPECTED_FUTURE_SEQUENCES:
            raise ValueError("web audit must explicitly cover every pending sequence 16..60 exactly once")
        if self.research_pages_reviewed != len(self.research_pages):
            raise ValueError("web-audit page count differs from its URL inventory")
        if len(self.research_pages) < self.minimum_research_pages:
            raise ValueError("web audit does not meet its minimum research-page requirement")
        represented_hosts = {urlparse(url).hostname for url in self.research_pages}
        source_families = {
            "ccel.org" if host in {"ccel.org", "www.ccel.org"} else
            "newadvent.org" if host in {"newadvent.org", "www.newadvent.org"} else
            "spurgeon.org" if host in {"spurgeon.org", "www.spurgeon.org"} else
            "ligonier.org" if host in {"ligonier.org", "www.ligonier.org", "learn.ligonier.org"} else
            "gty.org"
            for host in represented_hosts
        }
        if source_families != {"ccel.org", "newadvent.org", "spurgeon.org", "ligonier.org", "gty.org"}:
            raise ValueError("web audit must retain all five reviewed source families")
        return self


def load_source_web_audit(path: Path) -> QuoteSourceWebAudit:
    try:
        return QuoteSourceWebAudit.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist quote source web audit {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LordChrist quote source web-audit evidence.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    audit = load_source_web_audit(args.path)
    print(
        json.dumps(
            {
                "release_id": audit.release_id,
                "queue_digest": audit.queue_digest,
                "published_boundary": audit.published_boundary,
                "future_sequences_reviewed": len(audit.future_sequences_reviewed),
                "research_pages_reviewed": audit.research_pages_reviewed,
                "checked_on": audit.checked_on.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
