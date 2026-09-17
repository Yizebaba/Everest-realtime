"""
Full Matrix Parser & Engine Evaluator for 49 Control Rules.
Parses CEP_EXPERIMENT_MANUAL.md dynamically.
"""
import re
import datetime as dt
import sqlite3
from pathlib import Path
from collections import deque


def load_matrix_config(manual_path="CEP_EXPERIMENT_MANUAL.md"):
    p = Path(manual_path)
    if not p.exists():
        p = Path(__file__).resolve().parents[1] / manual_path
    if not p.exists():
        text = ""
    else:
        text = p.read_text(encoding="utf-8")
    
    # Helper to extract [ val ]
    def get_val(pattern, default):
        m = re.search(pattern, text)
        return float(m.group(1).strip()) if m else default

    cfg = {
        # Seismic
        "mag_micro": get_val(r'01\..*?M\s*>=\s*\[\s*([0-9.]+)\s*\]', 2.0),
        "mag_moderate": get_val(r'02\..*?M\s*>=\s*\[\s*([0-9.]+)\s*\]', 2.0),
        "mag_destructive": get_val(r'03\..*?M\s*>=\s*\[\s*([0-9.]+)\s*\]', 2.0),
        "mag_global": get_val(r'04\..*?M\s*>=\s*\[\s*([0-9.]+)\s*\]', 5.0),
        "depth_ultra_shallow": get_val(r'05\..*?深度\s*<=\s*\[\s*([0-9.]+)\s*\]', 0.5),
        "depth_shallow": get_val(r'06\..*?深度\s*<=\s*\[\s*([0-9.]+)\s*\]', 1.0),
        "seq_seismic_window": get_val(r'11\..*?\[\s*([0-9.]+)\s*\]\s*分钟', 30.0),
        "seq_seismic_count": int(get_val(r'11\..*?连续发生\s*\[\s*([0-9]+)\s*\]\s*次', 3)),
        
        # Weather
        "gust_storm": get_val(r'17\..*?最大阵风\s*>=\s*\[\s*([0-9.]+)\s*\]', 20.0),
        "gust_alert": get_val(r'18\..*?最大阵风\s*>=\s*\[\s*([0-9.]+)\s*\]', 15.0),
        "sustained_wind": get_val(r'19\..*?持续\s*10\s*米风速\s*>=\s*\[\s*([0-9.]+)\s*\]', 10.0),
        "wind_deg_shear": get_val(r'20\..*?偏转角度\s*>=\s*\[\s*([0-9.]+)\s*\]', 65.0),
        "temp_extreme_cold": get_val(r'21\..*?实测气温\s*<=\s*\[\s*([0-9.-]+)\s*\]', -30.0),
        "temp_chill_factor": get_val(r'23\..*?体感温度\s*<=\s*\[\s*([0-9.-]+)\s*\]', -20.0),
        "pressure_drop_rate": get_val(r'24\..*?地表气压下降\s*>=\s*\[\s*([0-9.]+)\s*\]', 3.0),
        "precipitation_snow": get_val(r'26\..*?降水量\s*>=\s*\[\s*([0-9.]+)\s*\]', 5.0),
        "humidity_fog": get_val(r'27\..*?相对湿度\s*>=\s*\[\s*([0-9.]+)\s*\]', 70.0),
        "seq_weather_window": get_val(r'29\..*?在\s*\[\s*([0-9.]+)\s*\]\s*分钟', 5.0),
        "seq_weather_count": int(get_val(r'29\..*?连续\s*\[\s*([0-9]+)\s*\]\s*次', 3)),
        
        # Glacier & Water
        "glof_surge_pct": get_val(r'31\..*?上涨幅度\s*>=\s*\[\s*([0-9.]+)\s*\]', 15.0),
        "rain_landslide_mm": get_val(r'36\..*?累计降水\s*>=\s*\[\s*([0-9.]+)\s*\]', 1.0),
        
        # Voting Mode
        "voting_mode": "A" if "[a " in text.lower() or "[a]" in text.lower() else "A"
    }
    return cfg

