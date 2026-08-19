from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILOVI = ROOT / "content/telegram/milovi-cake"
MEDIA_MAP = MILOVI / "media-source-map-2026-08.json"
SOURCE_READINESS = MILOVI / "video-source-readiness-2026-08.json"
CONVERSION_CONTRACT = MILOVI / "video-conversion-contract-2026-08.json"
OUTPUT_RECORDS = MILOVI / "video-output-records-2026-08.json"
RUNBOOK = MILOVI / "video-conversion-readiness-2026-08.md"
VIDEO_ARTIFACT_WORKFLOW = ROOT / ".github/workflows/milovi-telegram-video-artifacts.yml"

EXPECTED_SOURCE = {
    "v01": ("4d04ef09c0c62fd938ecf72a9e804ff2c3213f9e", 2587943),
    "v02": ("7b21b6bd55f18dc4a5db0ed512e54674cb92c7a9", 1598663),
    "v03": ("c07d0d4b1c6ba22ef3d8295e9eda2b9a5ca01a03", 1338352),
    "v04": ("b6aa0b02cbaf38be883428a6846c2c1b0c3644ff", 1021079),
    "v05": ("45505f593ce2b54b09ea83cd03ba934e1af49ff3", 1058419),
    "v06": ("eb1145107d7a3893005b0b6dfafe15537ce595af", 897630),
    "v07": ("a8aab6292dde376c88cd878f24dd2a293d1cb188", 925560),
    "v08": ("203dad0931adf549b9e83c121896851899c9e6eb", 1820997),
    "v09": ("4d6759412f4004e6c6f148ca2e64fa4ca2e20605", 1809965),
    "v10": ("461a8417a39f341995b37ca1321ac035ad9a0d4c", 1315558),
    "v11": ("3ce76a706f5ef767522934caab058f95a8f354fb", 1237107),
    "v12": ("b95d8a197eaac5a1eb4714c8fcfc6277689406a4", 740815),
    "v13": ("fb31601131831f85ab986374fab108056e88dcdd", 1817845),
    "v14": ("e585d678d4d0d05d012caa518dca767b61ea6a14", 2375569),
    "v15": ("22d8af58225c73570bf69b74c70ac53365314cc6", 1685606),
    "v16": ("a86e61b6044de476060929131932c2bfda6e0fef", 1293911),
}

PROBE_FIELDS = {
    "container",
    "video_codec",
    "pixel_format",
    "width",
    "height",
    "avg_frame_rate",
    "duration_seconds",
    "audio_present",
    "audio_codec",
}

OUTPUT_NULL_FIELDS = {
    "source_sha256",
    "source_probe",
    "ffmpeg_version",
    "ffprobe_version",
    "execution_environment_digest",
    "conversion_command_argv",
    "output_path",
    "output_sha256",
    "output_byte_size",
    "output_container",
    "output_video_codec",
    "output_pixel_format",
    "output_width",
    "output_height",
    "output_avg_frame_rate",
    "output_duration_seconds",
    "output_audio_present",
    "output_audio_codec",
}


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_video_source_readiness_matches_exact_canonical_gallery_identity() -> None:
    media_map = _load_json(MEDIA_MAP)
    readiness = _load_json(SOURCE_READINESS)
    media_videos = {item["id"]: item for item in media_map["items"] if item["type"] == "video"}
    readiness_videos = {item["id"]: item for item in readiness["videos"]}

    assert readiness["schema_name"] == "video-channel-manager.milovi-telegram-video-source-readiness"
    assert readiness["project_key"] == "milovi-cake"
    assert readiness["status"] == "provider_inert"
    assert readiness["source_repository"] == "FedorMilovanov/Milovi_Cake"
    assert readiness["source_commit"] == "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370"
    assert (
        readiness["source_gallery_blob_sha"]
        == media_map["source_blob_sha"]
        == "e20e60c07479e8b20c1db700f1a40364b81eb669"
    )
    assert readiness["declared_video_count"] == 16
    assert readiness["telegram_native_video_ready_count"] == 0
    assert set(readiness_videos) == set(media_videos) == set(EXPECTED_SOURCE)

    for media_id, source in readiness_videos.items():
        canonical = media_videos[media_id]
        assert source["title"] == canonical["title"]
        assert source["poster"] == canonical["poster"]
        assert source["source_path"] == canonical["src"].removeprefix("/")
        assert source["source_path"].endswith(".webm")
        assert source["source_container_expected"] == "webm"


def test_video_source_blobs_and_sizes_are_exact_and_probe_stays_unresolved() -> None:
    readiness = _load_json(SOURCE_READINESS)
    videos = {item["id"]: item for item in readiness["videos"]}

    for media_id, (expected_blob, expected_size) in EXPECTED_SOURCE.items():
        item = videos[media_id]
        assert item["source_git_blob_sha1"] == expected_blob
        assert item["source_byte_size"] == expected_size
        assert item["native_telegram_video_ready"] is False
        assert item["output_mp4"] is None
        assert set(item["probe"]) == PROBE_FIELDS
        assert all(item["probe"][field] is None for field in PROBE_FIELDS)

    assert min(item["source_byte_size"] for item in videos.values()) == 740815
    assert max(item["source_byte_size"] for item in videos.values()) == 2587943


