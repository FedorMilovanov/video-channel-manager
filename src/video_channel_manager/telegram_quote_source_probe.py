from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal
from video_channel_manager.telegram_quote_source_audit import canonical_url, load_source_web_audit

PROBE_SCHEMA = "video-channel-manager.telegram-quote-source-live-probe"
PROBE_SCHEMA_VERSION = 2
PROBE_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BotBlockedStatus = {401, 403, 406, 429}
NotFoundStatus = {404, 410}
ProbeOutcome = Literal[
    "retrieved",
    "transport_failure",
    "bot_protection",
    "stale_url_relocated",
    "not_found",
    "insufficient_evidence",
]
FAILURE_OUTCOMES = frozenset({"transport_failure", "bot_protection", "stale_url_relocated", "not_found"})
FAILURE_SEMANTICS = (
    "Retrieval-layer observations only. A failed probe is not evidence that the source URL is dead, incorrect or "
    "editorially invalid: transport failures, bot protection, stale relocations and missing pages are recorded as "
    "distinct classes so a reviewer can see exactly what happened without weakening the quotation."
)
BOT_CHALLENGE_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "checking your browser",
    "attention required",
    "enable javascript and cookies to continue",
)


@dataclass(frozen=True)
class ProbeResult:
    url: str
    outcome: ProbeOutcome
    http_status: int | None
    final_url: str | None
    note: str

    def as_payload(self) -> dict[str, object]:
        return {
            "url": self.url,
            "outcome": self.outcome,
            "http_status": self.http_status,
            "final_url": self.final_url,
            "note": self.note,
        }


def classify_response(*, requested: str, final_url: str, status: int, body: str) -> ProbeResult:
    """Classify one HTTP observation without ever judging the quotation itself."""

    lowered = body[:4096].casefold()
    if status in BotBlockedStatus or any(marker in lowered for marker in BOT_CHALLENGE_MARKERS):
        return ProbeResult(
            url=requested,
            outcome="bot_protection",
            http_status=status,
            final_url=final_url if final_url != requested else None,
            note="The host answered with a bot-protection response; this layer cannot judge the document.",
        )
    if status in NotFoundStatus:
        return ProbeResult(
            url=requested,
            outcome="not_found",
            http_status=status,
            final_url=final_url if final_url != requested else None,
            note="The requested URL answered 'gone'; treat as a stale citation needing review, never as proof about the quotation.",
        )
    if status >= 400:
        return ProbeResult(
            url=requested,
            outcome="transport_failure",
            http_status=status,
            final_url=final_url if final_url != requested else None,
            note="The server answered an error status at the transport layer.",
        )
    if final_url != requested:
        # Safe canonicalization (www prefix, scheme, trailing slash, preserved query)
        # keeps the same reviewed page; anything else is a relocation for review.
        if canonical_url(final_url) == canonical_url(requested):
            return ProbeResult(
                url=requested,
                outcome="retrieved",
                http_status=status,
                final_url=final_url,
                note="Retrieved through a safe canonicalization of the same reviewed page.",
            )
        return ProbeResult(
            url=requested,
            outcome="stale_url_relocated",
            http_status=status,
            final_url=final_url,
            note="The citation redirected to a different canonical location; the reviewed document needs a relocation record.",
        )
    if not body.strip():
        return ProbeResult(
            url=requested,
            outcome="insufficient_evidence",
            http_status=status,
            final_url=None,
            note="The endpoint answered without a document body, so no retrieval claim can be made.",
        )
    return ProbeResult(
        url=requested,
        outcome="retrieved",
        http_status=status,
        final_url=None,
        note="Retrieved successfully at the exact reviewed URL.",
    )


def probe_url(url: str, *, timeout: float) -> ProbeResult:
    request = urllib.request.Request(url, headers={"User-Agent": PROBE_USER_AGENT, "Accept-Language": "en,ru;q=0.8"})
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310 - reviewed public HTTPS inventory
            body = response.read(200_000).decode("utf-8", errors="replace")
            return classify_response(
                requested=url,
                final_url=response.geturl(),
                status=int(response.status),
                body=body,
            )
    except urllib.error.HTTPError as error:
        body = ""
        try:
            body = error.read(4096).decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover - defensive read of an error body
            body = ""
        return classify_response(requested=url, final_url=error.geturl() or url, status=int(error.code), body=body)
    except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as error:
        return ProbeResult(
            url=url,
            outcome="transport_failure",
            http_status=None,
            final_url=None,
            note=f"The automated probe could not complete the request ({type(error).__name__}); not evidence about the quotation.",
        )


def probe_inventory(*, inventory_path: Path, timeout: float, limit: int | None = None) -> dict[str, object]:
    audit = load_source_web_audit(inventory_path)
    urls = list(audit.research_pages)
    if limit is not None:
        urls = urls[:limit]
    results = [probe_url(url, timeout=timeout) for url in urls]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    retrieved = counts.get("retrieved", 0)
    return {
        "schema_name": PROBE_SCHEMA,
        "schema_version": PROBE_SCHEMA_VERSION,
        "release_id": audit.release_id,
        "queue_digest": audit.queue_digest,
        "web_audit_file": inventory_path.name,
        "probed_on": date.today().isoformat(),
        "urls_attempted": len(results),
        "urls_fetched_successfully": retrieved,
        "fetch_failures": len(results) - retrieved,
        "failure_semantics": FAILURE_SEMANTICS,
        "classification_counts": counts,
        "results": [result.as_payload() for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only classification re-probe of the reviewed LordChrist quote source inventory."
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    payload = probe_inventory(inventory_path=args.inventory, timeout=args.timeout, limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "release_id": payload["release_id"],
                "queue_digest": payload["queue_digest"],
                "urls_attempted": payload["urls_attempted"],
                "urls_fetched_successfully": payload["urls_fetched_successfully"],
                "classification_counts": payload["classification_counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
