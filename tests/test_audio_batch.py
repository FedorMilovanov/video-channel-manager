from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from video_channel_manager.local_media.audio_batch import (
    AudioBatchCandidate,
    AudioBatchError,
    AudioMetadataPolicy,
    AudioProbeReport,
    build_audio_batch_plan,
    chunk_ready_audio_items,
    derive_audio_metadata,
    probe_audio_file,
)


def _completed(payload: object, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def _probe(path: Path) -> AudioProbeReport:
    resolved = path.resolve()
    content = resolved.read_bytes()
    return AudioProbeReport(
        path=str(resolved),
        size_bytes=len(content),
        sha256=f"sha256:{hashlib.sha256(content).hexdigest()}",
        duration_seconds=3600.0,
        format_names=("mp3",),
        audio_stream_count=1,
        attached_picture_stream_count=0,
        audio_codec="mp3",
        bit_rate_bps=128000,
        sample_rate_hz=44100,
        channels=2,
        tags={},
    )


def test_metadata_default_refuses_to_guess_filename_convention() -> None:
    decision = derive_audio_metadata("Название - Луки 20:19-26 - Джон МакАртур [source-1].mp3")

    assert decision.status == "requires_review"
    assert decision.reason == "filename_convention_not_declared"
    assert decision.artist is None
    assert decision.title is None
    assert decision.source_id_hint == "source-1"


def test_metadata_explicit_fields_are_exact_not_prefix_matches() -> None:
    decision = derive_audio_metadata(
        "Название - Джон МакАртур.mp3",
        explicit_artist="Джон МакАртур",
        explicit_title="Диагноз отвергающих Христа — Луки 20:19–26",
    )

    assert decision.status == "ready"
    assert decision.reason == "explicit_exact_fields"
    assert decision.artist == "Джон МакАртур"
    assert decision.title == "Диагноз отвергающих Христа — Луки 20:19–26"


def test_metadata_requires_explicit_pair() -> None:
    decision = derive_audio_metadata("Название.mp3", explicit_artist="Проповедник")

    assert decision.status == "requires_review"
    assert decision.reason == "explicit_artist_and_title_must_be_supplied_together"


def test_declared_last_segment_policy_parses_known_ingest_convention() -> None:
    decision = derive_audio_metadata(
        "Диагноз отвергающих Христа - Луки 20:19-26 - Джон МакАртур [29jEzoXnHm0].mp3",
        policy=AudioMetadataPolicy(artist_position="last", minimum_segments=3),
    )

    assert decision.status == "ready"
    assert decision.artist == "Джон МакАртур"
    assert decision.title == "Диагноз отвергающих Христа - Луки 20:19-26"
    assert decision.source_id_hint == "29jEzoXnHm0"


def test_declared_policy_rejects_mixed_separators() -> None:
    decision = derive_audio_metadata(
        "Название — место Писания - Проповедник.mp3",
        policy=AudioMetadataPolicy(artist_position="last"),
    )

    assert decision.status == "requires_review"
    assert decision.reason == "missing_or_mixed_metadata_separator"


def test_probe_audio_accepts_attached_cover_and_preserves_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "sermon.mp3"
    original = b"audio-bytes"
    path.write_bytes(original)
    payload = {
        "format": {
            "format_name": "mp3",
            "duration": "3600.5",
            "bit_rate": "128000",
            "tags": {"artist": "Джон МакАртур", "title": "Проповедь"},
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "audio",
                "codec_name": "mp3",
                "sample_rate": "44100",
                "channels": 2,
            },
            {
                "index": 1,
                "codec_type": "video",
                "codec_name": "mjpeg",
                "disposition": {"attached_pic": 1},
            },
        ],
    }
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _completed(payload))

    report = probe_audio_file(path)

    assert report.duration_seconds == 3600.5
    assert report.audio_stream_count == 1
    assert report.attached_picture_stream_count == 1
    assert report.audio_codec == "mp3"
    assert report.tags == {"artist": "Джон МакАртур", "title": "Проповедь"}
    assert report.sha256 == f"sha256:{hashlib.sha256(original).hexdigest()}"
    assert path.read_bytes() == original


