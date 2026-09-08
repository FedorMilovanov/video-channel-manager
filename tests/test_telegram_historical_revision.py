from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.telegram_historical_revision import (
    load_historical_revision_package,
    preflight_historical_revision,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path("content/telegram/lordchrist/historical-editorial/v1/v3/spurgeon-down-grade-1887/revision.json")


def _package_payload() -> dict[str, object]:
    value = json.loads((REPO_ROOT / PACKAGE).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_package(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "revision.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_spurgeon_v3_revision_preflight_binds_copy_evidence_and_media_without_provider_authority() -> None:
    report = preflight_historical_revision(PACKAGE, repo_root=REPO_ROOT)

    assert report.status == "PASS"
    assert report.publication_id == "lordchrist-history-spurgeon-down-grade-1887-v3"
    assert report.source_count == 48
    assert report.grade_a_count >= 1
    assert report.grade_bplus_count >= 1
    assert report.independent_evidence_groups >= 4
    assert report.claim_count >= 6
    assert report.direct_quote_count == 1
    assert report.editorial_media_count == 2
    assert report.transport_ready_media_count == 0
    assert report.provider_writes_authorized is False
    assert report.live_eligible is False
    assert report.provider_write_performed is False


def test_revision_package_preserves_exact_accepted_editorial_media_identities() -> None:
    package = load_historical_revision_package(PACKAGE, repo_root=REPO_ROOT)
    media = {item.asset_id: item for item in package.editorial_media}

    assert media["img-spurgeon-v3-hero"].accepted_sha256 == (
        "sha256:9ccb4ff08042b3cf996164653c0b26759f870c853da12518b4f673b4daa9d2f1"
    )
    assert media["img-spurgeon-v3-hero"].accepted_byte_length == 131308
    assert (media["img-spurgeon-v3-hero"].accepted_width, media["img-spurgeon-v3-hero"].accepted_height) == (1200, 675)
    assert media["img-spurgeon-v3-portrait"].accepted_sha256 == (
        "sha256:d257d13b6fa1ecf060b7540960d5e1c49c4a655c827f348f551b282778aff23f"
    )
    assert media["img-spurgeon-v3-portrait"].accepted_byte_length == 89046
    assert (media["img-spurgeon-v3-portrait"].accepted_width, media["img-spurgeon-v3-portrait"].accepted_height) == (
        800,
        1000,
    )
    assert all(item.transport_ready is False for item in package.editorial_media)


def test_revision_preflight_rejects_bound_git_blob_drift(tmp_path: Path) -> None:
    payload = _package_payload()
    post = payload["post"]
    assert isinstance(post, dict)
    post["git_blob_sha"] = "0" * 40
    path = _write_package(tmp_path, payload)

    with pytest.raises(ValueError, match="Git blob differs"):
        preflight_historical_revision(path, repo_root=REPO_ROOT)


def test_revision_schema_rejects_promoting_editorial_artwork_to_transport_ready(tmp_path: Path) -> None:
    payload = _package_payload()
    media = payload["editorial_media"]
    assert isinstance(media, list) and isinstance(media[0], dict)
    media[0]["transport_ready"] = True
    path = _write_package(tmp_path, payload)

    with pytest.raises(ValueError):
        load_historical_revision_package(path, repo_root=REPO_ROOT)


def test_revision_schema_requires_non_historical_disclosure_for_ai_editorial_artwork(tmp_path: Path) -> None:
    payload = _package_payload()
    media = payload["editorial_media"]
    assert isinstance(media, list) and isinstance(media[0], dict)
    media[0]["disclosure"] = "Редакционная иллюстрация для исторической статьи без дополнительного указания статуса изображения."
    path = _write_package(tmp_path, payload)

    with pytest.raises(ValueError, match="non-historical photography"):
        load_historical_revision_package(path, repo_root=REPO_ROOT)


def test_revision_preflight_rejects_unknown_media_placement(tmp_path: Path) -> None:
    payload = _package_payload()
    media = payload["editorial_media"]
    assert isinstance(media, list) and isinstance(media[0], dict)
    media[0]["placement_after"] = "missing-section"
    path = _write_package(tmp_path, payload)

    with pytest.raises(ValueError, match="media placement does not exist"):
        preflight_historical_revision(path, repo_root=REPO_ROOT)
