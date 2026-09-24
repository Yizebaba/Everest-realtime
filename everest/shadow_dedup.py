"""Shadow-only implementation of DEDUPLICATION_EXPERIMENT_MANUAL.md.

The results are observational. This module never changes Store.record(), cards,
or delivery, and therefore cannot suppress or create a notification.
"""
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
from difflib import SequenceMatcher


TITLE_SIMILARITY = 0.70
QUAKE_DISTANCE_KM = 1.0
QUAKE_TIME_MINUTES = 180
GUST_DEADBAND = 3.0
TEMP_DEADBAND = 1.0
PRESSURE_DEADBAND = 1.5
GUST_ESCALATION = 10.0
COOLDOWN_MINUTES = 30

NOISE_WORDS = (
    'election', 'agm', 'general meeting', 'committee', 'executive',
    'sponsor', 'partnership', 'brand', 'discount', 'anniversary',
    'golden jubilee', 'in memory', 'taxpayer', 'revenue', 'budget',
    'financial report', '换届', '选举', '代表大会', '理事会', '赞助',
    '商务合作', '周年', '纪念', '纳税', '财报',
)


def _connect(data_dir):
    con = sqlite3.connect(data_dir / 'monitor.sqlite3', timeout=10)
    con.execute('''CREATE TABLE IF NOT EXISTS shadow_dedup_v2_records (
        rule_id TEXT NOT NULL,
        record_type TEXT NOT NULL,
        signature TEXT NOT NULL,
        payload TEXT NOT NULL,
        observed_at TEXT NOT NULL
    )''')
    return con


def _normalized(value):
    return re.sub(r'\W+', ' ', (value or '').lower()).strip()


def _distance_km(lat_a, lon_a, lat_b, lon_b):
    radius = 6371.0
    lat_a, lon_a, lat_b, lon_b = map(math.radians, (lat_a, lon_a, lat_b, lon_b))
    a = math.sin((lat_b - lat_a) / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(a))


def _article_records(result):
    records = []
    for article in result.get('article_records', []):
        url = article.get('url') or ''
        title = article.get('title') or ''
        if url or title:
            records.append({'url': url, 'title': title, 'published_at': article.get('published_at')})
    return records[:5]


def _quake_records(result):
    records = []
    for network in result.get('network_records', []):
        data = network.get('data')
        items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            props = item.get('properties') or item
            geometry = item.get('geometry') or {}
            coords = geometry.get('coordinates') or []
            event_id = item.get('id') or props.get('id') or ''
            magnitude = props.get('magnitude', props.get('mag'))
            event_time = props.get('time', props.get('at', ''))
            lat = props.get('latitude')
            lon = props.get('longitude')
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
            if event_id and magnitude is not None:
                records.append({
                    'id': str(event_id), 'magnitude': float(magnitude), 'time': str(event_time),
                    'lat': float(lat) if lat is not None else None,
                    'lon': float(lon) if lon is not None else None,
                })
    content = ' '.join(result.get('content', []))
    for event_id, stamp, lat, lon, depth, mag in re.findall(
        r'(CC\.\d+\.\d+).*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)', content
    ):
        records.append({'id': event_id, 'magnitude': float(mag), 'time': stamp, 'lat': float(lat), 'lon': float(lon)})
    return records


def _weather_record(result):
    for network in result.get('network_records', []):
        data = network.get('data')
        if isinstance(data, dict):
            current = data.get('current') or data
            gust = current.get('wind_gusts_10m') or current.get('wind_speed_10m')
            if gust is not None:
                return {
                    'time': str(current.get('time', '')),
                    'gust': float(gust),
                    'temperature': current.get('temperature_2m'),
                    'pressure': current.get('surface_pressure'),
                }
    content = ' '.join(result.get('content', []))
    gust = re.search(r'([\d.]+)\s*km/h', content, re.I)
    return {'time': '', 'gust': float(gust.group(1)) if gust else None, 'temperature': None, 'pressure': None}


