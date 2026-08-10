"""Legacy release digest fixtures must stay frozen and the bridge must be additive.

The rich article bridge is additive: it must not change the canonical
serialization (and therefore the frozen SHA-256 digests) of the existing
regular Telegram message pipeline.  These tests re-derive the committed legacy
digests from the repository content fixtures and assert they are unchanged,
and prove the model/validation/loader/fallback layer pulls in no
provider/state/workflow code.
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


def test_rich_bridge_layers_import_without_provider_or_state_modules() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent(
                """
                import sys

                from video_channel_manager import (
                    svodka_rich_loader,
                    telegram_rich_fallback,
                    telegram_rich_models,
                    telegram_rich_validation,
                )

                loaded = set(sys.modules)
                forbidden_prefixes = (
                    "video_channel_manager.platforms",
                    "video_channel_manager.telegram_multichannel_transport",
                    "video_channel_manager.telegram_transport",
                    "video_channel_manager.telegram_publisher",
                    "video_channel_manager.telegram_state",
                    "video_channel_manager.telegram_rich_provider",
                    "video_channel_manager.persistence",
                    "video_channel_manager.application",
                    "video_channel_manager.editorial",
                    "video_channel_manager.cli",
                    "httpx",
                    "requests",
                    "sqlalchemy",
                    "alembic",
                    "typer",
                )
                bad = sorted(name for name in loaded if name.startswith(forbidden_prefixes))
                assert not bad, f"rich bridge layers pulled in forbidden imports: {bad}"
                assert telegram_rich_models.RICH_ARTICLE_SCHEMA_VERSION == 1
                assert callable(telegram_rich_validation.validate_document)
                assert callable(svodka_rich_loader.load_svodka_rich_article)
                assert callable(telegram_rich_fallback.render_rich_html_fallback)
                """
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_rich_bridge_sources_contain_no_provider_writes_or_io() -> None:
    for filename in (
        "telegram_rich_models.py",
        "telegram_rich_validation.py",
        "svodka_rich_loader.py",
        "telegram_rich_fallback.py",
        "telegram_rich_renderer.py",
    ):
        source = (ROOT / "src" / "video_channel_manager" / filename).read_text(encoding="utf-8")
        for forbidden in (
            "import httpx",
            "import requests",
            "bot_token",
            "os.environ",
            "getenv",
            "api.telegram.org",
            "sendRichMessage(",
        ):
            assert forbidden not in source, f"{filename} must stay provider-inert (found {forbidden!r})"
