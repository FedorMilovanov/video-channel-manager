from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_transport import GenericPhotoPayload
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
BINDING = ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
RELEASE = ROOT / "content/telegram/milovi-cake/oneoff-canary-authorized-release-2026-08-18.json"
AUTH = ROOT / "content/telegram/milovi-cake/oneoff-canary-execution-authorization-2026-08-18.json"
PROVIDER = ROOT / ".github/workflows/milovi-telegram-oneoff-canary.yml"
CONTROLLER = ROOT / ".github/workflows/milovi-telegram-oneoff-canary-dispatch.yml"


def test_oneoff_release_is_exact_and_separate_from_stale_bootstrap_identity() -> None:
    profile = load_channel_profile(PROFILE)
    binding = load_target_binding(BINDING, profile)
    release = load_release(RELEASE)

    assert release.digest == "sha256:04fd7792c9a2bb698259935ac81c5b04071f73883b3a9270eb324d3355b0ebfe"
    assert release.reviewed_candidate_sha256 == (
        "sha256:c83ae0f172341f2c247dcd3a150e7da8e6dcd423b026002b81d45b4d0963b39b"
    )
    assert release.release_authorized is True
    assert release.target_binding_sha256 == binding.digest
    assert len(release.items) == 1

    item = release.items[0]
    assert item.publication_id == "milovi-canary-20260818-001"
    assert item.publication_id != "milovi-bootstrap-003"
    assert item.scheduled_at.isoformat() == "2026-08-18T16:10:00+03:00"
    assert isinstance(item.payload, GenericPhotoPayload)
    assert item.payload.provider_payload_sha256 == (
        "sha256:60ba1bdd1e9a05d6bb7620951a5861140c253477c533be25d3aabe362c96cdef"
    )
    assert item.payload.media_sha256 == ("sha256:8bb0956e44084265d7a3a14ce01f96eb1e4a9c327c780448de34e068f6cf6f10")


def test_execution_authorization_is_one_operation_and_zero_blind_retries() -> None:
    release = load_release(RELEASE)
    auth = json.loads(AUTH.read_text(encoding="utf-8"))

    assert auth["release_digest"] == release.digest
    assert auth["publication_id"] == release.items[0].publication_id
    assert auth["execution_authorized"] is True
    assert auth["automatic_dispatch_authorized"] is True
    assert auth["max_provider_attempts"] == 1
    assert auth["blind_mutation_retries"] == 0
    assert auth["supersedes_publication_id"] == "milovi-bootstrap-003"
    assert auth["supersedes_only_if_prior_intent_absent"] is True
    assert auth["execute_not_before"] == "2026-08-18T16:10:00+03:00"
    assert auth["execute_not_after"] == "2026-08-18T18:10:00+03:00"


def test_provider_workflow_keeps_intent_before_send_and_quality_before_provider() -> None:
    text = PROVIDER.read_text(encoding="utf-8")
    activation = text.index("Resolve exact one-off execution authorization before provider access")
    quality = text.index("Require exact current-main one-off quality and media proofs")
    preflight = text.index("Fresh exact target preflight")
    prepare = text.index("Prepare one durable exact one-off intent")
    persist = text.index("Persist one-off intent and target proof before provider mutation")
    send = text.index("Send exactly once through generic Telegram runtime")
    outcome = text.index("Apply provider outcome and persist final state")

    assert activation < quality < preflight < prepare < persist < send < outcome
    assert "group: milovi-cake-telegram-publisher" in text
    assert "cancel-in-progress: false" in text
    assert "--mode manual" in text
    assert '--publication-id "$PUBLICATION_ID"' in text
    assert "blind replay is blocked" in text
    assert "schedule:" not in text.split("permissions:", 1)[0]


def test_controller_is_manual_exact_and_provider_inert() -> None:
    text = CONTROLLER.read_text(encoding="utf-8")
    trigger = text.split("permissions:", 1)[0]

    assert "schedule:" not in trigger
    assert "workflow_dispatch:" in trigger
    assert "confirm:" in trigger
    assert "Exact controller confirmation" in trigger
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "EXPECTED_CONTROLLER_CONFIRM: DISPATCH:@MiloviCake:milovi-canary-20260818-001" in text
    assert "PROVIDER_CONFIRM: PUBLISH:@MiloviCake:milovi-canary-20260818-001" in text
    assert "EXECUTION_AUTH_PATH:" in text
    assert 'authorization["execute_not_before"]' in text
    assert 'authorization["execute_not_after"]' in text
    assert "controller_dispatch_window_end" not in text
    assert "Fail closed when controller dispatch is unauthorized or expired" in text
    assert "Fail closed if provider workflow was already dispatched" in text
    assert "Re-prove main did not move before provider dispatch" in text
    assert "event=workflow_dispatch" in text
    assert "per_page=100" in text
    assert 'authorization["authorized_at"]' in text
    assert 'current_main="$(gh api' in text
    assert '[[ "$current_main" != "$GITHUB_SHA" ]]' in text
    assert "exit 3" in text
    assert "ci.yml" in text
    assert "milovi-telegram-oneoff-canary-quality.yml" in text
    assert "milovi-telegram-bootstrap-media-proof.yml" in text
    assert "LORDCHRIST_TELEGRAM_BOT_TOKEN" not in text
    assert "telegram_channel_cli preflight" not in text
    assert "send-once" not in text


def test_controller_does_not_mutate_historical_execution_authorization() -> None:
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    text = CONTROLLER.read_text(encoding="utf-8")

    assert auth["controller_dispatch_window_end"] == "2026-08-18T17:05:00+03:00"
    assert "controller_dispatch_window_end" not in text
    assert auth["execute_not_after"] == "2026-08-18T18:10:00+03:00"
