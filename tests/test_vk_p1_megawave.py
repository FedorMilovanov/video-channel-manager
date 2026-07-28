from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.platforms.vk.editorial_final_megawave import (
    extract_poem_blocks,
    managed_membership_pairs,
    membership_pairs,
    render_final_description,
    system_membership_counts,
    system_membership_pairs,
)
from video_channel_manager.platforms.vk.editorial_final_megawave_resume import (
    rebuild_legacy_intermediate_guards,
)


_POLICY = Path("content/policies/vk-p1-final-megawave-policy-20260728.json")
_RETIRED_POLICY = Path("content/policies/vk-p1-megawave-policy-20260728.json")
_WRAPPER = Path("scripts/Invoke-VkP1Megawave.ps1")
_EXECUTOR = Path("scripts/run_vk_p1_final_megawave.py")
_RESUME_EXECUTOR = Path("scripts/run_vk_p1_final_megawave_resume.py")
_FINAL_BUILDER = Path("src/video_channel_manager/platforms/vk/editorial_final_megawave.py")


def _policy() -> dict[str, object]:
    payload = json.loads(_POLICY.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _membership(collection_id: str, video_id: str) -> dict[str, object]:
    return {
        "collection_ref": {"remote_id": collection_id},
        "video_ref": {"remote_id": video_id},
    }


def test_final_megawave_policy_closes_full_scope_once() -> None:
    payload = _policy()
    targets = payload["targets"]
    assert isinstance(targets, list)
    target_ids = [str(item["video_id"]) for item in targets]

    assert payload["decision_set_id"] == "p1-final-all-in-one-20260728"
    assert len(target_ids) == 42
    assert len(set(target_ids)) == 42
    assert sum("title_override" in item for item in targets) == 3
    assert payload["rules"]["single_command"] is True
    assert payload["rules"]["replace_legacy_playlist_links_with_vk"] is True
    assert payload["rules"]["canonicalize_brand_links"] is True
    assert payload["rules"]["canonicalize_hashtags"] is True
    assert payload["rules"]["add_missing_expected_memberships"] is True
    assert payload["rules"]["remove_memberships"] is False


def test_every_target_has_work_author_and_vk_playlist_mapping() -> None:
    payload = _policy()
    work_metadata = payload["work_metadata"]
    author_names = payload["author_names"]
    collection_labels = payload["collection_labels"]

    for target in payload["targets"]:
        assert target["work_key"] in work_metadata
        assert target["author_key"] in author_names
        assert target["expected_collection_ids"]
        for collection_id in target["expected_collection_ids"]:
            assert str(collection_id) in collection_labels
            assert not str(collection_id).startswith("-")


def test_short_versions_have_full_vk_links_and_playlist_memberships() -> None:
    payload = _policy()
    short_targets = [item for item in payload["targets"] if item["format"] == "short"]

    assert len(short_targets) == 13
    assert all(item.get("full_version_video_id") for item in short_targets)
    poetry_shorts = [item for item in short_targets if item["author_key"] != "alisa"]
    assert all("4" in item["expected_collection_ids"] for item in poetry_shorts)


def test_final_description_uses_vk_site_channels_and_standard_tags() -> None:
    payload = _policy()
    target = next(item for item in payload["targets"] if item["video_id"] == "-235216998_456239049")
    poem = "Первая строка\nВторая строка\nТретья строка\nЧетвёртая строка"
    collections = {
        "4": {"metadata": {"share_url": "https://vkvideo.ru/playlist/-235216998_4?uh=singing"}},
        "9": {"metadata": {"share_url": "https://vkvideo.ru/playlist/-235216998_9?uh=pushkin"}},
    }

    rendered, metadata = render_final_description(
        "Старая неподтверждённая биография.\n\n" + poem + "\n\nhttps://youtube.com/old-playlist",
        policy=payload,
        target=target,
        collections=collections,
    )

    assert "Старая неподтверждённая" not in rendered
    assert poem in rendered
    assert "https://youtube.com/old-playlist" not in rendered
    assert "https://vkvideo.ru/playlist/-235216998_4?uh=singing" in rendered
    assert "https://vkvideo.ru/playlist/-235216998_9?uh=pushkin" in rendered
    assert "https://vkvideo.ru/video-235216998_456239048" in rendered
    assert "https://thelegendarypoet.ru/poets/alexander-pushkin" in rendered
    assert "https://thelegendarypoet.ru/music" in rendered
    assert "https://vk.com/thelegendarypoet" in rendered
    assert "https://t.me/thelegendarypoet" in rendered
    assert "#АлександрПушкин" in rendered
    assert "#Shorts" in rendered
    assert metadata["all_legacy_links_replaced"] is True


def test_poem_extraction_rejects_prose_lists() -> None:
    poem = "Первая строка\nВторая строка\nТретья строка\nЧетвёртая строка"
    prose = "Основные идеи:\n➛ первый тезис\n➛ второй тезис\n➛ третий тезис"

    assert extract_poem_blocks(poem) == [poem]
    assert extract_poem_blocks(prose) == []


def test_managed_and_dynamic_system_memberships_are_separated() -> None:
    snapshot = {
        "memberships": [
            _membership("4", "video-a"),
            _membership("9", "video-a"),
            _membership("-2", "video-a"),
            _membership("-2", "video-b"),
            _membership("-13", "video-b"),
        ]
    }

    assert membership_pairs(snapshot) == {
        ("4", "video-a"),
        ("9", "video-a"),
        ("-2", "video-a"),
        ("-2", "video-b"),
        ("-13", "video-b"),
    }
    assert managed_membership_pairs(snapshot) == {("4", "video-a"), ("9", "video-a")}
    assert system_membership_pairs(snapshot) == {
        ("-2", "video-a"),
        ("-2", "video-b"),
        ("-13", "video-b"),
    }
    assert system_membership_counts(snapshot) == {"-13": 1, "-2": 2}


def test_partial_descriptions_only_policy_is_retired() -> None:
    payload = json.loads(_RETIRED_POLICY.read_text(encoding="utf-8"))

    assert payload["status"] == "retired"
    assert payload["approved_decision_set"] == "p1-final-all-in-one-20260728"
    assert payload["superseded_by"] == str(_POLICY).replace("\\", "/")


def test_final_plan_records_the_exact_legacy_intermediate_state() -> None:
    builder = _FINAL_BUILDER.read_text(encoding="utf-8")

    assert '"legacy_intermediate_description"' in builder
    assert '"legacy_intermediate_description_sha256"' in builder
    assert '"accepted_intermediate_decision_set_id"' in builder
    assert "p1-all-remaining-megawave-20260728" in builder
    assert '"schema_version": 2' in builder


def test_resume_guards_reproduce_37_shared_replacements_for_42_targets() -> None:
    operations: list[dict[str, object]] = []
    targets: list[dict[str, str]] = []
    for index in range(42):
        group = 0 if index < 6 else index - 5
        video_id = f"video-{index:02d}"
        targets.append({"video_id": video_id})
        operations.append(
            {
                "operation_id": f"operation-{index:02d}",
                "target_video_id": video_id,
                "before_title": f"Заголовок {index:02d}",
                "before_description": f"Исходное описание общей группы {group:02d}.",
                "legacy_intermediate_title": f"Заголовок {index:02d}",
                "legacy_intermediate_description": "неверный индивидуальный guard",
                "legacy_intermediate_title_sha256": "old",
                "legacy_intermediate_description_sha256": "old",
                "legacy_intermediate_metadata": {},
            }
        )

    corrected = rebuild_legacy_intermediate_guards(
        {"video_text_operations": operations, "plan_sha256": "old"},
        {"targets": targets},
    )
    corrected_operations = corrected["video_text_operations"]
    shared = [item for item in corrected_operations if item["before_description"].endswith("00.")]

    assert corrected["accepted_intermediate_research_unit_count"] == 37
    assert corrected["accepted_intermediate_duplicate_target_count"] == 5
    assert len({item["legacy_intermediate_description"] for item in shared}) == 1
    assert all("Заголовок 00" in item["legacy_intermediate_description"] for item in shared)
    assert all(
        item["legacy_intermediate_metadata"]["shared_research_unit_first_video_id"] == "video-00"
        for item in shared
    )


def test_wrapper_invokes_only_final_resumable_executor() -> None:
    wrapper = _WRAPPER.read_text(encoding="utf-8")
    executor = _EXECUTOR.read_text(encoding="utf-8")
    resume_executor = _RESUME_EXECUTOR.read_text(encoding="utf-8")

    assert "run_vk_p1_final_megawave_resume.py" in wrapper
    assert "vk-p1-final-megawave-policy-20260728.json" in wrapper
    assert "--execute" in wrapper
    assert "build_vk_p1_megawave_decisions.py" not in wrapper
    assert "apply_vk_editorial_cleanup_plan.py" not in wrapper
    assert "rebuild_legacy_intermediate_guards" in resume_executor
    assert '"placements_to_add": 32' in executor
    assert '"total_operations": 77' in executor
    assert "ready_legacy" in executor
    assert "managed_membership_pairs" in executor
    assert "system_membership_identity_drift_ignored" in executor
    assert "recent_album_identity_drift_allowed" in executor
    assert "writer.add_to_album" in executor
    assert "writer.rename_album" in executor
