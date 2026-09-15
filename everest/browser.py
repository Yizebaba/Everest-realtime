"""Return rendered DOM, screenshot and browser-loaded structured/map data together."""
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from .core import now


def public_url(url):
    parts = urlsplit(url)
    query = [(k, '[redacted]' if re.search('token|key|signature|password|secret', k, re.I) else v)
             for k,v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def render(url, folder, settings, capture_map=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        opts = {'headless': True}
        channel = settings.get('browser_channel', 'chromium')
        if channel != 'chromium': opts['channel'] = channel
        if settings.get('proxy'): opts['proxy'] = {'server': settings['proxy']}
        browser = p.chromium.launch(**opts)
        responses = []
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.on('response', lambda response: responses.append(response))
            response = page.goto(url, wait_until='domcontentloaded', timeout=35000)
            if response and response.status >= 400:
                raise ValueError('Browser HTTP '+str(response.status))
            page.wait_for_timeout(settings.get('browser_wait_ms', 2500))
            # Trigger lazy-loaded paragraphs and layers before obtaining DOM.
            for _ in range(2):
                page.mouse.wheel(0, 700)
                page.wait_for_timeout(400)
            page.evaluate('window.scrollTo(0,0)')
            dom = page.content()
            (folder/'rendered.html').write_text(dom, encoding='utf-8')
            page.screenshot(path=str(folder/'page.png'), full_page=True, timeout=15000)
            network=[]; images=[]; records=[]
            for r in responses:
                ctype=r.headers.get('content-type','')
                if not r.ok: continue
                if re.search('analytics|doubleclick|googletag|facebook|telemetry',r.url,re.I): continue
                is_json='json' in ctype and r.request.resource_type in ('xhr','fetch')
                is_tile=capture_map and 'image/' in ctype and re.search(r'wmts|tile|wms|D531106|/\d+/\d+|GetMap',r.url,re.I)
                if not is_json and not is_tile: continue
                if is_json and len(records)>=settings.get('max_network_records',30): continue
                if is_tile and len(images)>=settings.get('max_map_assets',4): continue
                try:
                    if int(r.headers.get('content-length','0'))>settings['max_response_bytes']: continue
                    body=r.body()
                    if len(body)>settings['max_response_bytes']: continue
                    token=hashlib.sha256(body).hexdigest()[:16]
                    target=folder/f'network-{token}.bin'
                    target.write_bytes(body)
                    meta={'url':public_url(r.url),'content_type':ctype,'path':str(target)}
                    network.append(meta)
                    if is_json: records.append({'source_url':meta['url'],'data':json.loads(body)})
                    if is_tile:
                        from PIL import Image
                        import io
                        image=Image.open(io.BytesIO(body)).convert('RGBA')
                        target=folder/f'map-{token}.png'; image.save(target)
                        images.append({'path':str(target),'url':meta['url'],'time':None})
                except Exception:
                    continue
            return {'dom':dom.encode(),'captured_at':now(),'final_url':public_url(page.url),
                    'network':network,'network_records':records,'map_images':images}
        finally:
            browser.close()
