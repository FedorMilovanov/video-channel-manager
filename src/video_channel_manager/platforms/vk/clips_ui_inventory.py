from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

from video_channel_manager.editorial._project_profiles import PROJECT_VK_COMMUNITY_IDS

VK_CLIPS_UI_INVENTORY_SCHEMA = "vk-clips-browser-ui-read-v1"
MILOVI_PROJECT_KEY = "milovi-cake"
MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
MILOVI_PUBLIC_CLIPS_URL = "https://vkvideo.ru/@milovi_cake/clips"

_CLIP_TOKEN_RE = re.compile(r"clip(-?\d+)_(\d+)", flags=re.IGNORECASE)
_BLOCK_HINTS = (
    "captcha",
    "робот",
    "авториз",
    "войдите",
    "sign in",
    "access denied",
    "доступ ограничен",
)
_ALLOWED_RESPONSE_HOST_SUFFIXES = ("vk.com", "vk.ru", "vkvideo.ru", "vkuser.net", "userapi.com")
_DOM_EXTRACT_SCRIPT = r"""
() => Array.from(document.querySelectorAll('a[href]'))
  .map((node) => {
    const href = node.href || node.getAttribute('href') || '';
    if (!/clip-?\d+_\d+/i.test(href)) return null;
    const container = node.closest('article, li, [data-testid], [class*=Card], [class*=card], div');
    const context = container && container.innerText ? container.innerText : '';
    return {
      href,
      text: (node.innerText || '').trim().slice(0, 500),
      title: (node.getAttribute('title') || '').trim().slice(0, 500),
      aria: (node.getAttribute('aria-label') || '').trim().slice(0, 500),
      context: context.trim().slice(0, 1200),
    };
  })
  .filter(Boolean)
"""
_SCROLL_METRICS_SCRIPT = r"""
() => {
  const doc = document.documentElement;
  const body = document.body;
  const scrollHeight = Math.max(
    doc ? doc.scrollHeight : 0,
    body ? body.scrollHeight : 0,
    doc ? doc.offsetHeight : 0,
    body ? body.offsetHeight : 0
  );
  return {
    scrollHeight,
    scrollY: window.scrollY || window.pageYOffset || 0,
    innerHeight: window.innerHeight || 0,
  };
}
"""
_SCROLL_TO_END_SCRIPT = r"""
() => {
  const doc = document.documentElement;
  const body = document.body;
  const height = Math.max(
    doc ? doc.scrollHeight : 0,
    body ? body.scrollHeight : 0,
    doc ? doc.offsetHeight : 0,
    body ? body.offsetHeight : 0
  );
  window.scrollTo(0, height);
}
"""
_BODY_TEXT_SCRIPT = "() => document.body ? document.body.innerText.slice(0, 12000) : ''"


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _validate_identity(*, project_key: str, community_id: int, owner_id: int, url: str) -> str:
    normalized_project = project_key.strip()
    if normalized_project != MILOVI_PROJECT_KEY:
        raise ValueError(f"VK Clips browser reader is intentionally scoped to {MILOVI_PROJECT_KEY}; got {project_key}")
    if community_id != MILOVI_COMMUNITY_ID:
        raise ValueError(f"unexpected Milovi VK community_id: {community_id}")
    if owner_id != MILOVI_OWNER_ID:
        raise ValueError(f"unexpected Milovi VK owner_id: {owner_id}")
    if community_id not in PROJECT_VK_COMMUNITY_IDS.get(normalized_project, frozenset()):
        raise ValueError("Milovi project/community identity is not canonical in repository profiles")
    normalized_url = url.rstrip("/")
    if normalized_url != MILOVI_PUBLIC_CLIPS_URL:
        raise ValueError(f"unexpected Milovi public Clips route: {url}")
    return normalized_project


