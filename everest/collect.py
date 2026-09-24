import datetime as dt
import json
import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .core import now
from .filters import structured_match
from .discovery import discover, feed_links, article_metadata, news_direct_event
from urllib.parse import urlsplit


SCOPE_TERMS = (
    'everest', 'qomolangma', 'sagarmatha', 'khumbu', 'solukhumbu',
    'himalaya', 'himalayan', 'nepal', 'tibet', 'xizang', 'bhutan',
    'sikkim', 'uttarakhand', '珠峰', '珠穆朗玛', '喜马拉雅', '尼泊尔',
    '西藏', '日喀则', '定日', '吉隆', '樟木', '亚东',
)


def classify_matches(source, matches):
    """Separate locally relevant event candidates from raw source content."""
    # 1. Fast earthquake & national warning channels: monitor ALL new global/national events directly into deduplication
    rid = source.get('rule_id', '')
    if rid in ('earthquake-02', 'earthquake-03', 'earthquake-04', 'earthquake-05', 'earthquake-07', 'platform-10', 'special-02'):
        if matches:
            return list(dict.fromkeys(matches)), 'in_scope', 'candidate'
        return [], 'out_of_scope', 'not_event'

    if source.get('category_id') == 'satellite':
        return [], 'out_of_scope', 'product_update'
    if source.get('category_id') == 'news':
        scoped = [item for item in matches if news_direct_event(item)]
        if not scoped:
            return [], 'out_of_scope', 'not_event'
        return list(dict.fromkeys(scoped)), 'in_scope', 'candidate'
    source_text = ' '.join(str(source.get(key, '')) for key in ('name', 'url', 'note')).lower()
    source_in_scope = any(term.lower() in source_text for term in SCOPE_TERMS)
    scoped = [item for item in matches if any(term.lower() in item.lower() for term in SCOPE_TERMS)]
    if source_in_scope:
        scoped = matches
    if not scoped:
        return [], 'out_of_scope', 'not_event'
    return list(dict.fromkeys(scoped)), 'in_scope', 'candidate'


def select_path(value, path):
    for key in path.split('.'):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def extract(body, ctype, source, defaults, encoding=None):
    watch = source.get('watch', {})
    title = ''
    source_time = None
    if 'json' in ctype:
        obj = json.loads(body)
        if watch.get('source_time_path'):
            stamp = select_path(obj, watch['source_time_path'])
            parsed = dt.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                source_time = parsed.isoformat()
        if watch.get('json_path'):
            obj = select_path(obj, watch['json_path'])
        if isinstance(obj, dict) and isinstance(obj.get('features'), list):
            obj = obj['features']
        elif isinstance(obj, dict) and isinstance(obj.get('feed'), dict) and isinstance(obj['feed'].get('entry'), list):
            obj = obj['feed']['entry']
        elif isinstance(obj, dict) and isinstance(obj.get('data'), list):
            obj = obj['data']
        items = obj if isinstance(obj, list) else [obj]
        content = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items
                   if structured_match(item, watch.get('structured', {}))]
    elif any(kind in ctype for kind in ('xml', 'rss', 'atom')):
        if b'<!ENTITY' in body or b'<!DOCTYPE' in body:
            raise ValueError('Unsupported XML entity/doctype')
        root = ET.fromstring(body)
        entries = [e for e in root.iter() if e.tag.split('}')[-1] in ('item', 'entry')]
        def allowed(entry):
            fields={node.tag.split('}')[-1]:node.text for node in entry}
            fields['published_at']=fields.get('pubDate') or fields.get('published') or fields.get('updated')
            return structured_match(fields,watch.get('structured',{}))
        content = [' '.join(e.itertext()) for e in entries if allowed(e)] if entries else [' '.join(root.itertext())]
    elif 'html' in ctype or ctype.startswith('text/'):
        soup = BeautifulSoup(body, 'html.parser', from_encoding=encoding)
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        if watch.get('selector'):
            nodes = soup.select(watch['selector'])
            if not nodes:
                raise ValueError('Configured selector missing')
        else:
            nodes = soup.select('article, p, li, tr, h1, h2, h3')
            # Use leaf blocks to avoid merging unrelated articles into one keyword hit.
            nodes = [n for n in nodes if not n.select('article, p, li, tr, h1, h2, h3')]
        content = [n.get_text(' ', strip=True) for n in nodes] if nodes else list(soup.stripped_strings)
        if not any(x.strip() for x in content):
            raise ValueError('Empty page or client-rendered content unavailable')
    else:
        raise ValueError('Unsupported content type: ' + ctype)
    content = list(dict.fromkeys(' '.join(x.split()) for x in content if x.strip()))
    keywords = watch.get('filter_keywords', defaults.get('keywords', []))
    signals = watch.get('signal_keywords', defaults.get('signals', []))
    exclude = watch.get('exclude_keywords', [])
    matches = []
    for item in content:
        cleaned = item
        for pattern in defaults.get('ignore', []) + watch.get('ignore', []):
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.I)
        lowered = cleaned.lower()
        mode = watch.get('match_mode', defaults.get('match_mode', 'all'))
        if mode == 'all':
            if cleaned.strip(): matches.append(' '.join(cleaned.split()))
            continue
        if any(word.lower() in lowered for word in exclude):
            continue
        if mode == 'any':
            if any(word.lower() in lowered for word in keywords + signals):
                matches.append(' '.join(cleaned.split()))
            continue
        if keywords and not any(word.lower() in lowered for word in keywords):
            continue
        if keywords and signals and not any(word.lower() in lowered for word in signals):
            continue
        if cleaned.strip():
            matches.append(' '.join(cleaned.split()))
    return title, content, matches, source_time


