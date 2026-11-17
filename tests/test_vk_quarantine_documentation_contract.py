"""Keep canonical VK docs aligned with the retired-token quarantine.

This test reads checked-in text only; it never imports a VK client or opens a
browser session. Live credential provenance must still be independently proven.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
REGISTRY = ROOT / "docs" / "operations" / "project-identity-registry.md"


def test_readme_does_not_invite_vk_api_calls_using_quarantined_user_alias() -> None:
    readme = README.read_text(encoding="utf-8")
    for command in (
        "video-manager vk login --account legendary-poet",
        "video-manager vk communities --account legendary-poet",
        "video-manager vk scan --account legendary-poet",
        "video-manager vk token-capabilities --account legendary-poet",
    ):
        assert command not in readme, f"README must not offer quarantined VK API command: {command}"
    assert "video-manager vk accounts" in readme
    assert "docs/operations/vk-credential-quarantine.md" in readme


def test_registry_separates_legacy_token_from_reusable_isolated_browser() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    assert registry.count("Historical shared VK **user-token** alias:") == 3
    assert "VK API calls" in registry
    assert "`default`" in registry
    assert "vk-lord-god-community-key" in registry
    assert "browser profile/session" in registry
    for community in ("60805374", "235216998", "68859909"):
        assert community in registry
