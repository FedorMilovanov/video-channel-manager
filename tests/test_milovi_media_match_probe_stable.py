from pathlib import Path

from video_channel_manager.platforms.vk import milovi_media_match_probe as base
from video_channel_manager.platforms.vk import milovi_media_match_probe_stable as stable_probe
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence


def test_exact_vk_capture_url_binds_owner_and_video_id() -> None:
    assert (
        stable_sequence._vk_capture_url("-68859909_456239182")
        == "https://vk.com/clip_ext.php?oid=-68859909&id=456239182&autoplay=1"
    )
    assert stable_sequence._stable_identity_url_matches(
        platform="vk",
        expected_id="-68859909_456239182",
        raw_url="https://vk.com/clip_ext.php?oid=-68859909&id=456239182&autoplay=1",
    )
    assert not stable_sequence._stable_identity_url_matches(
        platform="vk",
        expected_id="-68859909_456239182",
        raw_url="https://vk.com/clip_ext.php?oid=-68859909&id=456239172&autoplay=1",
    )


def test_stable_probe_installs_exact_isolated_transport_and_restores(monkeypatch, tmp_path: Path) -> None:
    original_capture = sequence._capture_page_sequence
    original_identity = sequence._identity_url_matches
    observed = {}

    def fake_build_media_match_probe(**kwargs):
        observed["capture"] = sequence._capture_page_sequence
        observed["identity"] = sequence._identity_url_matches
        observed["kwargs"] = kwargs
        return {
            "status": "completed",
            "browser_probe": {"youtube_capture_count": 11, "vk_capture_count": 16},
            "exhaustive_thumbnail_review": {
                "candidate_count": 13,
                "pair_space_reviewed": 1378,
                "selected_sequence_probe_pair_count": 18,
            },
        }

    monkeypatch.setattr(base, "build_media_match_probe", fake_build_media_match_probe)

    result = stable_probe.build_media_match_probe(
        final_input=tmp_path / "final.zip",
        gap_input=tmp_path / "gap.zip",
        output_dir=tmp_path / "out",
        zip_output=tmp_path / "out.zip",
        browser_executable=None,
        headless=True,
        wait_ms=750,
    )

    assert result["status"] == "completed"
    assert observed["capture"] is stable_sequence._isolated_capture_page_sequence
    assert observed["identity"] is stable_sequence._stable_identity_url_matches
    assert sequence._capture_page_sequence is original_capture
    assert sequence._identity_url_matches is original_identity
    assert observed["kwargs"]["headless"] is True
    assert observed["kwargs"]["wait_ms"] == 750
