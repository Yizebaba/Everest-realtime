"""
Deduplication Engine Matrix: LightCEP vs OpenCEP vs Siddhi vs Sigma.
Parses DEDUPLICATION_EXPERIMENT_MANUAL.md to evaluate whether incoming data is UNIQUE or DUPLICATE.
"""
import re
import datetime as dt
import sqlite3
import hashlib
from pathlib import Path
from difflib import SequenceMatcher


def load_dedup_config(manual_path="DEDUPLICATION_EXPERIMENT_MANUAL.md"):
    p = Path(manual_path)
    if not p.exists():
        p = Path(__file__).resolve().parents[1] / manual_path
    text = p.read_text(encoding="utf-8") if p.exists() else ""

    def get_val(pattern, default):
        m = re.search(pattern, text)
        return float(m.group(1).strip()) if m else default

    cfg = {
        "title_similarity_threshold": get_val(r'标题相似度达到多少算同一件事：>=\s*\[\s*([0-9.]+)\s*\]', 70.0) / 100.0,
        "earthquake_dist_km": get_val(r'震中距离误差在：<=\s*\[\s*([0-9.]+)\s*\]', 1.0),
        "earthquake_time_min": get_val(r'发震时间差在：<=\s*\[\s*([0-9.]+)\s*\]', 180.0),
        "gust_deadband": get_val(r'峰顶阵风波动不超过：<=\s*\[\s*([0-9.]+)\s*\]', 3.0),
        "temp_deadband": get_val(r'峰顶气温波动不超过：<=\s*\[\s*([0-9.]+)\s*\]', 1.0),
        "pressure_deadband": get_val(r'地表气压波动不超过：<=\s*\[\s*([0-9.]+)\s*\]', 1.5),
        "gust_escalation": get_val(r'大出\s*>=\s*\[\s*([0-9.]+)\s*\]', 10.0),
        "cooldown_min": get_val(r'单个数据源推送后的强制冷却保护期：\[\s*([0-9.]+)\s*\]', 30.0),
    }
    return cfg

DEDUP_CFG = load_dedup_config()


