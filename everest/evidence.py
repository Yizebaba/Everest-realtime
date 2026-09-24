"""Original source screenshots only: no redrawn text or composited data cards."""
import html
import os
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import now, read_json
from .clean import clean_page
from .translation import dismiss_gates


BLOCK_PAGES = ('您的请求可能存在威胁', '请求已被阻断', 'WEB 应用防火墙', 'Just a moment...')


def screenshot(url, path, settings):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        opts = {'headless': True}
        if settings['browser_channel'] != 'chromium': opts['channel'] = settings['browser_channel']
        if settings.get('proxy'): opts['proxy'] = {'server':settings['proxy']}
        browser = p.chromium.launch(**opts)
        try:
            page = browser.new_page(viewport={'width':1280,'height':900})
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if response and response.status >= 400:
                raise ValueError('Browser HTTP '+str(response.status))
            page.wait_for_timeout(settings['browser_wait_ms'])
            if 'earthquake.usgs.gov/earthquakes/map' in url:
                try:
                    for item in page.locator('mat-list-option, .map-list-item, [role=option], .mat-list-item, .mat-mdc-list-item').all():
                        if item.inner_text().strip():
                            item.click(timeout=3000)
                            page.wait_for_timeout(2500)
                            break
                except Exception:
                    pass
            if 'nature.com' in url:
                try:
                    page.evaluate("""() => {
                        const m = document.querySelector('.c-site-messages, [class*="nature-briefing"], [id*="nature-briefing"]');
                        if (m) m.remove();
                    }""")
                except Exception:
                    pass
            text = page.title()+'\n'+page.locator('body').inner_text()
            if any(marker in text for marker in BLOCK_PAGES):
                raise ValueError('Source page blocked; original screenshot unavailable')
            dismiss_gates(page)
            cleaned = clean_page(page, settings)
            page.wait_for_timeout(600)
            if 'emsc-csem.org' in url:
                try:
                    right_box = page.locator('.hright, #hmap').first.bounding_box()
                    if right_box:
                        top = max(0, right_box['y'] - 10)
                        height = min(1200, right_box['height'] + 700)
                        page.screenshot(path=str(path), clip={'x': max(0, right_box['x'] - 10), 'y': top, 'width': min(1280, right_box['width'] + 20), 'height': height}, timeout=15000)
                    else:
                        page.screenshot(path=str(path), full_page=True, timeout=15000)
                except Exception:
                    page.screenshot(path=str(path), full_page=True, timeout=15000)
            else:
                page.screenshot(path=str(path), full_page=True, timeout=15000)
            return {'captured_at':now(),'final_url':page.url,'cleaned':cleaned}
        finally:
            browser.close()


