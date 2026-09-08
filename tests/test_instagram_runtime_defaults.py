from __future__ import annotations

from video_channel_manager.config.settings import AppSettings


def test_instagram_polling_defaults_match_meta_recommendation() -> None:
    settings = AppSettings(_env_file=None)

    assert settings.instagram_poll_interval_seconds == 60.0
    assert settings.instagram_poll_attempts == 5
