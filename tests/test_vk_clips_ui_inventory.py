from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import clips_ui_inventory
from video_channel_manager.platforms.vk.clips_ui_inventory import (
    MILOVI_PUBLIC_CLIPS_URL,
    build_vk_clips_ui_inventory,
)

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
KNOWN_SHREK_CLIP = "-68859909_456239130"


def test_network_short_video_extraction_keeps_exact_owner_and_counts_foreign_noise() -> None:
    records: dict[str, dict[str, Any]] = {}
    foreign: set[str] = set()
    payload = {
        "response": {
            "items": [
                {
                    "type": "short_video",
                    "owner_id": MILOVI_OWNER_ID,
                    "id": 456239130,
                    "title": "Торт со Шреком",
                    "description": "Milovi Cake",
                },
                {
                    "type": "short_video",
                    "owner_id": -235216998,
                    "id": 456240001,
                    "title": "Poet recommendation",
                },
                {
                    "type": "video",
                    "owner_id": MILOVI_OWNER_ID,
                    "id": 456239135,
                },
            ]
        }
    }

    observed = clips_ui_inventory._merge_network_payload(  # noqa: SLF001
        payload,
        owner_id=MILOVI_OWNER_ID,
        target_records=records,
        foreign_remote_ids=foreign,
    )

    assert observed == 2
    assert sorted(records) == [KNOWN_SHREK_CLIP]
    assert records[KNOWN_SHREK_CLIP]["type"] == "short_video"
    assert records[KNOWN_SHREK_CLIP]["evidence_sources"] == ["network_json_type_short_video"]
    assert foreign == {"-235216998_456240001"}


def test_dom_clip_links_are_deduplicated_and_query_strings_are_not_persisted() -> None:
    records: dict[str, dict[str, Any]] = {}
    foreign: set[str] = set()
    rows = [
        {
            "href": "https://vk.com/clip-68859909_456239130?c=1&tracking=secret",
            "text": "Торт со Шреком",
            "context": "Торт со Шреком от Milovi Cake",
        },
        {
            "href": "https://vk.com/clip-68859909_456239130?c=2",
            "title": "Торт со Шреком",
        },
    ]

    clips_ui_inventory._merge_dom_rows(  # noqa: SLF001
        rows,
        owner_id=MILOVI_OWNER_ID,
        target_records=records,
        foreign_remote_ids=foreign,
    )

    assert sorted(records) == [KNOWN_SHREK_CLIP]
    record = records[KNOWN_SHREK_CLIP]
    assert record["canonical_permalink"] == "https://vk.com/clip-68859909_456239130"
    assert record["observed_href_paths"] == ["https://vk.com/clip-68859909_456239130"]
    assert "tracking" not in str(record)
    assert foreign == set()


def test_snapshot_keeps_public_ui_observation_bounded_and_non_authorizing(monkeypatch) -> None:
    probe = {
        "status": "ok_bounded_ui_observation",
        "requested_url": MILOVI_PUBLIC_CLIPS_URL,
        "final_url": MILOVI_PUBLIC_CLIPS_URL,
        "page_title": "Milovi Cake",
        "browser_executable_name": "browser.exe",
        "playwright_version": "1.54.0",
        "headless": False,
        "persistent_profile_used": False,
        "scroll_iterations": 14,
        "stable_rounds_observed": 5,
        "stable_rounds_required": 5,
        "reached_stable_end": True,
        "response_json_documents": 3,
        "network_short_video_observations": 2,
        "foreign_clip_identity_count": 1,
        "blocked_hints": [],
        "interaction_evidence": {
            "navigation_calls": 1,
            "scroll_calls": 14,
            "dom_reads": True,
            "network_response_reads": True,
            "click_calls": 0,
            "form_fill_calls": 0,
            "keyboard_submit_calls": 0,
        },
        "clips": [
            {
                "remote_id": KNOWN_SHREK_CLIP,
                "owner_id": MILOVI_OWNER_ID,
                "video_id": 456239130,
                "type": "short_video",
                "is_native_clip": True,
                "title": "Торт со Шреком",
                "description": "",
                "canonical_permalink": "https://vk.com/clip-68859909_456239130",
                "observed_href_paths": ["https://vk.com/clip-68859909_456239130"],
                "evidence_sources": ["dom_clip_href"],
            }
        ],
    }
    monkeypatch.setattr(clips_ui_inventory, "_run_playwright_probe", lambda **kwargs: probe)

    snapshot = build_vk_clips_ui_inventory(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        required_remote_ids=[KNOWN_SHREK_CLIP],
    )

    assert snapshot["schema"] == "vk-clips-browser-ui-read-v1"
    assert snapshot["project_key"] == "milovi-cake"
    assert snapshot["read_only"] is True
    assert snapshot["provider_writes"] == 0
    assert snapshot["provider_mutation_authorized"] is False
    assert snapshot["transport"] == "browser_ui_read"
    assert snapshot["coverage"]["clip_count"] == 1
    assert snapshot["coverage"]["required_remote_ids_found"] == [KNOWN_SHREK_CLIP]
    assert snapshot["coverage"]["required_remote_ids_missing"] == []
    assert snapshot["coverage"]["bounded_ui_end_observed"] is True
    assert snapshot["coverage"]["surface_complete_claim"] is False
    assert snapshot["browser_probe"]["interaction_evidence"]["click_calls"] == 0


def test_reader_rejects_cross_project_or_wrong_route_before_browser_probe(monkeypatch) -> None:
    called = False

    def fake_probe(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(clips_ui_inventory, "_run_playwright_probe", fake_probe)

    try:
        build_vk_clips_ui_inventory(
            project_key="legendary-poet",
            community_id=235216998,
            owner_id=-235216998,
        )
    except ValueError as exc:
        assert "intentionally scoped" in str(exc)
    else:
        raise AssertionError("cross-project browser read must fail closed")

    try:
        build_vk_clips_ui_inventory(
            project_key="milovi-cake",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            url="https://vkvideo.ru/@thelegendarypoet/clips",
        )
    except ValueError as exc:
        assert "unexpected Milovi public Clips route" in str(exc)
    else:
        raise AssertionError("wrong public Clips route must fail closed")

    assert called is False


def test_browser_probe_source_contains_no_click_fill_or_submit_primitives() -> None:
    source = inspect.getsource(clips_ui_inventory._run_playwright_probe)  # noqa: SLF001
    forbidden = (
        ".click(",
        ".dblclick(",
        ".fill(",
        ".press(",
        ".check(",
        ".uncheck(",
        ".select_option(",
        ".set_input_files(",
        ".tap(",
    )
    assert not any(token in source for token in forbidden)
    assert "page.goto(" in source
    assert "window.scrollTo" not in source  # scrolling is confined to the fixed constant, not ad-hoc JS.


def test_browser_autodiscovery_accepts_explicit_existing_executable(tmp_path: Path) -> None:
    executable = tmp_path / "browser.exe"
    executable.write_bytes(b"placeholder")
    assert clips_ui_inventory._resolve_browser_executable(executable) == executable.resolve()  # noqa: SLF001
