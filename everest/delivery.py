import base64
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import requests

from .core import fingerprint, read_json
from .page_renderer import build_evidence_page

SIGNATURE = 'WeChat / VX : No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'

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


_WX_TOKEN_CACHE = {'token': None, 'expires_at': 0}


def destination(config):
    dest = {}
    sc_key = (config.get('serverchan') or {}).get('sendkey')
    if sc_key:
        dest['serverchan'] = sc_key
    wechat = config.get('wechat') or {}
    wx_app = wechat.get('app_id')
    wx_tmpl = wechat.get('template_id')
    if wx_app and wx_tmpl:
        touser = wechat.get('touser', [])
        dest['wechat'] = {
            'app_id': wx_app,
            'template_id': wx_tmpl,
            'touser': sorted(touser) if isinstance(touser, list) else touser
        }
    return fingerprint(dest) if dest else ''


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


def _deploy_to_github_pages(file_name, html_content, config):
    gh = config.get('github_pages') or {}
    owner = gh.get('owner', 'Yizebaba')
    repo = gh.get('repo', 'Everest-realtime')
    base_url = gh.get('base_url', f"https://{owner}.github.io/{repo}").rstrip('/')
    token = gh.get('token')
    if not token:
        token_file = Path('/app/github_token.txt')
        if not token_file.exists():
            token_file = Path('D:/Zhufenjianche/github_token.txt')
        if token_file.exists():
            token = token_file.read_text(encoding='utf-8').strip()
    if not token:
        print('GitHub Pages token not configured!', flush=True)
        return None
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Everest-Pages-Publisher'
    }
    rel_path = f"evidence/{file_name}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{rel_path}"
    content_b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get('sha') if get_res.status_code == 200 else None
    payload = {'message': f'publish: {rel_path} for wechat notification', 'content': content_b64}
    if sha:
        payload['sha'] = sha
    res = requests.put(url, headers=headers, json=payload, timeout=20)
    if res.status_code in (200, 201):
        return f"{base_url}/{rel_path}"
    print(f"Deploy to GitHub Pages error: {res.status_code} {res.text[:100]}", flush=True)
    return None


def _upload_github_image(path, config):
    p = Path(path)
    gh = config.get('github_pages') or {}
    owner = gh.get('owner', 'Yizebaba')
    repo = gh.get('repo', 'Everest-realtime')
    base_url = gh.get('base_url', f"https://{owner}.github.io/{repo}").rstrip('/')
    token = gh.get('token')
    if not token:
        token_file = Path('/app/github_token.txt')
        if not token_file.exists():
            token_file = Path('D:/Zhufenjianche/github_token.txt')
        if token_file.exists():
            token = token_file.read_text(encoding='utf-8').strip()
    if not token:
        raise ValueError("GitHub token missing for image upload")

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Everest-Image-Publisher'
    }
    file_bytes = p.read_bytes()
    content_b64 = base64.b64encode(file_bytes).decode('utf-8')
    rel_path = f"evidence/images/{p.name}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{rel_path}"
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get('sha') if get_res.status_code == 200 else None
    payload = {'message': f'upload: evidence image {p.name}', 'content': content_b64}
    if sha:
        payload['sha'] = sha
    put_res = requests.put(url, headers=headers, json=payload, timeout=30)
    if put_res.status_code in (200, 201):
        return f"{base_url}/{rel_path}"
    raise ValueError(f"GitHub image upload failed: {put_res.status_code}")


def upload(path, settings, config=None):
    """Upload via official GitHub Pages repository exclusively."""
    if not settings.get('delivery_enabled', False):
        raise ValueError('External media delivery is disabled; evidence remains local')
    if config and config.get('github_pages'):
        try:
            result = _upload_github_image(path, config)
            if result and result.startswith('https://'):
                return result
        except Exception as exc:
            print(f'GitHub image upload warning: {exc}', flush=True)
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


def _send_serverchan(config, title, text):
    key = config['serverchan']['sendkey']
    match = re.match(r'sctp(\d+)t', key)
    url = f'https://{match[1]}.push.ft07.com/send/{key}.send' if match else f'https://sctapi.ftqq.com/{key}.send'
    response = requests.post(url, data={'title': title, 'desp': text}, timeout=30)
    response.raise_for_status()
    return response.json()


