from __future__ import annotations

from video_channel_manager.config.settings import AppSettings


def test_instagram_polling_defaults_match_meta_recommendation() -> None:
    assert AppSettings.model_fields["instagram_poll_interval_seconds"].default == 60.0
    assert AppSettings.model_fields["instagram_poll_attempts"].default == 5
