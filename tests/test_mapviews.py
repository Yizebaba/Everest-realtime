import json
from pathlib import Path
from PIL import Image

from everest.evidence import make_cards
from everest.mapviews import load_views


def test_every_map_view_is_everest_positioned():
    root = Path(__file__).resolve().parents[1]
    config = load_views(root)
    assert config['everest']['center'] == [27.988, 86.925]
    assert len(config['everest']['bbox']) == 4
    assert config['views'], 'No map views configured'
    for rule_id, entry in config['views'].items():
        assert entry['views'], rule_id
        for view in entry['views']:
            assert view['layer'] and view['url'].startswith('https://'), (rule_id, view)


def test_unverified_or_dead_maps_are_declared_not_claimed():
    root = Path(__file__).resolve().parents[1]
    config = load_views(root)
    unavailable = config['unavailable']
    assert 'satellite-06' in unavailable and '停止服务' in unavailable['satellite-06']
    assert 'satellite-04' in unavailable
    for rule_id in unavailable:
        assert rule_id not in config['views'], rule_id


def test_map_view_capture_records_layer_and_errors(monkeypatch, tmp_path):
    import everest.mapviews as module
    calls = []
    monkeypatch.setattr(module, 'load_views', lambda root: {
        'everest': {'center': [27.988, 86.925]},
        'views': {'demo': {'views': [
            {'layer': 'wind', 'url': 'https://example.test/?wind', 'verified': True},
            {'layer': 'rain', 'url': 'https://example.test/?rain', 'verified': True},
        ]}},
        'unavailable': {},
    })

    class Canvas:
        def count(self): return 1
    class Empty:
        def count(self): return 0
        def is_visible(self): return False
    class Body:
        def inner_text(self): return 'map'
    class Page:
        def __init__(self, url): self.url = url
        def goto(self, url, **kw):
            calls.append(url)
            if 'rain' in url: raise ValueError('Map view HTTP 503')
            class R: status = 200
            return R()
        def wait_for_timeout(self, ms): pass
        def title(self): return 'demo map'
        def locator(self, sel): return Body() if sel == 'body' else Canvas()
        def get_by_role(self, role, **kw): return Empty()
        def get_by_text(self, text, **kw): return Empty()
        def screenshot(self, path, **kw): Image.new('RGB', (60, 40), 'blue').save(path)
        def close(self): pass
    class Browser:
        def new_page(self, **kw): return Page(kw.get('url'))
        def close(self): pass
    class Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        chromium = type('C', (), {'launch': lambda self, **kw: Browser()})()
    import playwright.sync_api
    monkeypatch.setattr(playwright.sync_api, 'sync_playwright', lambda: Ctx())

    views = module.capture_views('demo', tmp_path, {'browser_channel': 'chromium'}, '.')
    assert [v['layer'] for v in views] == ['wind', 'rain']
    assert views[0]['image'] and not views[0]['error']
    assert views[1]['image'] is None and '503' in views[1]['error']
    assert all(v['everest_center'] == [27.988, 86.925] for v in views)


def test_map_view_images_sent_without_translation_or_redraw(tmp_path):
    original = tmp_path / 'map-01-wind.png'
    Image.new('RGB', (80, 60), 'green').save(original)
    record = {
        'source': {'rule_id': 'weather-06', 'url': 'https://www.windy.com/'},
        'map_views': [{'layer': 'wind', 'view_url': 'https://www.windy.com/?wind',
                       'image': str(original), 'error': '', 'everest_center': [27.988, 86.925]}],
        'matches': ['found changed 获取时间'],
    }
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': True})
    assert record['image_kind'] == 'everest_map_view'
    assert record['map_view_layers'] == ['wind']
    assert Path(record['cards'][0]).read_bytes() == original.read_bytes()


def test_map_view_failure_does_not_fall_back_to_page(tmp_path):
    Image.new('RGB', (80, 60), 'green').save(tmp_path / 'page.png')
    record = {
        'source': {'rule_id': 'weather-06', 'url': 'https://www.windy.com/'},
        'screenshot': {'captured_at': '2026-09-15T00:00:00Z'},
        'map_views': [{'layer': 'wind', 'view_url': 'https://www.windy.com/?wind',
                       'image': None, 'error': 'ValueError: No map canvas rendered'}],
    }
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': True})
    assert record['cards'] == []
    assert 'No Everest map view' in record['screenshot_error']


def test_signature_renamed():
    from everest.delivery import SIGNATURE
    assert SIGNATURE == 'vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'
