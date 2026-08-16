import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / "content/telegram/milovi-cake/bootstrap-first-screen-candidates-2026-08.json"
READINESS_PATH = ROOT / "content/telegram/milovi-cake/bootstrap-photo-source-readiness-2026-08.json"
TRANSPORT_PROOF_PATH = ROOT / "content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json"
MEDIA_MAP_PATH = ROOT / "content/telegram/milovi-cake/media-source-map-2026-08.json"

SOURCE_REPOSITORY = "FedorMilovanov/Milovi_Cake"
SOURCE_COMMIT = "c4eb3bf6ed6fd5c3c9e4c2d857e53d8bae093370"
SOURCE_TREE = "34b8df8087d85c077302475da0ece442cd4c37d4"
GALLERY_BLOB = "e20e60c07479e8b20c1db700f1a40364b81eb669"

EXPECTED_PHOTOS = {
    "p02": (
        "Розовый торт с цветами",
        "img/gallery/gallery-02-hd.webp",
        "3a7813f643e4767d97a55478e4128258b0f88ed5",
        88702,
    ),
    "p03": (
        "Детский торт с зайчиком",
        "img/gallery/gallery-03-hd.webp",
        "5aa281e85a7d62a9e638ae657178d9b498a4636e",
        104376,
    ),
    "p04": (
        "3D-торт в прозрачном цилиндре",
        "img/gallery/gallery-04-hd.webp",
        "6a9cb1fa1ab747ba4deca74f0bd4b5be5a731523",
        151396,
    ),
    "p11": (
        "Светлый свадебный торт",
        "img/gallery/gallery-11-hd.webp",
        "53647470a15b3f7b2c7a2bc9f1b6047b0950e75e",
        130526,
    ),
    "p16": (
        "Капкейки с кремовым декором",
        "img/gallery/gallery-16-hd.webp",
        "94b153df857adb1f41ff902b46a8df159a04d479",
        161712,
    ),
    "p17": (
        "Павлова с ягодной начинкой",
        "img/gallery/gallery-17-hd.webp",
        "7936bd296ee601e298bbc4ada739024b77d37fc5",
        137280,
    ),
    "p20": (
        "3D-торт в стиле Minecraft",
        "img/gallery/gallery-20-hd.webp",
        "6ed782e0949096570a7fb77b2b47048e35955b5f",
        159284,
    ),
    "p23": (
        "Бенто с романтичной надписью",
        "img/gallery/gallery-23-hd.webp",
        "c39f99b65bf69a102091e25180121d5a3441d7ac",
        108422,
    ),
    "p25": (
        "Меренговые рулеты в коробке",
        "img/gallery/gallery-25-hd.webp",
        "9544a03c8a429e1fa7eba1d6678f91f2a0540b44",
        133328,
    ),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_photo_source_readiness_freezes_exact_reviewed_git_objects() -> None:
    readiness = _load(READINESS_PATH)

    assert readiness["schema_version"] == 3
    assert readiness["project_key"] == "milovi-cake"
    assert readiness["owning_issue"] == 353
    assert readiness["source_repository"] == SOURCE_REPOSITORY
    assert readiness["source_commit"] == SOURCE_COMMIT
    assert readiness["source_tree_sha"] == SOURCE_TREE
    assert readiness["source_gallery_path"] == "js/gallery/data.js"
    assert readiness["source_gallery_blob_sha"] == GALLERY_BLOB
    assert readiness["source_git_tree_verified"] is True
    assert readiness["full_source_bytes_materialized"] is True
    assert readiness["source_byte_verified_count"] == 9
    assert readiness["transport_ready_count"] == 9
    assert readiness["transport_proof"] == ("content/telegram/milovi-cake/bootstrap-photo-transport-proof-2026-08.json")

    photos = {photo["media_id"]: photo for photo in readiness["photos"]}
    assert set(photos) == set(EXPECTED_PHOTOS)
    assert readiness["selected_photo_count"] == len(EXPECTED_PHOTOS) == 9

    for media_id, (title, path, blob_sha, byte_size) in EXPECTED_PHOTOS.items():
        photo = photos[media_id]
        assert photo["canonical_title"] == title
        assert photo["source_path"] == path
        assert photo["source_git_blob_sha1"] == blob_sha
        assert photo["source_byte_size"] == byte_size
        assert photo["materialized_sha256"].startswith("sha256:")
        assert photo["pixel_width"] > 0
        assert photo["pixel_height"] > 0
        assert photo["decoded_media_type"] == "image/webp"
        assert photo["transport_sha256"].startswith("sha256:")
        assert photo["transport_byte_size"] > 0
        assert photo["transport_ready"] is True


def test_exact_transport_readiness_is_separate_from_write_authority() -> None:
    readiness = _load(READINESS_PATH)
    proof = _load(TRANSPORT_PROOF_PATH)

    assert readiness["status"] == "provider_inert_exact_source_and_transport_verified"
    assert readiness["transport_ready_count"] == 9
    assert readiness["full_source_bytes_materialized"] is True
    assert readiness["provider_mutation_allowed"] is False
    assert readiness["provider_write_authorized"] is False
    assert all(photo["transport_ready"] is True for photo in readiness["photos"])

    assert proof["status"] == "provider_inert_exact_transport_verified"
    assert proof["photo_count"] == 9
    assert proof["transport_ready_count"] == 9
    assert proof["provider_write_performed"] is False
    assert proof["execution_authorized"] is False
    assert proof["provider_mutation_allowed"] is False

    rule = readiness["rule"].lower()
    assert "does not authorize telegram publication" in rule
    assert "separate reviewed rollout release" in rule
    assert "durable intent" in rule


def test_bootstrap_photo_candidates_cross_link_to_current_media_source_map() -> None:
    bootstrap = _load(BOOTSTRAP_PATH)
    media_map = _load(MEDIA_MAP_PATH)
    readiness = _load(READINESS_PATH)

    assert media_map["project_key"] == "milovi-cake"
    assert media_map["source_repository"] == SOURCE_REPOSITORY
    assert media_map["source_path"] == "js/gallery/data.js"
    assert media_map["source_blob_sha"] == GALLERY_BLOB

    source_items = {item["id"]: item for item in media_map["items"]}
    ready_photos = {photo["media_id"]: photo for photo in readiness["photos"]}
    photo_candidates = [item for item in bootstrap["candidates"] if item["operation"] == "sendPhoto"]

    assert len(photo_candidates) == 9
    assert {item["media_id"] for item in photo_candidates} == set(EXPECTED_PHOTOS)

    for candidate in photo_candidates:
        media_id = candidate["media_id"]
        source = source_items[media_id]
        readiness_item = ready_photos[media_id]
        assert source["type"] == "photo"
        assert source["title"] == readiness_item["canonical_title"]
        assert source["full"].lstrip("/") == readiness_item["source_path"]
        assert candidate["transport_ready"] is True
        assert candidate["execution_ready"] is False
        assert candidate["publication_authorized"] is False


def test_first_screen_bootstrap_is_fail_closed_after_historical_canary() -> None:
    bootstrap = _load(BOOTSTRAP_PATH)

    assert bootstrap["schema_version"] == 3
    assert bootstrap["project_key"] == "milovi-cake"
    assert bootstrap["owning_issue"] == 353
    assert bootstrap["status"] == "provider_inert_transport_verified_candidates"
    assert bootstrap["publication_authorized"] is False
    assert bootstrap["execution_ready"] is False
    assert bootstrap["provider_mutation_allowed"] is False
    assert bootstrap["sequence_size"] == 10
    assert bootstrap["school_items_in_first_screen"] == 0
    assert len(bootstrap["candidates"]) == 10

    dependency = bootstrap["dependency"]
    assert dependency["required_canary_publication_id"] == "milovi-cake-canary-001"
    assert dependency["historical_canary_provider_outcome"] == "verified"
    assert dependency["historical_canary_message_id"] == 25
    assert dependency["historical_canary_current_visibility"] == "operator_reported_deleted"
    assert dependency["operator_correction"].endswith("operator-correction-2026-08-16.json")

    assert set(bootstrap["allowed_operations"]) == {"sendPhoto", "sendMessage"}
    assert set(bootstrap["forbidden_operations"]) == {
        "sendVideo",
        "sendMediaGroup",
        "sendPoll",
        "sendDocument",
        "pinChatMessage",
        "createChatInviteLink",
    }

    assert [item["sequence"] for item in bootstrap["candidates"]] == list(range(1, 11))
    assert len({item["publication_id"] for item in bootstrap["candidates"]}) == 10
    assert all(item["publication_authorized"] is False for item in bootstrap["candidates"])
    assert all(item["execution_ready"] is False for item in bootstrap["candidates"])
    assert {item["operation"] for item in bootstrap["candidates"]} <= {"sendPhoto", "sendMessage"}


def test_first_screen_cupcake_copy_uses_matching_source_and_format_guidance() -> None:
    bootstrap = _load(BOOTSTRAP_PATH)
    cupcake = next(item for item in bootstrap["candidates"] if item["media_id"] == "p16")

    assert cupcake["operation"] == "sendPhoto"
    assert cupcake["role"] == "format_guide"
    assert "Капкейки как единый праздничный набор" in cupcake["caption"]
    assert "реальная работа Milovi Cake" in cupcake["caption"]
    assert "дополнение к основному торту" in cupcake["caption"]
    assert "Что написать кондитеру" not in cupcake["caption"]


def test_bootstrap_artifacts_do_not_embed_provider_credentials() -> None:
    combined = BOOTSTRAP_PATH.read_text(encoding="utf-8") + READINESS_PATH.read_text(encoding="utf-8")
    lowered = combined.lower()

    assert ".webm" not in lowered
    assert "bot_token" not in lowered
    assert "telegram_bot_token" not in lowered


def test_verified_review_candidate_is_exactly_sourced_and_still_unauthorized() -> None:
    bootstrap = _load(BOOTSTRAP_PATH)
    review = next(item for item in bootstrap["candidates"] if item["role"] == "verified_social_proof")

    assert review["operation"] == "sendMessage"
    assert review["media_id"] is None
    assert review["transport_ready"] is True
    assert review["execution_ready"] is False
    assert review["publication_authorized"] is False
    assert review["fact_source"] == {
        "repository": SOURCE_REPOSITORY,
        "commit": SOURCE_COMMIT,
        "path": "otzyvy/index.html",
        "git_blob_sha1": "cccfbc9c12d9d3724b0a27a481cbb1347f77716a",
        "review_author": "Ирина Силантьева",
        "date_published": "2024-05-01",
    }
    assert "40-летию свадьбы" in review["caption"]
    assert "гости были в восторге" in review["caption"]