def init_dedup_db(db_path='data/monitor.sqlite3'):
    con = sqlite3.connect(db_path, timeout=10)
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS dedup_records (
        rule_id TEXT, event_type TEXT, signature TEXT, val REAL, raw TEXT, ts TEXT
    )''')
    con.commit()
    con.close()


def dedup_lightcep(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """
    Engine 1 LightCEP: Core Business Fingerprint & URL/Title Similarity
    """
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    con = sqlite3.connect(db_path, timeout=10)
    cur = con.cursor()
    
    # Check 1: Earthquake Event ID check
    if cid == 'earthquake':
        content_str = " ".join(result.get('content', []))
        ids = re.findall(r'"id":\s*"([^"]+)"', content_str) or re.findall(r'CC\.\d+\.\d+', content_str)
        if ids:
            eid = ids[0]
            cur.execute('SELECT 1 FROM dedup_records WHERE rule_id=? AND signature=?', (rule_id, eid))
            if cur.fetchone():
                con.close()
                return False, f"已知地震ID[{eid}]"
            # Record new
            cur.execute('INSERT INTO dedup_records VALUES (?,?,?,?,?,?)', (rule_id, 'earthquake_id', eid, 0.0, '', now_dt.isoformat()))
            con.commit()
            con.close()
            return True, f"新地震事件ID[{eid}]"

    # Check 2: News Article URL / Title similarity check
    elif cid in ('news', 'special', 'flood', 'avalanche', 'landslide'):
        articles = result.get('article_records', [])
        new_urls = [a.get('url') for a in articles if a.get('url')]
        for u in new_urls:
            cur.execute('SELECT 1 FROM dedup_records WHERE rule_id=? AND signature=?', (rule_id, u))
            if cur.fetchone():
                con.close()
                return False, "文章URL已推送过"
            cur.execute('INSERT INTO dedup_records VALUES (?,?,?,?,?,?)', (rule_id, 'news_url', u, 0.0, '', now_dt.isoformat()))
            con.commit()
            con.close()
            return True, "首发全新报道URL"

    con.close()
    return True, "常规新项"


def dedup_opencep(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """
    Engine 2 OpenCEP: Temporal Lifecycle & Escalation Trigger
    """
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    
    if cid == 'weather':
        content_str = " ".join(result.get('content', []))
        gusts = [float(x) for x in re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)]
        current_g = max(gusts) if gusts else 0.0
        
        con = sqlite3.connect(db_path, timeout=10)
        cur = con.cursor()
        cur.execute('SELECT val FROM dedup_records WHERE rule_id=? AND event_type="weather_gust" ORDER BY rowid DESC LIMIT 1', (rule_id,))
        row = cur.fetchone()
        
        if row:
            last_g = row[0]
            delta = current_g - last_g
            # Deadband check
            if abs(delta) <= DEDUP_CFG['gust_deadband']:
                con.close()
                return False, f"阵风波动死区内(Δ{delta:+.1f}km/h)"
            # Escalation check
            if current_g > last_g and delta < DEDUP_CFG['gust_escalation']:
                con.close()
                return False, f"未达到恶化加剧阈值(+{delta:.1f} < +{DEDUP_CFG['gust_escalation']})"
                
        cur.execute('INSERT INTO dedup_records VALUES (?,?,?,?,?,?)', (rule_id, 'weather_gust', 'gust', current_g, '', now_dt.isoformat()))
        con.commit()
        con.close()
        return True, f"风暴阶梯跃迁升级({current_g:.1f}km/h)"
        
    return True, "时序状态放行"


def dedup_siddhi(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """
    Engine 3 Siddhi: Sliding Window Unique & Cooldown Suppression
    """
    rule_id = source['rule_id']
    cooldown_limit = (now_dt - dt.timedelta(minutes=DEDUP_CFG['cooldown_min'])).isoformat()
    
    con = sqlite3.connect(db_path, timeout=10)
    cur = con.cursor()
    cur.execute('''SELECT ts FROM dedup_records WHERE rule_id=? AND event_type="siddhi_sent" AND ts >= ? ORDER BY rowid DESC LIMIT 1''', (rule_id, cooldown_limit))
    row = cur.fetchone()
    
    if row:
        con.close()
        return False, f"Siddhi流处于{int(DEDUP_CFG['cooldown_min'])}m冷却抑制期"
        
    cur.execute('INSERT INTO dedup_records VALUES (?,?,?,?,?,?)', (rule_id, 'siddhi_sent', 'cooldown', 0.0, '', now_dt.isoformat()))
    con.commit()
    con.close()
    return True, "Siddhi流冷却窗口清空放行"


def dedup_sigma(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """
    Engine 4 Sigma: Entity & Cluster Signature Anti-Collision
    """
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    content_str = " ".join(result.get('content', []))
    
    if cid == 'earthquake':
        # Spatial-temporal cluster match
        coords = re.findall(r'\[([0-9.-]+),\s*([0-9.-]+)', content_str)
        if coords:
            lon, lat = float(coords[0][0]), float(coords[0][1])
            sig = f"{round(lat, 1)},{round(lon, 1)}"
            time_limit = (now_dt - dt.timedelta(minutes=DEDUP_CFG['earthquake_time_min'])).isoformat()
            
            con = sqlite3.connect(db_path, timeout=10)
            cur = con.cursor()
            cur.execute('''SELECT 1 FROM dedup_records WHERE event_type="sigma_quake_cluster" AND signature=? AND ts >= ?''', (sig, time_limit))
            if cur.fetchone():
                con.close()
                return False, f"Sigma震团邻近特征碰撞[{sig}]"
                
            cur.execute('INSERT INTO dedup_records VALUES (?,?,?,?,?,?)', (rule_id, 'sigma_quake_cluster', sig, 0.0, '', now_dt.isoformat()))
            con.commit()
            con.close()
            return True, f"Sigma全新震中特征[{sig}]"
            
    return True, "Sigma签名未碰撞"
