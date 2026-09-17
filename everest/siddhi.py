"""
Siddhi-style SQL/CQL Complex Event Processing Simulator for Python.

Emulates WSO2/Siddhi-io streaming queries:
  from WeatherStream#window.time(10 min)
  select min(temperature) as min_t, max(wind_gusts) as max_g, count() as cnt
  group by rule_id
  having max_g >= 38.0 and cnt >= 2
"""
import datetime as dt
import re
import sqlite3
from pathlib import Path


def evaluate_siddhi(source, result, now_dt, db_path='data/monitor.sqlite3'):
    """
    Siddhi Stream Processing Engine Evaluation:
    Uses SQL-like sliding window aggregation over event streams.
    
    Siddhi Query Logic:
      - Window: 10 minutes sliding window
      - Aggregations: MAX(metric), DELTA(metric), COUNT(*)
      - Having Clauses:
          1. Weather: MAX(wind_gusts) >= 38.0 km/h AND COUNT >= 2 in window
          2. Earthquake: MAX(mag) >= 4.0 OR COUNT(mag >= 2.5) >= 2 in window
          3. News/River: COUNT(event) >= 2 in window (Burst detection)
    """
    rule_id = source['rule_id']
    cid = source.get('category_id', '')
    
    # 1. Extract numeric metric for streaming input
    metric_val = 0.0
    content_str = " ".join(result.get('content', [])[:50])
    
    if cid == 'weather':
        m = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)
        if m:
            metric_val = max(float(x) for x in m)
    elif cid == 'earthquake':
        m = re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str)
        if not m:
            m = re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str)
        if m:
            metric_val = max(float(x) for x in m)
    else:
        metric_val = float(len(result.get('matches', [])))

    # 2. Insert into Siddhi Stream Table
    window_limit = (now_dt - dt.timedelta(minutes=10)).isoformat()
    try:
        con = sqlite3.connect(db_path, timeout=10)
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS siddhi_stream (
            rule_id TEXT, cid TEXT, val REAL, ts TEXT
        )''')
        cur.execute('''INSERT INTO siddhi_stream VALUES (?,?,?,?)''', (rule_id, cid, metric_val, now_dt.isoformat()))
        
        # 3. Execute Siddhi-style Sliding Window Aggregation Queries
        # Query A: Weather Stream Aggregation
        if cid == 'weather':
            cur.execute('''
                SELECT COUNT(*), MAX(val), AVG(val)
                FROM siddhi_stream
                WHERE rule_id = ? AND ts >= ?
            ''', (rule_id, window_limit))
            cnt, max_val, avg_val = cur.fetchone()
            con.commit()
            con.close()
            if cnt and cnt >= 2 and max_val >= 38.0:
                return True, f"Siddhi流聚合达成 [10分钟内采样{cnt}次, 峰值阵风{max_val:.1f}km/h, 均值{avg_val:.1f}km/h]"
            return False, ""

        # Query B: Earthquake Stream Aggregation (Cluster / Magnitude threshold)
        elif cid == 'earthquake':
            cur.execute('''
                SELECT COUNT(*), MAX(val)
                FROM siddhi_stream
                WHERE rule_id = ? AND ts >= ?
            ''', (rule_id, window_limit))
            cnt, max_val = cur.fetchone()
            con.commit()
            con.close()
            if max_val and max_val >= 4.0:
                return True, f"Siddhi流断言命中 [单次或聚合强震 M{max_val:.1f} >= 4.0]"
            elif cnt and cnt >= 2 and max_val >= 2.5:
                return True, f"Siddhi地震群流聚合 [10分钟内频发{cnt}次, 峰值M{max_val:.1f}]"
            return False, ""

        # Query C: News / Disaster Burst Stream
        else:
            cur.execute('''
                SELECT COUNT(*), SUM(val)
                FROM siddhi_stream
                WHERE rule_id = ? AND ts >= ?
            ''', (rule_id, window_limit))
            cnt, total_matches = cur.fetchone()
            con.commit()
            con.close()
            if total_matches and total_matches >= 3:
                return True, f"Siddhi突发事件流聚合 [10分钟窗口累积爆发 {int(total_matches)} 条有效通报]"
            return False, ""

    except Exception as e:
        return False, ""
