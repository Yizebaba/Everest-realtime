"""Everest-positioned map view capture.

Each configured view is a fixed Everest URL with a named layer. We screenshot the
viewport (maps are viewport-bound, not full page) and record the layer, view URL
and capture time. Pixel change is not a hazard classification.
"""
import json
from pathlib import Path

from .core import now, read_json
from .translation import dismiss_gates


BLOCK_PAGES = ('您的请求可能存在威胁', '请求已被阻断', 'WEB 应用防火墙', 'Just a moment...')


def load_views(root):
    path = Path(root) / 'config' / 'map_views.json'
    if not path.is_file():
        return {'views': {}, 'unavailable': {}, 'everest': {}}
    return read_json(path)


def capture_views(rule_id, folder, settings, root):
    """Return one record per configured layer, or an empty list if unconfigured."""
    config = load_views(root)
    entry = config.get('views', {}).get(rule_id)
    if not entry:
        return []
    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as p:
        opts = {'headless': True}
        if settings['browser_channel'] != 'chromium':
            opts['channel'] = settings['browser_channel']
        if settings.get('proxy'):
            opts['proxy'] = {'server': settings['proxy']}
        browser = p.chromium.launch(**opts)
        try:
            for index, view in enumerate(entry['views'], 1):
                page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='zh-CN')
                record = {'layer': view['layer'], 'layer_name': view.get('name', view['layer']),
                          'view_url': view['url'], 'verified': view.get('verified', False),
                          'everest_center': config.get('everest', {}).get('center'),
                          'captured_at': now(), 'image': None, 'error': ''}
                try:
                    response = page.goto(view['url'], wait_until='domcontentloaded', timeout=45000)
                    if response and response.status >= 400:
                        raise ValueError('Map view HTTP ' + str(response.status))
                    page.wait_for_timeout(settings.get('map_settle_ms', 7000))
                    record['dismissed'] = dismiss_gates(page)
                    # If this view requested collapsing sidebars to maximize map canvas view
                    if view.get('collapse_sidebar'):
                        try:
                            collapse_btn = page.locator("button.sidebar-collapse, button[title*='Collapse sidebar'], [aria-label*='Collapse sidebar']").first
                            if collapse_btn.count() and collapse_btn.is_visible():
                                collapse_btn.click(timeout=3000)
                                page.wait_for_timeout(1000)
                        except Exception:
                            pass
                    if record['dismissed']:
                        page.wait_for_timeout(settings.get('map_settle_ms', 7000))
                    text = page.title() + '\n' + page.locator('body').inner_text()
                    if any(marker in text for marker in BLOCK_PAGES):
                        raise ValueError('Map view is a blocked page')
                    if page.locator('canvas').count() == 0 and 'map' not in text.lower():
                        raise ValueError('No map canvas rendered')
                    target = folder / f"map-{index:02d}-{view['layer']}.png"
                    page.screenshot(path=str(target), full_page=False, timeout=20000)
                    record['image'] = str(target)
                    record['title'] = page.title()
                except Exception as exc:
                    record['error'] = type(exc).__name__ + (': ' + str(exc) if isinstance(exc, ValueError) else '')
                finally:
                    page.close()
                results.append(record)
        finally:
            browser.close()
    return results
