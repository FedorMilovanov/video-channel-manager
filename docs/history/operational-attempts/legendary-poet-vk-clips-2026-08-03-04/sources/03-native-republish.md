# Historical source snapshots

> Non-executable evidence only. Do not copy or run without a new reviewed design and tests.

## 009. Prepare 48 files for native Clips republish

- Original: `prepare_republish_48.py`
- SHA-256: `23ec6557689326429b15dc63aaf64f6db2c2d7ec831466c5eaec851a3e92cd36`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from video_channel_manager.config import get_settings
from video_channel_manager.local_media.quality import probe_media
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

BRAND_RE = re.compile(r"@thelegendarypoet|#thelegendarypoet|#theepicpoet|#shorts", re.I)
NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+", re.I)
SPACE_RE = re.compile(r"\s+")
VERSION_RE = re.compile(r"\b(?:версия|version)\s*[-–—:]?\s*(\d+)\b", re.I)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def canonical_sha256(payload: dict[str, Any], omit_key: str) -> str:
    body = dict(payload)
    body.pop(omit_key, None)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    text = BRAND_RE.sub(" ", text).replace("version", "версия")
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def versions(value: str) -> frozenset[int]:
    return frozenset(int(x.group(1)) for x in VERSION_RE.finditer(normalize(value)))


def youtube_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in audit.get("videos", []):
        if not isinstance(item, dict):
            continue
        ref = item.get("ref")
        sid = str(ref.get("remote_id") or "") if isinstance(ref, dict) else ""
        if sid and sid not in result:
            result[sid] = item
    return result


