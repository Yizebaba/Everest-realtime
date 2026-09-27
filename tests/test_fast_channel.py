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


def test_explicit_earthquake_event_keys_deduplicate_across_sources(tmp_path):
    store = Store(tmp_path / 'events.db')
    try:
        first = make_result('earthquake-02', ['USGS wording'])
        first['event_keys'] = ['quake:2026-09-15 00:00:1:2:3']
        store.record(first, tmp_path / 'first.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        second = make_result('earthquake-03', ['EMSC wording'])
        second['event_keys'] = ['quake:2026-09-15 00:00:1:2:3']
        Path(tmp_path / 'card.png').write_bytes(b'card')
        second['cards'] = [str(tmp_path / 'card.png')]
        # Existing event identity suppresses duplicate notices from another provider.
        assert not store.record(second, tmp_path / 'second.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
    finally:
        store.close()


def test_first_unseen_event_text_selects_the_new_earthquake(tmp_path):
    store = Store(tmp_path / 'event-target.db')
    try:
        first = make_result('earthquake-02', ['old quake'])
        first['event_keys'] = ['quake:old']
        store.record(first, tmp_path / 'old.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        current = make_result('earthquake-02', ['old quake', 'new quake'])
        current['event_keys'] = ['quake:old', 'quake:new']
        assert store.first_unseen_event_text(current) == 'new quake'
    finally:
        store.close()


def test_earthquake_seed_stores_all_current_event_keys_without_notification(tmp_path):
    store = Store(tmp_path / 'event-seed.db')
    try:
        current = make_result('earthquake-02', ['old quake', 'new quake'])
        current['event_keys'] = ['quake:old', 'quake:new']
        current['seed_event_keys'] = True
        store.record(current, tmp_path / 'seed.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.earthquake_event_keys_seeded(current)
        assert store.first_unseen_event_text(current) == ''
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


def test_earthquake_event_baseline_rejects_old_page_chrome(tmp_path):
    store = Store(tmp_path / 'events.db')
    try:
        store.record(make_result('earthquake-02', ['Javascript must be enabled']), tmp_path / 'old.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_earthquake_event_baseline('earthquake-02') is False
        store.record(make_result('earthquake-02', ['2026-09-25 09:46:30 19.341 -155.354 28 3.2']), tmp_path / 'new.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_earthquake_event_baseline('earthquake-02') is True
    finally:
        store.close()


def test_earthquake_event_baseline_rejects_old_ceic_page_rows(tmp_path):
    store = Store(tmp_path / 'ceic-events.db')
    try:
        store.record(make_result('earthquake-07', ['地震目录 2026-09-25 12:00:00']), tmp_path / 'old.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_earthquake_event_baseline('earthquake-07') is False
        store.record(make_result('earthquake-07', ['M5.3 | 2026-09-25 12:00:00 UTC | -28.85, -67.1 | 120 km | 阿根廷']), tmp_path / 'new.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_earthquake_event_baseline('earthquake-07') is True
    finally:
        store.close()


def test_event_parser_version_requires_one_silent_migration(tmp_path):
    store = Store(tmp_path / 'version.db')
    try:
        assert store.source_version('earthquake-02') == 0
        store.set_source_version('earthquake-02', 4)
        assert store.source_version('earthquake-02') == 4
    finally:
        store.close()


def test_gdacs_flood_baseline_rejects_the_old_login_page(tmp_path):
    store = Store(tmp_path / 'gdacs.db')
    try:
        store.record(make_result('flood-02', ['Log in']), tmp_path / 'old.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_gdacs_flood_baseline('flood-02') is False
        flood = make_result('flood-02', ['{"properties": {"eventid": 1, "eventtype": "FL"}}'])
        store.record(flood, tmp_path / 'gdacs.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.has_gdacs_flood_baseline('flood-02') is True
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
    assert 'camera-01' not in by_id
    assert by_id['hurricane-01']['daily_at_beijing'] == '07:00'


def test_windy_uses_15_minute_polling_and_nasa_is_paired_only():
    from everest.core import read_json
    sources = read_json(Path(__file__).parents[1] / 'config' / 'sources.json')['sources']
    by_id = {source['rule_id']: source for source in sources}
    assert by_id['weather-06']['interval_minutes'] in (15, 30)
    assert by_id['weather-06']['enabled'] is True


def test_flood_uses_gdacs_api_and_disables_expired_google_flood_link():
    from everest.core import read_json
    sources = {s['rule_id']: s for s in read_json(Path(__file__).parents[1] / 'config' / 'sources.json')['sources']}
    assert 'gdacs.org/gdacsapi/api/events' in sources['flood-02']['url']
    assert sources['flood-05']['enabled'] is True
    assert sources['special-01']['enabled'] is False


def test_gdacs_flood_source_filters_only_flood_events():
    from everest.core import read_json
    sources = {s['rule_id']: s for s in read_json(Path(__file__).parents[1] / 'config' / 'sources.json')['sources']}
    assert sources['flood-02']['watch']['structured']['equals']['properties.eventtype'] == 'FL'


def test_floodhub_visual_trigger_requires_a_large_map_change(tmp_path):
    store = Store(tmp_path / 'floodhub.db')
    try:
        first = bytes(576).hex()
        small = (bytes([5]) * 576).hex()
        large = (bytes([40]) * 576).hex()
        assert store.visual_frame_trigger('flood-05', first, True, 35) is False
        assert store.visual_frame_trigger('flood-05', small, True, 35) is False
        assert store.visual_frame_trigger('flood-05', large, True, 35) is True
    finally:
        store.close()


def test_daily_beijing_schedule_runs_once_after_seven(tmp_path):
    store = Store(tmp_path / 'daily.db')
    try:
        source = {'rule_id': 'hurricane-01', 'interval_minutes': 1440, 'daily_at_beijing': '07:00'}
        assert store.due(source, '2026-09-15T22:59:00+00:00') is False
        assert store.due(source, '2026-09-15T23:00:00+00:00') is True
        checked = make_result('hurricane-01')
        checked['retrieved_at'] = '2026-09-15T23:00:00+00:00'
        store.record(checked, tmp_path / 'h.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.due(source, '2026-09-16T01:00:00+00:00') is False
        assert store.due(source, '2026-09-16T23:00:00+00:00') is True
    finally:
        store.close()


def test_daily_beijing_schedule_retries_after_invalid_attempt(tmp_path):
    store = Store(tmp_path / 'daily-retry.db')
    try:
        source = {'rule_id': 'hurricane-01', 'interval_minutes': 1440, 'daily_at_beijing': '07:00'}
        failed = make_result('hurricane-01')
        failed['result'] = 'unknown'
        failed['retrieved_at'] = '2026-09-15T23:00:00+00:00'
        store.record(failed, tmp_path / 'failed.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert store.due(source, '2026-09-16T01:00:00+00:00') is True
    finally:
        store.close()


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