def fetch_page(url, settings, max_retries=3):
    """Fetch page with automatic exponential backoff retry on timeouts, 5xx errors, or network glitches."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        started = time.monotonic()
        try:
            with requests.get(url, timeout=settings['timeout_seconds'], stream=True,
                              headers={'User-Agent': 'Everest-realtime/4.0 (Windows NT 10.0; Win64; x64)'}) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_content(65536):
                    payload.extend(chunk)
                    if len(payload) > settings['max_response_bytes'] or time.monotonic() - started > 90:
                        raise ValueError('Response exceeds configured size/time budget')
                return bytes(payload), response.headers.get('Content-Type','').split(';')[0], response.url, response.encoding if 'charset=' in response.headers.get('Content-Type','').lower() else None
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep_s = attempt * 2  # retry backoff: 2s, 4s
                time.sleep(sleep_s)
            else:
                raise last_exc


def collect(source, defaults, settings, folder, run_id):
    folder.mkdir(parents=True, exist_ok=True)
    result = {'source': source, 'run_id': run_id, 'result': 'unknown', 'retrieved_at': now(),
               'source_time': None, 'content': [], 'matches': [], 'cards': [], 'error': '',
               'pages': [], 'network_records': [], 'map_images': [], 'article_records': [],
               'acquisition_errors': [], 'pending_urls': [], 'alert_screenshots': []}
    try:
        plan = settings.get('source_plans', {}).get(source['rule_id'], {})
        lightweight = bool(source.get('lightweight'))
        map_source = plan.get('map', source.get('category_id') == 'satellite')
        queue = [{'url':source['url'], 'kind':'root'}] + [{'url':u,'kind':'endpoint'} for u in plan.get('endpoints', [])]
        seen = set()
        max_pages = 1 if lightweight else int(source.get('max_pages', settings.get('max_pages_per_source', 6)))
        while queue and len(seen) < max_pages:
            entry = queue.pop(0); url = entry['url']
            if url in seen: continue
            seen.add(url)
            target = folder if entry['kind']=='root' else folder/f'page-{len(seen):02d}'
            target.mkdir(exist_ok=True)
            try:
                try:
                    body, ctype, final_url, encoding = fetch_page(url, settings)
                except Exception:
                    if not settings.get('render_html') or entry['kind']=='endpoint': raise
                    body, ctype, final_url, encoding = b'', 'text/html', url, None
                (target/'response.bin').write_bytes(body)
                if entry['kind']=='root':
                    result.update(content_type=ctype, final_url=final_url, raw_path=str(target/'response.bin'))
                if 'html' in ctype and settings.get('render_html') and not lightweight:
                    from .browser import render
                    try:
                        render_options = {}
                        if (source.get('category_id') == 'news' or source['rule_id'] == 'weather-03') and entry['kind'] == 'root':
                            render_options['capture_screenshot'] = False
                        rendered = render(url, target, settings, map_source, **render_options)
                        body = rendered.pop('dom')
                        final_url = rendered['final_url']
                        if entry['kind']=='root':
                            result['screenshot'] = {k:rendered[k] for k in ('captured_at','final_url')}
                        result['network_records'].extend(rendered['network_records'])
                        result['map_images'].extend(rendered['map_images'])
                    except Exception as exc:
                        result['acquisition_errors'].append({'url':url,'stage':'browser','error':type(exc).__name__})
                try:
                    title, content, matches, source_time = extract(body,ctype,source,defaults,encoding)
                except ValueError:
                    if map_source and result['map_images']:
                        title,content,matches,source_time=source['name'],[],[],None
                    else: raise
                result['title'] = result.get('title') or title
                result['content'].extend(content); result['matches'].extend(matches)
                if source.get('category_id') == 'news' and entry['kind'] == 'matched_article':
                    screenshot = target / 'page.png'
                    article_text = ' '.join(content)
                    if news_direct_event(article_text) and screenshot.is_file():
                        result['alert_screenshots'].append(str(screenshot))
                if source['rule_id'] == 'weather-03':
                    if entry['kind'] == 'root':
                        result['matches'] = []
                    elif entry['kind'] == 'nmc_alert':
                        screenshot = target / 'page.png'
                        if screenshot.is_file():
                            result['alert_screenshots'].append(str(screenshot))
                if source_time: result['source_time']=source_time
                result['pages'].append({'url':final_url,'kind':entry['kind'],'content_type':ctype,'retrieved_at':now(),'items':len(content)})
                if 'html' in ctype:
                    result['article_records'].append(article_metadata(body,final_url))
                    if not lightweight:
                        queue.extend(discover(
                            body, final_url, settings,
                            news_only=source.get('category_id') == 'news',
                            nmc_alerts_only=source['rule_id'] == 'weather-03'))
                elif any(x in ctype for x in ('rss','atom','xml')):
                    articles=feed_links(body,final_url)
                    result['article_records'].extend(articles)
                    if settings.get('follow_details') and not lightweight:
                        queue.extend({'url':a['url'],'kind':'article'} for a in articles)
            except Exception as exc:
                result['acquisition_errors'].append({'url':url,'stage':'fetch_parse','error':type(exc).__name__})
        result['pending_urls'] = list(dict.fromkeys(e['url'] for e in queue if e['url'] not in seen))
        for network in result['network_records']:
            data=network['data']
            items=data.get('features',[data]) if isinstance(data,dict) else (data if isinstance(data,list) else [data])
            for item in items:
                if structured_match(item, source.get('watch',{}).get('structured',{})):
                    text=json.dumps(item,ensure_ascii=False,sort_keys=True)
                    result['content'].append(text)
                    # Feed API records through the same explicit (optional) filters.
                    _,_,matches,_=extract(json.dumps(item).encode(),'application/json',source,defaults)
                    result['matches'].extend(matches)
        if plan.get('wms'):
            from .maps import fetch_wms
            try:
                image,metadata=fetch_wms(plan['wms'],folder,settings)
                result['map_images'].insert(0,{'path':str(image),**metadata})
                result['source_time']=metadata.get('time')
                result['matches'].append(json.dumps({k:v for k,v in metadata.items() if k!='attempts'},ensure_ascii=False,sort_keys=True))
            except Exception as exc:
                result['acquisition_errors'].append({'stage':'wms','error':type(exc).__name__})
        from .mapviews import capture_views
        defer_views = source['rule_id'] in settings.get('defer_map_views_for', [])
        views = [] if lightweight or defer_views else capture_views(source['rule_id'], folder, settings, settings.get('_root', '.'))
        if views:
            result['map_views'] = views
            for view in views:
                if view['error']:
                    result['acquisition_errors'].append({'stage':'map_view','layer':view['layer'],'error':view['error']})
            if any(view['image'] for view in views):
                result['result'] = 'found'
        result['content']=list(dict.fromkeys(result['content']))
        # Filter out noisy live webcam heartbeat and transient model query versions from Windy content diff
        if source.get('rule_id') == 'weather-06':
            result['content'] = [
                c for c in result['content']
                if '"cams":' not in c and '"ref":' not in c and '"update":' not in c
            ]
        result['matches']=list(dict.fromkeys(result['matches']))
        has_content_match = bool(result['matches'])
        result['matches'], result['relevance'], result['event_status'] = classify_matches(source, result['matches'])
        result['coverage']='partial' if result['pending_urls'] or result['acquisition_errors'] else 'complete_for_requested_pages'
        if result['pages'] or result['map_images'] or result.get('map_views'):
            result['result']='found' if has_content_match or result['map_images'] else 'not_found'
        else:
            result['error']='No source data acquired'
    except Exception as exc:
        result['error'] = type(exc).__name__ + (': '+str(exc) if isinstance(exc, (ValueError, KeyError)) else '')
    result['retrieved_at'] = now()
    result.setdefault('relevance', 'uncertain' if result['result'] == 'unknown' else 'out_of_scope')
    result.setdefault('event_status', 'not_event')
    return result
