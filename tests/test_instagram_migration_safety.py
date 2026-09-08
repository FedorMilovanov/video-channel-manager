from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from video_channel_manager.config import get_settings


def test_instagram_ledger_downgrade_refuses_non_empty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "durable-ledger.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("VCM_DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = Config(str(repository_root / "alembic.ini"))
    config.set_main_option("script_location", str(repository_root / "migrations"))
    try:
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO instagram_publications (
                            publication_key,
                            account_id,
                            content_hash,
                            manifest,
                            status,
                            attempt_count,
                            created_at,
                            updated_at
                        ) VALUES (
                            :publication_key,
                            :account_id,
                            :content_hash,
                            :manifest,
                            :status,
                            :attempt_count,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "publication_key": "durable-ledger-test",
                        "account_id": "17841400000000000",
                        "content_hash": f"sha256:{'0' * 64}",
                        "manifest": "{}",
                        "status": "planned",
                        "attempt_count": 0,
                    },
                )
        finally:
            engine.dispose()

        with pytest.raises(RuntimeError, match="Refusing to drop non-empty Instagram publication ledger"):
            command.downgrade(config, "0001")
    finally:
        get_settings.cache_clear()

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "instagram_publications" in inspector.get_table_names()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002"
            assert connection.execute(text("SELECT COUNT(*) FROM instagram_publications")).scalar_one() == 1
    finally:
        engine.dispose()
