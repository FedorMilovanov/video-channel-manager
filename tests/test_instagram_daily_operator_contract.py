from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operator" / "Invoke-InstagramDailyQueue.ps1"


def test_daily_operator_is_provider_inert_and_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '$env:VCM_INSTAGRAM_WRITES_ENABLED = "false"' in text
    assert "publish --execute" not in text
    assert "Meta provider writes: disabled." in text
    assert "durable ledger status is" in text
    assert "reconcile before advancing" in text


def test_daily_operator_requires_exact_public_integrity_path() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "instagram production validate-local" in text
    assert "instagram production validate-public" in text
    assert "release-assets.githubusercontent.com" in text
    assert "gh.exe release upload" in text


def test_daily_operator_never_skips_nonfinal_provider_state() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '$LedgerStatus -and $LedgerStatus -ne "planned"' in text
    assert '$LedgerStatus -eq "published"' in text

def test_daily_operator_closed_gop_fallback_is_narrow_and_deterministic() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'if ($ValidationText -notmatch "closed-GOP|closed GOP|non_idr_intra_frame")' in text
    assert "fallback transcode is refused" in text
    assert '-c:v libx264 -preset medium -crf 18 -profile:v high -pix_fmt yuv420p' in text
    assert '-g 60 -keyint_min 60 -sc_threshold 0' in text
    assert 'open-gop=0:scenecut=0:keyint=60:min-keyint=60' in text
    assert "fallback transcode still failed validate-local" in text