def test_probe_audio_rejects_non_cover_video_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "sermon.mp3"
    path.write_bytes(b"audio")
    payload = {
        "format": {"format_name": "mp3", "duration": "5"},
        "streams": [
            {"codec_type": "audio", "codec_name": "mp3"},
            {"codec_type": "video", "codec_name": "h264", "disposition": {"attached_pic": 0}},
        ],
    }
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _completed(payload))

    with pytest.raises(AudioBatchError, match="non-cover video stream"):
        probe_audio_file(path)


def test_probe_audio_rejects_wrong_extension_before_ffprobe(tmp_path: Path) -> None:
    path = tmp_path / "sermon.wav"
    path.write_bytes(b"audio")

    with pytest.raises(AudioBatchError, match="extension is not allowed"):
        probe_audio_file(path)


def test_batch_plan_is_deterministic_and_marks_duplicate_sha(tmp_path: Path) -> None:
    first = tmp_path / "b.mp3"
    duplicate = tmp_path / "c.mp3"
    unique = tmp_path / "a.mp3"
    first.write_bytes(b"same")
    duplicate.write_bytes(b"same")
    unique.write_bytes(b"unique")
    candidates = [
        AudioBatchCandidate(first, source_id="source-b", explicit_artist="B", explicit_title="Title B"),
        AudioBatchCandidate(duplicate, source_id="source-b", explicit_artist="B", explicit_title="Title B"),
        AudioBatchCandidate(unique, source_id="source-a", explicit_artist="A", explicit_title="Title A"),
    ]

    plan = build_audio_batch_plan(candidates, project_key="lord-god-strength", probe=_probe)
    reversed_plan = build_audio_batch_plan(reversed(candidates), project_key="lord-god-strength", probe=_probe)

    assert plan.to_dict() == reversed_plan.to_dict()
    assert plan.schema_version == "1.1"
    assert plan.ready_count == 2
    assert plan.duplicate_count == 1
    assert plan.review_count == 0
    assert len({item.operation_id for item in plan.items}) == len(plan.items)
    duplicate_item = next(item for item in plan.items if item.status == "duplicate_input")
    assert duplicate_item.reason == "duplicate_sha256"
    assert duplicate_item.duplicate_of is not None
    assert plan.manifest_sha256.startswith("sha256:")


def test_exact_metadata_candidate_becomes_canonical_even_when_path_sorts_later(tmp_path: Path) -> None:
    ambiguous = tmp_path / "a-ambiguous.mp3"
    exact = tmp_path / "z-exact.mp3"
    ambiguous.write_bytes(b"same")
    exact.write_bytes(b"same")

    plan = build_audio_batch_plan(
        [
            AudioBatchCandidate(ambiguous, source_id="same-id", raw_title="Непонятное название"),
            AudioBatchCandidate(exact, source_id="same-id", explicit_artist="Artist", explicit_title="Track"),
        ],
        project_key="legendary-poet",
        probe=_probe,
    )

    canonical = next(item for item in plan.items if item.status == "ready")
    duplicate = next(item for item in plan.items if item.status == "duplicate_input")
    assert canonical.path == str(exact.resolve())
    assert canonical.reason == "explicit_exact_fields"
    assert duplicate.path == str(ambiguous.resolve())
    assert duplicate.duplicate_of == canonical.operation_id


def test_batch_plan_blocks_same_source_id_with_different_bytes(tmp_path: Path) -> None:
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    plan = build_audio_batch_plan(
        [
            AudioBatchCandidate(first, source_id="same-id", explicit_artist="A", explicit_title="One"),
            AudioBatchCandidate(second, source_id="same-id", explicit_artist="A", explicit_title="Two"),
        ],
        project_key="legendary-poet",
        probe=_probe,
    )

    assert plan.ready_count == 0
    assert plan.duplicate_count == 0
    assert plan.review_count == 2
    assert {item.reason for item in plan.items} == {"source_id_sha256_conflict"}
    assert all(item.duplicate_of is None for item in plan.items)


