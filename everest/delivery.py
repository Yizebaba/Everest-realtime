import hashlib
import json
import re
import time
from pathlib import Path

import requests

from .core import fingerprint, read_json


def destination(config):
    key = (config.get('serverchan') or {}).get('sendkey')
    return fingerprint({'serverchan': key}) if key else ''


def upload(path, settings):
    with Path(path).open('rb') as f:
        response = requests.post(settings['image_upload_url'], files={'files[]': (Path(path).name, f, 'image/png')}, timeout=45)
    response.raise_for_status()
    data = response.json()
    if not data.get('success') or not data.get('files'):
        raise ValueError('Image upload rejected')
    url = data['files'][0]['url']
    if not url.startswith('https://'):
        raise ValueError('Image URL must be HTTPS')
    return url


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
        text = f"来源：{source['url']}\n\n获取时间 UTC：{record['retrieved_at']}\n\n结果：{record['result']} · {record['change']}\n\n"
        text += '\n\n'.join(f'![数据卡 {i+1}]({url})' for i,url in enumerate(urls))
        text += f"\n\n逐条内容见图片，本地运行：{run_id}\n\n—— vx:No1-Shine ｜ 珠峰多灾监控系统［测试版］"
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
        sleeper(max(3, float(settings['notification_interval_seconds'])))
    return stats
