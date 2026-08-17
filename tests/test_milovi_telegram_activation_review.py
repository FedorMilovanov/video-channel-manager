from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_activation_review import verify_review_ready_package
from video_channel_manager.milovi_telegram_bootstrap import build_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release, save_release
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_release_binding import bind_release_candidate
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding, target_binding_from_proof

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content" / "telegram" / "channels" / "milovi-cake.json"
MILOVI = ROOT / "content" / "telegram" / "milovi-cake"
MAIN_SHA = "a" * 40
ARTIFACT_DIGEST = "sha256:" + "b" * 64


def _write_inert_profile(tmp_path: Path) -> Path:
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert payload["provider_writes_authorized"] is True
    payload["provider_writes_authorized"] = False
    path = tmp_path / "write-disabled-milovi-profile.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _package(tmp_path: Path) -> tuple[Path, str, str]:
    profile_path = _write_inert_profile(tmp_path)
    profile = load_channel_profile(profile_path)
    proof = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="milovi-cake",
        channel_username="@MiloviCake",
        profile_sha256=profile.digest,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1002215328390,
        chat_username="MiloviCake",
        chat_title="Milovi Cake",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 8, 17, 0, 30, tzinfo=UTC),
    )
    binding = target_binding_from_proof(profile, proof)
    unbound = build_release_candidate(
        profile,
        rollout_path=MILOVI / "bootstrap-rollout-candidate-2026-08.json",
        candidates_path=MILOVI / "bootstrap-first-screen-candidates-2026-08.json",
        transport_proof_path=MILOVI / "bootstrap-photo-transport-proof-2026-08.json",
        publishing_window_path=MILOVI / "publishing-window-2026-08.json",
    )
    bound = bind_release_candidate(
        unbound,
        profile=profile,
        binding=binding,
        expected_unbound_candidate_sha256=unbound.candidate_digest(),
    )

    package = tmp_path / "package"
    package.mkdir()
    (package / "profile.json").write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    (package / "target-binding.json").write_text(binding.model_dump_json(indent=2) + "\n", encoding="utf-8")
    save_release(package / "bootstrap-unbound.json", unbound)
    save_release(package / "bootstrap-bound-unauthorized.json", bound)
    summary = {
        "schema_name": "video-channel-manager.milovi-bootstrap-activation-package",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "channel_username": "@MiloviCake",
        "current_main_sha": MAIN_SHA,
        "provider_access_mode": "read_only_target_discovery_only",
        "provider_write_performed": False,
        "release_authorized": False,
        "profile_writes_required_to_remain_disabled": True,
        "chat_id": -1002215328390,
        "bot_id": 8716602202,
        "bot_username": "preaching_mp3_bot",
        "target_binding_sha256": binding.digest,
        "unbound_candidate_sha256": unbound.candidate_digest(),
        "bound_candidate_sha256": bound.candidate_digest(),
        "bound_release_sha256": bound.digest,
        "bootstrap_items": 10,
    }
    (package / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return package, binding.digest, bound.candidate_digest()


def _verify(package: Path, binding_digest: str, bound_digest: str) -> dict[str, object]:
    return verify_review_ready_package(
        profile_path=package / "profile.json",
        package_dir=package,
        expected_main_sha=MAIN_SHA,
        expected_target_binding_sha256=binding_digest,
        expected_bound_candidate_sha256=bound_digest,
        source_run_id=123456,
        source_artifact_id=987654,
        source_artifact_digest=ARTIFACT_DIGEST,
        checked_at=datetime(2026, 8, 17, 0, 45, tzinfo=UTC),
    )


def test_real_frozen_bootstrap_package_becomes_review_ready_but_not_authorized(tmp_path: Path) -> None:
    package, binding_digest, bound_digest = _package(tmp_path)

    receipt = _verify(package, binding_digest, bound_digest)

    assert receipt["review_ready"] is True
    assert receipt["release_authorized"] is False
    assert receipt["provider_accessed_by_verifier"] is False
    assert receipt["provider_write_performed"] is False
    assert receipt["current_main_sha"] == MAIN_SHA
    assert receipt["target_binding_sha256"] == binding_digest
    assert receipt["bound_candidate_sha256"] == bound_digest
    assert receipt["source_package_run_id"] == 123456
    assert receipt["source_artifact_digest"] == ARTIFACT_DIGEST


def test_review_ready_rejects_explicit_digest_or_main_drift(tmp_path: Path) -> None:
    package, binding_digest, bound_digest = _package(tmp_path)

    with pytest.raises(ValueError, match="explicitly reviewed digest"):
        verify_review_ready_package(
            profile_path=package / "profile.json",
            package_dir=package,
            expected_main_sha=MAIN_SHA,
            expected_target_binding_sha256=binding_digest,
            expected_bound_candidate_sha256="sha256:" + "0" * 64,
            source_run_id=123456,
            source_artifact_id=987654,
            source_artifact_digest=ARTIFACT_DIGEST,
            checked_at=datetime(2026, 8, 17, 0, 45, tzinfo=UTC),
        )

    summary_path = package / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["current_main_sha"] = "c" * 40
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected current main SHA"):
        _verify(package, binding_digest, bound_digest)


def test_review_ready_rejects_already_authorized_release(tmp_path: Path) -> None:
    package, binding_digest, bound_digest = _package(tmp_path)
    profile = load_channel_profile(package / "profile.json")
    binding = load_target_binding(package / "target-binding.json", profile)
    bound = load_release(package / "bootstrap-bound-unauthorized.json")
    authorized = authorize_release_candidate(
        bound,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=bound.candidate_digest(),
        reviewed_by="test-reviewer",
        reviewed_at=datetime(2026, 8, 17, 0, 50, tzinfo=UTC),
    )
    save_release(package / "bootstrap-bound-unauthorized.json", authorized)

    with pytest.raises(ValueError, match="must remain unauthorized"):
        _verify(package, binding_digest, bound_digest)


def test_review_verifier_has_no_provider_client_or_secret_dependency() -> None:
    source = (ROOT / "src/video_channel_manager/milovi_telegram_activation_review.py").read_text(encoding="utf-8")
    for forbidden in (
        "httpx",
        "urllib.request",
        "preflight_channel",
        "discover_channel_target",
        "BOT_TOKEN",
        "os.environ",
        "sendMessage",
        "sendPhoto",
        "sendPoll",
    ):
        assert forbidden not in source