def _latest(con, rule_id, record_type):
    row = con.execute(
        'SELECT signature, payload, observed_at FROM shadow_dedup_v2_records WHERE rule_id=? AND record_type=? ORDER BY rowid DESC LIMIT 1',
        (rule_id, record_type),
    ).fetchone()
    return (row[0], json.loads(row[1]), dt.datetime.fromisoformat(row[2])) if row else (None, None, None)


def _insert(con, rule_id, record_type, signature, payload, now):
    con.execute(
        'INSERT INTO shadow_dedup_v2_records VALUES (?,?,?,?,?)',
        (rule_id, record_type, signature, json.dumps(payload, ensure_ascii=False), now.isoformat()),
    )


def _article_shadow(con, source, result, now):
    articles = _article_records(result)
    if not articles:
        return {name: {'duplicate': False, 'reason': 'article_records_unavailable'} for name in ('LightCEP', 'OpenCEP', 'Siddhi', 'Sigma')}
    article = articles[0]
    url = article['url']
    title = article['title']
    title_key = _normalized(title)
    noise = any(word in (title + ' ' + ' '.join(result.get('matches', [])[:10])).lower() for word in NOISE_WORDS)
    seen_url = bool(url and con.execute('SELECT 1 FROM shadow_dedup_v2_records WHERE record_type="article" AND signature=? LIMIT 1', (url,)).fetchone())
    previous = con.execute('SELECT payload FROM shadow_dedup_v2_records WHERE record_type="article" ORDER BY rowid DESC LIMIT 100').fetchall()
    similar = False
    for row in previous:
        prior_title = json.loads(row[0]).get('title', '')
        if title_key and prior_title and SequenceMatcher(None, title_key, _normalized(prior_title)).ratio() >= TITLE_SIMILARITY:
            similar = True
            break
    signature = url or hashlib.sha256(title_key.encode()).hexdigest()
    _insert(con, source['rule_id'], 'article', signature, article, now)
    return {
        'LightCEP': {'duplicate': seen_url, 'reason': 'article_url_already_seen' if seen_url else 'new_article_url'},
        'OpenCEP': {'duplicate': noise, 'reason': 'noise_only_lifecycle' if noise else 'new_article_lifecycle'},
        'Siddhi': {'duplicate': False, 'reason': 'article_window_observation_only'},
        'Sigma': {'duplicate': similar, 'reason': 'title_similarity_ge_70pct' if similar else 'new_article_entity'},
    }


def _quake_shadow(con, source, result, now):
    events = _quake_records(result)
    if not events:
        return {name: {'duplicate': False, 'reason': 'event_id_unavailable'} for name in ('LightCEP', 'OpenCEP', 'Siddhi', 'Sigma')}
    event = events[0]
    seen_id = bool(con.execute('SELECT 1 FROM shadow_dedup_v2_records WHERE record_type="quake" AND signature=? LIMIT 1', (event['id'],)).fetchone())
    last_sig, last, last_time = _latest(con, source['rule_id'], 'quake')
    cooldown = bool(last_time and (now - last_time).total_seconds() < COOLDOWN_MINUTES * 60)
    escalated = bool(last and event['magnitude'] > float(last.get('magnitude', 0)) + 0.5)
    spatial_duplicate = False
    if event['lat'] is not None and event['lon'] is not None:
        rows = con.execute('SELECT payload, observed_at FROM shadow_dedup_v2_records WHERE record_type="quake" ORDER BY rowid DESC LIMIT 200').fetchall()
        for payload, observed_at in rows:
            candidate = json.loads(payload)
            if candidate.get('lat') is None or candidate.get('lon') is None:
                continue
            try:
                age = now - dt.datetime.fromisoformat(observed_at)
                if age.total_seconds() <= QUAKE_TIME_MINUTES * 60 and _distance_km(event['lat'], event['lon'], candidate['lat'], candidate['lon']) <= QUAKE_DISTANCE_KM:
                    spatial_duplicate = True
                    break
            except Exception:
                pass
    _insert(con, source['rule_id'], 'quake', event['id'], event, now)
    return {
        'LightCEP': {'duplicate': seen_id, 'reason': 'known_event_id' if seen_id else 'new_event_id'},
        'OpenCEP': {'duplicate': bool(last and not escalated), 'reason': 'no_magnitude_escalation' if last and not escalated else 'first_or_escalated_event'},
        'Siddhi': {'duplicate': cooldown, 'reason': 'cooldown_active_30m' if cooldown else 'cooldown_expired'},
        'Sigma': {'duplicate': spatial_duplicate, 'reason': 'spatiotemporal_entity_match' if spatial_duplicate else 'new_spatiotemporal_entity'},
    }


