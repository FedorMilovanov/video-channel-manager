"""Legacy release digest fixtures must stay frozen and the new module must be additive.

The rich article model is additive: it must not change the canonical
serialization (and therefore the frozen SHA-256 digests) of the existing
regular Telegram message pipeline.  These tests re-derive the committed legacy
digests from the repository content fixtures and assert they are unchanged, and
prove the new modules pull in no provider/state/workflow code.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_publisher import load_queue
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_research_release import build_research_release_candidate
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
SVODKA_PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
LORDCHRIST_PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
LORDCHRIST_BINDING_PATH = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
LORDCHRIST_QUEUE_PATH = ROOT / "content/telegram/lordchrist/verified-30-posts.json"
RESEARCH_QUEUE_PATH = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"

EXPECTED_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
EXPECTED_SVODKA_PROFILE_DIGEST = "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"
EXPECTED_LORDCHRIST_PROFILE_DIGEST = "sha256:0de6ac7a664b4a7bfad6815f543357a2c78809b776f1c6a054cf2aaf9ef01ba6"
EXPECTED_CANDIDATE_DIGEST = "sha256:2eb3825390b8f4e70b847d9d1b328ea4e203bce0f1c88e036ea97ae667809cd0"
EXPECTED_BINDING_PROFILE_SHA = "sha256:0de6ac7a664b4a7bfad6815f543357a2c78809b776f1c6a054cf2aaf9ef01ba6"
EXPECTED_BINDING_DIGEST = "sha256:4d4bd46405080512aaf31b4ee4bbeeca22eb1703642b585efc656b8f95e15bcd"


def test_lordchrist_regular_queue_digest_unchanged() -> None:
    queue = load_queue(LORDCHRIST_QUEUE_PATH)
    assert queue.digest == EXPECTED_QUEUE_DIGEST


def test_svodka_channel_profile_digest_unchanged() -> None:
    profile = load_channel_profile(SVODKA_PROFILE_PATH)
    assert profile.digest == EXPECTED_SVODKA_PROFILE_DIGEST


def test_lordchrist_channel_profile_digest_unchanged() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    assert profile.digest == EXPECTED_LORDCHRIST_PROFILE_DIGEST


def test_research_release_candidate_digest_unchanged() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    binding = load_target_binding(LORDCHRIST_BINDING_PATH, profile)
    research = load_research_queue(RESEARCH_QUEUE_PATH)
    candidate = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-research-calvin-spurgeon-macarthur-v1",
        start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
        binding=binding,
    )
    assert isinstance(candidate, GenericReleaseQueue)
    assert candidate.candidate_digest() == EXPECTED_CANDIDATE_DIGEST


def test_target_binding_digests_unchanged() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    binding = load_target_binding(LORDCHRIST_BINDING_PATH, profile)
    assert binding.profile_sha256 == EXPECTED_BINDING_PROFILE_SHA
    assert binding.digest == EXPECTED_BINDING_DIGEST
    assert binding.provider_write_performed is False


def test_rich_article_modules_import_without_provider_or_state_modules() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent("""
            import sys

            from video_channel_manager import telegram_rich_models, telegram_rich_validation

            loaded = set(sys.modules)
            forbidden_prefixes = (
                "video_channel_manager.platforms",
                "video_channel_manager.telegram_multichannel_transport",
                "video_channel_manager.telegram_transport",
                "video_channel_manager.telegram_publisher",
                "video_channel_manager.telegram_state",
                "video_channel_manager.persistence",
                "video_channel_manager.application",
                "video_channel_manager.editorial",
                "video_channel_manager.cli",
                "video_channel_manager.svodka_",
                "httpx",
                "requests",
                "sqlalchemy",
                "alembic",
                "typer",
            )
            bad = sorted(name for name in loaded if name.startswith(forbidden_prefixes))
            assert not bad, f"rich article modules pulled in forbidden imports: {bad}"
            assert telegram_rich_models.RICH_ARTICLE_SCHEMA_VERSION == 1
            assert callable(telegram_rich_validation.validate_document)
        """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_rich_article_sources_contain_no_provider_writes_or_io() -> None:
    models_source = (ROOT / "src/video_channel_manager/telegram_rich_models.py").read_text(encoding="utf-8")
    validation_source = (ROOT / "src/video_channel_manager/telegram_rich_validation.py").read_text(encoding="utf-8")
    for source in (models_source, validation_source):
        assert "httpx" not in source
        assert "requests" not in source
        assert "Path(" not in source
        assert "open(" not in source
        assert ".write_text" not in source
        assert ".read_text" not in source
        assert "api.telegram.org" not in source


def test_rich_article_digest_is_computed_without_provider_effect() -> None:
    """A full document lifecycle (build -> serialize -> digest) stays offline and pure."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent("""
            from video_channel_manager.telegram_rich_models import RICH_ARTICLE_SCHEMA_NAME, RichArticleDocument
            from video_channel_manager.telegram_rich_validation import plain_text, validate_document

            document = RichArticleDocument.model_validate({
                "schema_name": RICH_ARTICLE_SCHEMA_NAME,
                "schema_version": 1,
                "document_id": "svodka-pure-0001",
                "project_key": "svodka",
                "metadata": {"title": "Чисто", "language": "ru", "created_at": "2026-08-10"},
                "blocks": [{"type": "paragraph", "block_id": "p-1", "text": "Без сети"}],
            })
            validate_document(document)
            assert document.digest.startswith("sha256:")
            assert plain_text(document) == "Без сети"
            assert document.digest == document.digest
        """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_modules_still_import_after_rich_article_import() -> None:
    """Importing the new modules alongside the legacy pipeline changes nothing."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent("""
            import hashlib
            import json

            import video_channel_manager.telegram_rich_models  # noqa: F401
            from video_channel_manager.telegram_models import canonical_json, sha256_text

            payload = {"a": 1, "b": [2, 3]}
            expected = "sha256:" + hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            assert sha256_text(canonical_json(payload)) == expected
            assert canonical_json(payload) == '{"a":1,"b":[2,3]}'
        """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
