#!/usr/bin/env python3
"""Read-only owner Studio + public watch-page verification for one exact YouTube video.

Requires Playwright in the operator environment and an already authenticated
isolated Chrome CDP session. No Save, provider calls, retries or publication.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys

from video_channel_manager.youtube_public_render_proof import verify_public_description

CHANNEL = "UC-78ys2S3cQ3lpqgXfo-SvQ"
ID_RE = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--expected-description-file", type=Path, required=True)
    parser.add_argument("--expected-title", default="")
    parser.add_argument("--expected-playlist-memberships", type=int, choices=range(0, 101))
    parser.add_argument("--check-owner-pin", action="store_true")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9236")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not ID_RE.fullmatch(args.video_id):
        parser.error("Video ID must be an exact 11-character YouTube identifier.")
    if not args.expected_description_file.is_file():
        parser.error("Expected description file not found.")
    expected = args.expected_description_file.read_text(encoding="utf-8").strip()
    if not expected:
        parser.error("Expected description is empty.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("Playwright is optional; install it only in the dedicated operator environment.")

    problems: list[str] = []
    evidence: dict[str, object] = {
        "project_key": "legendary-poet",
        "channel_id": CHANNEL,
        "video_id": args.video_id,
        "checked_utc": datetime.now(UTC).isoformat(),
        "checks": "read-only browser observation, no provider writes",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=15000)
        if not browser.contexts:
            raise RuntimeError("CDP browser has no existing owner context.")
        page = browser.contexts[0].new_page()
        try:
            url = f"https://studio.youtube.com/video/{args.video_id}/edit"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if page.url.split("?")[0] != url:
                raise RuntimeError("Studio exact video ID redirect/identity mismatch.")
            editors = page.locator("[contenteditable=true]")
            editors.nth(1).wait_for(state="visible", timeout=15000)
            page.wait_for_timeout(1000)
            observed_title = editors.nth(0).inner_text().strip()
            observed = editors.nth(1).inner_text().strip()
            if args.expected_title and observed_title != args.expected_title:
                problems.append("studio_title_drift")
            playlist = page.locator("ytcp-video-metadata-playlists").inner_text().strip()
            memberships = 0 if playlist == "Select" else None
            match = re.fullmatch(r"(\d+) playlists?", playlist)
            if match:
                memberships = int(match.group(1))
            evidence["studio_playlist_memberships"] = memberships
            if args.expected_playlist_memberships is not None and memberships != args.expected_playlist_memberships:
                problems.append("playlist_membership_drift")

            page.goto(
                f"https://www.youtube.com/watch?v={args.video_id}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(900)
            identity = page.evaluate(
                """() => ({
                  id: window.ytInitialPlayerResponse?.videoDetails?.videoId,
                  channel: window.ytInitialPlayerResponse?.videoDetails?.channelId,
                })"""
            )
            if identity.get("id") != args.video_id or identity.get("channel") != CHANNEL:
                raise RuntimeError("Public player video or channel identity mismatch.")
            expander = page.locator("#description-inline-expander")
            expander.scroll_into_view_if_needed(timeout=9000)
            expander.locator("#expand").click(timeout=7000)
            block = expander.locator("#expanded")
            public = block.inner_text(timeout=7000)
            bold = block.locator('span[style*="font-weight: 700"],span.ytAttributedStringBolded').all_inner_texts()
            italic = block.locator("span.ytAttributedStringItalicized").all_inner_texts()
            render = verify_public_description(
                studio_expected=expected,
                studio_observed=observed,
                public_description_text=public,
                public_bold_fragments=bold,
                public_italic_fragments=italic,
            )
            evidence["public_render"] = asdict(render)
            problems.extend(render.problems)

            if args.check_owner_pin:
                page.locator("ytd-comments#comments").scroll_into_view_if_needed(timeout=10000)
                page.wait_for_timeout(1700)
                owners = page.locator("ytd-comment-thread-renderer").filter(has_text="@TheLegendaryPoet")
                if owners.count() != 1:
                    problems.append("owner_comment_missing_or_ambiguous")
                else:
                    owners.first.get_by_role("button", name="Action menu").click(timeout=7000)
                    menu = page.locator("ytd-menu-popup-renderer").inner_text()
                    evidence["owner_pinned"] = "Unpin" in menu
                    if not evidence["owner_pinned"]:
                        problems.append("owner_comment_not_pinned")
            evidence["problems"] = sorted(set(problems))
            evidence["verified"] = not problems
        finally:
            page.close()
            browser.close()

    output = json.dumps(evidence, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0 if evidence["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
