from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from video_channel_manager.config import get_settings


def test_fresh_alembic_upgrade_head_creates_instagram_ledger(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "fresh-upgrade.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("VCM_DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = Config(str(repository_root / "alembic.ini"))
    config.set_main_option("script_location", str(repository_root / "migrations"))
    try:
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "instagram_publications" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("instagram_publications")}
        assert {
            "publication_key",
            "account_id",
            "content_hash",
            "manifest",
            "status",
            "provider_container_id",
            "provider_media_id",
            "provider_status",
            "attempt_count",
            "last_error_code",
            "last_error_message",
            "container_requested_at",
            "publish_requested_at",
            "published_at",
            "created_at",
            "updated_at",
        } <= columns
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "0002"
    finally:
        engine.dispose()
