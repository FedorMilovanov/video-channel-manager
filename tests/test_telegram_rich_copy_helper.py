from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "telegram-rich-copy" / "index.html"
MANUAL_STANDARD = ROOT / "content" / "telegram" / "lordchrist" / "MANUAL_RICH_COPY.md"
LORCHRIST_README = ROOT / "content" / "telegram" / "lordchrist" / "README.md"


def _helper() -> str:
    return HELPER.read_text(encoding="utf-8")


def test_manual_rich_copy_helper_is_present_and_documented() -> None:
    """The manual rich-copy path is a repository asset, not a chat bookmark."""

    assert HELPER.is_file()
    manual = MANUAL_STANDARD.read_text(encoding="utf-8")
    readme = LORCHRIST_README.read_text(encoding="utf-8")

    assert "tools/telegram-rich-copy/index.html" in manual
    assert "MANUAL_RICH_COPY.md" in readme

    # The manual lane never becomes provider authority by itself.
    assert "does **not** authorize a provider write" in manual
    assert "Saved Messages" in manual
    assert "top-level" in manual and "HTTPS" in manual
    # Both clipboard lanes stay distinct and discoverable from the contract.
    assert "DIRECT_COPY_TO_TELEGRAM.md" in manual
    assert "RICH_EDITOR_ARTICLE_STANDARD.md" in manual


def test_helper_refuses_an_unverified_environment_instead_of_silent_fallback() -> None:
    """Silent plain-text fallback is the defect this helper exists to prevent."""

    helper = _helper()

    assert "isSecureContext" in helper
    assert "window.top === window.self" in helper
    assert "ClipboardItem.supports" in helper
    assert "text/html" in helper
    # Every path either succeeds with a rich write or reports a hard failure.
    assert "✗ " in helper
    assert "✓ Clipboard API подтвердил rich write" in helper
    for forbidden in (
        "execCommand",
        "document.designMode",
        "fallback",
        "text/plain only",
    ):
        assert forbidden not in helper, forbidden


def test_helper_writes_one_clipboard_item_with_both_representations() -> None:
    helper = _helper()

    item = re.search(r"new ClipboardItem\(\{(?P<body>.*?)\}\);", helper, re.DOTALL)
    assert item is not None, "the helper must build one ClipboardItem"
    body = item.group("body")

    assert "'text/plain'" in body
    assert "'text/html'" in body
    assert "navigator.clipboard.write" in helper


def test_helper_performs_no_network_or_provider_mutation() -> None:
    helper = _helper()

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "sendBeacon",
        "WebSocket",
        "EventSource",
        "api.telegram.org",
    ):
        assert forbidden not in helper, forbidden

    # No remote assets: a third-party script or stylesheet would leak the article.
    for tag in re.findall(r"<(?:script|link)[^>]*>", helper):
        assert "http://" not in tag and "https://" not in tag, tag


def test_helper_rejects_code_fences_and_renders_supported_constructs() -> None:
    helper = _helper()

    assert "Кодовые блоки" in helper
    assert "<blockquote>" in helper
    assert "<b>$1</b>" in helper
    assert "<i>$1</i>" in helper
    # The operator gets a known-good payload to isolate clipboard regressions.
    assert "Жирный текст" in helper
    assert "Настоящий блок цитаты" in helper
