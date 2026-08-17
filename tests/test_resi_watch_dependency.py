from __future__ import annotations

from pathlib import Path

import pytest

from video_channel_manager.resi_watch import PageProbeResult, ResiWatchDependencyError, watch_for_new_manifest

RU_PAGE = "https://www.gracechurch.org/live?language=russian"
RU_OLD = "https://resi.media/GiHDtf/a19407ff-e767-4a17-87d0-f3758bd87bfe/Manifest.mpd?src=emb"


def test_browser_dependency_failure_is_not_retried_as_transient(tmp_path: Path) -> None:
    calls = [0]
    sleeps: list[float] = []

    def missing_dependency(_page: str, _wait: float) -> PageProbeResult:
        calls[0] += 1
        raise ResiWatchDependencyError("Playwright is required")

    with pytest.raises(ResiWatchDependencyError, match="Playwright is required"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=RU_OLD,
            compare_page=None,
            timeout_seconds=10800,
            poll_seconds=30,
            probe_wait_seconds=12,
            max_consecutive_probe_errors=10,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=tmp_path / "state.json",
            probe=missing_dependency,
            sleeper=sleeps.append,
        )

    assert calls == [1]
    assert sleeps == []