def _get_wechat_token(app_id, app_secret):
    now_ts = time.time()
    if _WX_TOKEN_CACHE['token'] and _WX_TOKEN_CACHE['expires_at'] > now_ts + 60:
        return _WX_TOKEN_CACHE['token']
    url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}'
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if 'access_token' not in data:
        raise ValueError('WeChat access_token failed: ' + str(data))
    _WX_TOKEN_CACHE['token'] = data['access_token']
    _WX_TOKEN_CACHE['expires_at'] = now_ts + int(data.get('expires_in', 7200))
    return _WX_TOKEN_CACHE['token']


def _send_wechat(config, title, text, image_urls=None):
    wechat = config['wechat']
    app_id = wechat['app_id']
    app_secret = wechat['app_secret']
    template_id = wechat['template_id'].strip()
    tousers = wechat.get('touser', [])
    if isinstance(tousers, str):
        tousers = [tousers]
    if not tousers:
        raise ValueError('WeChat touser is empty')
    token = _get_wechat_token(app_id, app_secret)
    url = f'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}'

    m_time = re.search(r'监测时间：([^\n]+)', text)
    time_raw = m_time.group(1) if m_time else ''
    
    # 微信卡片时间：统一换算为北京时间 (UTC+8) 便于手机即时查看
    card_time_bj = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if time_raw:
        try:
            t_iso = time_raw.replace('Z', '+00:00')
            dt_obj = dt.datetime.fromisoformat(t_iso)
            card_time_bj = dt_obj.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            card_time_bj = time_raw.replace('T', ' ')[:19]

    source_name = title.replace('珠峰监控 · ', '').replace('产品名称 · ', '')

    # Map parameters for standard and custom category templates
    # thing16 limit is 20 chars
    prod_name = (source_name if len(source_name) <= 20 else source_name[:19] + '…')
    card_title = f"产品名称 · {source_name}"
    data = {
        'first': {'value': card_title, 'color': '#173177'},
        'keyword1': {'value': source_name, 'color': '#173177'},
        'keyword2': {'value': '监测到自然环境数据/遥感画面更新', 'color': '#e02020'},
        'keyword3': {'value': card_time_bj, 'color': '#888888'},
        'remark': {'value': 'vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］', 'color': '#666666'},
        'title': {'value': card_title},
        'content': {'value': text[:100] + '...' if len(text) > 100 else text},
        'time': {'value': card_time_bj},
        # Category template keywords (e.g. thing16, time6 for 工单审批通知/运维)
        'thing16': {'value': prod_name},
        'time6': {'value': card_time_bj}
    }

    # If multiple images (multi-layer), send one template message for each layer image
    urls_to_send = image_urls if (image_urls and len(image_urls) > 0) else ['']
    last_res = None
    for target_url in urls_to_send:
        for openid in tousers:
            payload = {
                'touser': openid,
                'template_id': template_id,
                'url': target_url,
                'data': data
            }
            res = requests.post(url, json=payload, timeout=20)
            res.raise_for_status()
            ret = res.json()
            if ret.get('errcode') != 0:
                return {'code': ret.get('errcode', -1), 'message': ret.get('errmsg')}
            last_res = ret
            time.sleep(0.5)
    return {'code': 0, 'data': last_res}


def send(config, title, text, image_urls=None):
    results = {}
    errors = {}
    if (config.get('serverchan') or {}).get('sendkey'):
        try:
            results['serverchan'] = _send_serverchan(config, title, text)
        except Exception as e:
            errors['serverchan'] = str(e)
    wechat = config.get('wechat') or {}
    if wechat.get('app_id') and wechat.get('template_id'):
        try:
            results['wechat'] = _send_wechat(config, title, text, image_urls)
        except Exception as e:
            errors['wechat'] = str(e)
    if not results and errors:
        err_msg = '; '.join(f'{k}: {v}' for k, v in errors.items())
        return {'code': -1, 'message': err_msg}
    if not results and not errors:
        raise ValueError('未配置可用的通知渠道')
    has_success = any(r.get('code') == 0 for r in results.values())
    if has_success:
        return {'code': 0, 'results': results, 'channel_errors': errors}
    first_failure = next((r for r in results.values() if r.get('code') != 0), None)
    return first_failure or {'code': -1, 'message': 'All channels failed'}


