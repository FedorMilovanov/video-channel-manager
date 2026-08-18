from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence, cast
from zoneinfo import ZoneInfo

import httpx

from video_channel_manager.lordchrist_cross_track_effect_guard import require_no_cross_track_unresolved_effects
from video_channel_manager.lordchrist_rich_successor import build_provider_free_document
from video_channel_manager.platforms.http import HttpClientOwner, HttpOperationClass, RetryPolicy, execute_http_request
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, preflight_channel
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderOutcome,
    publish_rich_once,
)

PROJECT = "lord-god-strength"
CHANNEL = "@lordchrist"
CHAT_ID = -1001295216957
CHAT_USERNAME = "lordchrist"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
REPOSITORY = "FedorMilovanov/video-channel-manager"
RELEASE_ID = "lordchrist-rich-live-canary-2026-08-18"
PUBLICATION_ID = "lordchrist-rich-sermons-survive-century"
OWNING_ISSUE = 473
MEDIA_USER_AGENT = "video-channel-manager-lordchrist-rich/1 (+https://github.com/FedorMilovanov/video-channel-manager)"
MOSCOW = ZoneInfo("Europe/Moscow")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _verify(root: Path, identity: dict[str, Any]) -> Path:
    path = root / str(identity["path"])
    actual = _blob(path.read_bytes())
    if actual != identity.get("git_blob_sha"):
        raise ValueError(f"release-bound Git blob differs: {path} ({actual})")
    return path


def load_release(path: Path, root: Path) -> dict[str, Any]:
    release = _read(path)
    if (
        release.get("schema_name") != "video-channel-manager.lordchrist-rich-live-canary-release"
        or release.get("schema_version") != 1
        or release.get("release_id") != RELEASE_ID
        or release.get("owning_issue") != OWNING_ISSUE
        or release.get("project_key") != PROJECT
        or release.get("channel_username") != CHANNEL
        or release.get("chat_id") != CHAT_ID
        or release.get("bot_id") != BOT_ID
        or str(release.get("bot_username") or "").casefold() != BOT_USERNAME.casefold()
        or release.get("state_branch") != "state/lordchrist-telegram"
        or release.get("approved") is not True
        or release.get("max_combined_verified_per_day_moscow") != 2
        or release.get("max_rich_verified_per_day_moscow") != 1
        or release.get("publication_id") != PUBLICATION_ID
    ):
        raise ValueError("invalid LordChrist rich live canary release header")

    not_before = datetime.fromisoformat(str(release["execute_not_before_moscow"]))
    not_after = datetime.fromisoformat(str(release["execute_not_after_moscow"]))
    if not_before.utcoffset() != timedelta(hours=3) or not_after.utcoffset() != timedelta(hours=3):
        raise ValueError("LordChrist live canary window must use UTC+03:00")
    if not_after <= not_before:
        raise ValueError("LordChrist live canary window is empty")

    for key in ("profile", "legacy_profile", "target_binding", "media_registry", "article"):
        _verify(root, cast(dict[str, Any], release[key]))
    return release


def release_digest(release: dict[str, Any]) -> str:
    return _sha(release)


def require_live_window(release: dict[str, Any], now: datetime | None = None) -> None:
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    not_before = datetime.fromisoformat(str(release["execute_not_before_moscow"]))
    not_after = datetime.fromisoformat(str(release["execute_not_after_moscow"]))
    if current < not_before or current > not_after:
        raise ValueError("LordChrist rich live canary authorization window is not active")


def build_document(root: Path, release: dict[str, Any]) -> tuple[Any, Any, Any]:
    document, render, article = build_provider_free_document(
        _verify(root, cast(dict[str, Any], release["article"])),
        _verify(root, cast(dict[str, Any], release["media_registry"])),
        _verify(root, cast(dict[str, Any], release["profile"])),
        _verify(root, cast(dict[str, Any], release["target_binding"])),
    )
    if article.document_id != PUBLICATION_ID or document.publication_id != PUBLICATION_ID:
        raise ValueError("LordChrist live canary document identity mismatch")
    if [media.media_id for media in article.media] != ["media-calvin", "media-spurgeon", "media-tape"]:
        raise ValueError("LordChrist live canary must bind exactly the three reviewed media slots")
    if len(document.provider_assigned_media_paths) != 3:
        raise ValueError("LordChrist live canary must render exactly three provider-assigned media paths")
    return document, render, article


