from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.milovi_telegram_follow_on import (
    build_readiness_template,
    validate_follow_on_bundle,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger

EXPECTED_PROJECT_KEY = "milovi-cake"
EXPECTED_FINAL_PUBLICATION_ID = "milovi-bootstrap-010"
EXPECTED_CHAT_ID = -1002215328390
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
TERMINAL_STATES = {"published", "skipped"}

ORDER_QUICK_CALC = (
    "Напишите повод, дату, примерный вес или количество гостей и пожелания по декору — "
    "мы подскажем формат и ориентировочную цену."
)
ORDER_TIMING = (
    "Обычно лучше писать за 2–3 дня, а сложные 3D и свадебные торты согласовывать заранее. "
    "Срочные заказы обсуждаются индивидуально."
)
BENTO_INSCRIPTION = (
    "Да, можно короткую фразу, имя, дату, шутку или признание. Если текст длинный, подскажем как красиво разместить."
)
SCHOOL_PUBLICATION_IDS = {
    "milovi-follow-on-003": "laduree-1862",
    "milovi-follow-on-007": "paris-brest-race-dessert",
    "milovi-follow-on-011": "careme-first-celebrity-chef",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"unable to read readiness source snapshot {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid readiness JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"readiness JSON must contain an object: {path}")
    return value


def _school_expected_titles(candidates: dict[str, Any]) -> dict[str, str]:
    items = candidates.get("items")
    if not isinstance(items, list):
        raise ValueError("Milovi follow-on candidates have no items")
    pool_path = candidates.get("source_bindings", {}).get("school_pool_path")
    if not isinstance(pool_path, str) or not pool_path:
        raise ValueError("Milovi follow-on candidates lost School pool binding")
    pool = _read_json(Path(pool_path))
    pool_items = pool.get("candidates")
    if not isinstance(pool_items, list):
        raise ValueError("Milovi School candidate pool has no candidates")
    by_id = {
        str(item.get("candidate_id")): item
        for item in pool_items
        if isinstance(item, dict) and item.get("candidate_id")
    }
    titles: dict[str, str] = {}
    for publication_id, slug in SCHOOL_PUBLICATION_IDS.items():
        wave_item = next(
            (item for item in items if isinstance(item, dict) and item.get("publication_id") == publication_id),
            None,
        )
        if wave_item is None:
            raise ValueError(f"missing School follow-on publication: {publication_id}")
        if wave_item.get("source_slug") != slug:
            raise ValueError(f"School source slug drift for {publication_id}")
        candidate_id = str(wave_item.get("school_candidate_id") or "")
        source = by_id.get(candidate_id)
        if source is None or source.get("source_slug") != slug:
            raise ValueError(f"School pool binding drift for {publication_id}")
        title = str(source.get("source_title") or "")
        if not title:
            raise ValueError(f"School source title missing for {publication_id}")
        titles[slug] = title
    return titles


def _source_revalidation_blockers(
    *,
    candidates: dict[str, Any],
    order_html: str,
    bento_html: str,
    school_articles: str,
) -> list[str]:
    blockers: list[str] = []
    if ORDER_QUICK_CALC not in order_html:
        blockers.append("cake_order_quick_calc_source_drift")
    if ORDER_TIMING not in order_html:
        blockers.append("cake_order_timing_source_drift")
    if BENTO_INSCRIPTION not in bento_html:
        blockers.append("cake_bento_inscription_source_drift")

    for slug, title in _school_expected_titles(candidates).items():
        if f"id: '{slug}'" not in school_articles:
            blockers.append(f"school_article_missing:{slug}")
        if f"title: '{title}'" not in school_articles:
            blockers.append(f"school_article_title_drift:{slug}")
    return blockers


def build_readiness_result(
    *,
    profile_path: Path,
    candidates_path: Path,
    transport_manifest_path: Path,
    policy_path: Path,
    bootstrap_release_path: Path,
    bootstrap_ledger_path: Path,
    order_snapshot_path: Path,
    bento_snapshot_path: Path,
    school_articles_snapshot_path: Path,
    cake_source_commit: str,
    school_source_commit: str,
    checked_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if checked_at.tzinfo is None:
        raise ValueError("readiness checked_at must be timezone-aware")
    checked_at = checked_at.astimezone(UTC)
    profile = load_channel_profile(profile_path)
    candidates, transport, policy = validate_follow_on_bundle(
        profile,
        candidates_path=candidates_path,
        transport_manifest_path=transport_manifest_path,
        policy_path=policy_path,
    )
    template = build_readiness_template(candidates=candidates, transport=transport, policy=policy)
    blockers: list[str] = []
    bootstrap_verified_at: datetime | None = None

    if not bootstrap_release_path.is_file():
        blockers.append("bootstrap_authorized_release_missing")
    if not bootstrap_ledger_path.is_file():
        blockers.append("bootstrap_state_ledger_missing")

    if not blockers:
        try:
            bootstrap_release = load_release(bootstrap_release_path)
            if not bootstrap_release.release_authorized:
                blockers.append("bootstrap_release_not_authorized")
            elif bootstrap_release.project_key != EXPECTED_PROJECT_KEY:
                blockers.append("bootstrap_release_project_drift")
            else:
                ledger = load_ledger(bootstrap_ledger_path, bootstrap_release)
                if set(entry.state for entry in ledger.entries.values()) - TERMINAL_STATES:
                    blockers.append("bootstrap_queue_not_terminal")
                final_entry = ledger.entries.get(EXPECTED_FINAL_PUBLICATION_ID)
                if final_entry is None:
                    blockers.append("bootstrap_final_publication_missing")
                elif final_entry.state != "published" or final_entry.provider_effect != "verified":
                    blockers.append("bootstrap_final_not_verified")
                elif final_entry.published_at_utc is None:
                    blockers.append("bootstrap_final_verified_timestamp_missing")
                elif (
                    final_entry.actual_chat_id != EXPECTED_CHAT_ID
                    or final_entry.bot_id != EXPECTED_BOT_ID
                    or (final_entry.bot_username or "").casefold() != EXPECTED_BOT_USERNAME
                ):
                    blockers.append("bootstrap_final_target_identity_drift")
                else:
                    bootstrap_verified_at = final_entry.published_at_utc.astimezone(UTC)
        except ValueError as exc:
            blockers.append(f"bootstrap_state_invalid:{exc}")

    source_paths = (order_snapshot_path, bento_snapshot_path, school_articles_snapshot_path)
    if not all(path.is_file() for path in source_paths):
        blockers.append("current_source_snapshot_missing")
    else:
        try:
            blockers.extend(
                _source_revalidation_blockers(
                    candidates=candidates,
                    order_html=_read_text(order_snapshot_path),
                    bento_html=_read_text(bento_snapshot_path),
                    school_articles=_read_text(school_articles_snapshot_path),
                )
            )
        except ValueError as exc:
            blockers.append(f"source_revalidation_invalid:{exc}")

    ready = not blockers and bootstrap_verified_at is not None
    report = {
        "schema_name": "video-channel-manager.milovi-follow-on-readiness-report",
        "schema_version": 1,
        "project_key": EXPECTED_PROJECT_KEY,
        "ready": ready,
        "blockers": blockers,
        "checked_at_utc": checked_at.isoformat(),
        "cake_source_commit": cake_source_commit,
        "school_source_commit": school_source_commit,
        "bootstrap_final_publication_id": EXPECTED_FINAL_PUBLICATION_ID,
        "bootstrap_final_verified_at": bootstrap_verified_at.isoformat() if bootstrap_verified_at else None,
        "candidate_canonical_sha256": template["candidate_canonical_sha256"],
        "media_manifest_canonical_sha256": template["media_manifest_canonical_sha256"],
        "provider_write_performed": False,
        "telegram_provider_accessed": False,
        "state_branch_write_performed": False,
    }
    if not ready:
        return report, None

    assert bootstrap_verified_at is not None
    receipt = dict(template)
    receipt.update(
        {
            "status": "verified_current_sources",
            "bootstrap_terminal_status": "verified",
            "bootstrap_final_verified_at": bootstrap_verified_at.isoformat(),
            "source_revalidated_at": checked_at.isoformat(),
            "cake_source_commit": cake_source_commit,
            "school_source_commit": school_source_commit,
        }
    )
    return report, receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a read-only Milovi follow-on readiness report")
    parser.add_argument("--profile", type=Path, default=Path("content/telegram/channels/milovi-cake.json"))
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-wave-candidates-2026-08.json"),
    )
    parser.add_argument(
        "--transport-manifest",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-photo-source-manifest-2026-08.json"),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("content/telegram/milovi-cake/follow-on-release-policy-2026-08.json"),
    )
    parser.add_argument("--bootstrap-release", type=Path, required=True)
    parser.add_argument("--bootstrap-ledger", type=Path, required=True)
    parser.add_argument("--order-snapshot", type=Path, required=True)
    parser.add_argument("--bento-snapshot", type=Path, required=True)
    parser.add_argument("--school-articles-snapshot", type=Path, required=True)
    parser.add_argument("--cake-source-commit", required=True)
    parser.add_argument("--school-source-commit", required=True)
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    checked_at = datetime.fromisoformat(args.checked_at)
    report, receipt = build_readiness_result(
        profile_path=args.profile,
        candidates_path=args.candidates,
        transport_manifest_path=args.transport_manifest,
        policy_path=args.policy,
        bootstrap_release_path=args.bootstrap_release,
        bootstrap_ledger_path=args.bootstrap_ledger,
        order_snapshot_path=args.order_snapshot,
        bento_snapshot_path=args.bento_snapshot,
        school_articles_snapshot_path=args.school_articles_snapshot,
        cake_source_commit=args.cake_source_commit,
        school_source_commit=args.school_source_commit,
        checked_at=checked_at,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif args.receipt.exists():
        args.receipt.unlink()
    print(json.dumps({"ready": report["ready"], "blockers": report["blockers"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
