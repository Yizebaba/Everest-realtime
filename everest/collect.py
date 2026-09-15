import datetime as dt
import json
import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .core import now
from .filters import structured_match
from .discovery import discover, feed_links, article_metadata
from urllib.parse import urlsplit


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


def fetch_page(url, settings):
    started = time.monotonic()
    with requests.get(url, timeout=settings['timeout_seconds'], stream=True,
                      headers={'User-Agent': 'Everest-realtime/4.0'}) as response:
        response.raise_for_status()
        payload = bytearray()
        for chunk in response.iter_content(65536):
            payload.extend(chunk)
            if len(payload) > settings['max_response_bytes'] or time.monotonic()-started > 90:
                raise ValueError('Response exceeds configured size/time budget')
        return bytes(payload), response.headers.get('Content-Type','').split(';')[0], response.url, response.encoding if 'charset=' in response.headers.get('Content-Type','').lower() else None


def collect(source, defaults, settings, folder, run_id):
    folder.mkdir(parents=True, exist_ok=True)
    result = {'source': source, 'run_id': run_id, 'result': 'unknown', 'retrieved_at': now(),
              'source_time': None, 'content': [], 'matches': [], 'cards': [], 'error': '',
              'pages': [], 'network_records': [], 'map_images': [], 'article_records': [],
              'acquisition_errors': [], 'pending_urls': []}
    try:
        plan = settings.get('source_plans', {}).get(source['rule_id'], {})
        map_source = plan.get('map', source.get('category_id') == 'satellite')
        queue = [{'url':source['url'], 'kind':'root'}] + [{'url':u,'kind':'endpoint'} for u in plan.get('endpoints', [])]
        seen = set()
        max_pages = int(source.get('max_pages', settings.get('max_pages_per_source', 6)))
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
                if 'html' in ctype and settings.get('render_html'):
                    from .browser import render
                    try:
                        rendered = render(url,target,settings,map_source)
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
                if source_time: result['source_time']=source_time
                result['pages'].append({'url':final_url,'kind':entry['kind'],'content_type':ctype,'retrieved_at':now(),'items':len(content)})
                if 'html' in ctype:
                    result['article_records'].append(article_metadata(body,final_url))
                    queue.extend(discover(body,final_url,settings))
                elif any(x in ctype for x in ('rss','atom','xml')):
                    articles=feed_links(body,final_url)
                    result['article_records'].extend(articles)
                    if settings.get('follow_details'):
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
                result['matches'].append(json.dumps(metadata,ensure_ascii=False,sort_keys=True))
            except Exception as exc:
                result['acquisition_errors'].append({'stage':'wms','error':type(exc).__name__})
        result['content']=list(dict.fromkeys(result['content']))
        result['matches']=list(dict.fromkeys(result['matches']))
        result['coverage']='partial' if result['pending_urls'] or result['acquisition_errors'] else 'complete_for_requested_pages'
        if result['pages'] or result['map_images']:
            result['result']='found' if result['matches'] or result['map_images'] else 'not_found'
        else:
            result['error']='No source data acquired'
    except Exception as exc:
        result['error'] = type(exc).__name__ + (': '+str(exc) if isinstance(exc, (ValueError, KeyError)) else '')
    result['retrieved_at'] = now()
    return result