def new_ledger(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "video-channel-manager.lordchrist-rich-live-canary-ledger",
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "project_key": PROJECT,
        "channel_username": CHANNEL,
        "entries": {
            PUBLICATION_ID: {
                "publication_id": PUBLICATION_ID,
                "state": "pending",
                "provider_effect": "impossible",
                "workflow_run_id": None,
                "workflow_run_attempt": None,
                "github_sha": None,
                "document_sha256": None,
                "intent_created_at_utc": None,
                "published_at_utc": None,
                "message_id": None,
                "message_url": None,
                "error": None,
            }
        },
    }


def load_ledger(path: Path, release: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    ledger = new_ledger(release) if create and not path.exists() else _read(path)
    if (
        ledger.get("schema_name") != "video-channel-manager.lordchrist-rich-live-canary-ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("release_id") != RELEASE_ID
        or ledger.get("release_sha256") != release_digest(release)
        or ledger.get("owning_issue") != OWNING_ISSUE
        or ledger.get("project_key") != PROJECT
        or ledger.get("channel_username") != CHANNEL
    ):
        raise ValueError("LordChrist rich live canary ledger is bound to another release")
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or list(entries) != [PUBLICATION_ID]:
        raise ValueError("LordChrist rich live canary ledger entries differ from release")
    return ledger


def _rich_entry(ledger: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, dict[str, Any]], ledger["entries"])[PUBLICATION_ID]


def _legacy_verified_today(legacy_ledger_path: Path, today_moscow: str) -> int:
    legacy = _read(legacy_ledger_path)
    entries = legacy.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("legacy LordChrist ledger has no entries")
    count = 0
    for raw in entries.values():
        if not isinstance(raw, dict) or raw.get("state") != "published" or raw.get("provider_effect") != "verified":
            continue
        published = raw.get("published_at_utc")
        if not published:
            raise ValueError("verified legacy LordChrist entry lacks published_at_utc")
        if (
            datetime.fromisoformat(str(published).replace("Z", "+00:00")).astimezone(MOSCOW).date().isoformat()
            == today_moscow
        ):
            count += 1
    return count


def guard_state(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    require_live_window(release, now)
    cross_track = require_no_cross_track_unresolved_effects(
        profile_path=_verify(root, cast(dict[str, Any], release["legacy_profile"])),
        legacy_queue_path=root / "content/telegram/lordchrist/verified-30-posts.json",
        legacy_ledger_path=state_root / "content/telegram/lordchrist/publication-ledger.json",
        research_ledger_path=state_root / "content/telegram/lordchrist/research-v2/publication-ledger.json",
    )
    entry = _rich_entry(ledger)
    if entry["state"] in {"intent", "may_exist", "failed_no_effect"}:
        raise ValueError(f"unresolved LordChrist rich canary state blocks writer: {entry['state']}")
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    today = current.date().isoformat()
    legacy_count = _legacy_verified_today(
        state_root / "content/telegram/lordchrist/publication-ledger.json",
        today,
    )
    rich_count = 1 if entry["state"] == "published" and entry.get("provider_effect") == "verified" else 0
    if rich_count >= int(release["max_rich_verified_per_day_moscow"]):
        raise ValueError("LordChrist rich daily verified limit is already used")
    if legacy_count + rich_count >= int(release["max_combined_verified_per_day_moscow"]):
        raise ValueError("combined LordChrist verified daily limit is already used")
    return {
        "clear": True,
        "moscow_date": today,
        "legacy_verified_today": legacy_count,
        "rich_verified_today": rich_count,
        "combined_verified_today": legacy_count + rich_count,
        "cross_track": cross_track,
        "provider_write_performed": False,
    }


def _target_proof(path: Path) -> GenericTargetProof:
    return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))


