from __future__ import annotations

from video_channel_manager.platforms.vk.models import VkAccessToken


def test_token_can_be_parsed_from_redirect_url() -> None:
    token = VkAccessToken.from_text("https://oauth.vk.com/blank.html#access_token=secret&expires_in=3600&user_id=42")
    assert token.access_token == "secret"
    assert token.user_id == 42
    assert token.expires_at is not None


def test_raw_token_is_supported() -> None:
    token = VkAccessToken.from_text("plain-secret-token")
    assert token.access_token == "plain-secret-token"
    assert token.user_id is None
