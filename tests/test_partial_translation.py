from pathlib import Path
from PIL import Image

from everest.evidence import make_cards


def _record():
    return {'source': {'rule_id': 'weather-09', 'url': 'https://example.test/everest'},
            'screenshot': {'captured_at': '2026-09-15T00:00:00Z'}, 'matches': [], 'cards': []}


def test_partial_translation_failure_keeps_successful_pages(monkeypatch, tmp_path):
    import everest.translation as module
    Image.new('RGB', (40, 40), 'red').save(tmp_path / 'page.png')
    Image.new('RGB', (40, 40), 'green').save(tmp_path / 'page-02.png')
    (tmp_path / 'page-02').mkdir(exist_ok=True)
    (tmp_path / 'page-02' / 'screenshot-info.json').write_text('{"source_url": "https://example.test/story"}', encoding='utf-8')
    (tmp_path / 'page-02' / 'page.png').write_bytes((tmp_path / 'page-02.png').read_bytes())

    calls = []
    def fake(url, path, settings, language):
        calls.append(url)
        if 'story' in url:
            raise ValueError('No translated Chinese source content')
        Image.new('RGB', (40, 40), 'blue').save(path)
        return {'source_url': url, 'chinese_characters': 100}
    monkeypatch.setattr(module, 'chinese_screenshot', fake)

    record = _record()
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': False,
                                  'max_translated_pages': 3})
    # The homepage translated, so we still produce a card and record the other page's error.
    assert record['cards'], 'a successful translation must still be delivered'
    assert record['image_kind'] == 'translated_source_screenshot'
    assert any('ValueError' in e for e in record['translation_errors'])


def test_all_translations_failing_falls_back_to_original(monkeypatch, tmp_path):
    import everest.translation as module
    Image.new('RGB', (40, 40), 'red').save(tmp_path / 'page.png')
    def fake(*a, **kw):
        raise ValueError('No translated Chinese source content')
    monkeypatch.setattr(module, 'chinese_screenshot', fake)
    record = _record()
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': False})
    # Translation is impossible for this page, but we still send the real original page
    # and label the reason instead of silently producing nothing.
    assert record['cards'], 'original screenshot must still be delivered'
    assert record['image_kind'] == 'original_screenshot'
    assert 'translation unavailable' in record['screenshot_error']


def test_all_translations_failing_without_fallback_is_empty(monkeypatch, tmp_path):
    import everest.translation as module
    Image.new('RGB', (40, 40), 'red').save(tmp_path / 'page.png')
    def fake(*a, **kw):
        raise ValueError('No translated Chinese source content')
    monkeypatch.setattr(module, 'chinese_screenshot', fake)
    record = _record()
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': False,
                                  'fallback_to_original_on_translation_failure': False})
    assert record['cards'] == []
    assert 'Chinese translation failed for all pages' in record['screenshot_error']


def test_max_translated_pages_caps_work(monkeypatch, tmp_path):
    import everest.translation as module
    Image.new('RGB', (40, 40), 'red').save(tmp_path / 'page.png')
    for i in range(2, 6):
        d = tmp_path / f'page-0{i}'
        d.mkdir(exist_ok=True)
        (d / 'page.png').write_bytes((tmp_path / 'page.png').read_bytes())
        (d / 'screenshot-info.json').write_text(f'{{"source_url": "https://example.test/p{i}"}}', encoding='utf-8')
    calls = []
    def fake(url, path, settings, language):
        calls.append(url)
        Image.new('RGB', (40, 40), 'blue').save(path)
        return {'source_url': url, 'chinese_characters': 50}
    monkeypatch.setattr(module, 'chinese_screenshot', fake)
    record = _record()
    make_cards(record, tmp_path, {'translate_screenshots': True, 'screenshots': False,
                                  'max_translated_pages': 2})
    assert len(calls) == 2