def _normalize_required_remote_ids(values: Sequence[str], *, owner_id: int) -> list[str]:
    expected_prefix = f"{owner_id}_"
    normalized: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value.startswith(expected_prefix):
            raise ValueError(f"required Clip ID does not belong to exact Milovi owner: {value}")
        suffix = value[len(expected_prefix) :]
        if not suffix.isdigit() or int(suffix) <= 0:
            raise ValueError(f"invalid required Clip ID: {value}")
        normalized.append(value)
    if len(normalized) != len(set(normalized)):
        raise ValueError("required Clip IDs must be unique")
    return normalized


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return parsed.path


def _int_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _text_value(value: object, *, limit: int = 1200) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _walk_short_video_objects(payload: object) -> Iterable[dict[str, Any]]:
    stack: list[object] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if str(current.get("type") or "") == "short_video":
                owner_id = _int_value(current.get("owner_id"))
                video_id = _int_value(current.get("id"))
                if owner_id is not None and video_id is not None and video_id > 0:
                    yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _new_record(*, owner_id: int, video_id: int) -> dict[str, Any]:
    remote_id = f"{owner_id}_{video_id}"
    return {
        "remote_id": remote_id,
        "owner_id": owner_id,
        "video_id": video_id,
        "type": "short_video",
        "is_native_clip": True,
        "title": "",
        "description": "",
        "canonical_permalink": f"https://vk.com/clip{remote_id}",
        "observed_href_paths": [],
        "evidence_sources": [],
    }


def _merge_record(
    records: dict[str, dict[str, Any]],
    *,
    owner_id: int,
    video_id: int,
    source: str,
    title: object = "",
    description: object = "",
    href: str = "",
) -> None:
    remote_id = f"{owner_id}_{video_id}"
    record = records.setdefault(remote_id, _new_record(owner_id=owner_id, video_id=video_id))
    if source not in record["evidence_sources"]:
        record["evidence_sources"].append(source)
    title_text = _text_value(title, limit=500)
    description_text = _text_value(description, limit=1500)
    if title_text and not record["title"]:
        record["title"] = title_text
    if description_text and not record["description"]:
        record["description"] = description_text
    if href:
        safe_href = _safe_url(href)
        if safe_href and safe_href not in record["observed_href_paths"]:
            record["observed_href_paths"].append(safe_href)


def _merge_dom_rows(
    rows: object,
    *,
    owner_id: int,
    target_records: dict[str, dict[str, Any]],
    foreign_remote_ids: set[str],
) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        href = str(row.get("href") or "")
        for match in _CLIP_TOKEN_RE.finditer(href):
            candidate_owner = int(match.group(1))
            video_id = int(match.group(2))
            remote_id = f"{candidate_owner}_{video_id}"
            if candidate_owner != owner_id:
                foreign_remote_ids.add(remote_id)
                continue
            title = row.get("title") or row.get("aria") or row.get("text") or row.get("context") or ""
            description = row.get("context") or ""
            _merge_record(
                target_records,
                owner_id=candidate_owner,
                video_id=video_id,
                source="dom_clip_href",
                title=title,
                description=description,
                href=href,
            )


def _merge_network_payload(
    payload: object,
    *,
    owner_id: int,
    target_records: dict[str, dict[str, Any]],
    foreign_remote_ids: set[str],
) -> int:
    observed = 0
    for item in _walk_short_video_objects(payload):
        candidate_owner = _int_value(item.get("owner_id"))
        video_id = _int_value(item.get("id"))
        if candidate_owner is None or video_id is None or video_id <= 0:
            continue
        observed += 1
        remote_id = f"{candidate_owner}_{video_id}"
        if candidate_owner != owner_id:
            foreign_remote_ids.add(remote_id)
            continue
        _merge_record(
            target_records,
            owner_id=candidate_owner,
            video_id=video_id,
            source="network_json_type_short_video",
            title=item.get("title"),
            description=item.get("description"),
        )
    return observed