def _trim_bottom_blank(img, sample_threshold=235):
    """Trim bottom uniform/blank rows without altering real page content."""
    w, h = img.size
    cutoff = h
    step = 5
    for y in range(h - step, 300, -step):
        pixels = [img.getpixel((x, y)) for x in range(0, w, max(1, w // 25))]
        first = pixels[0]
        is_blank = all(abs(p[0] - first[0]) < 5 and abs(p[1] - first[1]) < 5 and abs(p[2] - first[2]) < 5 for p in pixels)
        is_light = (first[0] >= sample_threshold and first[1] >= sample_threshold and first[2] >= sample_threshold)
        if not (is_blank and is_light):
            cutoff = min(h, y + step + 10)
            break
    if cutoff < h:
        return img.crop((0, 0, w, cutoff))
    return img


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


def _decorate_evidence_card(image, source_url='', retrieved_at='', layer_title='', font_path=None, include_signature=True):
    """Prepend a clean dark header with source URL, timestamp, layer info, and append signature at bottom if required."""
    sig = 'WeChat / VX : No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'
    font_file = font_path or os.environ.get('EVEREST_FONT', 'C:/Windows/Fonts/msyh.ttc')
    # Enlarged high-visibility font sizes for phone screens
    font_size = max(26, int(image.width * 0.026))
    title_size = max(30, int(image.width * 0.030))
    footer_size = max(24, int(image.width * 0.024))
    try:
        font = ImageFont.truetype(font_file, font_size)
        title_font = ImageFont.truetype(font_file, title_size)
        footer_font = ImageFont.truetype(font_file, footer_size)
    except Exception:
        font = ImageFont.load_default()
        title_font = font
        footer_font = font

    # Format header text lines
    lines = []
    if source_url:
        lines.append(('来源网址：' + source_url, '#38bdf8', font))
    time_clean = (retrieved_at or now()).replace('T', ' ')[:19]
    line2 = f"监测时间：{time_clean}"
    if layer_title:
        line2 += f"    {layer_title}"
    lines.append((line2, '#f1f5f9', title_font if layer_title else font))

    line_h = int(font_size * 1.7)
    header_pad = int(font_size * 1.0)
    header_h = header_pad * 2 + len(lines) * line_h

    banner_h = int(footer_size * 3.2) if include_signature else 0
    total_h = header_h + image.height + banner_h

    out_img = Image.new('RGB', (image.width, total_h), '#0f172a')
    draw = ImageDraw.Draw(out_img)

    # Render header
    curr_y = header_pad
    for text_content, color, f in lines:
        draw.text((24, curr_y), text_content, fill=color, font=f)
        curr_y += line_h
    draw.line([(0, header_h), (image.width, header_h)], fill='#38bdf8', width=3)

    # Paste screenshot image
    out_img.paste(image, (0, header_h))

    # Render bottom signature only on designated card
    if include_signature:
        footer_top = header_h + image.height
        draw.line([(0, footer_top), (image.width, footer_top)], fill='#334155', width=2)
        bbox = draw.textbbox((0, 0), sig, font=footer_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = max(10, (image.width - text_w) // 2)
        y = footer_top + (banner_h - text_h) // 2
        draw.text((x, y), sig, fill='#cbd5e1', font=footer_font)

    return out_img


def _append_signature_bar(image, font_path=None, include_signature=True):
    return _decorate_evidence_card(image, font_path=font_path, include_signature=include_signature)


def make_cards(result, folder, settings):
    """Keep the existing cards transport field, but fill it only with original page pixels."""
    result['cards'] = []
    result['image_kind'] = 'original_screenshot'
    result['screenshot_error'] = ''
    map_views = result.get('map_views') or []
    if map_views:
        captured = [view for view in map_views if view.get('image') and not view.get('error')]
        if captured:
            result['map_view_items'] = []
            total_layers = len(captured)
            for idx, view in enumerate(captured, 1):
                target = folder / f"mapview-{view['layer']}.png"
                layer_cn = view.get('layer_name') or LAYER_NAMES.get(view['layer'], view['layer'])
                layer_banner = f"珠峰视角图层（共 {total_layers} 层） | 第 {idx} 层：{layer_cn}"
                is_last_card = (idx == total_layers)
                with Image.open(view['image']) as img:
                    signed_img = _decorate_evidence_card(
                        img.convert('RGB'),
                        source_url=view.get('view_url') or result['source']['url'],
                        retrieved_at=result.get('retrieved_at'),
                        layer_title=layer_banner,
                        font_path=settings.get('font'),
                        include_signature=is_last_card
                    )
                    signed_img.save(target)
                result['cards'].append(str(target))
                result['map_view_items'].append({
                    'path': str(target),
                    'layer': view['layer'],
                    'name': layer_cn,
                    'url': view.get('view_url', '')
                })
            result['image_kind'] = 'everest_map_view'
            result['map_view_layers'] = [view['layer'] for view in captured]
            return result
        result['screenshot_error'] = 'No Everest map view captured'
        return result
    override = settings.get('original_screenshot_urls', {}).get(result['source']['rule_id'])
    sources = []
    if not override:
        if result['source']['rule_id'] == 'weather-03':
            sources = [Path(path) for path in result.get('alert_screenshots', [])]
        elif result['source'].get('category_id') == 'news':
            if result.get('alert_screenshots'):
                sources = [Path(path) for path in result.get('alert_screenshots', [])]
            elif result.get('screenshot') and (folder/'page.png').is_file():
                sources = [folder/'page.png']
        else:
            subpages = sorted(folder.glob('page-*/page.png'))
            if result.get('screenshot') and (folder/'page.png').is_file():
                sources.append(folder/'page.png')
            sources.extend(subpages)
        sources = [path for path in sources if not (path.parent/'rendered.html').exists() or not any(marker in
            (path.parent/'rendered.html').read_text(encoding='utf-8', errors='replace')
            for marker in BLOCK_PAGES)]
    sources = sources[:1]
    if not sources and settings.get('screenshots', True):
        target = folder/'source-original.png'
        try:
            capture = screenshot(override or result['source']['url'], target, settings)
            if capture is None or not target.is_file():
                raise ValueError('No original screenshot produced')
            result['original_capture'] = capture
            sources.append(target)
        except Exception as exc:
            result['screenshot_error'] = str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            return result
    result['original_screenshots'] = [str(path) for path in sources]
    result['translations'] = []
    result['translation_errors'] = []
    if settings.get('translate_screenshots', False):
        from .translation import chinese_screenshot
        max_pages = 1
        translated=[]
        for i, source in enumerate(sources[:max_pages]):
            info_path=source.parent/'screenshot-info.json'
            if info_path.exists():
                url=read_json(info_path)['source_url']
            elif source.parent==folder:
                url=override or result['source']['url']
            else:
                result['translation_errors'].append('detail screenshot has no source URL')
                continue
            target=folder/f'chinese-page-{i+1:02d}.png'
            try:
                language=settings.get('translation_source_languages',{}).get(result['source']['rule_id'],'auto')
                info=chinese_screenshot(url,target,settings,language)
                result['translations'].append(info)
                translated.append(target)
            except Exception as exc:
                # One page failing must not discard the pages that did translate.
                result['translation_errors'].append(f"{type(exc).__name__}: {str(exc)[:80]}")
                continue
        if translated:
            sources=translated
            result['image_kind']='translated_source_screenshot'
        elif sources and settings.get('fallback_to_original_on_translation_failure', True):
            # Translation is unavailable (JS-only page, map canvas, blocked widget).
            # Send the real original screenshot and say so, instead of nothing.
            result['image_kind']='original_screenshot'
            detail = result['translation_errors'][0] if result['translation_errors'] else 'unknown'
            result['screenshot_error'] = 'Chinese translation unavailable, sent original page: '+detail
        else:
            result['screenshot_error']='Chinese translation failed for all pages: '+(
                result['translation_errors'][0] if result['translation_errors'] else 'unknown')
            return result
    for source in sources[:1]:
        with Image.open(source) as raw_image:
            image = _trim_bottom_blank(raw_image.convert('RGB'))
            # One notification carries one key image; cap at reasonable single-screen height (no huge multi-page strip)
            if image.height > 1600:
                image = image.crop((0, 0, image.width, 1600))
            prefix = 'chinese' if result['image_kind'] == 'translated_source_screenshot' else 'original'
            target = folder / f'{prefix}-01.png'
            source_url = result.get('original_capture', {}).get('final_url') or result['source']['url']
            signed_image = _decorate_evidence_card(
                image,
                source_url=source_url,
                retrieved_at=result.get('retrieved_at'),
                font_path=settings.get('font')
            )
            signed_image.save(target)
            result['cards'].append(str(target))
    return result


def write_report(folder, results):
    escape = html.escape
    sections = []
    for result in results:
        source = result['source']
        images = ''.join(f'<a href="{escape(Path(p).relative_to(folder).as_posix())}"><img loading="lazy" src="{escape(Path(p).relative_to(folder).as_posix())}" alt="{escape(source["name"])} 原文截图"></a>' for p in result['cards'])
        text = '\n\n'.join(result.get('matches', [])) or '无匹配内容'
        sections.append(f'''<section><h2>{escape(source['name'])}</h2>
<p>{escape(source['rule_id'])} · {escape(result['result'])} · {escape(result['retrieved_at'])}</p>
<a href="{escape(source['url'], quote=True)}" rel="noreferrer">来源</a> ·
<a href="{escape(source['rule_id'])}/result.json">完整结果 JSON</a> ·
<a href="{escape(source['rule_id'])}/response.bin">原始响应</a>
<p>{escape(result.get('error',''))}</p><p>{escape(result.get('screenshot_error',''))}</p>{images}<details><summary>实际匹配内容</summary><pre>{escape(text)}</pre></details></section>''')
    document = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>珠峰逐来源监控结果</title><style>body{max-width:1100px;margin:30px auto;padding:16px;background:#f3f5f7;font:16px system-ui;color:#182631}section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd3da}img{max-width:100%;display:block;margin:15px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#0755a0}</style>
<h1>逐来源原文截图与数据</h1>'''+''.join(sections)+'</html>'
    (folder/'index.html').write_text(document,encoding='utf-8')
