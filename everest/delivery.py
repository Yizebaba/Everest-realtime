import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import requests

from .core import fingerprint, read_json

SIGNATURE = 'vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'

LAYER_NAMES = {
    'wind': '风力图层',
    'rain': '降水/对流图层',
    'temp': '气温图层',
    'clouds': '云量图层',
    'default': '全要素底图',
    'true_color': '真彩色遥感底图',
    'true_color_modis': 'MODIS Terra 真彩色遥感底图',
    'snow_cover_ndsi': 'MODIS 积雪覆盖与冰川反射 (NDSI)',
    'surface_temp_day': '白天地表与冰面温度 (LST Day)',
    'surface_temp_night': '夜间地表与冰面温度 (LST Night)',
    'viirs_hires_truecolor': 'Suomi NPP / VIIRS 高清真彩',
    'fires_thermal_375m': 'NOAA-20 VIIRS 375米热异常/火点',
    'active_fires_24h': '珠峰24小时热异常检测',
    'geocolor': '全盘真彩云图',
    'webcams': '实时网络摄像头',
    'flood_forecast': '洪水预报/预警地图',
    'global_overview': '全球河流洪涝概览',
    'disaster_spot': '洪水灾害点放大直达',
    'hazards': '国家综合灾害地图'
}


def destination(config):
    key = (config.get('serverchan') or {}).get('sendkey')
    return fingerprint({'serverchan': key}) if key else ''


def _upload_uguu(path, settings):
    with Path(path).open('rb') as f:
        response = requests.post(settings['image_upload_url'],
                                 files={'files[]': (Path(path).name, f, 'image/png')}, timeout=45)
    response.raise_for_status()
    data = response.json()
    if not data.get('success') or not data.get('files'):
        raise ValueError('Image upload rejected')
    return data['files'][0]['url']


def _upload_tmpfiles(path, settings):
    with Path(path).open('rb') as f:
        response = requests.post(settings['image_upload_fallback'],
                                 files={'file': (Path(path).name, f, 'image/png')}, timeout=45)
    response.raise_for_status()
    data = response.json()
    url = (data.get('data') or {}).get('url', '')
    if not url:
        raise ValueError('Fallback image upload rejected')
    return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')


def upload(path, settings):
    """Try the primary image host, then the fallback. Public HTTPS URL required."""
    hosts = [(_upload_uguu, settings.get('image_upload_url')),
             (_upload_tmpfiles, settings.get('image_upload_fallback'))]
    errors = []
    for func, url in hosts:
        if not url:
            continue
        try:
            result = func(path, settings)
            if not result.startswith('https://'):
                raise ValueError('Image URL must be HTTPS')
            return result
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise ValueError('All image hosts failed: ' + ', '.join(errors))


def send(config, title, text):
    key = config['serverchan']['sendkey']
    match = re.match(r'sctp(\d+)t', key)
    url = f'https://{match[1]}.push.ft07.com/send/{key}.send' if match else f'https://sctapi.ftqq.com/{key}.send'
    response = requests.post(url, data={'title': title, 'desp': text}, timeout=30)
    response.raise_for_status()
    return response.json()


def deliver(store, run_id, config, settings, uploader=upload, sender=send, sleeper=time.sleep):
    """Only this run; never flush old projects' queues. No image means no send."""
    binding = destination(config)
    if not binding:
        raise ValueError('Server 酱渠道尚未配置')
    stats = {'accepted': 0, 'blocked': 0, 'unconfirmed': 0}
    for notice in store.notices(run_id):
        key = notice['id']
        if notice['destination'] != binding:
            store.update_notice(key, 'blocked', 'destination_changed')
            stats['blocked'] += 1
            continue
        record = read_json(notice['result_path'])
        try:
            if record.get('image_kind') not in ('original_screenshot','translated_source_screenshot','everest_map_view'):
                raise ValueError('Original screenshot required; redrawn cards are not sent')
            cards = record.get('cards', [])
            hashes = record.get('card_hashes', {})
            if not cards:
                raise ValueError('No cards')
            for p in cards:
                if hashlib.sha256(Path(p).read_bytes()).hexdigest() != hashes.get(p):
                    raise ValueError('Card hash mismatch')
            urls = [uploader(p, settings) for p in cards]
        except Exception as exc:
            store.update_notice(key, 'blocked', 'media_failed:'+type(exc).__name__)
            stats['blocked'] += 1
            continue
        source = record['source']
        source_url = record.get('original_capture', {}).get('final_url') or source['url']
        retrieved_raw = record.get('retrieved_at')
        if retrieved_raw:
            try:
                dt_obj = dt.datetime.fromisoformat(retrieved_raw)
                bj_time = dt_obj.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
                time_line = f"监测时间：{bj_time}\n"
            except Exception:
                time_line = f"监测时间：{retrieved_raw}\n"
        else:
            time_line = ""
        text = f"来源：{source_url}\n{time_line}\n"
        if record.get('image_kind') == 'everest_map_view':
            items = record.get('map_view_items') or []
            if items and len(items) == len(urls):
                names = [it.get('name') or LAYER_NAMES.get(it['layer'], it['layer']) for it in items]
                text += f"珠峰视角图层（共{len(items)}层）：{'、'.join(names)}\n\n"
                for it, url in zip(items, urls):
                    name = it.get('name') or LAYER_NAMES.get(it['layer'], it['layer'])
                    text += f"{name}\n![{name}]({url})\n\n"
            else:
                raw = record.get('map_view_layers') or []
                names = [LAYER_NAMES.get(l, l) for l in raw]
                text += f"珠峰视角图层：{'、'.join(names)}\n\n"
                for i, url in enumerate(urls):
                    name = names[i] if i < len(names) else f"图层 {i+1}"
                    text += f"{name}\n![{name}]({url})\n\n"
        elif record.get('image_kind') == 'translated_source_screenshot':
            label = '中文网页截图（机器翻译）'
            text += '\n\n'.join(f'![{label} {i+1}]({url})' for i,url in enumerate(urls)) + '\n\n'
        else:
            label = '原文截图'
            text += '\n\n'.join(f'![{label} {i+1}]({url})' for i,url in enumerate(urls)) + '\n\n'
        text += SIGNATURE
        store.update_notice(key, 'sending')
        try:
            receipt = sender(config, '珠峰监控 · '+source['name'], text)
        except Exception as exc:
            # The provider may already have accepted a timed-out request. Do not auto-replay it.
            store.update_notice(key, 'unconfirmed', type(exc).__name__)
            stats['unconfirmed'] += 1
            break
        if receipt.get('code') != 0:
            store.update_notice(key, 'blocked', 'provider_rejected', {'code': receipt.get('code')})
            stats['blocked'] += 1
            break
        store.update_notice(key, 'accepted', receipt={'code': 0})
        stats['accepted'] += 1
        print(f"已接收：{source['rule_id']} {source['name']}", flush=True)
        interval = float(settings.get('notification_interval_seconds', 0))
        if interval > 0:
            sleeper(interval)
    return stats