def test_small_webm_source_size_never_implies_native_telegram_readiness() -> None:
    readiness = _load_json(SOURCE_READINESS)
    contract = _load_json(CONVERSION_CONTRACT)
    hard_max = contract["output_policy"]["size_policy"]["telegram_hard_max_bytes"]

    assert hard_max == 50 * 1024 * 1024
    assert all(item["source_byte_size"] < hard_max for item in readiness["videos"])
    assert all(item["native_telegram_video_ready"] is False for item in readiness["videos"])
    assert readiness["telegram_native_video_ready_count"] == 0
    assert "does not imply native sendVideo readiness" in readiness["rule"]


def test_video_conversion_contract_is_deterministic_provider_inert_and_no_document_fallback() -> None:
    contract = _load_json(CONVERSION_CONTRACT)
    policy = contract["output_policy"]
    audio = policy["audio_policy"]
    toolchain = contract["toolchain_lock"]

    assert contract["schema_name"] == "video-channel-manager.milovi-telegram-video-conversion-contract"
    assert contract["project_key"] == "milovi-cake"
    assert contract["status"] == "provider_inert"
    assert contract["provider_write_authorized"] is False
    assert contract["source_mutation_allowed"] is False
    assert contract["document_fallback_allowed"] is False
    assert contract["conversion_execution_ready"] is VIDEO_ARTIFACT_WORKFLOW.exists()

    assert toolchain["ffmpeg_version"] is None
    assert toolchain["ffprobe_version"] is None
    assert toolchain["execution_environment_digest"] is None

    assert contract["probe_gate"]["required"] is True
    assert set(contract["probe_gate"]["fields"]) >= {
        "source_sha256",
        "container",
        "video_codec",
        "width",
        "height",
        "duration_seconds",
        "audio_present",
    }

    assert policy["container"] == "mp4"
    assert policy["video_codec"] == "h264"
    assert policy["encoder"] == "libx264"
    assert policy["pixel_format"] == "yuv420p"
    assert policy["movflags"] == "+faststart"
    assert policy["overwrite_existing_output"] is False
    assert "never upscale" in policy["geometry_policy"]
    assert "preserve source timing/frame rate" in policy["frame_rate_policy"]
    assert "never synthesize silence or music" in audio["if_source_has_no_audio"]
    assert audio["extra_audio_streams_allowed"] is False
    assert "does not authorize sendVideo" in contract["rollout_rule"]


def test_video_output_records_are_one_to_one_blocked_and_empty_until_real_conversion() -> None:
    readiness = _load_json(SOURCE_READINESS)
    outputs = _load_json(OUTPUT_RECORDS)
    source_by_id = {item["id"]: item for item in readiness["videos"]}
    records = {item["media_id"]: item for item in outputs["records"]}

    assert outputs["schema_name"] == "video-channel-manager.milovi-telegram-video-output-records"
    assert outputs["status"] == "provider_inert_blocked"
    assert outputs["accepted_output_count"] == 0
    assert outputs["provider_write_authorized"] is False
    assert set(records) == set(source_by_id) == set(EXPECTED_SOURCE)
    assert len(records) == 16

    for media_id, record in records.items():
        source = source_by_id[media_id]
        assert record["source_git_blob_sha1"] == source["source_git_blob_sha1"]
        assert record["poster"] == source["poster"]
        assert record["editorial_title"] == source["title"]
        assert record["accepted"] is False
        assert all(record[field] is None for field in OUTPUT_NULL_FIELDS)


def test_v04_identity_cannot_be_inferred_from_eclair_filename() -> None:
    readiness = _load_json(SOURCE_READINESS)
    outputs = _load_json(OUTPUT_RECORDS)
    v04 = next(item for item in readiness["videos"] if item["id"] == "v04")
    output = next(item for item in outputs["records"] if item["media_id"] == "v04")

    assert v04["source_path"].endswith("video-04-eclair.webm")
    assert v04["title"] == "Видео: меренговый рулет"
    assert "canonical gallery metadata identifies the content as meringue roll" in v04["identity_note"]
    assert output["editorial_title"] == "Видео: меренговый рулет"
    assert "eclair" not in output["editorial_title"].casefold()


def test_video_readiness_runbook_keeps_conversion_separate_from_editorial_crop_and_provider_send() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "all 16 native-video outputs blocked" in runbook
    assert "Do not infer them from `.webm`" in runbook
    assert "Cropping and conversion are different operations." in runbook
    assert "Do not force 30 fps or 60 fps" in runbook
    assert "Do not synthesize silence or add music." in runbook
    assert "Do not silently call `sendDocument`" in runbook
    assert "accepted MP4 outputs: **0 / 16**" in runbook
    assert "provider write authorization: **false**" in runbook
