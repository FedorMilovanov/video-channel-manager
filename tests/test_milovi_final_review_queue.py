from __future__ import annotations

from pathlib import Path

from video_channel_manager.platforms.vk import milovi_final_review_queue as review


def _candidate(youtube_id: str, gate: str = "MEDIA_RECONCILIATION_REQUIRED") -> dict[str, object]:
    return {
        "youtube_id": youtube_id,
        "title": youtube_id,
        "scope": "CAKE",
        "transfer_gate": gate,
    }


def test_manual_adjudication_scope_is_exact_and_conservative() -> None:
    assert len(review._MANUAL_ADJUDICATIONS) == 8
    decisions = [row["decision"] for row in review._MANUAL_ADJUDICATIONS.values()]
    assert decisions.count("EXISTING_NATIVE_REPRESENTATION_OBSERVED") == 5
    assert decisions.count("DISTINCT_FROM_PROBED_VK_CLIP") == 2
    assert decisions.count("REFERENCE_NATIVE_REPRESENTATION_OBSERVED") == 1


def test_candidate_derivation_blocks_five_existing_native_representations() -> None:
    resolved = [
        "FQGxV4DRPQw",
        "MdQ0kNBSsa8",
        "cE0ofu6WV3s",
        "CQ29P1F8Hfo",
        "R-LknUy9BEs",
    ]
    candidates = [_candidate(youtube_id) for youtube_id in resolved]
    candidates.extend([_candidate("safe-a"), _candidate("safe-b")])

    blocked, remaining = review._derive_candidate_rows(candidates)

    assert {row["youtube_id"] for row in blocked} == set(resolved)
    assert {row["youtube_id"] for row in remaining} == {"safe-a", "safe-b"}
    assert all(row["upload_authorized"] is False for row in blocked + remaining)


def test_negative_controls_never_become_existing_native_blocks() -> None:
    candidates = [_candidate("SiluLt5Bz1c"), _candidate("BAVKrQQ00XI")]
    blocked, remaining = review._derive_candidate_rows(candidates)

    assert blocked == []
    assert {row["youtube_id"] for row in remaining} == {"SiluLt5Bz1c", "BAVKrQQ00XI"}
    assert all(row["status"] == "NOT_PROVEN_MISSING_REVIEW_REQUIRED" for row in remaining)


def test_module_source_has_no_provider_mutation_primitives() -> None:
    source = Path(review.__file__).read_text(encoding="utf-8")

    assert '"provider_writes": 0' in source
    assert ".click(" not in source
    assert ".fill(" not in source
    assert "set_input_files" not in source
    assert "video.save" not in source
    assert "wall.post" not in source
    assert '"upload_authorized": False' in source
