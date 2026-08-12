from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID, MILOVI_OWNER_ID
from video_channel_manager.platforms.vk.milovi_rollout_sources import SourceAsset

MILOVI_SCREEN_NAME = "milovi_cake"


class MiloviBrowserBlocked(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserRuntime:
    executable: str
    user_data_dir: str
    profile_directory: str


def detect_browser_runtime() -> BrowserRuntime:
    local = Path(os.environ.get("LOCALAPPDATA", "")).expanduser()
    candidates = [
        (
            local / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
            local / "Yandex" / "YandexBrowser" / "User Data",
        ),
        (
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            local / "Microsoft" / "Edge" / "User Data",
        ),
        (
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            local / "Microsoft" / "Edge" / "User Data",
        ),
    ]
    for executable, user_data_dir in candidates:
        if not executable.is_file() or not user_data_dir.is_dir():
            continue
        profile_directory = "Default"
        local_state = user_data_dir / "Local State"
        if local_state.is_file():
            try:
                payload = json.loads(local_state.read_text(encoding="utf-8"))
                observed = str(((payload.get("profile") or {}).get("last_used") or "")).strip()
                if observed and (user_data_dir / observed).is_dir():
                    profile_directory = observed
            except (OSError, ValueError, TypeError):
                pass
        return BrowserRuntime(
            executable=str(executable.resolve()),
            user_data_dir=str(user_data_dir.resolve()),
            profile_directory=profile_directory,
        )
    raise MiloviBrowserBlocked("No supported logged-in Yandex/Edge browser profile was found")


def target_tokens_present(*, page_url: str, html: str, text: str) -> bool:
    joined = f"{page_url}\n{html}\n{text}".casefold()
    route_ok = f"/clips/club{MILOVI_COMMUNITY_ID}" in page_url.casefold()
    exact_token = (
        f"club{MILOVI_COMMUNITY_ID}" in joined or str(MILOVI_OWNER_ID) in joined or MILOVI_SCREEN_NAME in joined
    )
    title_token = bool(re.search(r"\bmilovi\s*cake\b", text, flags=re.IGNORECASE))
    wrong_selected = "thelegendarypoet" in joined and (
        'aria-selected="true"' in joined or 'aria-checked="true"' in joined
    )
    return route_ok and exact_token and title_token and not wrong_selected


def _visible_dialog_or_page(page: Any) -> Any:
    dialogs = page.locator('[role="dialog"]:visible')
    try:
        if dialogs.count():
            return dialogs.last
    except Exception:
        pass
    return page


def assert_browser_target(page: Any, *, stage: str) -> None:
    root = _visible_dialog_or_page(page)
    try:
        html = str(root.evaluate("(node) => node.outerHTML || document.documentElement.outerHTML"))
    except Exception:
        html = str(page.content())
    try:
        text = str(root.inner_text(timeout=3000))
    except Exception:
        text = str(page.locator("body").inner_text(timeout=3000))
    if not target_tokens_present(page_url=str(page.url), html=html, text=text):
        raise MiloviBrowserBlocked(
            f"Browser target proof failed at {stage}; exact Milovi community/screen identity was not observed"
        )


def _click_first(candidates: Iterable[Any], *, timeout_ms: int = 5000) -> bool:
    for candidate in candidates:
        try:
            count = candidate.count()
        except Exception:
            continue
        for index in range(min(count, 8)):
            item = candidate.nth(index)
            try:
                if item.is_visible(timeout=300) and item.is_enabled(timeout=300):
                    item.click(timeout=timeout_ms)
                    return True
            except Exception:
                continue
    return False


def open_add_clip(page: Any) -> None:
    target_url = f"https://vkvideo.ru/clips/club{MILOVI_COMMUNITY_ID}"
    page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(1500)
    if f"/clips/club{MILOVI_COMMUNITY_ID}" not in str(page.url):
        raise MiloviBrowserBlocked(f"VK Video did not retain exact Milovi group Clip route: {page.url}")
    direct = [
        page.get_by_text(re.compile(r"^Добавить клип$", re.I)),
        page.get_by_text(re.compile(r"^Опубликовать клип$", re.I)),
        page.get_by_role("button", name=re.compile(r"добавить клип|опубликовать клип", re.I)),
    ]
    if not _click_first(direct, timeout_ms=10000):
        plus = [
            page.get_by_role("button", name=re.compile(r"добавить|создать", re.I)),
            page.locator('button[aria-label*="Добавить" i]'),
        ]
        if not _click_first(plus, timeout_ms=5000):
            raise MiloviBrowserBlocked("Native Clip UI entrypoint was not found")
        page.wait_for_timeout(500)
        if not _click_first(direct, timeout_ms=5000):
            raise MiloviBrowserBlocked("Native Clip action was not found after opening the create menu")
    page.wait_for_timeout(700)


def select_exact_publisher(page: Any) -> None:
    root = _visible_dialog_or_page(page)
    exact = [
        root.locator(f'a[href*="club{MILOVI_COMMUNITY_ID}"]'),
        root.locator(f'a[href*="{MILOVI_SCREEN_NAME}"]'),
        root.locator(f'[data-owner-id="{MILOVI_OWNER_ID}"]'),
        root.locator(f'[data-community-id="{MILOVI_COMMUNITY_ID}"]'),
        root.get_by_text(re.compile(r"^Milovi\s*Cake$", re.I)),
    ]
    _click_first(exact, timeout_ms=3000)
    page.wait_for_timeout(500)
    assert_browser_target(page, stage="publisher-selection")


def uncheck_wall(page: Any) -> None:
    pattern = re.compile(r"пост на стене|опубликовать.*стен", re.I)
    controls = [
        page.get_by_role("checkbox", name=pattern),
        page.get_by_role("switch", name=pattern),
    ]
    for control in controls:
        try:
            if not control.count():
                continue
            loc = control.first
            if not loc.is_visible(timeout=500):
                continue
            try:
                checked = bool(loc.is_checked())
            except Exception:
                checked = str(loc.get_attribute("aria-checked") or "").lower() == "true"
            if checked:
                try:
                    loc.uncheck()
                except Exception:
                    loc.click()
            try:
                still_checked = bool(loc.is_checked())
            except Exception:
                still_checked = str(loc.get_attribute("aria-checked") or "").lower() == "true"
            if still_checked:
                raise MiloviBrowserBlocked("Could not disable Clip-form wall publication")
            return
        except MiloviBrowserBlocked:
            raise
        except Exception:
            continue
    labels = [
        page.get_by_text(re.compile(r"^Пост на стене$", re.I)),
        page.get_by_text(re.compile(r"Опубликовать.*стен", re.I)),
    ]
    for label in labels:
        try:
            if not label.count() or not label.first.is_visible(timeout=500):
                continue
            checkbox = label.first.locator('xpath=ancestor-or-self::label[1]//input[@type="checkbox"]')
            if checkbox.count():
                if checkbox.first.is_checked():
                    checkbox.first.uncheck()
                if checkbox.first.is_checked():
                    raise MiloviBrowserBlocked("Could not disable Clip-form wall publication")
                return
        except MiloviBrowserBlocked:
            raise
        except Exception:
            continue
    raise MiloviBrowserBlocked("Clip-form wall-post control could not be verified; stopping before Publish")


def _fill_first(candidates: Iterable[Any], value: str) -> bool:
    for candidate in candidates:
        try:
            if not candidate.count():
                continue
            loc = candidate.first
            if not loc.is_visible(timeout=500):
                continue
            loc.fill(value)
            return True
        except Exception:
            continue
    return False


def set_file_and_metadata(page: Any, asset: SourceAsset) -> None:
    select_exact_publisher(page)
    assert_browser_target(page, stage="pre-file")
    file_input = page.locator('input[type="file"]')
    if not file_input.count():
        raise MiloviBrowserBlocked("Native Clip form has no file input")
    file_input.first.set_input_files(asset.media_path)
    deadline = time.monotonic() + 180
    description_filled = False
    while time.monotonic() < deadline:
        _fill_first(
            [
                page.get_by_label(re.compile(r"Название", re.I)),
                page.locator('input[placeholder*="назван" i]'),
            ],
            asset.title[:200],
        )
        if _fill_first(
            [
                page.get_by_label(re.compile(r"Описание", re.I)),
                page.locator('textarea[placeholder*="опис" i]'),
                page.locator("textarea"),
                page.locator('[contenteditable="true"]'),
            ],
            asset.description,
        ):
            description_filled = True
            break
        page.wait_for_timeout(1000)
    if not description_filled:
        raise MiloviBrowserBlocked("Native Clip description field was not found after file selection")
    deadline = time.monotonic() + 120
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            uncheck_wall(page)
            return
        except MiloviBrowserBlocked as exc:
            last_error = exc
            page.wait_for_timeout(1000)
    raise MiloviBrowserBlocked(f"Could not verify Clip-form wall setting: {last_error}")


def click_publish(page: Any, *, timeout_seconds: int = 1800) -> None:
    candidates = [
        page.get_by_role("button", name=re.compile(r"^Опубликовать$", re.I)),
        page.get_by_role("button", name=re.compile(r"Опубликовать клип", re.I)),
        page.get_by_text(re.compile(r"^Опубликовать$", re.I)),
    ]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _click_first(candidates, timeout_ms=5000):
            return
        page.wait_for_timeout(1000)
    raise MiloviBrowserBlocked("Publish button did not become safely clickable")


__all__ = [
    "BrowserRuntime",
    "MILOVI_SCREEN_NAME",
    "MiloviBrowserBlocked",
    "assert_browser_target",
    "click_publish",
    "detect_browser_runtime",
    "open_add_clip",
    "select_exact_publisher",
    "set_file_and_metadata",
    "target_tokens_present",
    "uncheck_wall",
]
