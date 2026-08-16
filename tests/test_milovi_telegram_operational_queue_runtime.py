from __future__ import annotations

from pathlib import Path

from video_channel_manager.milovi_telegram_bootstrap import (
    build_release_candidate,
    validate_bootstrap_bundle,
)
from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
QUEUE = ROOT / "content/telegram/milovi-cake/queues/bootstrap-first-screen-queue-2026-08.json"
CANDIDATES = ROOT / "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json"
PROOF = ROOT / "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json"
WINDOW = ROOT / "content/telegram/milovi-cake/publishing-window-2026-08.json"


def test_operational_queue_is_a_runtime_compatible_rollout_source() -> None:
    profile = load_channel_profile(PROFILE)
    rollout, _candidates, _proof, _window = validate_bootstrap_bundle(
        profile,
        rollout_path=QUEUE,
        candidates_path=CANDIDATES,
        transport_proof_path=PROOF,
        publishing_window_path=WINDOW,
    )
    assert rollout["queue_id"] == "milovi-first-screen-2026-08-17"

    release = build_release_candidate(
        profile,
        rollout_path=QUEUE,
        candidates_path=CANDIDATES,
        transport_proof_path=PROOF,
        publishing_window_path=WINDOW,
    )
    assert release.release_id == "milovi-telegram-first-screen-2026-08"
    assert release.release_authorized is False
    assert release.target_binding_sha256 is None
    assert release.items[0].publication_id == "milovi-bootstrap-001"
    assert release.items[0].scheduled_at.isoformat() == "2026-08-17T10:30:00+03:00"
    assert release.items[-1].publication_id == "milovi-bootstrap-010"
    assert release.items[-1].scheduled_at.isoformat() == "2026-08-21T20:00:00+03:00"
