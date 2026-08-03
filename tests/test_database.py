from sqlalchemy import inspect, text

from video_channel_manager.persistence import Database


def test_database_creates_foundation_tables(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        database.create_schema()
        tables = set(inspect(database.engine).get_table_names())
        assert {"channels", "remote_videos", "change_plans", "operation_attempts"} <= tables
    finally:
        database.close()


def test_file_sqlite_enables_reliability_pragmas(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'reliable.db'}")
    try:
        with database.engine.connect() as connection:
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

        assert str(journal_mode).lower() == "wal"
        assert busy_timeout == 5_000
        assert foreign_keys == 1
    finally:
        database.close()


def test_memory_sqlite_skips_wal_but_keeps_connection_pragmas() -> None:
    database = Database("sqlite:///:memory:")
    try:
        with database.engine.connect() as connection:
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

        assert str(journal_mode).lower() == "memory"
        assert busy_timeout == 5_000
        assert foreign_keys == 1
    finally:
        database.close()
