from sqlalchemy import inspect

from video_channel_manager.persistence import Database


def test_database_creates_foundation_tables(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    database.create_schema()
    tables = set(inspect(database.engine).get_table_names())
    assert {"channels", "remote_videos", "change_plans", "operation_attempts"} <= tables
