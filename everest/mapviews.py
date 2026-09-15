"""Everest-positioned map view capture.

Each configured view is a fixed Everest URL with a named layer. We screenshot the
viewport (maps are viewport-bound, not full page) and record the layer, view URL
and capture time. Pixel change is not a hazard classification.
"""
import json
from pathlib import Path

from .core import now, read_json


BLOCK_PAGES = ('您的请求可能存在威胁', '请求已被阻断', 'WEB 应用防火墙', 'Just a moment...')

# Modal gates that cover the map until dismissed. Text is matched exactly or as a
# substring of the button label; we never click links or navigation.
DISMISS_TEXTS = (
    'OK, I Understand', 'OK I Understand', 'I Understand', 'Got it', 'Got It',
    'Accept all cookies', 'Accept only essential cookies', 'Accept All', 'Accept',
    'I agree', 'Agree', 'Continue anonymously', 'Continue', 'Dismiss', 'Close',
    '知道了', '我了解', '我同意', '接受', '同意', '关闭', '继续',
)


def _dismiss_gates(page, settings):
    """Click only short, exact-label dismiss buttons; record what was clicked."""
    clicked = []
    for _ in range(3):
        hit = None
        for text in DISMISS_TEXTS:
            locator = page.get_by_role('button', name=text, exact=True)
            try:
                if locator.count() and locator.first.is_visible():
                    hit = (text, locator.first)
                    break
            except Exception:
                continue
        if hit is None:
            for text in DISMISS_TEXTS:
                locator = page.get_by_text(text, exact=True)
                try:
                    if locator.count() and locator.first.is_visible():
                        hit = (text, locator.first)
                        break
                except Exception:
                    continue
        if hit is None:
            break
        try:
            hit[1].click(timeout=3000)
            clicked.append(hit[0])
            page.wait_for_timeout(1200)
        except Exception:
            break
    return clicked


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
                    record['dismissed'] = _dismiss_gates(page, settings)
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