# Global cache
MATRIX_CFG = load_matrix_config()
_EVENT_STREAMS = {}


def _save_event(rule_id, val, now_dt, db_path='data/monitor.sqlite3'):
    try:
        con = sqlite3.connect(db_path, timeout=10)
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS cep_events (rule_id TEXT, val REAL, ts TEXT)''')
        cur.execute('''INSERT INTO cep_events VALUES (?,?,?)''', (rule_id, val, now_dt.isoformat()))
        con.commit()
        con.close()
    except Exception:
        pass


def _load_stream(rule_id, db_path='data/monitor.sqlite3'):
    events = []
    try:
        con = sqlite3.connect(db_path, timeout=10)
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS cep_events (rule_id TEXT, val REAL, ts TEXT)''')
        cur.execute('''SELECT val, ts FROM cep_events WHERE rule_id=? ORDER BY rowid DESC LIMIT 15''', (rule_id,))
        rows = cur.fetchall()
        con.close()
        for v, t in reversed(rows):
            events.append((dt.datetime.fromisoformat(t), v))
    except Exception:
        pass
    return deque(events)


def evaluate_opencep(source, result, now_dt):
    """Engine 1: OpenCEP - Strict Sequential Pattern (SEQ) & Ascend Windows"""
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    
    window_min = MATRIX_CFG['seq_weather_window'] if cid == 'weather' else MATRIX_CFG['seq_seismic_window']
    window = dt.timedelta(minutes=window_min)
    req_count = MATRIX_CFG['seq_weather_count'] if cid == 'weather' else MATRIX_CFG['seq_seismic_count']
    
    metric_val = 0.0
    content_str = " ".join(result.get('content', []))
    
    if cid == 'weather':
        m = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)
        if m: metric_val = max(float(x) for x in m)
    elif cid == 'earthquake':
        m = re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str) or re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str)
        if m: metric_val = max(float(x) for x in m)
    else:
        metric_val = float(len(result.get('matches', [])))

    stream = _load_stream(rule_id)
    stream.append((now_dt, metric_val))
    _save_event(rule_id, metric_val, now_dt)
    
    while stream and (now_dt - stream[0][0]) > window:
        stream.popleft()
        
    if len(stream) >= req_count:
        recent = list(stream)[-req_count:]
        vals = [v for _, v in recent]
        is_asc = all(vals[i] <= vals[i+1] for i in range(len(vals)-1))
        has_var = any(vals[i] != vals[0] for i in range(len(vals)))
        if is_asc and (has_var or vals[0] > 0):
            return True, f"时序演进达成 [连续{req_count}次走高: {'->'.join(str(v) for v in vals)} ({int(window_min)}m内)]"
    return False, ""


def evaluate_lightcep(source, result, now_dt):
    """Engine 2: LightCEP - Multi-Dimensional Boolean Matrix & Assertions"""
    cid = source.get('category_id', '')
    content_str = " ".join(result.get('content', []))
    lowered = content_str.lower()
    
    # 1. Seismic Thresholds
    if cid == 'earthquake':
        mags = [float(x) for x in (re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str) or re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str))]
        for m in mags:
            if m >= MATRIX_CFG['mag_micro']:
                return True, f"测得震级 M{m} >= 门槛 {MATRIX_CFG['mag_micro']}"
                
    # 2. Weather Thresholds
    elif cid == 'weather':
        gusts = [float(x) for x in re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)]
        for g in gusts:
            if g >= MATRIX_CFG['gust_alert']:
                return True, f"高空阵风 {g} km/h >= 门槛 {MATRIX_CFG['gust_alert']} km/h"
        temps = [float(x) for x in re.findall(r'([0-9.-]+)\s*°C', content_str)]
        for t in temps:
            if t <= MATRIX_CFG['temp_extreme_cold'] or t <= MATRIX_CFG['temp_chill_factor']:
                return True, f"测得极限低温 {t} ℃ <= 警戒线"

    # 3. News & Life Safety
    elif cid in ('news', 'special', 'flood', 'avalanche', 'landslide'):
        danger_words = ["dead", "dies", "died", "killed", "rescue", "trapped", "missing", "avalanche", "flood", "landslide", "遇难", "搜救", "失联", "雪崩", "滑坡", "塌方"]
        noise_words = ["election", "agm", "anniversary", "sponsor", "taxpayer", "选举", "换届", "周年", "赞助", "大会"]
        has_danger = any(w in lowered for w in danger_words)
        is_noise = any(w in lowered for w in noise_words)
        if has_danger and not is_noise:
            hits = [w for w in danger_words if w in lowered]
            return True, f"现场生命险情断言命中: {', '.join(hits[:2])}"

    if len(result.get('matches', [])) > 0:
        return True, f"规则矩阵有效数据命中 ({len(result['matches'])}条)"
    return False, ""


