"""
Sigma Rule Engine for Disaster and Environment Threat Detection.
Converts YAML-like Sigma signature rules into structured detection logic:
  - selection: positive matches (keywords, regex, field conditions)
  - filter: negation exclusions (false positives)
  - condition: selection and not filter
"""
import re

# Sigma-standard signature catalog for natural disaster and high-altitude emergencies
SIGMA_RULES = [
    {
        "id": "SIGMA-GEO-001",
        "title": "喜马拉雅/全球破坏性大地震特征检测",
        "category": "earthquake",
        "level": "critical",
        "detection": {
            "selection_mag": {"mag": 4.5},
            "selection_places": ["nepal", "xizang", "tibet", "himalaya", "sikkim", "everest", "china", "indonesia", "japan"],
            "condition": "selection_mag and selection_places"
        }
    },
    {
        "id": "SIGMA-MET-002",
        "title": "珠峰高空极限暴风与冷害特征检测",
        "category": "weather",
        "level": "high",
        "detection": {
            "selection_wind": {"gust": 40.0},
            "condition": "selection_wind"
        }
    },
    {
        "id": "SIGMA-NEWS-003",
        "title": "高山现场突发致命险情/搜救通报检测",
        "category": "news",
        "level": "critical",
        "detection": {
            "selection_disaster": ["avalanche", "rescue", "trapped", "casualty", "dead", "died", "death", "missing", "icefall", "landslide", "雪崩", "遇难", "搜救", "失联", "滑坡", "塌方", "伤亡"],
            "selection_locations": ["everest", "himalaya", "manaslu", "khumbu", "nepal", "tibet", "珠峰", "喜马拉雅", "西藏", "尼泊尔"],
            "filter_noise": ["election", "agm", "obituary", "taxpayer", "anniversary", "sponsor", "选举", "换届", "周年", "赞助", "大会"],
            "condition": "selection_disaster and selection_locations and not filter_noise"
        }
    }
]


def evaluate_sigma(source, result, now_dt):
    """
    Evaluate incoming source event against Sigma signature rules.
    """
    cid = source.get('category_id', '')
    content_str = " ".join(result.get('content', []))
    lowered = content_str.lower()
    
    for rule in SIGMA_RULES:
        det = rule['detection']
        
        # Rule 1: Earthquake Sigma Signature
        if rule['category'] == 'earthquake' and cid == 'earthquake':
            # Check mag
            mags = re.findall(r'"mag":\s*([0-9]+(?:\.[0-9]+)?)', content_str)
            if not mags:
                mags = re.findall(r'M\s*([0-9]+(?:\.[0-9]+)?)', content_str)
            
            mag_hit = False
            for m in mags:
                try:
                    if float(m) >= det['selection_mag']['mag']:
                        mag_hit = True
                        break
                except Exception:
                    pass
            
            place_hit = any(p in lowered for p in det['selection_places'])
            if mag_hit and place_hit:
                return True, f"命中Sigma特征[{rule['id']} - {rule['title']}]"
                
        # Rule 2: High altitude weather storm signature
        elif rule['category'] == 'weather' and cid == 'weather':
            gusts = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*km/h', content_str)
            for g in gusts:
                try:
                    if float(g) >= det['selection_wind']['gust']:
                        return True, f"命中Sigma特征[{rule['id']} - 阵风{g}km/h达到高危阈值]"
                except Exception:
                    pass

        # Rule 3: Emergency news / rescue signature
        elif rule['category'] == 'news' and cid in ('news', 'special', 'flood', 'avalanche', 'landslide'):
            disaster_hit = any(w in lowered for w in det['selection_disaster'])
            loc_hit = any(w in lowered for w in det['selection_locations'])
            noise_hit = any(w in lowered for w in det['filter_noise'])
            
            if disaster_hit and loc_hit and not noise_hit:
                matched = [w for w in det['selection_disaster'] if w in lowered]
                return True, f"命中Sigma特征[{rule['id']} - 捕获突发高危词: {', '.join(matched[:2])}]"

    return False, ""