def _require_target(proof: GenericTargetProof, document: Any, *, now: datetime | None = None) -> None:
    if (proof.chat_id, proof.bot_id, proof.bot_username.casefold(), proof.can_post_messages, proof.profile_sha256) != (
        document.target.chat_id,
        document.target.bot_id,
        document.target.bot_username.casefold(),
        True,
        document.target.profile_sha256,
    ):
        raise ValueError("fresh LordChrist target proof differs from exact rich target")
    age = (now or datetime.now(tz=UTC)) - proof.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > timedelta(minutes=15):
        raise ValueError("LordChrist rich target proof is stale")


def run_preflight(root: Path, release: dict[str, Any], *, token: str) -> GenericTargetProof:
    require_live_window(release)
    document, _render, _article = build_document(root, release)
    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    proof = preflight_channel(
        profile,
        token=token,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
    )
    _require_target(proof, document)
    return proof


def _registry_mime(root: Path, release: dict[str, Any]) -> dict[str, str]:
    registry = _read(_verify(root, cast(dict[str, Any], release["media_registry"])))
    raw_assets = registry.get("assets")
    if not isinstance(raw_assets, list):
        raise ValueError("LordChrist rich media registry has no assets")
    result: dict[str, str] = {}
    for raw in raw_assets:
        if not isinstance(raw, dict) or raw.get("article_id") != PUBLICATION_ID:
            continue
        slot_id = str(raw.get("media_slot_id") or "")
        if slot_id in {"media-calvin", "media-spurgeon", "media-tape"}:
            result[slot_id] = str(raw.get("expected_mime") or "")
    if result != {"media-calvin": "image/jpeg", "media-spurgeon": "image/jpeg", "media-tape": "image/jpeg"}:
        raise ValueError("LordChrist rich live canary media MIME registry mismatch")
    return result


class _LordChristMediaReader(HttpClientOwner):
    def __init__(self) -> None:
        self._initialize_http_client(
            None,
            timeout=httpx.Timeout(connect=15, read=30, write=15, pool=15),
            follow_redirects=True,
            trust_env=False,
        )

    def fetch(self, url: str) -> tuple[int, str, bytes]:
        result = execute_http_request(
            lambda: self._http_client.get(url, headers={"User-Agent": MEDIA_USER_AGENT}),
            provider="https-media",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource="lordchrist-rich-live-canary-media",
            retry_policy=RetryPolicy(max_attempts=2),
        )
        response = result.response
        return (
            response.status_code,
            response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
            response.content,
        )