def evaluate_siddhi(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """Engine 3: Siddhi - Stream Aggregation & Statistical Bursts"""
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    metric_val = 0.0
    content_str = " ".join(result.get('content', []))
    
    if cid == 'weather':
        m = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)
        if m: metric_val = max(float(x) for x in m)
    elif cid == 'earthquake':
        m = re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str) or re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str)
        if m: metric_val = max(float(x) for x in m)
    else:
        metric_val = float(len(result.get('matches', [])))

    win_limit = (now_dt - dt.timedelta(minutes=15)).isoformat()
    try:
        con = sqlite3.connect(db_path, timeout=10)
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS siddhi_stream (rule_id TEXT, cid TEXT, val REAL, ts TEXT)''')
        cur.execute('''INSERT INTO siddhi_stream VALUES (?,?,?,?)''', (rule_id, cid, metric_val, now_dt.isoformat()))
        
        cur.execute('''SELECT COUNT(*), MAX(val), AVG(val) FROM siddhi_stream WHERE rule_id=? AND ts>=?''', (rule_id, win_limit))
        cnt, max_v, avg_v = cur.fetchone()
        con.commit()
        con.close()
        
        if cid == 'weather' and max_v and max_v >= MATRIX_CFG['gust_alert']:
            return True, f"Siddhi风暴流聚合 [15m内采样{cnt}次, 峰值{max_v:.1f}km/h]"
        if cid == 'earthquake' and max_v and max_v >= MATRIX_CFG['mag_moderate']:
            return True, f"Siddhi强震流聚合 [15m内频发{cnt}次, 峰值M{max_v:.1f}]"
        if cnt and cnt >= 2:
            return True, f"Siddhi多频突发流聚合 [15m内连续活跃{cnt}次]"
    except Exception:
        pass
    return False, ""


def evaluate_sigma(source, result, now_dt):
    """Engine 4: Sigma - Structured Threat & Disaster Signature Catalog"""
    cid = source.get('category_id', '')
    content_str = " ".join(result.get('content', []))
    lowered = content_str.lower()
    
    if cid == 'earthquake':
        mags = [float(x) for x in (re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str) or re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str))]
        for m in mags:
            if m >= MATRIX_CFG['mag_destructive']:
                return True, f"命中Sigma特征[SIGMA-GEO-001 强震特征检测 M{m}>={MATRIX_CFG['mag_destructive']}]"
                
    elif cid == 'weather':
        gusts = [float(x) for x in re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)]
        for g in gusts:
            if g >= MATRIX_CFG['gust_storm']:
                return True, f"命中Sigma特征[SIGMA-MET-002 峰顶风暴威胁签名 {g}km/h]"
                
    elif cid in ('news', 'special', 'flood', 'avalanche', 'landslide'):
        emergency = ["dead", "dies", "died", "killed", "rescue", "trapped", "missing", "avalanche", "flood", "landslide", "遇难", "搜救", "失联", "雪崩", "滑坡", "塌方"]
        places = ["everest", "himalaya", "manaslu", "khumbu", "nepal", "tibet", "珠峰", "喜马拉雅", "西藏", "尼泊尔"]
        if any(e in lowered for e in emergency) and any(p in lowered for p in places):
            hits = [e for e in emergency if e in lowered]
            return True, f"命中Sigma高山致命险情特征[SIGMA-NEWS-003: {', '.join(hits[:2])}]"
            
    return False, ""
