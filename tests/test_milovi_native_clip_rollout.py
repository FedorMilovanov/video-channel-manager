from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_SOURCE_ALLOWLIST
from video_channel_manager.platforms.vk.milovi_native_clip_browser import target_tokens_present
from video_channel_manager.platforms.vk.milovi_native_clip_rollout import (
    CANARY_SOURCE_ID,
    EXECUTION_CONFIRMATION,
    MiloviRolloutBlocked,
    run_issue_323_rollout,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import (
    ROLL_OUT_IDS,
    SOURCE_SNAPSHOT_ID,
    build_description,
    build_wall_message,
)


def test_issue_323_rollout_allowlist_is_exact() -> None:
    assert len(ROLL_OUT_IDS) == 12
    assert frozenset(ROLL_OUT_IDS) == MILOVI_SOURCE_ALLOWLIST
    assert ROLL_OUT_IDS[0] == CANARY_SOURCE_ID == "d48QLgOuiTs"
    assert "SiluLt5Bz1c" not in ROLL_OUT_IDS
    assert SOURCE_SNAPSHOT_ID == "milovi-cake-issue-323-reviewed-public106-final-d48-a8841ece-v1"


def test_source_description_and_wall_copy_keep_exact_source_marker() -> None:
    source_id = "d48QLgOuiTs"
    description = build_description("Торт", source_id)
    wall_message = build_wall_message("Торт", source_id)

    assert description.endswith(f"https://www.youtube.com/shorts/{source_id}")
    assert wall_message.count(f"https://www.youtube.com/shorts/{source_id}") == 1
    assert "https://milovicake.ru/" in wall_message


def test_browser_target_proof_accepts_exact_milovi_route_and_identity() -> None:
    assert target_tokens_present(
        page_url="https://vkvideo.ru/clips/club68859909",
        html='<div data-community-id="68859909"><a href="/milovi_cake">Milovi Cake</a></div>',
        text="Milovi Cake\nДобавить клип",
    )


def test_browser_target_proof_rejects_route_without_identity_inside_active_ui() -> None:
    assert not target_tokens_present(
        page_url="https://vkvideo.ru/clips/club68859909",
        html="<div>Milovi Cake</div>",
        text="Milovi Cake\nДобавить клип",
    )


def test_browser_target_proof_rejects_wrong_route() -> None:
    assert not target_tokens_present(
        page_url="https://vkvideo.ru/clips/club235216998",
        html='<div data-community-id="68859909">Milovi Cake</div>',
        text="Milovi Cake",
    )


def test_browser_target_proof_rejects_selected_legendary_poet() -> None:
    assert not target_tokens_present(
        page_url="https://vkvideo.ru/clips/club68859909",
        html=(
            '<div data-community-id="68859909">Milovi Cake</div>'
            '<div data-screen-name="thelegendarypoet" aria-selected="true">The Legendary Poet</div>'
        ),
        text="Milovi Cake\nThe Legendary Poet",
    )


def test_execution_confirmation_fails_before_runtime_work(tmp_path) -> None:
    with pytest.raises(MiloviRolloutBlocked, match="Exact Issue #323 execution confirmation"):
        run_issue_323_rollout(
            confirmation="WRONG",
            output_path=tmp_path / "result.json",
            journal_path=tmp_path / "journal.json",
            work_dir=tmp_path / "work",
        )
    assert not (tmp_path / "result.json").exists()


def test_execution_confirmation_constant_is_exact_reviewed_phrase() -> None:
    assert EXECUTION_CONFIRMATION == "ISSUE_323_UPLOAD_12_AND_WALL_IMMEDIATE"
