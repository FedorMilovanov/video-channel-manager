"""Static release contracts for the one-owner Milovi Cake HTTPS canary.

The real PowerShell dry-run is separately exercised on the Windows scheduler
host with read-only Graph calls. These tests never perform provider writes.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "instagram" / "milovi_cake_due_slot_single_writer.ps1"
CANARY = ROOT / "scripts" / "instagram" / "milovi_cake_https_single_slot_20261114.ps1"

KEY = "milovi-cake.2026-11-14.yt-fbGZYKS7byM.public-https-v1"
SOURCE_SHA = "54b6731ca166a25405fb1ff135eb9bf5c0905a9bd5d03241ef432a80b692d2d3"
INDEX_SHA = "19a211320f32e3c0f16c0aad1ed23db4b2bd89f100bbd22b8d1b801734aba5a4"
MANIFEST_SHA = "52c40517d3fa32ab4c4912f09a5ca47b5de7f9ba3bd346817468ba44f353bdde"


def test_single_writer_retains_existing_exclusive_lock() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "milovi-reels-single-writer.lock" in source
    assert "[System.IO.FileShare]::None" in source
    assert "$Lock.Dispose()" in source
    assert "AddMinutes(18)" in source
    assert "milovi_original_audio_owner_risk_release.ps1" in source
    assert "milovi_cake_https_single_slot_20261114.ps1" in source
    assert "$UrlOnly" in source
    assert "TRANSPORT=" in source
    assert "No silent fallback to rupload" in source
    assert INDEX_SHA in source
    assert "-OwnerApprovalFile $ack -Execute" in source


def test_canary_is_bound_to_exact_approval_and_immutable_media() -> None:
    source = CANARY.read_text(encoding="utf-8")
    for value in (
        KEY,
        SOURCE_SHA,
        INDEX_SHA,
        MANIFEST_SHA,
        "fbGZYKS7byM",
        "2026-11-14T19:00:00",
        "17841407843933779",
        "989716813600695",
        "fedormilovanov.github.io",
        "11400270",
        "accepts_unverified_crossplatform_audio_risk",
        "source_owned_youtube_channel_verified",
        "caption_editorially_reviewed",
    ):
        assert value in source


def test_canary_does_not_create_a_second_writer_or_automatic_retry() -> None:
    source = CANARY.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    assert "if ($Execute -and ($Msk -lt $Slot -or $Msk -ge $Slot.AddMinutes(18)))" in source
    assert "if (!$Execute)" in source
    assert "VCM_INSTAGRAM_WRITES_ENABLED = 'false'" in source
    assert "VCM_INSTAGRAM_WRITES_ENABLED = 'true'" in source
    assert "& $Cli instagram production publish $ManifestPath --execute" in source
    assert "Any previous durable attempt blocks re-dispatch of this source" in source
    assert "instr(publication_key, ?) > 0" in source
    assert "mode=ro" in source
    assert "one-writer OS file lock" in source
    assert "Start-ScheduledTask" not in source + runner
    assert "Register-ScheduledTask" not in source + runner
    assert "Invoke-RestMethod -Method POST" not in source + runner
    assert "publish-local" not in source
    assert "retry" not in source.lower().replace("never retry", "")