def _browser_candidates(explicit: Path | None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if local_app_data:
        root = Path(local_app_data)
        candidates.extend(
            [
                root / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
                root / "Google" / "Chrome" / "Application" / "chrome.exe",
                root / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
        )
    for raw_root in (program_files, program_files_x86):
        if not raw_root:
            continue
        root = Path(raw_root)
        candidates.extend(
            [
                root / "Google" / "Chrome" / "Application" / "chrome.exe",
                root / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                root / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
            ]
        )
    return candidates


def _resolve_browser_executable(explicit: Path | None) -> Path:
    candidates = _browser_candidates(explicit)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    if explicit is not None:
        raise RuntimeError(f"browser executable does not exist: {explicit}")
    raise RuntimeError(
        "no supported installed Chromium browser was found; pass --browser-executable with Chrome, Edge, or Yandex Browser"
    )


def _playwright_version() -> str | None:
    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        return None


def _run_playwright_probe(
    *,
    url: str,
    owner_id: int,
    browser_executable: Path | None,
    profile_dir: Path | None,
    headless: bool,
    max_scrolls: int,
    stable_rounds_required: int,
    wait_ms: int,
) -> dict[str, Any]:
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'Playwright is not installed; install current repo with: pip install -e ".[browser-read]"'
        ) from exc

    sync_playwright: Any = vars(sync_api)["sync_playwright"]
    executable = _resolve_browser_executable(browser_executable)
    target_records: dict[str, dict[str, Any]] = {}
    foreign_remote_ids: set[str] = set()
    network_short_video_observations = 0
    response_json_documents = 0
    scroll_iterations = 0
    stable_rounds = 0
    reached_stable_end = False
    final_url = url
    page_title = ""
    body_text = ""
    last_signature: tuple[int, int, bool] | None = None

    with sync_playwright() as playwright:
        chromium = playwright.chromium
        browser: Any | None = None
        if profile_dir is not None:
            profile_dir.mkdir(parents=True, exist_ok=True)
            context: Any = chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                executable_path=str(executable),
                headless=headless,
            )
        else:
            browser = chromium.launch(executable_path=str(executable), headless=headless)
            context = browser.new_context()

        try:
            page = context.pages[0] if context.pages else context.new_page()

            def on_response(response: Any) -> None:
                nonlocal network_short_video_observations, response_json_documents
                try:
                    parsed = urlsplit(str(response.url))
                    host = parsed.hostname or ""
                    if not any(
                        host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_RESPONSE_HOST_SUFFIXES
                    ):
                        return
                    content_type = str(response.headers.get("content-type") or "").lower()
                    if "json" not in content_type:
                        return
                    payload = response.json()
                except Exception:
                    return
                response_json_documents += 1
                network_short_video_observations += _merge_network_payload(
                    payload,
                    owner_id=owner_id,
                    target_records=target_records,
                    foreign_remote_ids=foreign_remote_ids,
                )

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(max(wait_ms, 1500))

            for index in range(max_scrolls + 1):
                rows = page.evaluate(_DOM_EXTRACT_SCRIPT)
                _merge_dom_rows(
                    rows,
                    owner_id=owner_id,
                    target_records=target_records,
                    foreign_remote_ids=foreign_remote_ids,
                )
                metrics_raw = page.evaluate(_SCROLL_METRICS_SCRIPT)
                metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
                scroll_height = int(metrics.get("scrollHeight") or 0)
                scroll_y = int(metrics.get("scrollY") or 0)
                inner_height = int(metrics.get("innerHeight") or 0)
                at_bottom = scroll_height > 0 and scroll_y + inner_height >= scroll_height - 8
                signature = (len(target_records), scroll_height, at_bottom)
                if at_bottom and signature == last_signature:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                last_signature = signature
                if stable_rounds >= stable_rounds_required:
                    reached_stable_end = True
                    break
                if index >= max_scrolls:
                    break
                page.evaluate(_SCROLL_TO_END_SCRIPT)
                scroll_iterations += 1
                page.wait_for_timeout(wait_ms)

            page.wait_for_timeout(wait_ms)
            rows = page.evaluate(_DOM_EXTRACT_SCRIPT)
            _merge_dom_rows(
                rows,
                owner_id=owner_id,
                target_records=target_records,
                foreign_remote_ids=foreign_remote_ids,
            )
            final_url = _safe_url(str(page.url))
            page_title = _text_value(page.title(), limit=500)
            body_text = _text_value(page.evaluate(_BODY_TEXT_SCRIPT), limit=12000)
        finally:
            context.close()
            if browser is not None:
                browser.close()

    blocked_hints = sorted({hint for hint in _BLOCK_HINTS if hint in body_text.lower()})
    if target_records and reached_stable_end:
        status = "ok_bounded_ui_observation"
    elif target_records:
        status = "partial_ui_observation"
    elif blocked_hints:
        status = "blocked_or_login_required"
    else:
        status = "no_target_clips_observed"

    clips = [target_records[key] for key in sorted(target_records)]
    for item in clips:
        item["evidence_sources"] = sorted(item["evidence_sources"])
        item["observed_href_paths"] = sorted(item["observed_href_paths"])

    return {
        "status": status,
        "requested_url": url,
        "final_url": final_url,
        "page_title": page_title,
        "browser_executable_name": executable.name,
        "playwright_version": _playwright_version(),
        "headless": headless,
        "persistent_profile_used": profile_dir is not None,
        "scroll_iterations": scroll_iterations,
        "stable_rounds_observed": stable_rounds,
        "stable_rounds_required": stable_rounds_required,
        "reached_stable_end": reached_stable_end,
        "response_json_documents": response_json_documents,
        "network_short_video_observations": network_short_video_observations,
        "foreign_clip_identity_count": len(foreign_remote_ids),
        "blocked_hints": blocked_hints,
        "clips": clips,
        "interaction_evidence": {
            "navigation_calls": 1,
            "scroll_calls": scroll_iterations,
            "dom_reads": True,
            "network_response_reads": True,
            "click_calls": 0,
            "form_fill_calls": 0,
            "keyboard_submit_calls": 0,
        },
    }


