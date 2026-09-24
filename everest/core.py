import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def catalog(path):
    value = read_json(path)
    ids = set()
    for source in value['sources']:
        key = source['rule_id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key) or key in ids:
            raise ValueError('Invalid or duplicate rule_id: ' + key)
        ids.add(key)
        if not source['url'].startswith(('https://', 'http://')):
            raise ValueError('Invalid source URL')
        if float(source['interval_minutes']) <= 0:
            raise ValueError('interval_minutes must be positive')
    return value


@contextlib.contextmanager
def run_lock(directory):
    """OS-held lock; a killed process releases it without deleting another owner's lock."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'monitor.lock').open('a+b') as f:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b'0'); f.flush()
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=15000')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS baseline (
                rule_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                content TEXT NOT NULL, checked_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checks (
                rule_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notices (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                result_path TEXT NOT NULL, destination TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', error TEXT,
                receipt TEXT, sent_at TEXT);
            CREATE TABLE IF NOT EXISTS event_keys (
                category_id TEXT NOT NULL, event_key TEXT NOT NULL,
                first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                PRIMARY KEY (category_id, event_key));
            CREATE TABLE IF NOT EXISTS paired_weather (
                rule_id TEXT PRIMARY KEY, active INTEGER NOT NULL,
                temperature_c REAL, checked_at TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def due(self, source, stamp):
        row = self.db.execute('SELECT checked_at FROM checks WHERE rule_id=?', (source['rule_id'],)).fetchone()
        if row is None:
            return True
        interval = source.get('interval_seconds')
        seconds = float(interval) if interval else float(source['interval_minutes']) * 60
        return (dt.datetime.fromisoformat(stamp) - dt.datetime.fromisoformat(row[0])).total_seconds() >= seconds

    def record(self, result, path, policy, destination):
        key = result['source']['rule_id']
        old = self.db.execute('SELECT * FROM baseline WHERE rule_id=?', (key,)).fetchone()
        valid = (result['result'] != 'unknown' and result.get('relevance') != 'out_of_scope'
                 and result.get('event_status') != 'product_update')
        content = result.get('matches', [])
        digest = fingerprint(content)
        changed = valid and old is not None and old['fingerprint'] != digest
        prior = json.loads(old['content']) if old else []
        result['change'] = ('unknown' if result['result'] == 'unknown' else
                            'out_of_scope' if not valid else
                            'baseline' if old is None else ('changed' if changed else 'unchanged'))
        result['added'] = [x for x in content if x not in prior] if changed else []
        result['removed'] = [x for x in prior if x not in content] if changed else []
        category = result['source'].get('category_id', '')
        event_keys = [fingerprint({'category': category, 'content': item}) for item in result['added']]
        seen = set()
        if event_keys:
            placeholders = ','.join('?' for _ in event_keys)
            seen = {row['event_key'] for row in self.db.execute(
                f'SELECT event_key FROM event_keys WHERE category_id=? AND event_key IN ({placeholders})',
                (category, *event_keys))}
        result['duplicate_event_keys'] = len(seen)
        new_event = bool(set(event_keys) - seen)
        selected = valid and bool(result.get('cards')) and (policy == 'all' or (policy == 'changed' and changed and new_event))
        result['selected_for_notification'] = selected
        write_json(path, result)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO checks VALUES (?,?)', (key, result['retrieved_at']))
            if valid:
                self.db.execute('INSERT OR REPLACE INTO baseline VALUES (?,?,?,?)', (key, digest, json.dumps(content, ensure_ascii=False), result['retrieved_at']))
                for event_key in event_keys:
                    self.db.execute('INSERT INTO event_keys VALUES (?,?,?,?) ON CONFLICT(category_id,event_key) DO UPDATE SET last_seen_at=excluded.last_seen_at',
                        (category, event_key, result['retrieved_at'], result['retrieved_at']))
            if selected:
                self.db.execute('INSERT OR IGNORE INTO notices (id,run_id,rule_id,result_path,destination) VALUES (?,?,?,?,?)',
                    (result['run_id'] + ':' + key, result['run_id'], key, str(path), destination))
        return selected

    def changed(self, source, result):
        """True when this result differs from the stored baseline. Never records."""
        if result.get('result') == 'unknown' or result.get('relevance') == 'out_of_scope':
            return False
        row = self.db.execute('SELECT fingerprint FROM baseline WHERE rule_id=?', (source['rule_id'],)).fetchone()
        if row is None:
            return False
        return row['fingerprint'] != fingerprint(result.get('matches', []))

    def paired_weather_trigger(self, rule_id, active, temperature_c, drop_c):
        """Trigger a paired capture when risk starts or temperature drops sharply."""
        row = self.db.execute('SELECT active,temperature_c FROM paired_weather WHERE rule_id=?', (rule_id,)).fetchone()
        prior_temperature = row['temperature_c'] if row else None
        temperature_drop = (temperature_c is not None and prior_temperature is not None
                            and temperature_c <= prior_temperature - drop_c)
        trigger = bool((active and (row is None or not row['active'])) or temperature_drop)
        with self.db:
            self.db.execute('INSERT INTO paired_weather VALUES (?,?,?,?) ON CONFLICT(rule_id) DO UPDATE SET active=excluded.active,temperature_c=excluded.temperature_c,checked_at=excluded.checked_at',
                (rule_id, int(active), temperature_c, now()))
        return trigger

    def notices(self, run_id):
        return self.db.execute("SELECT * FROM notices WHERE run_id=? AND state IN ('pending','blocked') ORDER BY rule_id", (run_id,)).fetchall()

    def update_notice(self, key, state, error='', receipt=None):
        with self.db:
            self.db.execute('UPDATE notices SET state=?,error=?,receipt=?,sent_at=? WHERE id=?',
                (state, error, json.dumps(receipt) if receipt else None, now() if state == 'accepted' else None, key))
