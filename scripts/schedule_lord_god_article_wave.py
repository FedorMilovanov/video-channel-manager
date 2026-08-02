#!/usr/bin/env python3
"""Plan or schedule ten daily article link cards for the theological VK group."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
import httpx
from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkApiClient, VkApiError, VkTokenStore
from video_channel_manager.platforms.vk.lock import local_vk_write_lock
from video_channel_manager.platforms.vk.wall_content_audit import fetch_wall_posts
PROJECT_KEY = 'lord-god-strength'
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
ACCOUNT_ALIAS = 'legendary-poet'
DECISION_SET_ID = 'lord-god-article-wave-202608'
POLICY_PATH = Path('content/policies/lord-god-article-wave-202608.json')
EXPECTED_SHA = 'sha256:458b716dad898f7a692da7204259b43c42b1803387e9ea5ca855d456f044b85b'
MOSCOW = timezone(timedelta(hours=3), name='UTC+03:00')
URL_RE = re.compile('https://gospod-bog\\.ru/[^\\s<>\\"]+')

class Meta(HTMLParser):

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical = ''
        self.og_url = ''
        self.image = ''

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {str(k).lower(): str(v or '').strip() for k, v in attrs}
        if tag.lower() == 'meta':
            p = (a.get('property') or a.get('name') or '').lower()
            c = a.get('content', '')
            if p == 'og:image' and (not self.image):
                self.image = c
            if p == 'og:url' and (not self.og_url):
                self.og_url = c
        elif tag.lower() == 'link' and 'canonical' in a.get('rel', '').lower().split() and (not self.canonical):
            self.canonical = a.get('href', '')

def now() -> str:
    return datetime.now(UTC).astimezone().isoformat()

def text(v: object) -> str:
    return str(v or '').replace('\r\n', '\n').replace('\r', '\n').strip()

def sha(v: object) -> str:
    raw = json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return f'sha256:{hashlib.sha256(raw).hexdigest()}'

def msg_sha(v: object) -> str:
    return f'sha256:{hashlib.sha256(text(v).encode()).hexdigest()}'

def norm(v: object) -> str:
    s = str(v or '').strip()
    p = urlsplit(s)
    path = p.path or '/'
    if path != '/' and (not path.rsplit('/', 1)[-1].count('.')):
        path = path.rstrip('/') + '/'
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, '', ''))

def write(path: Path, v: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(v, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)

def read(path: Path, default: object) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default

def load_policy(repo: Path) -> dict[str, Any]:
    v = json.loads((repo / POLICY_PATH).read_text(encoding='utf-8'))
    if not isinstance(v, dict):
        raise ValueError('Policy root must be an object')
    return v

def validate(p: dict[str, Any]) -> None:
    exact = {'schema_name': 'video-manager.vk-lord-god-article-wave-policy', 'schema_version': 1, 'decision_set_id': DECISION_SET_ID, 'project_key': PROJECT_KEY, 'source_repository': 'FedorMilovanov/gb-is-my-strength', 'source_manifest_blob_sha': '952cfbd8b276fc7e877a784660fb4481dc8bd83f', 'vk_community_id': COMMUNITY_ID, 'vk_owner_id': OWNER_ID, 'schedule_timezone': 'UTC+03:00', 'schedule_hour': 14, 'attachment_mode': 'external-link-card'}
    if any((p.get(k) != v for k, v in exact.items())):
        raise ValueError('Article policy identity mismatch')
    digest = sha({k: v for k, v in p.items() if k != 'policy_sha256'})
    if p.get('policy_sha256') != digest or digest != EXPECTED_SHA:
        raise ValueError('Article policy digest mismatch')
    ops = p.get('operations')
    if not isinstance(ops, list) or len(ops) != 10:
        raise ValueError('Expected exactly ten article operations')
    ids: set[str] = set()
    urls: set[str] = set()
    dates: set[int] = set()
    previous = 0
    for n, o in enumerate(ops, 1):
        if not isinstance(o, dict) or o.get('ordinal') != n:
            raise ValueError(f'Bad ordinal {n}')
        op = str(o.get('operation_id') or '')
        url = norm(o.get('url'))
        image = norm(o.get('og_image'))
        message = text(o.get('message'))
        dt = datetime.fromisoformat(str(o.get('publish_at') or ''))
        stamp = o.get('publish_date')
        if not op.startswith(DECISION_SET_ID + '-') or not url.startswith('https://gospod-bog.ru/'):
            raise ValueError(f'Bad identity {n}')
        if not image.startswith('https://gospod-bog.ru/') or not image.endswith('.webp'):
            raise ValueError(f'Bad OG image {n}')
        if url not in message or not 300 <= len(message) <= 1200 or o.get('message_sha256') != msg_sha(message):
            raise ValueError(f'Bad message {n}')
        if not isinstance(stamp, int) or int(dt.timestamp()) != stamp or dt.astimezone(MOSCOW).strftime('%H:%M') != '14:00':
            raise ValueError(f'Bad time {n}')
        if stamp <= previous or op in ids or url in urls or (stamp in dates):
            raise ValueError(f'Duplicate/order error {n}')
        ids.add(op)
        urls.add(url)
        dates.add(stamp)
        previous = stamp

def verify_sources(p: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/148 Safari/537.36'}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as c:
        for o in p['operations']:
            url = norm(o['url'])
            expected = norm(o['og_image'])
            r = c.get(url)
            r.raise_for_status()
            m = Meta()
            m.feed(r.text)
            canonical = norm(urljoin(url, m.canonical or m.og_url or url))
            image = norm(urljoin(url, m.image))
            if canonical != url or image != expected:
                raise RuntimeError(f"Live metadata differs: {o['operation_id']}")
            ir = c.get(image, headers={'Range': 'bytes=0-2047'})
            if ir.status_code not in {200, 206} or not ir.headers.get('content-type', '').lower().startswith('image/'):
                raise RuntimeError(f"Live OG image failed: {o['operation_id']}")
            out.append({'operation_id': o['operation_id'], 'canonical_url': canonical, 'og_image': image, 'status': 'verified'})
    return out

def has_image(link: dict[str, Any]) -> bool:
    photo = link.get('photo')
    if isinstance(photo, dict):
        sizes = photo.get('sizes')
        if isinstance(sizes, list) and any((isinstance(x, dict) and str(x.get('url') or '').startswith('http') for x in sizes)):
            return True
        if any((str(k).startswith('photo_') and v for k, v in photo.items())):
            return True
    return any((str(link.get(k) or '').startswith('http') for k in ('image_src', 'preview_image', 'photo_50', 'photo_100', 'photo_200')))

def ref(post: dict[str, Any], queue: str) -> dict[str, Any]:
    links = []
    images = []
    for a in post.get('attachments') if isinstance(post.get('attachments'), list) else []:
        if isinstance(a, dict) and a.get('type') == 'link' and isinstance(a.get('link'), dict):
            link = a['link']
            url = norm(link.get('url'))
            if url:
                links.append(url)
                images.append(has_image(link))
    message = text(post.get('text'))
    urls = [norm(x) for x in URL_RE.findall(message)]
    return {'queue': queue, 'owner_id': post.get('owner_id'), 'post_id': post.get('id'), 'date': post.get('date'), 'message': message, 'link_urls': sorted(set(links)), 'text_urls': sorted(set(urls)), 'link_card_has_image': bool(images) and all(images)}

def snapshot(c: VkApiClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (fetch_wall_posts(c, community_id=COMMUNITY_ID, filter_name='owner'), fetch_wall_posts(c, community_id=COMMUNITY_ID, filter_name='postponed'))

def indexes(pub: list[dict[str, Any]], post: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_date: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for q, items in (('published', pub), ('postponed', post)):
        for raw in items:
            r = ref(raw, q)
            for u in set(r['link_urls'] + r['text_urls']):
                by_url[u].append(r)
            if q == 'postponed' and isinstance(r['date'], int):
                by_date[r['date']].append(r)
    return (dict(by_url), dict(by_date))

def preflight(p: dict[str, Any], pub: list[dict[str, Any]], post: list[dict[str, Any]], journal: dict[str, Any], safe: int=300) -> dict[str, Any]:
    by_url, by_date = indexes(pub, post)
    jops = journal.get('operations') if isinstance(journal.get('operations'), dict) else {}
    current = int(datetime.now(UTC).timestamp())
    states = []
    conflicts = []
    for o in p['operations']:
        op = o['operation_id']
        url = norm(o['url'])
        stamp = int(o['publish_date'])
        refs = by_url.get(url, [])
        exact = [r for r in refs if r['queue'] == 'postponed' and r['date'] == stamp and (r['message'] == text(o['message'])) and (url in r['link_urls']) and r['link_card_has_image']]
        occupied = [r for r in by_date.get(stamp, []) if r not in exact]
        old = jops.get(op)
        status = old.get('status') if isinstance(old, dict) else None
        if len(exact) == 1 and len(refs) == 1 and (not occupied):
            state, detail = ('already_applied', 'exact link card with image exists')
        elif refs:
            state, detail = ('conflict', 'article URL already appears on wall')
        elif occupied:
            state, detail = ('conflict', '14:00 slot is occupied')
        elif status in {'unknown', 'accepted_unverified'}:
            state, detail = ('conflict', f'previous outcome requires inspection: {status}')
        elif stamp <= current + safe:
            state, detail = ('conflict', 'publish time is not safely in the future')
        else:
            state, detail = ('ready', 'article absent and slot free')
        if state == 'conflict':
            conflicts.append(f'{op}: {detail}')
        states.append({'operation_id': op, 'ordinal': o['ordinal'], 'article_title': o['title'], 'article_url': url, 'publish_at': o['publish_at'], 'state': state, 'detail': detail, 'references': refs, 'time_conflicts': occupied})
    c = Counter((x['state'] for x in states))
    return {'schema_name': 'video-manager.vk-lord-god-article-wave-preflight', 'schema_version': 1, 'generated_at': now(), 'policy_sha256': p['policy_sha256'], 'published_wall_posts': len(pub), 'postponed_wall_posts': len(post), 'total_operations': len(states), 'ready': c['ready'], 'already_applied': c['already_applied'], 'conflicts': c['conflict'], 'global_conflicts': conflicts, 'states': states}

def fingerprint(r: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: x[k] for k in ('operation_id', 'state', 'references', 'time_conflicts')} for x in r['states']]

def post_once(c: VkApiClient, o: dict[str, Any]) -> object:
    token = c.token_store.load_token(c.account_alias)
    if token.is_expired():
        raise RuntimeError('Stored VK token is expired')
    return c._call_once('wall.post', {'access_token': token.access_token, 'v': c.api_version, 'owner_id': str(OWNER_ID), 'from_group': '1', 'message': o['message'], 'attachments': o['url'], 'publish_date': str(o['publish_date']), 'guid': o['operation_id']})

def post_id(v: object) -> int:
    n = v if isinstance(v, int) else v.get('post_id') if isinstance(v, dict) else None
    if isinstance(n, int) and n > 0:
        return n
    raise RuntimeError(f'wall.post returned no post ID: {v!r}')

def wait_exact(c: VkApiClient, o: dict[str, Any], pid: int) -> dict[str, Any]:
    for attempt in range(8):
        for raw in fetch_wall_posts(c, community_id=COMMUNITY_ID, filter_name='postponed'):
            if raw.get('owner_id') == OWNER_ID and raw.get('id') == pid:
                r = ref(raw, 'postponed')
                url = norm(o['url'])
                if r['message'] != text(o['message']) or r['date'] != o['publish_date']:
                    raise RuntimeError(f"Accepted post differs: {o['operation_id']}")
                if url not in r['link_urls'] or not r['link_card_has_image']:
                    raise RuntimeError(f"Accepted card lacks exact image link: {o['operation_id']}")
                return r
        if attempt < 7:
            time.sleep(2)
    raise RuntimeError(f"Accepted post is not visible: {o['operation_id']}")

def review(p: dict[str, Any], r: dict[str, Any]) -> str:
    states = {x['operation_id']: x['state'] for x in r['states']}
    lines = ['# Господь Бог — Сила Моя: 10 статей на стену', '', 'Одна статья ежедневно в 14:00 UTC+03:00. Отдельные изображения не загружаются; используется OG-карточка статьи.', '']
    for o in p['operations']:
        lines += [f"## {o['ordinal']}. {o['title']}", f"Время: `{o['publish_at']}` · Статус: `{states[o['operation_id']]}`", f"OG: {o['og_image']}", '', o['message'], '']
    return '\n'.join(lines).rstrip() + '\n'

def run(repo: Path, execute: bool) -> int:
    repo = repo.resolve()
    out = repo / 'data' / 'vk-wall' / DECISION_SET_ID
    out.mkdir(parents=True, exist_ok=True)
    p = load_policy(repo)
    validate(p)
    write(out / 'plan.json', p)
    sources = verify_sources(p)
    write(out / 'source-check.json', {'verified': len(sources), 'items': sources, 'generated_at': now()})
    settings = get_settings()
    client = VkApiClient(token_store=VkTokenStore(settings.data_dir), account_alias=ACCOUNT_ALIAS, api_version=settings.vk_api_version)
    community = client.get_community(COMMUNITY_ID)
    if community.ref.remote_id != str(COMMUNITY_ID) or not community.metadata.get('managed_by_token'):
        raise RuntimeError('Stored token does not manage VK community 60805374')
    jp = out / 'journal.json'
    journal = read(jp, {'schema_name': 'video-manager.vk-lord-god-article-wave-journal', 'schema_version': 1, 'decision_set_id': DECISION_SET_ID, 'policy_sha256': p['policy_sha256'], 'operations': {}})
    if not isinstance(journal, dict) or journal.get('decision_set_id') != DECISION_SET_ID or journal.get('policy_sha256') != p['policy_sha256']:
        raise RuntimeError('Journal belongs to another plan')
    pub, post = snapshot(client)
    report = preflight(p, pub, post, journal)
    write(out / 'preflight.json', report)
    (out / 'plan-review.md').write_text(review(p, report), encoding='utf-8')
    print(json.dumps({'mode': 'apply' if execute else 'plan', 'source_pages_with_og_images': len(sources), 'operations': 10, 'ready': report['ready'], 'already_applied': report['already_applied'], 'conflicts': report['conflicts'], 'first_publish_at': p['summary']['first_publish_at'], 'last_publish_at': p['summary']['last_publish_at'], 'plan_review': str(out / 'plan-review.md')}, ensure_ascii=False, indent=2))
    if report['conflicts']:
        raise RuntimeError('Article queue blocked: ' + '; '.join(report['global_conflicts']))
    if not execute:
        print('READ-ONLY ARTICLE PLAN COMPLETE. No VK writes were sent.')
        return 0
    if os.environ.get('VCM_ALLOW_WALL_POSTS') != '1':
        raise RuntimeError('Execution requires VCM_ALLOW_WALL_POSTS=1')
    result = {'status': 'running', 'policy_sha256': p['policy_sha256'], 'started_at': now(), 'operations': []}
    rp = out / 'result.json'
    write(rp, result)
    lock = settings.data_dir / 'locks' / f'vk-wall-{COMMUNITY_ID}.lock'
    with local_vk_write_lock(lock, account=ACCOUNT_ALIAS, community_id=COMMUNITY_ID, operation=DECISION_SET_ID):
        a, b = snapshot(client)
        locked = preflight(p, a, b, journal)
        if locked['conflicts'] or fingerprint(locked) != fingerprint(report):
            raise RuntimeError('Locked preflight differs from reviewed preflight')
        states = {x['operation_id']: x['state'] for x in locked['states']}
        jops = journal['operations']
        for o in p['operations']:
            op = o['operation_id']
            if states[op] == 'already_applied':
                result['operations'].append({'operation_id': op, 'status': 'already_applied'})
                write(rp, result)
                continue
            jops[op] = {'status': 'intent', 'article_url': o['url'], 'publish_date': o['publish_date'], 'message_sha256': o['message_sha256'], 'intent_at': now()}
            journal['updated_at'] = now()
            write(jp, journal)
            try:
                response = post_once(client, o)
            except Exception as exc:
                jops[op].update(status='unknown', error=f'{type(exc).__name__}: {exc}', updated_at=now())
                write(jp, journal)
                result.update(status='stopped_unknown', error=f'{op}: {exc}', stopped_at=now())
                write(rp, result)
                raise RuntimeError(f'Unknown wall.post outcome: {op}') from exc
            pid = post_id(response)
            jops[op].update(status='accepted', post_id=pid, accepted_at=now())
            write(jp, journal)
            try:
                card = wait_exact(client, o, pid)
            except Exception as exc:
                jops[op].update(status='accepted_unverified', error=f'{type(exc).__name__}: {exc}', updated_at=now())
                write(jp, journal)
                result.update(status='stopped_accepted_unverified', error=f'{op}: {exc}', stopped_at=now())
                write(rp, result)
                raise RuntimeError(f'Accepted post requires inspection: {op}') from exc
            jops[op].update(status='verified', verified_at=now(), link_card_has_image=True)
            write(jp, journal)
            result['operations'].append({'operation_id': op, 'post_id': pid, 'status': 'verified', 'link_card_has_image': card['link_card_has_image']})
            write(rp, result)
            print(f"SCHEDULED {o['ordinal']}/10 post={OWNER_ID}_{pid} image=yes")
            time.sleep(0.8)
        a, b = snapshot(client)
        final = preflight(p, a, b, journal, safe=0)
        write(out / 'postflight.json', final)
        if final['conflicts'] or final['ready'] or final['already_applied'] != 10:
            raise RuntimeError('Postflight did not verify all ten article cards')
        result.update(status='completed', completed_at=now(), verified_operations=10, verified_postponed=10, verified_link_cards_with_images=10, separate_uploaded_images=0, conflicts=0, first_publish_at=p['summary']['first_publish_at'], last_publish_at=p['summary']['last_publish_at'])
        write(rp, result)
    print(json.dumps({'status': 'completed', 'verified_operations': 10, 'verified_link_cards_with_images': 10, 'result_path': str(rp)}, ensure_ascii=False, indent=2))
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=Path.cwd())
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    return run(a.repo, a.execute)
if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, json.JSONDecodeError, OSError, RuntimeError, ValueError, VkApiError) as exc:
        print(f'ERROR: {exc}', file=os.sys.stderr)
        raise SystemExit(2) from exc
