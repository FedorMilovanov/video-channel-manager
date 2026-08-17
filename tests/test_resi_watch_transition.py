from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.resi_handoff import canonical_source_identity
from video_channel_manager.resi_watch import (
    ManifestObservation,
    PageProbeResult,
    ResiWatchAmbiguous,
    extract_resi_player_id,
    source_fingerprint,
    watch_for_new_manifest,
)

RU_PAGE = "https://www.gracechurch.org/live?language=russian"
RU_FRAME = "https://control.resi.io/webplayer/video.html?id=52260827-f6e9-4a2e-8978-aed53dbf1413"
RU_OLD = "https://resi.media/GiHDtf/a19407ff-e767-4a17-87d0-f3758bd87bfe/Manifest.mpd?src=emb"
RU_NEW = "https://resi.media/GiHDtf/e4335292-5fe8-4525-b6c0-845265e30192/Manifest.mpd?src=emb"
RU_OTHER_NEW = "https://resi.media/GiHDtf/11111111-2222-3333-4444-555555555555/Manifest.mpd?src=emb"


def obs(manifest: str) -> ManifestObservation:
    return ManifestObservation(
        page_url=RU_PAGE,
        final_page_url=RU_PAGE,
        manifest_url=manifest,
        source_identity=canonical_source_identity(manifest),
        source_fingerprint=source_fingerprint(manifest),
        frame_url=RU_FRAME,
        player_id=extract_resi_player_id(RU_FRAME),
    )


def test_known_baseline_plus_one_new_manifest_in_same_probe_captures_new(tmp_path: Path) -> None:
    result = PageProbeResult(RU_PAGE, RU_PAGE, (obs(RU_OLD), obs(RU_NEW)))

    payload = watch_for_new_manifest(
        RU_PAGE,
        known_manifest=RU_OLD,
        compare_page=None,
        timeout_seconds=30,
        poll_seconds=1,
        probe_wait_seconds=1,
        latest_txt=tmp_path / "latest.txt",
        latest_json=tmp_path / "latest.json",
        state_path=tmp_path / "state.json",
        probe=lambda _page, _wait: result,
    )

    assert payload["target"]["manifest_url"] == RU_NEW


def test_two_new_manifests_after_baseline_filter_still_fail_closed(tmp_path: Path) -> None:
    result = PageProbeResult(RU_PAGE, RU_PAGE, (obs(RU_OLD), obs(RU_NEW), obs(RU_OTHER_NEW)))

    with pytest.raises(ResiWatchAmbiguous, match="multiple distinct new Resi manifests"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=RU_OLD,
            compare_page=None,
            timeout_seconds=30,
            poll_seconds=1,
            probe_wait_seconds=1,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=tmp_path / "state.json",
            probe=lambda _page, _wait: result,
        )