def deliver(store, run_id, config, settings, uploader=upload, sender=send, sleeper=time.sleep):
    """Only this run; never flush old projects' queues. No image means no send."""
    binding = destination(config)
    if not binding:
        raise ValueError('通知渠道尚未配置')
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
            try:
                urls = [uploader(p, settings, config) for p in cards]
            except TypeError:
                urls = [uploader(p, settings) for p in cards]
        except Exception as exc:
            store.update_notice(key, 'blocked', 'media_failed:'+type(exc).__name__)
            stats['blocked'] += 1
            continue
        source = record['source']
        source_url = record.get('original_capture', {}).get('final_url') or source['url']
        retrieved_raw = record.get('retrieved_at')
        time_line = f"监测时间：{retrieved_raw}\n" if retrieved_raw else ""
        text = f"来源：{source_url}\n{time_line}\n"
        layer_names_list = []
        if record.get('image_kind') == 'everest_map_view':
            items = record.get('map_view_items') or []
            if items and len(items) == len(urls):
                text += f"珠峰视角图层（共{len(items)}层）：\n\n"
                for it, url in zip(items, urls):
                    name = it.get('name') or LAYER_NAMES.get(it['layer'], it['layer'])
                    layer_names_list.append(name)
                    text += f"图层：{name}\n![{name}]({url})\n\n"
            else:
                raw = record.get('map_view_layers') or []
                count = len(urls) if urls else len(raw)
                text += f"珠峰视角图层（共{count}层）：\n\n"
                for i, url in enumerate(urls):
                    name = LAYER_NAMES.get(raw[i], f"图层 {i+1}") if i < len(raw) else f"图层 {i+1}"
                    layer_names_list.append(name)
                    text += f"图层：{name}\n![{name}]({url})\n\n"
        elif record.get('image_kind') == 'translated_source_screenshot':
            label = '中文网页截图（机器翻译）'
            text += '\n\n'.join(f'![{label} {i+1}]({url})' for i,url in enumerate(urls)) + '\n\n'
        else:
            label = '原文截图'
            text += '\n\n'.join(f'![{label} {i+1}]({url})' for i,url in enumerate(urls)) + '\n\n'
        text += SIGNATURE

        # Construct evidence cards list for HTML view
        evidence_cards = []
        is_map_view = (record.get('image_kind') == 'everest_map_view')
        total_imgs = len(urls)
        for idx, u in enumerate(urls, 1):
            cn_title = layer_names_list[idx - 1] if (is_map_view and idx - 1 < len(layer_names_list)) else ""
            evidence_cards.append({
                'layer_cn': cn_title,
                'layer_en': '',
                'layer_index': idx,
                'layer_total': total_imgs,
                'image_url': u,
                'layer_target_url': source_url
            })

        # Publish HTML evidence page to GitHub Pages
        final_jump_urls = urls
        try:
            html_content = render_notification_page(
                title=f"产品名称 · {source['name']}",
                source_url=source_url,
                time_str=retrieved_raw or now(),
                image_cards=evidence_cards,
                signature=SIGNATURE
            )
            clean_key = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', key)
            file_name = f"{clean_key}_{int(time.time())}.html"
            gh_page_url = _deploy_to_github_pages(file_name, html_content, config)
            if gh_page_url:
                final_jump_urls = [gh_page_url]
            else:
                print('GitHub Pages deploy returned None, check token/repo permissions', flush=True)
        except Exception as exc:
            print(f"GitHub Pages deploy note: {exc}", flush=True)

        store.update_notice(key, 'sending')
        try:
            try:
                receipt = sender(config, '珠峰监控 · '+source['name'], text, final_jump_urls)
            except TypeError:
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
