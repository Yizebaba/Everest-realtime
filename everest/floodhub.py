"""Rendered Google Flood Hub map monitoring for the Everest vicinity."""
import io
from pathlib import Path

from PIL import Image

from .core import now
from .webcam import _visual_signature


def collect_floodhub(source, folder, settings, run_id):
    from playwright.sync_api import sync_playwright

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
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
                    raise ValueError('Flood Hub HTTP ' + str(response.status))
                page.wait_for_timeout(settings.get('floodhub_settle_ms', 12000))
                image = Image.open(io.BytesIO(page.screenshot(type='png'))).convert('RGB')
                target = folder / 'page.png'
                image.save(target)
                result['visual_frame_signature'] = _visual_signature(image).hex()
                result['visual_frame_path'] = str(target)
                result['content'] = ['Flood Hub Everest vicinity map']
                result['matches'] = list(result['content'])
                result['result'] = 'found'
                result['pages'] = [{'url': page.url, 'kind': 'floodhub_map', 'content_type': 'text/html',
                                    'retrieved_at': result['retrieved_at'], 'items': 1}]
                result['screenshot'] = {'captured_at': result['retrieved_at'], 'final_url': page.url}
            finally:
                browser.close()
    except Exception as exc:
        result['error'] = type(exc).__name__
        result['acquisition_errors'].append({'url': source['url'], 'stage': 'floodhub_map', 'error': type(exc).__name__})
    return result
