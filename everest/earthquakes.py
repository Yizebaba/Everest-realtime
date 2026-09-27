"""Browser-backed extraction of real earthquake rows for global fast alerts."""
import re
import json
import requests
from bs4 import BeautifulSoup

from .core import now


def _event_key(text, source_id=''):
    stamp = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', text)
    if stamp:
        before = text[:stamp.start()]
        # Agencies may revise magnitude (for example USGS 5.3 vs GEOFON 5.1)
        # while referring to the same origin time. Minute-level origin time is the
        # common stable identity across the seven independent public sources.
        return f"quake:{stamp.group(0)}"
    return 'quake:' + re.sub(r'\s+', ' ', text).strip().lower()


def _event_text(time, magnitude, latitude, longitude, depth, place):
    return f"M{magnitude} | {time} UTC | {latitude}, {longitude} | {depth} km | {place}"


def collect_earthquakes(source, folder, settings, run_id):
    from playwright.sync_api import sync_playwright
    result = {'source': source, 'run_id': run_id, 'result': 'unknown', 'retrieved_at': now(),
              'source_time': None, 'content': [], 'matches': [], 'cards': [], 'error': '',
              'pages': [], 'network_records': [], 'map_images': [], 'article_records': [],
              'acquisition_errors': [], 'pending_urls': [], 'alert_screenshots': [],
              'relevance': 'in_scope', 'event_status': 'candidate'}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='zh-CN')
                response = page.goto(source['url'], wait_until='domcontentloaded', timeout=45000)
                if response and response.status >= 400:
                    raise ValueError('Earthquake source HTTP ' + str(response.status))
                page.wait_for_timeout(settings.get('browser_wait_ms', 2500) + 3500)
                if source['rule_id'] == 'earthquake-02':
                    rows = [' '.join(x.split()) for x in page.locator('.mat-mdc-list-item').all_inner_texts()]
                    events = [x for x in rows if not x.startswith('Auto Update') and re.search(r'\d{4}-\d{2}-\d{2}', x) and re.search(r'\d(?:\.\d)?', x)]
                    event_keys = [_event_key(x, source['rule_id']) for x in events]
                elif source['rule_id'] == 'earthquake-03':
                    data = requests.get('https://www.seismicportal.eu/fdsnws/event/1/query?format=json&limit=100&orderby=time', timeout=settings['timeout_seconds']).json()
                    events = [_event_text(f['properties']['time'].replace('T', ' ')[:19], f['properties']['mag'], f['properties']['lat'], f['properties']['lon'], f['properties']['depth'], f['properties'].get('flynn_region', '')) for f in data['features']]
                    event_keys = [f"quake:{f['properties']['time'][:16].replace('T', ' ')}:m{f['properties']['mag']}" for f in data['features']]
                elif source['rule_id'] == 'earthquake-04':
                    data = requests.get('https://www.seismicportal.eu/fdsnws/event/1/query?format=json&limit=100&orderby=time', timeout=settings['timeout_seconds']).json()
                    events = [_event_text(f['properties']['time'].replace('T', ' ')[:19], f['properties']['mag'], f['properties']['lat'], f['properties']['lon'], f['properties']['depth'], f['properties'].get('flynn_region', '')) for f in data['features']]
                    event_keys = [f"quake:{f['properties']['time'][:16].replace('T', ' ')}:m{f['properties']['mag']}" for f in data['features']]
                elif source['rule_id'] == 'earthquake-05':
                    soup = BeautifulSoup(requests.get(source['url'], timeout=settings['timeout_seconds']).content, 'html.parser')
                    events = [' '.join(row.get_text(' ', strip=True).split()) for row in soup.select('.eqinfo-all')]
                    events = [x for x in events if re.search(r'\d{4}-\d{2}-\d{2}', x)]
                    event_keys = [_event_key(x, source['rule_id']) for x in events]
                elif source['rule_id'] == 'earthquake-07':
                    data = requests.get('https://www.ceic.ac.cn/data/data.json', timeout=settings['timeout_seconds']).json()
                    events = [_event_text(x['time'], x['magnitude'], x['latitude'], x['longitude'], x['depth'], x['location']) for x in data]
                    event_keys = [f"quake:{x['time'][:16]}:m{x['magnitude']}" for x in data]
                elif source['rule_id'] == 'special-02':
                    events = [' '.join(row.split()) for row in page.locator('table tr').all_inner_texts()]
                    events = [x for x in events if 'UTC:' in x and 'ML' in x]
                    event_keys = [f"quake:{m.group(1)} {m.group(2)}:m{m.group(3)}" for x in events
                                  for m in [re.search(r'ई\.सं\.:\s*(\d{4}-\d{2}-\d{2}).*?UTC:\s*(\d{2}:\d{2}).*?([\d.]+)\s+ML', x)]
                                  if m]
                else:
                    events, event_keys = [], []
                events = list(dict.fromkeys(events))[:100]
                if not events:
                    raise ValueError('No earthquake event rows found')
                result['content'] = events
                result['matches'] = events
                result['event_keys'] = event_keys[:len(events)]
                result['screenshot_event_text'] = events[0]
                result['result'] = 'found'
                result['pages'] = [{'url': page.url, 'kind': 'earthquake_list', 'content_type': 'text/html',
                                    'retrieved_at': result['retrieved_at'], 'items': len(events)}]
            finally:
                browser.close()
    except Exception as exc:
        result['error'] = type(exc).__name__
        result['acquisition_errors'].append({'url': source['url'], 'stage': 'earthquake_events', 'error': type(exc).__name__})
    return result
