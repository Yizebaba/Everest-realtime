import copy
import datetime as dt
from pathlib import Path

from everest.core import Store
from everest.delivery import destination


def make_result(rule_id='earthquake-05', matches=None, run='r1'):
    return {
        'run_id': run,
        'source': {'rule_id': rule_id, 'name': 'GEOFON', 'url': 'https://geofon.gfz.de/eqinfo/list.php'},
        'result': 'found',
        'retrieved_at': '2026-09-15T00:00:00+00:00',
        'matches': matches if matches is not None else ['M 5.0 Loyalty Islands'],
        'content': [],
        'error': '',
        'cards': [],
    }


def test_interval_seconds_controls_due(tmp_path):
    store = Store(tmp_path / 'f.db')
    try:
        source = {'rule_id': 'earthquake-05', 'interval_seconds': 3, 'interval_minutes': 15}
        assert store.due(source, '2026-09-15T00:00:00+00:00') is True
        store.record(make_result(), tmp_path / 'r.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        # 2 seconds later: not due for a 3-second interval
        assert store.due(source, '2026-09-15T00:00:02+00:00') is False
        # 4 seconds later: due
        assert store.due(source, '2026-09-15T00:00:04+00:00') is True
    finally:
        store.close()


def test_minute_interval_still_works(tmp_path):
    store = Store(tmp_path / 'f.db')
    try:
        source = {'rule_id': 'earthquake-05', 'interval_minutes': 15}
        store.record(make_result(), tmp_path / 'r.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.due(source, '2026-09-15T00:05:00+00:00') is False
        assert store.due(source, '2026-09-15T00:16:00+00:00') is True
    finally:
        store.close()


def test_changed_detects_new_event_and_ignores_identical(tmp_path):
    store = Store(tmp_path / 'f.db')
    try:
        source = {'rule_id': 'earthquake-05'}
        # No baseline yet -> first observation is not a change (avoids alerting the whole backlog)
        assert store.changed(source, make_result()) is False
        store.record(make_result(), tmp_path / 'r.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        # Identical content -> no change
        assert store.changed(source, make_result()) is False
        # New event appears -> change
        new = make_result(matches=['M 5.0 Loyalty Islands', 'M 6.1 Java Indonesia'])
        assert store.changed(source, new) is True
    finally:
        store.close()


def test_unknown_fast_result_never_counts_as_change(tmp_path):
    store = Store(tmp_path / 'f.db')
    try:
        source = {'rule_id': 'earthquake-05'}
        store.record(make_result(), tmp_path / 'r.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        failed = make_result(matches=[])
        failed['result'] = 'unknown'
        assert store.changed(source, failed) is False
    finally:
        store.close()


def test_requested_three_second_earthquake_sources():
    from everest.core import read_json
    sources = read_json(Path(__file__).parents[1] / 'config' / 'sources.json')['sources']
    by_id = {source['rule_id']: source for source in sources}
    fast_ids = {source['rule_id'] for source in sources if source.get('interval_seconds') == 3}
    assert {'earthquake-02', 'earthquake-03', 'earthquake-04', 'earthquake-05', 'special-02', 'earthquake-07', 'platform-10'} <= fast_ids
    assert by_id['earthquake-08']['enabled'] is False
    assert by_id['earthquake-10']['enabled'] is False


def test_windy_uses_15_minute_polling_and_nasa_is_paired_only():
    from everest.core import read_json
    sources = read_json(Path(__file__).parents[1] / 'config' / 'sources.json')['sources']
    by_id = {source['rule_id']: source for source in sources}
    assert by_id['weather-06']['interval_minutes'] in (15, 30)
    assert by_id['weather-06']['enabled'] is True


def test_paired_weather_triggers_on_activation_or_temperature_drop(tmp_path):
    store = Store(tmp_path / 'pair.db')
    try:
        assert store.paired_weather_trigger('weather-06', False, -20, 5) is False
        assert store.paired_weather_trigger('weather-06', True, -20, 5) is True
        assert store.paired_weather_trigger('weather-06', True, -21, 5) is False
        assert store.paired_weather_trigger('weather-06', True, -26, 5) is True
        assert store.paired_weather_trigger('weather-06', False, -32, 5) is True
    finally:
        store.close()


def test_lightweight_source_skips_browser_and_extra_pages(monkeypatch, tmp_path):
    import everest.collect as module
    calls = {'fetch': 0, 'render': 0}
    def fake_fetch(url, settings):
        calls['fetch'] += 1
        return (b'<html><body><table><tr><td>5.0</td><td>Loyalty</td></tr></table></body></html>',
                'text/html', url, None)
    def fake_render(*a, **kw):
        calls['render'] += 1
        raise AssertionError('lightweight source must not launch a browser')
    monkeypatch.setattr(module, 'fetch_page', fake_fetch)
    monkeypatch.setattr(module, 'render', fake_render, raising=False)
    source = {'rule_id': 'earthquake-05', 'name': 'GEOFON', 'url': 'https://geofon.gfz.de/eqinfo/list.php',
              'category_id': 'earthquake', 'lightweight': True}
    settings = {'render_html': True, 'max_pages_per_source': 6, '_root': '.', 'screenshots': False}
    result = module.collect(source, {}, settings, tmp_path / 'earthquake-05', 'run')
    assert calls['fetch'] == 1
    assert calls['render'] == 0
    assert result['result'] == 'found'
    assert any('Loyalty' in item for item in result['content'])
    assert result['relevance'] in ('in_scope', 'out_of_scope')