def build_vk_clips_ui_inventory(
    *,
    project_key: str,
    community_id: int,
    owner_id: int,
    required_remote_ids: Sequence[str] = (),
    url: str = MILOVI_PUBLIC_CLIPS_URL,
    browser_executable: Path | None = None,
    profile_dir: Path | None = None,
    headless: bool = False,
    max_scrolls: int = 240,
    stable_rounds_required: int = 5,
    wait_ms: int = 1200,
) -> dict[str, Any]:
    normalized_project = _validate_identity(
        project_key=project_key,
        community_id=community_id,
        owner_id=owner_id,
        url=url,
    )
    required = _normalize_required_remote_ids(required_remote_ids, owner_id=owner_id)
    if max_scrolls < 1 or max_scrolls > 1000:
        raise ValueError("max_scrolls must be between 1 and 1000")
    if stable_rounds_required < 2 or stable_rounds_required > 20:
        raise ValueError("stable_rounds_required must be between 2 and 20")
    if wait_ms < 250 or wait_ms > 10_000:
        raise ValueError("wait_ms must be between 250 and 10000")

    probe = _run_playwright_probe(
        url=url,
        owner_id=owner_id,
        browser_executable=browser_executable,
        profile_dir=profile_dir,
        headless=headless,
        max_scrolls=max_scrolls,
        stable_rounds_required=stable_rounds_required,
        wait_ms=wait_ms,
    )
    clips = probe.get("clips")
    if not isinstance(clips, list):
        raise ValueError("browser probe returned no clip list")
    remote_ids = [str(item.get("remote_id") or "") for item in clips if isinstance(item, dict)]
    if len(remote_ids) != len(set(remote_ids)):
        raise ValueError("browser probe returned duplicate exact-owner Clip IDs")
    if any(not remote_id.startswith(f"{owner_id}_") for remote_id in remote_ids):
        raise ValueError("browser probe normalized a foreign Clip into the Milovi target set")
    observed = set(remote_ids)
    required_found = [remote_id for remote_id in required if remote_id in observed]
    required_missing = [remote_id for remote_id in required if remote_id not in observed]

    return {
        "schema": VK_CLIPS_UI_INVENTORY_SCHEMA,
        "generated_at": _utc_iso(),
        "project_key": normalized_project,
        "community_id": community_id,
        "owner_id": owner_id,
        "read_only": True,
        "provider_effect": "safe_read_only",
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "transport": "browser_ui_read",
        "public_surface": {
            "requested_url": url,
            "identity_contract": "exact canonical Milovi project/community/owner plus exact-owner Clip identities",
            "credential_alias_selects_target": False,
        },
        "browser_probe": {key: value for key, value in probe.items() if key != "clips"},
        "coverage": {
            "clip_count": len(clips),
            "required_remote_ids": required,
            "required_remote_ids_found": required_found,
            "required_remote_ids_missing": required_missing,
            "bounded_ui_end_observed": probe.get("reached_stable_end") is True,
            "native_clip_identity_rule": (
                "exact-owner clip<owner>_<id> UI route and/or provider response object explicitly type=short_video"
            ),
            "surface_complete_claim": False,
            "surface_complete_reason": (
                "scroll stabilization is bounded browser evidence for the public Clips UI; it is not authority for hidden, private, draft, or otherwise non-rendered provider objects"
            ),
        },
        "clips": clips,
        "known_limitations": [
            "This reader never clicks, fills forms, submits keyboard actions, uploads, edits, hides, deletes, posts, or schedules.",
            "Foreign Clip identities rendered as recommendations are counted as noise and never enter the Milovi target set.",
            "The output does not persist cookies, headers, authorization data, network bodies, or URL query strings.",
            "A Clip absent from this bounded public UI read is not proof that no provider object exists.",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Read Milovi Cake VK Clips from the public browser UI without provider mutation."
    )
    root.add_argument("--project", required=True)
    root.add_argument("--community", required=True, type=int)
    root.add_argument("--owner-id", required=True, type=int)
    root.add_argument("--require-remote-id", action="append", default=[])
    root.add_argument("--url", default=MILOVI_PUBLIC_CLIPS_URL)
    root.add_argument("--browser-executable", type=Path)
    root.add_argument("--profile-dir", type=Path)
    root.add_argument("--headless", action="store_true")
    root.add_argument("--max-scrolls", type=int, default=240)
    root.add_argument("--stable-rounds", type=int, default=5)
    root.add_argument("--wait-ms", type=int, default=1200)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        snapshot = build_vk_clips_ui_inventory(
            project_key=args.project,
            community_id=args.community,
            owner_id=args.owner_id,
            required_remote_ids=args.require_remote_id,
            url=args.url,
            browser_executable=args.browser_executable,
            profile_dir=args.profile_dir,
            headless=args.headless,
            max_scrolls=args.max_scrolls,
            stable_rounds_required=args.stable_rounds,
            wait_ms=args.wait_ms,
        )
    except Exception as exc:
        failure = {
            "schema": VK_CLIPS_UI_INVENTORY_SCHEMA,
            "generated_at": _utc_iso(),
            "project_key": args.project,
            "community_id": args.community,
            "owner_id": args.owner_id,
            "read_only": True,
            "provider_writes": 0,
            "provider_mutation_authorized": False,
            "transport": "browser_ui_read",
            "status": "failed_before_inventory",
            "error": str(exc),
        }
        _write_json(args.output, failure)
        print(json.dumps({"status": "failed_before_inventory", "provider_writes": 0, "output": str(args.output)}))
        return 2

    _write_json(args.output, snapshot)
    probe = snapshot["browser_probe"]
    coverage = snapshot["coverage"]
    print(
        json.dumps(
            {
                "status": probe["status"],
                "clips": coverage["clip_count"],
                "required_found": coverage["required_remote_ids_found"],
                "required_missing": coverage["required_remote_ids_missing"],
                "bounded_ui_end_observed": coverage["bounded_ui_end_observed"],
                "surface_complete_claim": False,
                "provider_writes": 0,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MILOVI_PUBLIC_CLIPS_URL",
    "VK_CLIPS_UI_INVENTORY_SCHEMA",
    "build_vk_clips_ui_inventory",
]