def enumerate_shorts(yt_dlp: str, url: str) -> list[str]:
    p = subprocess.run(
        [yt_dlp, "--flat-playlist", "--dump-single-json", "--no-warnings", url],
        capture_output=True,
        check=False,
        timeout=300,
    )
    if p.returncode != 0:
        raise ValueError(p.stderr.decode("utf-8", errors="replace")[-4000:])
    payload = json.loads(p.stdout.decode("utf-8"))
    ids: list[str] = []
    seen: set[str] = set()
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        sid = str(entry.get("id") or entry.get("url") or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


def hydrate(yt_dlp: str, sid: str, channel_id: str) -> dict[str, Any]:
    p = subprocess.run(
        [yt_dlp, "--dump-single-json", "--no-playlist", "--no-warnings", f"https://www.youtube.com/watch?v={sid}"],
        capture_output=True,
        check=False,
        timeout=300,
    )
    if p.returncode != 0:
        raise ValueError(f"Cannot hydrate {sid}: {p.stderr.decode('utf-8', errors='replace')[-3000:]}")
    data = json.loads(p.stdout.decode("utf-8"))
    observed_channel = str(data.get("channel_id") or data.get("uploader_id") or "")
    if observed_channel != channel_id:
        raise ValueError(f"{sid} belongs to {observed_channel}, expected {channel_id}")
    return {
        "ref": {"remote_id": sid},
        "title": str(data.get("title") or ""),
        "description": str(data.get("description") or ""),
        "duration_seconds": int(round(float(data.get("duration") or 0))),
        "metadata": {"width": data.get("width"), "height": data.get("height")},
    }


def download(yt_dlp: str, sid: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    exact = cache / f"{sid}.mp4"
    if exact.is_file() and exact.stat().st_size > 0:
        return exact
    cmd = [
        yt_dlp, "--no-playlist", "--no-progress", "--newline",
        "--merge-output-format", "mp4", "--remux-video", "mp4",
        "--format", "bv*+ba/b", "--output", str(cache / f"{sid}.%(ext)s"),
        f"https://www.youtube.com/watch?v={sid}",
    ]
    if subprocess.run(cmd, check=False).returncode != 0:
        raise ValueError(f"Download failed before VK browser upload: {sid}")
    if not exact.is_file():
        candidates = sorted(cache.glob(f"{sid}*.mp4"))
        if not candidates:
            raise ValueError(f"MP4 not found after download: {sid}")
        exact = candidates[0]
    return exact


def build_clip_description(item: dict[str, Any], sid: str) -> str:
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    marker = f"Источник YouTube Shorts: https://www.youtube.com/shorts/{sid}"
    # Reserve space for the exact source marker; never truncate it away.
    prefix = title
    available = 4000 - len(marker) - 4
    if description and available > len(prefix) + 2:
        remaining = max(0, available - len(prefix) - 2)
        prefix = prefix + "\n\n" + description[:remaining]
    return prefix.rstrip() + "\n\n" + marker


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--youtube-audit", type=Path, required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--shorts-url", required=True)
    ap.add_argument("--channel-id", required=True)
    ap.add_argument("--community", type=int, required=True)
    ap.add_argument("--account", default="legendary-poet")
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--queue-output", type=Path, required=True)
    ap.add_argument("--yt-dlp", default="yt-dlp")
    ap.add_argument("--ffprobe", default="ffprobe")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--canary-only", action="store_true")
    args = ap.parse_args()

    republish = read_json(args.map)
    if republish.get("schema_name") != "video-manager.legendary-poet-republish-clips-map":
        raise ValueError("Unexpected republish map schema")
    if canonical_sha256(republish, "map_sha256") != republish.get("map_sha256"):
        raise ValueError("Republish map SHA-256 mismatch")
    if int(republish.get("vk_community_id") or 0) != args.community:
        raise ValueError("Republish map belongs to another VK community")
    items = [x for x in republish.get("items", []) if isinstance(x, dict)]
    if len(items) != 48 or len({str(x.get('source_id')) for x in items}) != 48:
        raise ValueError("Expected exactly 48 unique republish sources")

    live_shorts = enumerate_shorts(args.yt_dlp, args.shorts_url)
    live_set = set(live_shorts)
    queue_ids = {str(x["source_id"]) for x in items}
    missing_from_live = sorted(queue_ids - live_set)
    if missing_from_live:
        raise ValueError(f"Reviewed republish Shorts disappeared from live Shorts tab: {missing_from_live}")
    known_sources = queue_ids | {str(x) for x in republish.get("already_correct_source_ids", [])}
    extra_live = sorted(live_set - known_sources)

    audit = read_json(args.youtube_audit)
    by_id = youtube_map(audit)
    hydrated: list[str] = []
    for entry in items:
        sid = str(entry["source_id"])
        if sid not in by_id:
            print(f"Hydrating exact republish source absent from audit: {sid}")
            by_id[sid] = hydrate(args.yt_dlp, sid, args.channel_id)
            hydrated.append(sid)
        current = by_id[sid]
        if normalize(str(current.get("title") or "")) != normalize(str(entry.get("source_title") or "")):
            raise ValueError(f"Title changed for {sid}")
        actual_duration = int(current.get("duration_seconds") or 0)
        expected_duration = int(entry.get("source_duration_seconds") or 0)
        if actual_duration != expected_duration:
            raise ValueError(f"Duration changed for {sid}: {actual_duration} != {expected_duration}")
        if versions(str(current.get("title") or "")) != versions(str(entry.get("source_title") or "")):
            raise ValueError(f"Version marker changed for {sid}")

    settings = get_settings()
    token_store = VkTokenStore(settings.data_dir)
    client = VkApiClient(token_store=token_store, account_alias=args.account, api_version=settings.vk_api_version)
    vk_videos = client.list_videos(args.community)
    existing_short_ids: dict[str, str] = {}
    ambiguous: dict[str, list[str]] = {}
    for entry in items:
        sid = str(entry["source_id"])
        source = by_id[sid]
        source_title = str(source.get("title") or "")
        source_duration = int(source.get("duration_seconds") or 0)
        marker = f"youtube.com/shorts/{sid}"
        candidates=[]
        for record in vk_videos:
            md = record.metadata if isinstance(record.metadata, dict) else {}
            if str(md.get("vk_video_type") or "") != "short_video":
                continue
            desc = str(record.description or "").casefold()
            title_ok = normalize(record.title) in {normalize(source_title), normalize(str(entry.get('old_vk_title') or ''))}
            duration_ok = record.duration_seconds is not None and abs(int(record.duration_seconds)-source_duration) <= 4
            version_ok = versions(record.title) == versions(source_title)
            marker_ok = marker in desc
            if marker_ok or (title_ok and duration_ok and version_ok):
                candidates.append(record.ref.remote_id)
        if len(candidates)==1:
            existing_short_ids[sid]=candidates[0]
        elif len(candidates)>1:
            ambiguous[sid]=candidates
    if ambiguous:
        raise ValueError(f"Ambiguous existing VK clips: {ambiguous}")

    prepared=[]
    for index, entry in enumerate(items, start=1):
        sid=str(entry['source_id'])
        source=by_id[sid]
        media_path = args.cache / f"{sid}.mp4"
        report=None
        should_prepare = (not args.canary_only) or sid == str(republish["canary_source_id"])
        if sid not in existing_short_ids and should_prepare and not args.plan_only:
            media_path=download(args.yt_dlp,sid,args.cache)
            report=probe_media(media_path,ffprobe=args.ffprobe)
            if report.width is None or report.height is None or report.height <= report.width:
                raise ValueError(f"Source is not vertical: {sid} {report.width}x{report.height}")
            if report.duration_seconds > 180.5:
                raise ValueError(f"Source exceeds 3-minute clip limit: {sid} {report.duration_seconds}")
        prepared.append({
            **entry,
            'index':index,
            'source_url':f'https://www.youtube.com/shorts/{sid}',
            'description':build_clip_description(source,sid),
            'media_path':str(media_path.resolve()),
            'media': report.to_dict() if report else None,
            'status':(
                'already_present_clip' if sid in existing_short_ids
                else 'prepared' if should_prepare
                else 'pending_after_canary'
            ),
            'existing_clip_id':existing_short_ids.get(sid),
        })
        state = ('SKIP existing clip' if sid in existing_short_ids else 'Prepared' if should_prepare else 'Pending after canary')
        print(f"[{index}/48] {state} {sid} — {entry['source_title']}")

    payload={
        'schema_name':'video-manager.legendary-poet-browser-clip-queue',
        'schema_version':1,
        'created_at':datetime.now(UTC).isoformat(),
        'community_id':args.community,
        'channel_id':args.channel_id,
        'canary_source_id':str(republish['canary_source_id']),
        'delete_old_videos':False,
        'publish_to_wall':False,
        'live_shorts_count':len(live_shorts),
        'additional_live_shorts_not_in_republish_queue':extra_live,
        'hydrated_source_ids':hydrated,
        'items':prepared,
    }
    write_json(args.queue_output,payload)
    print(f"Queue ready: {args.queue_output}")
    print(f"Prepared for new clip upload: {sum(x['status']=='prepared' for x in prepared)}")
    print(f"Already present as short_video: {sum(x['status']=='already_present_clip' for x in prepared)}")
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
```

## 010. Browser UI uploader for 48 Clips

- Original: `upload_48_clips_browser.py`
- SHA-256: `0dc674d0c3a1a8e67ada345244dd0ec8c0700fb6763ab34658d67be48f686d86`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path.cwd()
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkTokenStore

try:
    from playwright.sync_api import BrowserContext, Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError as exc:
    raise SystemExit("Playwright is not installed. Run the PowerShell launcher.") from exc


def read_json(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict): raise ValueError(f'Expected object: {path}')
    return value


def write_json(path: Path,payload: dict[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    payload['updated_at']=datetime.now(UTC).isoformat()
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def get_live_videos(client: VkApiClient, community: int):
    return client.list_videos(community)


def click_first(page: Page, candidates: Iterable[Locator], *, timeout_ms: int=5000) -> bool:
    for loc in candidates:
        try:
            if loc.count() and loc.first.is_visible(timeout=700):
                loc.first.click(timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def fill_first(page: Page, candidates: Iterable[Locator], value: str) -> bool:
    for loc in candidates:
        try:
            if loc.count() and loc.first.is_visible(timeout=700):
                loc.first.fill(value)
                return True
        except Exception:
            continue
    return False


def open_add_clip(page: Page) -> None:
    page.goto('https://vkvideo.ru/', wait_until='domcontentloaded', timeout=120000)
    page.wait_for_timeout(1500)
    direct = [
        page.get_by_text(re.compile(r'^Добавить клип$', re.I)),
        page.get_by_text(re.compile(r'^Опубликовать клип$', re.I)),
        page.get_by_role('button', name=re.compile(r'добавить клип|опубликовать клип', re.I)),
    ]
    if click_first(page,direct,timeout_ms=10000):
        return
    plus = [
        page.get_by_role('button', name=re.compile(r'создать|добавить|загрузить', re.I)),
        page.locator('button').filter(has_text=re.compile(r'^\s*\+\s*$')),
        page.locator('[aria-label*="Создать" i], [aria-label*="Добавить" i], [aria-label*="Загрузить" i]'),
    ]
    if not click_first(page,plus,timeout_ms=10000):
        raise RuntimeError('Не найдена кнопка +/Создать в VK Видео')
    page.wait_for_timeout(700)
    if not click_first(page,direct,timeout_ms=10000):
        raise RuntimeError('Не найден пункт «Добавить клип» после открытия меню')


def assert_clip_form(page: Page) -> None:
    pattern = re.compile(r"добавить клип|опубликовать клип|новый клип|создать клип", re.I)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        candidates = [
            page.get_by_role("heading", name=pattern),
            page.locator('[role="dialog"]').get_by_text(pattern),
            page.get_by_text(pattern),
        ]
        for loc in candidates:
            try:
                if loc.count() and loc.first.is_visible(timeout=500):
                    return
            except Exception:
                continue
        if "clip" in page.url.casefold():
            return
        page.wait_for_timeout(500)
    raise RuntimeError(
        "Не удалось доказать, что открыта форма VK Клипов; файл не выбран и публикация остановлена"
    )


def choose_channel_if_needed(page: Page) -> None:
    options=[
        page.get_by_text(re.compile(r'The Legendary Poet',re.I)),
        page.get_by_text(re.compile(r'Легендарн.*Поэт',re.I)),
    ]
    click_first(page,options,timeout_ms=5000)


def uncheck_wall(page: Page) -> None:
    pattern = re.compile(r"пост на стене|опубликовать.*стен", re.I)
    controls = [
        page.get_by_role("checkbox", name=pattern),
        page.get_by_role("switch", name=pattern),
    ]
    for control in controls:
        try:
            if not control.count() or not control.first.is_visible(timeout=700):
                continue
            loc = control.first
            checked = False
            try:
                checked = loc.is_checked()
            except Exception:
                checked = str(loc.get_attribute("aria-checked") or "").lower() == "true"
            if checked:
                try:
                    loc.uncheck()
                except Exception:
                    loc.click()
            try:
                still_checked = loc.is_checked()
            except Exception:
                still_checked = str(loc.get_attribute("aria-checked") or "").lower() == "true"
            if still_checked:
                raise RuntimeError("Не удалось выключить публикацию клипа на стене")
            return
        except RuntimeError:
            raise
        except Exception:
            continue

    # Fallback for a text label wrapping a native checkbox. Never click blindly.
    labels = [
        page.get_by_text(re.compile(r"^Пост на стене$", re.I)),
        page.get_by_text(re.compile(r"Опубликовать.*стен", re.I)),
    ]
    for label in labels:
        try:
            if not label.count() or not label.first.is_visible(timeout=500):
                continue
            cb = label.first.locator('xpath=ancestor-or-self::label[1]//input[@type="checkbox"]')
            if cb.count():
                if cb.first.is_checked():
                    cb.first.uncheck()
                if cb.first.is_checked():
                    raise RuntimeError("Не удалось выключить публикацию клипа на стене")
                return
            raise RuntimeError(
                "Опция стены видна, но её состояние нельзя безопасно определить; публикация остановлена"
            )
        except RuntimeError:
            raise
        except Exception:
            continue
    raise RuntimeError(
        "Не найдена настройка «Пост на стене»; публикация остановлена до изменения интерфейса"
    )


def set_file_and_metadata(page: Page, item: dict[str,Any]) -> None:
    file_input=page.locator('input[type="file"]')
    deadline=time.monotonic()+120
    while time.monotonic()<deadline and not file_input.count():
        choose_channel_if_needed(page)
        page.wait_for_timeout(700)
        file_input=page.locator('input[type="file"]')
    if not file_input.count():
        raise RuntimeError('Не найден input[type=file] формы клипа')
    file_input.first.set_input_files(str(item['media_path']))

    title=str(item['source_title'])[:200]
    description=str(item['description'])
    form_deadline=time.monotonic()+180
    description_filled=False
    while time.monotonic()<form_deadline:
        fill_first(page,[
            page.get_by_label(re.compile(r'Название',re.I)),
            page.locator('input[placeholder*="назван" i]'),
        ],title)
        if fill_first(page,[
            page.get_by_label(re.compile(r'Описание',re.I)),
            page.locator('textarea[placeholder*="опис" i]'),
            page.locator('textarea'),
            page.locator('[contenteditable="true"]'),
        ],description):
            description_filled=True
            break
        page.wait_for_timeout(1000)
    if not description_filled:
        raise RuntimeError('Не найдено поле описания клипа после выбора файла')

    wall_deadline=time.monotonic()+120
    last_error=None
    while time.monotonic()<wall_deadline:
        try:
            uncheck_wall(page)
            return
        except RuntimeError as exc:
            last_error=exc
            page.wait_for_timeout(1000)
    raise RuntimeError(f'Не удалось безопасно проверить настройку стены: {last_error}')


def click_publish(page: Page, *, timeout_seconds: int=1800) -> None:
    candidates=[
        page.get_by_role('button',name=re.compile(r'^Опубликовать$',re.I)),
        page.get_by_text(re.compile(r'^Опубликовать$',re.I)),
    ]
    deadline=time.monotonic()+timeout_seconds
    last_report=0.0
    while time.monotonic()<deadline:
        for loc in candidates:
            try:
                if not loc.count() or not loc.first.is_visible(timeout=500):
                    continue
                if loc.first.is_enabled():
                    loc.first.click(timeout=15000)
                    page.wait_for_timeout(1000)
                    # Some versions show an additional confirmation dialog.
                    click_first(page,[
                        page.get_by_role('button',name=re.compile(r'^Опубликовать$',re.I)),
                        page.get_by_role('button',name=re.compile(r'^Подтвердить$',re.I)),
                    ],timeout_ms=5000)
                    return
            except Exception:
                continue
        if time.monotonic()-last_report>30:
            print('VK ещё загружает файл в форме; жду доступности кнопки «Опубликовать»...')
            last_report=time.monotonic()
        page.wait_for_timeout(1000)
    raise RuntimeError('Кнопка «Опубликовать» не стала доступной за отведённое время')


def find_exact_new_clip(client: VkApiClient, community: int, sid: str, expected_duration: int, baseline: set[str]):
    marker=f'youtube.com/shorts/{sid}'.casefold()
    ordinary=[]
    clips=[]
    for record in get_live_videos(client,community):
        if record.ref.remote_id in baseline:
            continue
        if marker not in str(record.description or '').casefold():
            continue
        if record.duration_seconds is not None and abs(int(record.duration_seconds)-expected_duration)>4:
            continue
        typ=str(record.metadata.get('vk_video_type') or '') if isinstance(record.metadata,dict) else ''
        if typ=='short_video': clips.append(record)
        else: ordinary.append(record)
    if len(clips)>1: raise RuntimeError(f'Multiple new clips match {sid}: {[x.ref.remote_id for x in clips]}')
    if clips: return clips[0], ordinary
    return None, ordinary


def wait_for_clip(client: VkApiClient, community: int, item: dict[str,Any], baseline:set[str], timeout_seconds:int):
    deadline=time.monotonic()+timeout_seconds
    last_ordinary=[]
    while time.monotonic()<deadline:
        clip,ordinary=find_exact_new_clip(client,community,str(item['source_id']),int(item['source_duration_seconds']),baseline)
        if clip is not None: return clip
        last_ordinary=ordinary
        time.sleep(10)
    if last_ordinary:
        raise RuntimeError(f"VK created ordinary video instead of clip for {item['source_id']}: {[x.ref.remote_id for x in last_ordinary]}")
    raise RuntimeError(f"New short_video was not found for {item['source_id']} within {timeout_seconds}s")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--queue',type=Path,required=True)
    ap.add_argument('--journal',type=Path,required=True)
    ap.add_argument('--profile-dir',type=Path,required=True)
    ap.add_argument('--browser-executable',type=Path,required=True)
    ap.add_argument('--community',type=int,required=True)
    ap.add_argument('--account',default='legendary-poet')
    ap.add_argument('--verify-timeout',type=int,default=1800)
    ap.add_argument('--canary-only',action='store_true')
    args=ap.parse_args()

    queue=read_json(args.queue)
    items=[x for x in queue.get('items',[]) if isinstance(x,dict)]
    prepared=[x for x in items if x.get('status')=='prepared']
    canary=str(queue.get('canary_source_id') or '')
    prepared.sort(key=lambda x:(0 if x['source_id']==canary else 1,int(x['source_duration_seconds']),x['source_id']))

    if args.journal.exists():
        journal=read_json(args.journal)
        if journal.get('schema_name')!='video-manager.legendary-poet-browser-clip-journal':
            raise ValueError('Unexpected existing browser clip journal schema')
    else:
        journal={
            'schema_name':'video-manager.legendary-poet-browser-clip-journal',
            'schema_version':1,
            'created_at':datetime.now(UTC).isoformat(),
            'community_id':args.community,
            'delete_old_videos':False,
            'publish_to_wall':False,
            'uploads':{},
        }
        write_json(args.journal,journal)
    uploads=journal['uploads']

    settings=get_settings()
    store=VkTokenStore(settings.data_dir)
    client=VkApiClient(token_store=store,account_alias=args.account,api_version=settings.vk_api_version)

    with sync_playwright() as pw:
        context=pw.chromium.launch_persistent_context(
            user_data_dir=str(args.profile_dir),
            executable_path=str(args.browser_executable),
            headless=False,
            viewport={'width':1440,'height':1000},
            args=['--disable-features=Translate'],
        )
        page=context.pages[0] if context.pages else context.new_page()
        page.goto('https://vkvideo.ru/',wait_until='domcontentloaded',timeout=120000)
        print('\nБраузер открыт. Если VK просит вход, войдите вручную в открытом окне.')
        print('После входа оставьте окно открытым.')
        input('Войдите в VK и откройте главную VK Видео, затем нажмите Enter здесь: ')
        page.goto('https://vkvideo.ru/', wait_until='domcontentloaded', timeout=120000)
        page.wait_for_timeout(1500)

        completed=0
        for item in prepared:
            sid=str(item['source_id'])
            existing=uploads.get(sid)
            if isinstance(existing,dict):
                status=str(existing.get('status') or '')
                if status=='confirmed_short_video':
                    print(f"SKIP confirmed {sid} -> {existing.get('new_clip_id')}")
                    continue
                if status in {'publish_clicked','needs_reconciliation'}:
                    baseline=set(existing.get('baseline_ids') or [])
                    try:
                        clip=wait_for_clip(client,args.community,item,baseline,args.verify_timeout)
                    except Exception as exc:
                        existing['status']='needs_reconciliation'
                        existing['error']=f'{type(exc).__name__}: {exc}'
                        write_json(args.journal,journal)
                        raise
                    existing['status']='confirmed_short_video'
                    existing['new_clip_id']=clip.ref.remote_id
                    existing['confirmed_at']=datetime.now(UTC).isoformat()
                    write_json(args.journal,journal)
                    print(f"Reconciled {sid} -> https://vk.com/clip{clip.ref.remote_id}")
                    if sid==canary and args.canary_only:
                        break
                    continue

            baseline={x.ref.remote_id for x in get_live_videos(client,args.community)}
            print(f"\n[{completed+1}/{len(prepared)}] CLIP {sid} — {item['source_title']}")
            try:
                open_add_clip(page)
                assert_clip_form(page)
                choose_channel_if_needed(page)
                set_file_and_metadata(page,item)
                page.screenshot(path=str(args.journal.parent/f'clip-ready-{sid}.png'),full_page=True)
                uploads[sid]={
                    'source_id':sid,
                    'source_title':item['source_title'],
                    'old_vk_video_id':item['old_vk_video_id'],
                    'status':'ui_ready',
                    'baseline_ids':sorted(baseline),
                    'media_path':item['media_path'],
                    'wall_post_requested':False,
                    'delete_old_video_requested':False,
                    'ready_at':datetime.now(UTC).isoformat(),
                }
                write_json(args.journal,journal)
                click_publish(page)
                uploads[sid]['status']='publish_clicked'
                uploads[sid]['publish_clicked_at']=datetime.now(UTC).isoformat()
                write_json(args.journal,journal)
                clip=wait_for_clip(client,args.community,item,baseline,args.verify_timeout)
                uploads[sid]['status']='confirmed_short_video'
                uploads[sid]['new_clip_id']=clip.ref.remote_id
                uploads[sid]['confirmed_at']=datetime.now(UTC).isoformat()
                write_json(args.journal,journal)
                completed+=1
                print(f"CONFIRMED https://vk.com/clip{clip.ref.remote_id}")
            except BaseException as exc:
                entry=uploads.setdefault(sid,{'source_id':sid})
                entry['status']='needs_reconciliation'
                entry['error']=f'{type(exc).__name__}: {exc}'
                entry['stopped_at']=datetime.now(UTC).isoformat()
                try:
                    page.screenshot(path=str(args.journal.parent/f'clip-error-{sid}.png'),full_page=True)
                except Exception:
                    pass
                write_json(args.journal,journal)
                raise
            if sid==canary:
                print('Canary confirmed as short_video. Batch may continue.')
                if args.canary_only: break
            page.wait_for_timeout(2500)
        context.close()
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('STOPPED by user; journal preserved. Do not retry manually before reconciliation.',file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        raise SystemExit(2)
```

## 011. Republish PowerShell launcher

- Original: `run-republish-48-clips.ps1`
- SHA-256: `f18d084351ccf2cb12245eb15de4dd573391717126e2966ba85378f4bd5b90e6`

```powershell
param(
    [switch]$CanaryOnly
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$ChannelId   = "UC-78ys2S3cQ3lpqgXfo-SvQ"
$CommunityId = 235216998
$YouTubeAudit = ".\data\exports\youtube-legendary-poet-current.json"
$VkAudit      = ".\data\exports\vk-legendary-poet-before-republish-48.json"
$CacheDir     = ".\data\cache\legendary-poet-republish-48-clips"
$ReportDir    = ".\data\reports\legendary-poet-republish-48-clips"
$Queue        = Join-Path $ReportDir "queue.json"
$Journal      = Join-Path $ReportDir "browser-upload-journal.json"
$ProfileDir   = ".\data\cache\legendary-poet-vk-clips-browser-profile"
$Map          = Join-Path $PSScriptRoot "republish_48_map.json"
$Prepare      = Join-Path $PSScriptRoot "prepare_republish_48.py"
$Uploader     = Join-Path $PSScriptRoot "upload_48_clips_browser.py"

foreach ($required in @($Map, $Prepare, $Uploader)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Не найден файл пакета: $required"
    }
}

Write-Host "`n========== СВЕЖИЙ YOUTUBE-АУДИТ ==========" -ForegroundColor Cyan
video-manager youtube scan --account legendary-poet --channel $ChannelId --output $YouTubeAudit
if ($LASTEXITCODE -ne 0) { throw "YouTube-аудит не создан. VK не изменён." }

Write-Host "`n========== СВЕЖИЙ VK-АУДИТ ==========" -ForegroundColor Cyan
video-manager vk scan --account legendary-poet --community $CommunityId --output $VkAudit
if ($LASTEXITCODE -ne 0) { throw "VK-аудит не создан. VK не изменён." }

Write-Host "`n========== ПОДГОТОВКА 48 ИСХОДНИКОВ ==========" -ForegroundColor Cyan
$prepareArguments = @(
    $Prepare,
    "--youtube-audit", $YouTubeAudit,
    "--map", $Map,
    "--shorts-url", "https://www.youtube.com/channel/$ChannelId/shorts",
    "--channel-id", $ChannelId,
    "--community", "$CommunityId",
    "--account", "legendary-poet",
    "--cache", $CacheDir,
    "--queue-output", $Queue
)
if ($CanaryOnly) { $prepareArguments += "--canary-only" }
python @prepareArguments
if ($LASTEXITCODE -ne 0) { throw "Подготовка остановлена. VK не изменён браузерным пакетом." }

Write-Host "`n========== ПРОВЕРКА PLAYWRIGHT ==========" -ForegroundColor Cyan
python -c "import playwright" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Устанавливаю библиотеку Playwright (без отдельного браузера)..." -ForegroundColor Yellow
    python -m pip install --disable-pip-version-check "playwright>=1.54,<2"
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить Playwright." }
}

$browserCandidates = @(
    "$env:LOCALAPPDATA\Yandex\YandexBrowser\Application\browser.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$Browser = $browserCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $Browser) { throw "Не найден Yandex Browser, Chrome или Edge." }
Write-Host "Браузер: $Browser" -ForegroundColor Green

Write-Host "`n========== ЗАГРУЗКА ЧЕРЕЗ «ДОБАВИТЬ КЛИП» ==========" -ForegroundColor Cyan
Write-Host "Старые VK Видео НЕ удаляются. Публикация на стене отключается в форме." -ForegroundColor Yellow

$arguments = @(
    $Uploader,
    "--queue", $Queue,
    "--journal", $Journal,
    "--profile-dir", $ProfileDir,
    "--browser-executable", $Browser,
    "--community", "$CommunityId",
    "--account", "legendary-poet",
    "--verify-timeout", "1800"
)
if ($CanaryOnly) { $arguments += "--canary-only" }
python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Браузерная загрузка остановлена. Журнал сохранён: $Journal"
}

Write-Host "`nГотово. Старые VK Видео не удалялись." -ForegroundColor Green
Write-Host "Журнал новых клипов: $Journal" -ForegroundColor Green
```
