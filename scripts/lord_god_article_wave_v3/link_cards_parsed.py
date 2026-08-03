from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

from . import link_cards_hardened as core
from . import link_cards_hardened_entry as strict
from .common import (
    ACCOUNT_ALIAS,
    COMMUNITY_ID,
    DECISION_SET_ID,
    OWNER_ID,
    canonical_sha,
    canonical_text,
    now_iso,
    write_json,
)
from .parsed_link_contract import (
    LINK_PARSE_METHOD,
    WRITE_METHOD,
    execution_identity,
    load_journal,
    load_parsed_policy,
    observe_superseded_v2,
)
from .parsed_link_mutations import submit
from .parsed_link_preview import audit_parsed_link_cards
from .parsed_link_state import preflight, state_fingerprint
from .wall import wall_snapshot


def review_markdown(
    policy: dict[str, Any],
    contract: dict[str, Any],
    report: dict[str, Any],
    expectations: dict[str, dict[str, str]],
    parsed_items: list[dict[str, Any]],
) -> str:
    states = {item["operation_id"]: item["state"] for item in report["states"]}
    parsed = {item["operation_id"]: item for item in parsed_items}
    lines = [
        "# Господь Бог — Сила Моя: 10 parsed link-карточек",
        "",
        f"- Delivery contract: `{contract['contract_sha256']}`",
        f"- Подготовка ссылки: `{LINK_PARSE_METHOD}`.",
        f"- Запись: `{WRITE_METHOD}`.",
        "- Отдельные фотографии VK не загружаются и не прикрепляются.",
        "- Preview photo используется только как внутренний идентификатор карточки.",
        "- Порядок: Plan → Canary → ручная проверка → Apply.",
        "",
    ]
    for operation in policy["operations"]:
        operation_id = str(operation["operation_id"])
        expected = expectations[operation_id]
        parsed_item = parsed[operation_id]
        lines.extend(
            [
                f"## {operation['ordinal']}. {operation['title']}",
                "",
                f"- Время: `{operation['publish_at']}`",
                f"- Статус: `{states[operation_id]}`",
                f"- Link URL: {operation['url']}",
                f"- Parsed preview: `{parsed_item['link_photo_id']}`",
                f"- Ожидаемый заголовок: {expected['title']}",
                f"- Ожидаемое описание: {expected['description']}",
                "",
                str(operation["message"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def execute_scope(
    *,
    mode: str,
    policy: dict[str, Any],
    contract: dict[str, Any],
    expectations: dict[str, dict[str, str]],
    read_client: VkApiClient,
    mutation_client: VkApiClient,
    settings: Any,
    report: dict[str, Any],
    journal: dict[str, Any],
    journal_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if os.environ.get("VCM_ALLOW_WALL_POSTS") != "1":
        raise RuntimeError("Execution requires VCM_ALLOW_WALL_POSTS=1")

    states = {item["operation_id"]: item["state"] for item in report["states"]}
    canary = policy["operations"][0]
    canary_id = str(canary["operation_id"])
    if mode == "canary":
        selected = [canary]
        result_path = output_dir / "parsed-link-canary-result.json"
    elif mode == "apply":
        if states.get(canary_id) != "already_applied":
            raise RuntimeError("Apply requires the verified parsed link-card canary")
        selected = policy["operations"][1:]
        result_path = output_dir / "parsed-link-result.json"
    else:
        raise ValueError(f"Unsupported execution mode: {mode}")

    result: dict[str, Any] = {
        "schema_name": "video-manager.vk-lord-god-article-parsed-link-result",
        "schema_version": 3,
        "mode": mode,
        "status": "running",
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "parsed_link_execution_contract_sha256": execution_identity(policy, contract),
        "attachment_mode": contract["attachment_mode"],
        "link_preparation_method": LINK_PARSE_METHOD,
        "separate_vk_photo": False,
        "vk_photo_api_calls": 0,
        "started_at": now_iso(),
        "operations": [],
    }
    write_json(result_path, result)

    lock_path = settings.data_dir / "locks" / f"vk-wall-{COMMUNITY_ID}.lock"
    with local_vk_write_lock(
        lock_path,
        account=ACCOUNT_ALIAS,
        community_id=COMMUNITY_ID,
        operation=f"{DECISION_SET_ID}-parsed-link-{mode}",
    ):
        locked_published, locked_postponed = wall_snapshot(read_client)
        locked = preflight(
            policy,
            contract,
            expectations,
            locked_published,
            locked_postponed,
            journal,
        )
        if (
            locked["conflicts"]
            or state_fingerprint(locked) != state_fingerprint(report)
        ):
            raise RuntimeError(
                "Locked parsed link-card preflight differs from reviewed preflight"
            )
        locked_states = {
            item["operation_id"]: item["state"] for item in locked["states"]
        }

        for operation in selected:
            operation_id = str(operation["operation_id"])
            if locked_states[operation_id] == "already_applied":
                result["operations"].append(
                    {"operation_id": operation_id, "status": "already_applied"}
                )
                write_json(result_path, result)
                continue
            if locked_states[operation_id] != "ready":
                raise RuntimeError(f"Operation is not ready: {operation_id}")

            try:
                post_id, reference, parsed = submit(
                    operation=operation,
                    expected_metadata=expectations[operation_id],
                    policy=policy,
                    contract=contract,
                    read_client=read_client,
                    mutation_client=mutation_client,
                    journal=journal,
                    journal_path=journal_path,
                )
            except Exception as exc:
                entry = journal["operations"].get(operation_id)
                journal_stage = (
                    str(entry.get("stage") or "")
                    if isinstance(entry, dict)
                    else ""
                )
                result.update(
                    {
                        "status": "stopped",
                        "stopped_at": now_iso(),
                        "stopped_operation_id": operation_id,
                        "journal_stage": journal_stage or None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                write_json(result_path, result)
                raise

            card = reference["link_cards"][0]
            result["operations"].append(
                {
                    "operation_id": operation_id,
                    "post_id": post_id,
                    "status": "verified",
                    "publish_at": operation["publish_at"],
                    "parse_method": LINK_PARSE_METHOD,
                    "parsed_link_photo_id": parsed["link_photo_id"],
                    "single_link_attachment_verified": (
                        reference["attachment_types"] == ["link"]
                    ),
                    "link_title_verified": (
                        canonical_text(card["title"])
                        == canonical_text(expectations[operation_id]["title"])
                    ),
                    "link_description_verified": strict.strict_description_matches(
                        card["description"],
                        expectations[operation_id]["description"],
                    ),
                    "link_preview_photo_verified": bool(card["has_preview_photo"]),
                    "separate_photo_absent": not bool(reference["has_photo"]),
                }
            )
            write_json(result_path, result)
            print(
                f"SCHEDULED PARSED LINK CARD {operation['ordinal']}/10 "
                f"post={OWNER_ID}_{post_id} photo=no parse=yes "
                "title=yes description=yes preview=yes"
            )
            time.sleep(1)

        postflight_path = (
            output_dir / "parsed-link-canary-postflight.json"
            if mode == "canary"
            else output_dir / "parsed-link-postflight.json"
        )
        try:
            final_published, final_postponed = wall_snapshot(read_client)
            final = preflight(
                policy,
                contract,
                expectations,
                final_published,
                final_postponed,
                journal,
                minimum_future_seconds=0,
            )
            write_json(postflight_path, final)
        except Exception as exc:
            result.update(
                {
                    "status": "postflight_unknown",
                    "postflight": str(postflight_path),
                    "postflight_error": f"{type(exc).__name__}: {exc}",
                }
            )
            write_json(result_path, result)
            raise RuntimeError(
                f"{mode.capitalize()} parsed link-card postflight outcome is unknown"
            ) from exc

        expected_applied = 1 if mode == "canary" else 10
        expected_ready = 9 if mode == "canary" else 0
        if (
            final["conflicts"]
            or final["already_applied"] != expected_applied
            or final["ready"] != expected_ready
        ):
            result.update(
                {
                    "status": "postflight_failed",
                    "postflight": str(postflight_path),
                    "postflight_conflicts": final["conflicts"],
                    "postflight_already_applied": final["already_applied"],
                    "postflight_ready": final["ready"],
                }
            )
            write_json(result_path, result)
            raise RuntimeError(
                f"{mode.capitalize()} parsed link-card postflight rejected the result"
            )

        verified_now = sum(
            1 for item in result["operations"] if item.get("status") == "verified"
        )
        result.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "verified_operations": expected_applied,
                "verified_parsed_link_cards": expected_applied,
                "verified_single_link_attachments": expected_applied,
                "verified_link_titles": expected_applied,
                "verified_link_descriptions": expected_applied,
                "verified_link_preview_photos": expected_applied,
                "verified_posts_without_separate_photos": expected_applied,
                "verified_operations_this_run": verified_now,
                "conflicts": 0,
                "postflight": str(postflight_path),
                "first_publish_at": policy["summary"]["first_publish_at"],
                "last_publish_at": (
                    canary["publish_at"]
                    if mode == "canary"
                    else policy["summary"]["last_publish_at"]
                ),
            }
        )
        write_json(result_path, result)
    return result


def run(repo: Path, *, mode: str) -> int:
    repo = repo.resolve()
    output_dir = repo / "data" / "vk-wall" / DECISION_SET_ID
    output_dir.mkdir(parents=True, exist_ok=True)

    policy, contract = load_parsed_policy(repo)
    write_json(output_dir / "parsed-link-plan.json", policy)
    write_json(output_dir / "parsed-link-delivery-contract.json", contract)

    source_rows, source_manifest = strict.audit_sources(policy, contract)
    source_audit_path = output_dir / "parsed-link-source-audit.json"
    write_json(source_audit_path, source_manifest)
    expectations = core.build_link_expectations(source_rows)
    expected_source_summary = {
        "schema_version": 2,
        "status": "verified",
        "expected_external_resources": 40,
        "external_urls_checked": 40,
        "article_pages_verified": 10,
        "live_content_markers_verified": 10,
        "og_images_verified": 10,
        "og_image_dimensions_verified": 10,
        "pinned_source_files_verified": 10,
        "pinned_metadata_files_verified": 10,
        "live_metadata_matches_pinned_source": 10,
        "prepared_jpeg_assets": 0,
        "vk_photo_uploads_required": False,
        "conflicts": 0,
    }
    source_gate_errors = [
        f"{key}={source_manifest.get(key)!r}, expected {value!r}"
        for key, value in expected_source_summary.items()
        if source_manifest.get(key) != value
    ]
    if source_gate_errors:
        print(json.dumps(source_manifest, ensure_ascii=False, indent=2))
        raise RuntimeError(
            "Parsed link-card source audit blocked the queue: "
            + "; ".join(source_gate_errors)
            + f"; all findings are in {source_audit_path}"
        )

    settings = get_settings()
    read_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=4,
    )
    mutation_client = VkApiClient(
        token_store=VkTokenStore(settings.data_dir),
        account_alias=ACCOUNT_ALIAS,
        api_version=settings.vk_api_version,
        max_attempts=1,
    )
    community = read_client.get_community(COMMUNITY_ID)
    if (
        community.ref.remote_id != str(COMMUNITY_ID)
        or not community.metadata.get("managed_by_token")
    ):
        raise RuntimeError("Stored token does not manage VK community 60805374")

    parsed_items, parsed_audit = audit_parsed_link_cards(
        read_client,
        policy,
        expectations,
    )
    parsed_audit.update(
        {
            "policy_sha256": policy["policy_sha256"],
            "source_contract_sha256": policy["source_contract_sha256"],
            "delivery_contract_sha256": contract["contract_sha256"],
            "parsed_link_execution_contract_sha256": execution_identity(
                policy, contract
            ),
        }
    )
    parsed_audit["report_sha256"] = canonical_sha(
        {key: value for key, value in parsed_audit.items() if key != "report_sha256"}
    )
    parsed_audit_path = output_dir / "parsed-link-preview-audit.json"
    write_json(parsed_audit_path, parsed_audit)
    if (
        parsed_audit["calls"] != 10
        or parsed_audit["verified"] != 10
        or parsed_audit["conflicts"] != 0
    ):
        print(json.dumps(parsed_audit, ensure_ascii=False, indent=2))
        raise RuntimeError(
            f"wall.parseAttachedLink audit blocked the queue; see {parsed_audit_path}"
        )

    v2_observation = observe_superseded_v2(
        output_dir / "link-card-journal-v2.json",
        policy,
    )
    v2_observation_path = output_dir / "superseded-link-card-v2-observation.json"
    write_json(v2_observation_path, v2_observation)

    journal_path = output_dir / "parsed-link-journal-v3.json"
    journal = load_journal(journal_path, policy, contract)
    write_json(journal_path, journal)

    published, postponed = wall_snapshot(read_client)
    report = preflight(
        policy,
        contract,
        expectations,
        published,
        postponed,
        journal,
    )
    preflight_path = output_dir / "parsed-link-preflight.json"
    write_json(preflight_path, report)
    review_path = output_dir / "parsed-link-plan-review.md"
    review_path.write_text(
        review_markdown(policy, contract, report, expectations, parsed_items),
        encoding="utf-8",
    )

    summary = {
        "mode": mode,
        "policy_sha256": policy["policy_sha256"],
        "source_contract_sha256": policy["source_contract_sha256"],
        "delivery_contract_sha256": contract["contract_sha256"],
        "parsed_link_execution_contract_sha256": execution_identity(
            policy, contract
        ),
        "attachment_mode": contract["attachment_mode"],
        "asset_mode": contract["asset_mode"],
        "link_preparation_method": LINK_PARSE_METHOD,
        "description_match_mode": strict.DESCRIPTION_MATCH_MODE,
        **{key: source_manifest[key] for key in expected_source_summary},
        "parsed_link_calls": parsed_audit["calls"],
        "parsed_link_cards_verified": parsed_audit["verified"],
        "parsed_link_conflicts": parsed_audit["conflicts"],
        "vk_photo_api_calls": 0,
        "legacy_v2_rejection_observed": bool(v2_observation["observed_operations"]),
        "legacy_v2_rejection_safe_to_supersede": v2_observation[
            "safe_to_supersede"
        ],
        "operations": report["total_operations"],
        "ready": report["ready"],
        "already_applied": report["already_applied"],
        "conflicts": report["conflicts"],
        "postponed_wall_posts_seen": report["postponed_wall_posts"],
        "minimum_gap_minutes": report["minimum_gap_minutes"],
        "first_publish_at": policy["summary"]["first_publish_at"],
        "last_publish_at": policy["summary"]["last_publish_at"],
        "preflight": str(preflight_path),
        "source_audit": str(source_audit_path),
        "parsed_link_audit": str(parsed_audit_path),
        "plan_review": str(review_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["conflicts"]:
        raise RuntimeError(
            "Parsed link-card article queue blocked: "
            + "; ".join(report["global_conflicts"])
        )

    if mode == "plan":
        print(
            "READ-ONLY PARSED LINK-CARD PLAN COMPLETE. "
            "wall.parseAttachedLink was called for ten URLs; "
            "no photo upload, photo save, or wall.post was sent."
        )
        return 0

    result = execute_scope(
        mode=mode,
        policy=policy,
        contract=contract,
        expectations=expectations,
        read_client=read_client,
        mutation_client=mutation_client,
        settings=settings,
        report=report,
        journal=journal,
        journal_path=journal_path,
        output_dir=output_dir,
    )
    result_path = output_dir / (
        "parsed-link-canary-result.json"
        if mode == "canary"
        else "parsed-link-result.json"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": mode,
                "verified_operations": result["verified_operations"],
                "verified_parsed_link_cards": result[
                    "verified_parsed_link_cards"
                ],
                "verified_single_link_attachments": result[
                    "verified_single_link_attachments"
                ],
                "verified_link_titles": result["verified_link_titles"],
                "verified_link_descriptions": result[
                    "verified_link_descriptions"
                ],
                "verified_link_preview_photos": result[
                    "verified_link_preview_photos"
                ],
                "verified_posts_without_separate_photos": result[
                    "verified_posts_without_separate_photos"
                ],
                "result_path": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--canary", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    selected_mode = "canary" if args.canary else "apply" if args.execute else "plan"
    return run(args.repo, mode=selected_mode)


def guarded_main() -> None:
    try:
        raise SystemExit(main())
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        VkApiError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
