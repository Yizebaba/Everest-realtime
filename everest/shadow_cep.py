"""Non-blocking shadow evaluation for selected numeric sources.

This module records the four CEP-style opinions after acquisition and cards are
ready. Its results never alter capture, Store.record, or delivery decisions.
"""
import datetime as dt
import re
import sqlite3


SHADOW_RULE_IDS = {'earthquake-05', 'earthquake-07', 'weather-06', 'weather-10'}


def _metric(source, result):
    content = ' '.join(result.get('content', []))
    records = result.get('network_records', [])
    if source['rule_id'] == 'earthquake-07':
        for record in records:
            data = record.get('data')
            for item in data if isinstance(data, list) else []:
                if isinstance(item, dict) and item.get('magnitude') is not None:
                    return float(item['magnitude']), 'magnitude'
        match = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+[-\d.]+\s+[-\d.]+\s+\d+\s+([\d.]+)', content)
        return (float(match.group(1)), 'magnitude') if match else (None, '')
    if source['rule_id'] == 'earthquake-05':
        match = re.search(r'M\s*([\d.]+)', content)
        return (float(match.group(1)), 'magnitude') if match else (None, '')
    if source['rule_id'] == 'weather-10':
        for record in records:
            data = record.get('data')
            if isinstance(data, dict):
                current = data.get('current') or {}
                value = current.get('wind_gusts_10m') or current.get('wind_speed_10m')
                if value is not None:
                    return float(value), 'wind_gusts_kmh'
    if source['rule_id'] == 'weather-06':
        match = re.search(r'([\d.]+)\s*km/h', content, re.I)
        return (float(match.group(1)), 'wind_kmh') if match else (None, '')
    return None, ''


def evaluate(source, result, data_dir):
    """Return four observations for result.json; never raises into main flow."""
    if source['rule_id'] not in SHADOW_RULE_IDS:
        return None
    value, metric_name = _metric(source, result)
    now = dt.datetime.now(dt.timezone.utc)
    if value is None:
        return {
            'scope': 'shadow_only',
            'eligible': True,
            'metric': None,
            'engines': {name: {'triggered': False, 'reason': 'metric_unavailable'} for name in ('OpenCEP', 'LightCEP', 'Siddhi', 'Sigma')},
        }
    try:
        con = sqlite3.connect(data_dir / 'monitor.sqlite3', timeout=5)
        con.execute('CREATE TABLE IF NOT EXISTS shadow_cep_events (rule_id TEXT, value REAL, observed_at TEXT)')
        cutoff = (now - dt.timedelta(minutes=15)).isoformat()
        history = [row[0] for row in con.execute(
            'SELECT value FROM shadow_cep_events WHERE rule_id=? AND observed_at>=? ORDER BY rowid ASC',
            (source['rule_id'], cutoff),
        )]
        con.execute('INSERT INTO shadow_cep_events VALUES (?,?,?)', (source['rule_id'], value, now.isoformat()))
        con.commit()
        con.close()
    except Exception:
        history = []
    values = history + [value]
    earthquake = metric_name == 'magnitude'
    open_hit = len(values) >= 3 and values[-3] <= values[-2] <= values[-1] and values[-1] > 0
    siddhi_hit = len(values) >= 2 and max(values) >= (2.0 if earthquake else 15.0)
    light_hit = value >= (2.0 if earthquake else 15.0)
    sigma_hit = value >= (4.0 if earthquake else 30.0)
    return {
        'scope': 'shadow_only',
        'eligible': True,
        'metric': {'name': metric_name, 'value': value, 'observed_at': now.isoformat()},
        'engines': {
            'OpenCEP': {'triggered': open_hit, 'reason': 'three_point_ascending' if open_hit else 'sequence_not_complete'},
            'LightCEP': {'triggered': light_hit, 'reason': 'threshold_met' if light_hit else 'threshold_not_met'},
            'Siddhi': {'triggered': siddhi_hit, 'reason': 'window_aggregate_met' if siddhi_hit else 'window_not_complete'},
            'Sigma': {'triggered': sigma_hit, 'reason': 'high_risk_signature_met' if sigma_hit else 'high_risk_signature_not_met'},
        },
    }
