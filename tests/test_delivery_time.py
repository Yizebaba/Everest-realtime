import datetime as dt

from everest.delivery import format_observation_time, source_timezone


def test_observation_time_uses_configured_source_timezone():
    value = '2026-09-25T04:45:58.423461+00:00'
    assert format_observation_time(value, 'Europe/London') == '2026-09-25 05:45:58 BST (UTC+0100)'


def test_observation_time_keeps_utc_without_a_source_timezone():
    value = '2026-09-25T04:45:58+00:00'
    assert format_observation_time(value) == '2026-09-25 04:45:58 UTC (UTC+0000)'


def test_source_timezone_prefers_explicit_value_then_operator_headquarters():
    assert source_timezone({'url': 'https://www.windy.com/'}) == 'Europe/Prague'
    assert source_timezone({'url': 'https://www.windy.com/', 'timezone': 'Asia/Kathmandu'}) == 'Asia/Kathmandu'