def _weather_shadow(con, source, result, now):
    record = _weather_record(result)
    if record['gust'] is None:
        return {name: {'duplicate': False, 'reason': 'weather_metric_unavailable'} for name in ('LightCEP', 'OpenCEP', 'Siddhi', 'Sigma')}
    _, last, last_time = _latest(con, source['rule_id'], 'weather')
    gust_delta = record['gust'] - float(last.get('gust', record['gust'])) if last else None
    temp_delta = None if not last or record['temperature'] is None or last.get('temperature') is None else float(record['temperature']) - float(last['temperature'])
    pressure_delta = None if not last or record['pressure'] is None or last.get('pressure') is None else float(record['pressure']) - float(last['pressure'])
    deadband = bool(last and abs(gust_delta) <= GUST_DEADBAND and (temp_delta is None or abs(temp_delta) <= TEMP_DEADBAND) and (pressure_delta is None or abs(pressure_delta) <= PRESSURE_DEADBAND))
    escalated = bool(last and gust_delta >= GUST_ESCALATION)
    cooldown = bool(last_time and (now - last_time).total_seconds() < COOLDOWN_MINUTES * 60)
    signature = record['time'] or f"gust:{record['gust']}"
    _insert(con, source['rule_id'], 'weather', signature, record, now)
    return {
        'LightCEP': {'duplicate': deadband, 'reason': 'weather_deadband' if deadband else 'new_weather_state'},
        'OpenCEP': {'duplicate': bool(last and not escalated), 'reason': 'no_gust_escalation_10kmh' if last and not escalated else 'gust_escalated_or_first_record'},
        'Siddhi': {'duplicate': cooldown, 'reason': 'cooldown_active_30m' if cooldown else 'cooldown_expired'},
        'Sigma': {'duplicate': deadband, 'reason': 'known_weather_entity' if deadband else 'new_weather_entity'},
    }


def evaluate(source, result, data_dir):
    """Evaluate all documented dedup opinions without affecting main behavior."""
    now = dt.datetime.now(dt.timezone.utc)
    try:
        con = _connect(data_dir)
        cid = source.get('category_id', '')
        if cid == 'earthquake':
            engines = _quake_shadow(con, source, result, now)
        elif cid == 'weather':
            engines = _weather_shadow(con, source, result, now)
        elif cid in ('news', 'special', 'flood', 'landslide', 'avalanche', 'platform'):
            engines = _article_shadow(con, source, result, now)
        else:
            engines = {name: {'duplicate': False, 'reason': 'not_in_documented_dedup_scope'} for name in ('LightCEP', 'OpenCEP', 'Siddhi', 'Sigma')}
        con.commit()
        con.close()
    except Exception as exc:
        engines = {name: {'duplicate': False, 'reason': 'shadow_error:' + type(exc).__name__} for name in ('LightCEP', 'OpenCEP', 'Siddhi', 'Sigma')}
    return {'scope': 'shadow_only', 'mode': 'A_independent_observation', 'observed_at': now.isoformat(), 'engines': engines}