def test_batch_plan_blocks_same_bytes_claimed_by_multiple_source_ids(tmp_path: Path) -> None:
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"same")
    second.write_bytes(b"same")

    plan = build_audio_batch_plan(
        [
            AudioBatchCandidate(first, source_id="source-a", explicit_artist="A", explicit_title="One"),
            AudioBatchCandidate(second, source_id="source-b", explicit_artist="A", explicit_title="One"),
        ],
        project_key="legendary-poet",
        probe=_probe,
    )

    assert plan.ready_count == 0
    assert plan.duplicate_count == 0
    assert plan.review_count == 2
    assert {item.reason for item in plan.items} == {"sha256_multiple_source_ids"}


def test_batch_plan_keeps_ambiguous_metadata_out_of_ready_set(tmp_path: Path) -> None:
    path = tmp_path / "ambiguous.mp3"
    path.write_bytes(b"audio")

    plan = build_audio_batch_plan(
        [AudioBatchCandidate(path, raw_title="Непонятное название")],
        project_key="lord-god-strength",
        probe=_probe,
    )

    assert plan.ready_count == 0
    assert plan.review_count == 1
    assert plan.items[0].reason == "filename_convention_not_declared"


def test_chunking_defaults_to_single_writer_sequence(tmp_path: Path) -> None:
    candidates: list[AudioBatchCandidate] = []
    for index in range(3):
        path = tmp_path / f"{index}.mp3"
        path.write_bytes(f"audio-{index}".encode())
        candidates.append(
            AudioBatchCandidate(
                path,
                source_id=f"source-{index}",
                explicit_artist="Artist",
                explicit_title=f"Track {index}",
            )
        )
    plan = build_audio_batch_plan(candidates, project_key="lord-god-strength", probe=_probe)

    chunks = chunk_ready_audio_items(plan)

    assert [len(chunk) for chunk in chunks] == [1, 1, 1]
    assert [chunk[0].ordinal for chunk in chunks] == [1, 2, 3]


def test_chunking_rejects_item_above_byte_budget(tmp_path: Path) -> None:
    path = tmp_path / "large.mp3"
    path.write_bytes(b"large")
    plan = build_audio_batch_plan(
        [AudioBatchCandidate(path, explicit_artist="Artist", explicit_title="Track")],
        project_key="lord-god-strength",
        probe=_probe,
    )

    with pytest.raises(AudioBatchError, match="exceeds max_total_bytes"):
        chunk_ready_audio_items(plan, max_total_bytes=2)


def test_large_batch_is_deterministic_unique_and_chunkable(tmp_path: Path) -> None:
    candidates: list[AudioBatchCandidate] = []
    for index in range(1000):
        path = tmp_path / f"{index:04d}.mp3"
        path.write_bytes(f"audio-{index}".encode())
        candidates.append(
            AudioBatchCandidate(
                path,
                source_id=f"source-{index:04d}",
                explicit_artist="Artist",
                explicit_title=f"Track {index:04d}",
            )
        )

    plan = build_audio_batch_plan(candidates, project_key="lord-god-strength", probe=_probe)
    reversed_plan = build_audio_batch_plan(reversed(candidates), project_key="lord-god-strength", probe=_probe)
    chunks = chunk_ready_audio_items(plan, max_items=25)

    assert plan.to_dict() == reversed_plan.to_dict()
    assert plan.ready_count == 1000
    assert plan.review_count == 0
    assert plan.duplicate_count == 0
    assert len({item.operation_id for item in plan.items}) == 1000
    assert len(chunks) == 40
    assert all(len(chunk) == 25 for chunk in chunks)
