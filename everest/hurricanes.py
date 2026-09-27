"""Daily Windy hurricane tracker: identify storms by name, not map movement."""
from pathlib import Path

from .core import now
from .translation import dismiss_gates, translate_page_to_chinese


def collect_hurricanes(source, folder, settings, run_id):
    from playwright.sync_api import sync_playwright

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = {
        'source': source, 'run_id': run_id, 'result': 'unknown', 'retrieved_at': now(),
        'source_time': None, 'content': [], 'matches': [], 'cards': [], 'error': '',
        'pages': [], 'network_records': [], 'map_images': [], 'article_records': [],
        'acquisition_errors': [], 'pending_urls': [], 'alert_screenshots': [], 'map_views': [],
        'relevance': 'in_scope', 'event_status': 'candidate',
    }
    try:
        with sync_playwright() as p:
            opts = {'headless': True}
            if settings['browser_channel'] != 'chromium':
                opts['channel'] = settings['browser_channel']
            if settings.get('proxy'):
                opts['proxy'] = {'server': settings['proxy']}
            browser = p.chromium.launch(**opts)
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='zh-CN')
                response = page.goto(source['url'], wait_until='domcontentloaded', timeout=45000)
                if response and response.status >= 400:
                    raise ValueError('Hurricane tracker HTTP ' + str(response.status))
                page.wait_for_timeout(settings.get('map_settle_ms', 7000))
                dismiss_gates(page)
                translate_page_to_chinese(page, settings)
                lines = [line.strip() for line in page.locator('body').inner_text().splitlines() if line.strip()]
                entries = []
                for index, line in enumerate(lines[:-1]):
                    if line.startswith('飓风等级') or line in ('热带风暴', '热带低压'):
                        name = lines[index + 1]
                        if name not in entries:
                            entries.append(name)
                if not entries:
                    raise ValueError('No hurricane entries found')
                for index, name in enumerate(entries, 1):
                    # The tracker repeats names on the map and in the right-hand list;
                    # the last exact match is the list entry shown after its severity.
                    item = page.get_by_text(name, exact=True).last
                    item.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    target = folder / f'hurricane-{index:02d}.png'
                    page.screenshot(path=str(target), full_page=False, timeout=20000)
                    result['map_views'].append({
                        'layer': f'hurricane-{index:02d}', 'layer_name': f'飓风 {name}',
                        'layer_en': f'Hurricane {name}', 'view_url': page.url,
                        'captured_at': now(), 'image': str(target), 'error': '',
                    })
                result['content'] = entries
                result['matches'] = entries
                result['result'] = 'found'
                result['pages'] = [{'url': page.url, 'kind': 'hurricane_tracker',
                                    'content_type': 'text/html', 'retrieved_at': result['retrieved_at'],
                                    'items': len(entries)}]
            finally:
                browser.close()
    except Exception as exc:
        result['error'] = type(exc).__name__
        result['acquisition_errors'].append({'url': source['url'], 'stage': 'hurricane_tracker', 'error': type(exc).__name__})
    return result
