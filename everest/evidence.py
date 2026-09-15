import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import now


def screenshot(url, path, settings):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        opts = {'headless': True}
        if settings['browser_channel'] != 'chromium': opts['channel'] = settings['browser_channel']
        browser = p.chromium.launch(**opts)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if response and response.status >= 400:
                raise ValueError('Browser HTTP '+str(response.status))
            page.wait_for_timeout(settings['browser_wait_ms'])
            page.screenshot(path=str(path), timeout=15000)
            return {'captured_at': now(), 'final_url': page.url}
        finally:
            browser.close()


def make_cards(result, folder, settings):
    """Each source gets its own evidence, including explicitly labelled unavailable screenshots."""
    shot = folder / 'page.png'
    capture = result.get('screenshot')
    result['screenshot_error'] = ''
    if not capture and settings['screenshots'] and 'html' in result.get('content_type', ''):
        try:
            capture = screenshot(result['source']['url'], shot, settings)
        except Exception as exc:
            result['screenshot_error'] = type(exc).__name__
    result['screenshot'] = capture
    source = result['source']
    text = '\n'.join(result.get('matches', []))
    limit = settings.get('card_text_limit', 20000)
    truncated = len(text) > limit
    text = text[:limit]
    lines = [f"来源：{source['url']}", f"类别：{source['category']} ｜ 性质：{source['nature']}",
             f"获取时间 UTC：{result['retrieved_at']}", f"源时间：{result.get('source_time') or '未知'}",
             f"结果：{result['result']} ｜ 匹配片段：{len(result.get('matches', []))}"]
    if source['nature'] == 'forecast':
        lines.append('模型/页面预报，非实测；本程序不将其认证为官方预警。')
    if capture:
        lines.append('网页截图时间 UTC：'+capture['captured_at'])
    elif result['screenshot_error']:
        lines.append('网页截图失败：'+result['screenshot_error']+'；本卡是实际抓取数据卡。')
    else:
        lines.append('实际数据卡（非网页截图）。')
    if result['error']:
        lines.append('获取/解析失败：'+result['error'])
    lines += [f"获取页面：{len(result.get('pages', []))} ｜ 结构化接口：{len(result.get('network_records', []))}",
              f"地图影像：{len(result.get('map_images', []))} ｜ 获取范围：{result.get('coverage', '当前页面')}",
              '本次取得内容：', text or '没有提取到内容；请查看截图及采集错误。']
    if result.get('map_images'):
        lines.append('地图影像与图层记录已保存；像素变化不等于灾害消息。')
    if truncated:
        lines.append('卡片达到显示上限；完整匹配内容与原始响应保存在本地逐来源结果中。')
    font = ImageFont.truetype(settings['font'], 22)
    header = ImageFont.truetype(settings['font'], 29)
    wrapped = []
    for paragraph in '\n'.join(lines).splitlines():
        line = ''
        for ch in paragraph:
            if font.getlength(line + ch) > 1050:
                wrapped.append(line); line = ch
            else:
                line += ch
        wrapped.append(line)
    groups = [wrapped[i:i+45] for i in range(0, len(wrapped), 45)]
    cards = []
    for index, group in enumerate(groups):
        picture = None
        if index == 0 and capture:
            with Image.open(shot) as raw:
                picture = raw.convert('RGB'); picture.thumbnail((1060, 750))
        if index == 0 and result.get('map_images'):
            with Image.open(result['map_images'][0]['path']) as raw:
                picture = raw.convert('RGB'); picture.thumbnail((1060,750))
        offset = picture.height + 20 if picture else 0
        card = Image.new('RGB', (1120, 150 + offset + len(group)*32), '#ffffff')
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 0, 1120, 90), fill='#16202b')
        draw.text((25, 15), source['name'][:48], font=header, fill='white')
        draw.text((25, 55), f"{source['rule_id']} · {index+1}/{len(groups)} · 自动采集", font=font, fill='#c8d3de')
        y = 105
        if picture:
            card.paste(picture, (30, y)); y += offset
        for line in group:
            draw.text((30, y), line, font=font, fill='#243040'); y += 32
        draw.text((30, y+4), 'EVEREST · 信息监控 ｜ 原始来源内容，不代表已确认灾害', font=font, fill='#526579')
        target = folder / f'card-{index+1:02d}.png'
        card.save(target)
        cards.append(str(target))
    result['cards'] = cards
    return result


def write_report(folder, results):
    escape = html.escape
    sections = []
    for result in results:
        source = result['source']
        images = ''.join(f'<a href="{escape(source["rule_id"])}/{Path(p).name}"><img loading="lazy" src="{escape(source["rule_id"])}/{Path(p).name}" alt="{escape(source["name"])} 卡片"></a>' for p in result['cards'])
        text = '\n\n'.join(result.get('matches', [])) or '无匹配内容'
        sections.append(f'''<section><h2>{escape(source['name'])}</h2>
<p>{escape(source['rule_id'])} · {escape(result['result'])} · {escape(result['retrieved_at'])}</p>
<a href="{escape(source['url'], quote=True)}" rel="noreferrer">来源</a> ·
<a href="{escape(source['rule_id'])}/result.json">完整结果 JSON</a> ·
<a href="{escape(source['rule_id'])}/response.bin">原始响应</a>
<p>{escape(result.get('error',''))}</p>{images}<details><summary>实际匹配内容</summary><pre>{escape(text)}</pre></details></section>''')
    document = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>珠峰逐来源监控结果</title><style>body{max-width:1100px;margin:30px auto;padding:16px;background:#f3f5f7;font:16px system-ui;color:#182631}section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd3da}img{max-width:100%;display:block;margin:15px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#0755a0}</style>
<h1>逐来源实际数据与截图卡片</h1>'''+''.join(sections)+'</html>'
    (folder / 'index.html').write_text(document, encoding='utf-8')
