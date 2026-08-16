from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED_PROJECT_KEY = "milovi-cake"
EXPECTED_CHANNEL_USERNAME = "@MiloviCake"
EXPECTED_CHAT_ID = -1002215328390
EXPECTED_BOT_ID = 8716602202
EXPECTED_BOT_USERNAME = "preaching_mp3_bot"
EXPECTED_BOOTSTRAP_COUNT = 10


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Milovi activation package JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Milovi activation package JSON must be an object: {path}")
    return payload


def _require_sha40(value: str, label: str) -> None:
    if not SHA40_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact lowercase Git SHA-1")


def _require_sha256(value: str, label: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact sha256 value")


def _require_profile(profile: TelegramChannelProfile) -> None:
    if (
        profile.project_key != EXPECTED_PROJECT_KEY
        or profile.channel_username.casefold() != EXPECTED_CHANNEL_USERNAME.casefold()
    ):
        raise ValueError("selected profile is not the reviewed Milovi Cake channel")
    if profile.provider_writes_authorized:
        raise ValueError("review-ready verification requires Milovi provider writes to remain disabled")


def _require_binding(binding: TelegramTargetBinding) -> None:
    if binding.provider_write_performed:
        raise ValueError("activation package target binding claims a provider write")
    if binding.chat_id != EXPECTED_CHAT_ID or binding.bot_id != EXPECTED_BOT_ID:
        raise ValueError("activation package target binding numeric identity mismatch")
    if binding.bot_username.casefold() != EXPECTED_BOT_USERNAME.casefold():
        raise ValueError("activation package target binding bot username mismatch")
    if not binding.can_post_messages:
        raise ValueError("activation package target binding does not prove posting rights")


def _require_unauthorized_release(release: GenericReleaseQueue, label: str) -> None:
    if release.release_authorized:
        raise ValueError(f"{label} must remain unauthorized")
    if release.reviewed_candidate_sha256 is not None or release.reviewed_by is not None or release.reviewed_at is not None:
        raise ValueError(f"{label} must not contain completed review metadata")
    if len(release.items) != EXPECTED_BOOTSTRAP_COUNT:
        raise ValueError(f"{label} must contain exactly ten bootstrap items")
    expected_ids = tuple(f"milovi-bootstrap-{number:03d}" for number in range(1, EXPECTED_BOOTSTRAP_COUNT + 1))
    if tuple(item.publication_id for item in release.items) != expected_ids:
        raise ValueError(f"{label} publication ids differ from the frozen bootstrap sequence")


def verify_review_ready_package(
    *,
    profile_path: Path,
    package_dir: Path,
    expected_main_sha: str,
    expected_target_binding_sha256: str,
    expected_bound_candidate_sha256: str,
    source_run_id: int,
    source_artifact_id: int,
    source_artifact_digest: str,
    checked_at: datetime,
) -> dict[str, Any]:
    _require_sha40(expected_main_sha, "expected main SHA")
    _require_sha256(expected_target_binding_sha256, "expected target binding digest")
    _require_sha256(expected_bound_candidate_sha256, "expected bound candidate digest")
    _require_sha256(source_artifact_digest, "source artifact digest")
    if source_run_id <= 0 or source_artifact_id <= 0:
        raise ValueError("source run and artifact ids must be positive")
    if checked_at.tzinfo is None:
        raise ValueError("review-ready checked_at must be timezone-aware")

    profile = load_channel_profile(profile_path)
    _require_profile(profile)
    summary = _read_json(package_dir / "summary.json")
    binding = load_target_binding(package_dir / "target-binding.json", profile)
    unbound = load_release(package_dir / "bootstrap-unbound.json")
    bound = load_release(package_dir / "bootstrap-bound-unauthorized.json")

    if summary.get("schema_name") != "video-channel-manager.milovi-bootstrap-activation-package":
        raise ValueError("activation package summary schema mismatch")
    if summary.get("schema_version") != 1:
        raise ValueError("activation package summary version mismatch")
    if summary.get("project_key") != EXPECTED_PROJECT_KEY:
        raise ValueError("activation package summary project mismatch")
    if str(summary.get("channel_username") or "").casefold() != EXPECTED_CHANNEL_USERNAME.casefold():
        raise ValueError("activation package summary channel mismatch")
    if summary.get("current_main_sha") != expected_main_sha:
        raise ValueError("activation package was not produced from the expected current main SHA")
    if summary.get("provider_access_mode") != "read_only_target_discovery_only":
        raise ValueError("activation package provider access mode is not read-only target discovery")
    if summary.get("provider_write_performed") is not False or summary.get("release_authorized") is not False:
        raise ValueError("activation package summary unexpectedly claims write or release authorization")
    if summary.get("profile_writes_required_to_remain_disabled") is not True:
        raise ValueError("activation package no longer requires the profile write gate to remain disabled")
    if summary.get("bootstrap_items") != EXPECTED_BOOTSTRAP_COUNT:
        raise ValueError("activation package summary bootstrap item count mismatch")

    _require_binding(binding)
    _require_unauthorized_release(unbound, "unbound bootstrap release")
    _require_unauthorized_release(bound, "bound bootstrap release")

    if any(
        value is not None
        for value in (unbound.target_binding_sha256, unbound.chat_id, unbound.bot_id, unbound.bot_username)
    ):
        raise ValueError("unbound bootstrap release unexpectedly contains target identity")
    if unbound.items != bound.items:
        raise ValueError("target binding changed bootstrap release items")
    if bound.target_binding_sha256 != binding.digest:
        raise ValueError("bound release target binding digest differs from packaged binding")
    if bound.chat_id != binding.chat_id or bound.bot_id != binding.bot_id:
        raise ValueError("bound release numeric target identity differs from packaged binding")
    if (bound.bot_username or "").casefold() != binding.bot_username.casefold():
        raise ValueError("bound release bot username differs from packaged binding")

    unbound_candidate_sha256 = unbound.candidate_digest()
    bound_candidate_sha256 = bound.candidate_digest()
    if unbound_candidate_sha256 == bound_candidate_sha256:
        raise ValueError("target binding did not change the candidate digest")
    if binding.digest != expected_target_binding_sha256:
        raise ValueError("packaged target binding digest differs from explicitly reviewed digest")
    if bound_candidate_sha256 != expected_bound_candidate_sha256:
        raise ValueError("packaged bound candidate digest differs from explicitly reviewed digest")
    if summary.get("target_binding_sha256") != binding.digest:
        raise ValueError("activation package summary target binding digest mismatch")
    if summary.get("unbound_candidate_sha256") != unbound_candidate_sha256:
        raise ValueError("activation package summary unbound candidate digest mismatch")
    if summary.get("bound_candidate_sha256") != bound_candidate_sha256:
        raise ValueError("activation package summary bound candidate digest mismatch")
    if summary.get("bound_release_sha256") != bound.digest:
        raise ValueError("activation package summary bound release digest mismatch")

    return {
        "schema_name": "video-channel-manager.milovi-bootstrap-review-ready-receipt",
        "schema_version": 1,
        "project_key": EXPECTED_PROJECT_KEY,
        "channel_username": EXPECTED_CHANNEL_USERNAME,
        "review_ready": True,
        "release_authorized": False,
        "provider_accessed_by_verifier": False,
        "provider_write_performed": False,
        "current_main_sha": expected_main_sha,
        "source_package_run_id": source_run_id,
        "source_artifact_id": source_artifact_id,
        "source_artifact_digest": source_artifact_digest,
        "target_binding_sha256": binding.digest,
        "unbound_candidate_sha256": unbound_candidate_sha256,
        "bound_candidate_sha256": bound_candidate_sha256,
        "bound_release_sha256": bound.digest,
        "chat_id": binding.chat_id,
        "bot_id": binding.bot_id,
        "bot_username": binding.bot_username,
        "checked_at": checked_at.isoformat(),
        "next_step": "separate explicit human authorization of this exact bound candidate digest",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an exact Milovi bootstrap package is ready for human review")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--expected-target-binding-sha256", required=True)
    parser.add_argument("--expected-bound-candidate-sha256", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--source-artifact-id", type=int, required=True)
    parser.add_argument("--source-artifact-digest", required=True)
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    checked_at = datetime.fromisoformat(args.checked_at.replace("Z", "+00:00"))
    receipt = verify_review_ready_package(
        profile_path=args.profile,
        package_dir=args.package_dir,
        expected_main_sha=args.expected_main_sha,
        expected_target_binding_sha256=args.expected_target_binding_sha256,
        expected_bound_candidate_sha256=args.expected_bound_candidate_sha256,
        source_run_id=args.source_run_id,
        source_artifact_id=args.source_artifact_id,
        source_artifact_digest=args.source_artifact_digest,
        checked_at=checked_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