def media_proof(
    root: Path,
    release: dict[str, Any],
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_live_window(release)
    _document, _render, article = build_document(root, release)
    mime = _registry_mime(root, release)
    evidence: list[dict[str, Any]] = []
    reader = _LordChristMediaReader()
    try:
        for media in article.media:
            status, content_type, content = reader.fetch(media.uri)
            if (
                status != 200
                or content_type != mime[media.media_id]
                or not content
                or len(content) > 10_000_000
                or not content.startswith(b"\xff\xd8\xff")
            ):
                raise ValueError(
                    f"LordChrist rich media proof failed: {media.media_id} "
                    f"status={status} content_type={content_type!r} bytes={len(content)}"
                )
            evidence.append(
                {
                    "media_id": media.media_id,
                    "url": media.uri,
                    "content_type": content_type,
                    "content_length": len(content),
                    "content_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                }
            )
    finally:
        reader.close()
    proof = {
        "schema_name": "video-channel-manager.lordchrist-rich-live-media-proof",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "publication_id": PUBLICATION_ID,
        "checked_at_utc": datetime.now(tz=UTC).isoformat(),
        "items": evidence,
        "provider_write_performed": False,
    }
    if expected is not None and expected.get("items") != proof["items"]:
        raise ValueError("LordChrist rich media bytes changed after durable intent")
    return proof


def prepare(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    target_path: Path,
    proof_media: dict[str, Any],
    *,
    repository: str,
    sha: str,
    run_id: str,
    attempt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    guard_state(root, state_root, release, ledger)
    entry = _rich_entry(ledger)
    if entry["state"] != "pending":
        raise ValueError("LordChrist rich canary is not pending")
    document, render, _article = build_document(root, release)
    target = _target_proof(target_path)
    _require_target(target, document)
    if (
        repository != REPOSITORY
        or proof_media.get("release_sha256") != release_digest(release)
        or proof_media.get("publication_id") != PUBLICATION_ID
        or len(cast(list[Any], proof_media.get("items", []))) != 3
    ):
        raise ValueError("LordChrist rich durable intent inputs differ from exact release")
    created_at = datetime.now(tz=UTC).isoformat()
    intent = {
        "schema_name": "video-channel-manager.lordchrist-rich-live-canary-intent",
        "schema_version": 1,
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "publication_id": PUBLICATION_ID,
        "github_repository": repository,
        "github_sha": sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": attempt,
        "document_sha256": document.document_sha256,
        "render_sha256": render.render_sha256,
        "target_proof_sha256": _sha(target.model_dump(mode="json")),
        "media_proof": proof_media,
        "created_at_utc": created_at,
        "mutation_request_limit": 1,
        "automatic_retry_allowed": False,
        "blind_retry_allowed": False,
        "fallback_allowed": False,
    }
    entry.update(
        {
            "state": "intent",
            "provider_effect": "impossible",
            "workflow_run_id": run_id,
            "workflow_run_attempt": attempt,
            "github_sha": sha,
            "document_sha256": document.document_sha256,
            "intent_created_at_utc": created_at,
            "error": None,
        }
    )
    return intent, ledger


class _Archiver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> TelegramRichOutcomeArchiveReceipt:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(outcome_bytes)
        if "sha256:" + hashlib.sha256(outcome_bytes).hexdigest() != outcome_sha256:
            raise ValueError("LordChrist rich provider outcome archive digest mismatch")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=f"workflow-local:{self.path}",
            durable_before_state_mutation=True,
        )


def send(
    root: Path,
    release: dict[str, Any],
    intent: dict[str, Any],
    target_path: Path,
    recheck: dict[str, Any],
    outcome_path: Path,
    *,
    token: str,
) -> TelegramRichProviderOutcome:
    require_live_window(release)
    if (
        intent.get("release_sha256") != release_digest(release)
        or intent.get("owning_issue") != OWNING_ISSUE
        or intent.get("github_repository") != REPOSITORY
        or intent.get("publication_id") != PUBLICATION_ID
        or cast(dict[str, Any], intent.get("media_proof", {})).get("items") != recheck.get("items")
    ):
        raise ValueError("LordChrist rich durable intent/media recheck mismatch")
    document, render, _article = build_document(root, release)
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("LordChrist rich document changed after durable intent")
    target = _target_proof(target_path)
    _require_target(target, document)
    if _sha(target.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("LordChrist rich target proof changed after durable intent")
    profile = load_channel_profile(_verify(root, cast(dict[str, Any], release["profile"])))
    provider = HttpxTelegramRichMutationProvider(token=token)
    try:
        archived = publish_rich_once(
            document,
            target,
            provider,
            _Archiver(outcome_path),
            profile=profile,
            state_mutation=None,
        )
    finally:
        provider.close()
    return archived.outcome


def apply(ledger: dict[str, Any], intent: dict[str, Any], outcome: TelegramRichProviderOutcome) -> dict[str, Any]:
    entry = _rich_entry(ledger)
    if (
        entry["state"] != "intent"
        or entry.get("document_sha256") != intent.get("document_sha256")
        or outcome.document_sha256 != intent.get("document_sha256")
    ):
        raise ValueError("LordChrist rich outcome has no exact durable intent")
    if outcome.provider_effect == "verified":
        entry.update(
            {
                "state": "published",
                "provider_effect": "verified",
                "published_at_utc": datetime.now(tz=UTC).isoformat(),
                "message_id": outcome.message_id,
                "message_url": outcome.message_url,
                "error": None,
            }
        )
    elif outcome.provider_effect == "may_exist":
        entry.update(
            {
                "state": "may_exist",
                "provider_effect": "may_exist",
                "error": outcome.error or "ambiguous provider effect",
            }
        )
    else:
        entry.update(
            {
                "state": "failed_no_effect",
                "provider_effect": outcome.provider_effect,
                "error": outcome.error or f"provider effect: {outcome.provider_effect}",
            }
        )
    return ledger


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "ensure-ledger", "guard", "preflight", "media-proof", "prepare", "send", "apply", "status"):
        command = sub.add_parser(name)
        command.add_argument("--release", type=Path, required=True)
        command.add_argument("--root", type=Path, default=Path("."))
        if name in {"ensure-ledger", "guard", "prepare", "apply", "status"}:
            command.add_argument("--ledger", type=Path, required=True)
        if name in {"guard", "prepare"}:
            command.add_argument("--state-root", type=Path, required=True)
        if name == "preflight":
            command.add_argument("--output", type=Path, required=True)
        if name == "media-proof":
            command.add_argument("--expected", type=Path)
            command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--media-proof", type=Path, required=True)
            command.add_argument("--github-repository", required=True)
            command.add_argument("--github-sha", required=True)
            command.add_argument("--run-id", required=True)
            command.add_argument("--run-attempt", required=True)
            command.add_argument("--intent-output", type=Path, required=True)
        if name == "send":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--media-recheck", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
        if name == "apply":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    release = load_release(args.release, args.root)
    if args.cmd == "preview":
        document, render, article = build_document(args.root, release)
        print(
            json.dumps(
                {
                    "release_id": RELEASE_ID,
                    "release_sha256": release_digest(release),
                    "owning_issue": OWNING_ISSUE,
                    "publication_id": PUBLICATION_ID,
                    "document_sha256": document.document_sha256,
                    "render_sha256": render.render_sha256,
                    "media_ids": [media.media_id for media in article.media],
                    "media_count": len(article.media),
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "ensure-ledger":
        ledger = load_ledger(args.ledger, release, create=True)
        _write(args.ledger, ledger)
        print(json.dumps({"state": _rich_entry(ledger)["state"], "provider_write_performed": False}))
        return 0
    if args.cmd == "guard":
        ledger = load_ledger(args.ledger, release)
        print(json.dumps(guard_state(args.root, args.state_root, release, ledger), ensure_ascii=False))
        return 0
    if args.cmd == "preflight":
        target_proof = run_preflight(args.root, release, token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"])
        _write(args.output, target_proof.model_dump(mode="json"))
        print(target_proof.model_dump_json())
        return 0
    if args.cmd == "media-proof":
        expected = _read(args.expected) if args.expected else None
        media_evidence = media_proof(args.root, release, expected=expected)
        _write(args.output, media_evidence)
        print(json.dumps(media_evidence, ensure_ascii=False))
        return 0
    if args.cmd == "prepare":
        ledger = load_ledger(args.ledger, release)
        intent, ledger = prepare(
            args.root,
            args.state_root,
            release,
            ledger,
            args.target_proof,
            _read(args.media_proof),
            repository=args.github_repository,
            sha=args.github_sha,
            run_id=args.run_id,
            attempt=args.run_attempt,
        )
        _write(args.intent_output, intent)
        _write(args.ledger, ledger)
        print(json.dumps(intent, ensure_ascii=False))
        return 0
    if args.cmd == "send":
        outcome = send(
            args.root,
            release,
            _read(args.intent),
            args.target_proof,
            _read(args.media_recheck),
            args.outcome,
            token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"],
        )
        print(outcome.model_dump_json())
        return 0
    if args.cmd == "apply":
        ledger = load_ledger(args.ledger, release)
        outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        ledger = apply(ledger, _read(args.intent), outcome)
        _write(args.ledger, ledger)
        print(json.dumps(_rich_entry(ledger), ensure_ascii=False))
        return 0
    if args.cmd == "status":
        ledger = load_ledger(args.ledger, release)
        print(json.dumps(_rich_entry(ledger), ensure_ascii=False))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
