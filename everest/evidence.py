"""Original source screenshots only: no redrawn text or composited data cards."""
import html
import shutil
from pathlib import Path

from PIL import Image

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
            text = page.title()+'\n'+page.locator('body').inner_text()
            if any(marker in text for marker in BLOCK_PAGES):
                raise ValueError('Source page blocked; original screenshot unavailable')
            dismiss_gates(page)
            cleaned = clean_page(page, settings)
            page.wait_for_timeout(600)
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
            for view in captured:
                target = folder / f"mapview-{view['layer']}.png"
                shutil.copyfile(view['image'], target)
                result['cards'].append(str(target))
                result['map_view_items'].append({
                    'path': str(target),
                    'layer': view['layer'],
                    'name': view.get('layer_name', view['layer']),
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
        if result.get('screenshot') and (folder/'page.png').is_file():
            sources.append(folder/'page.png')
        sources.extend(sorted(folder.glob('page-*/page.png')))
        sources = [path for path in sources if not (path.parent/'rendered.html').exists() or not any(marker in
            (path.parent/'rendered.html').read_text(encoding='utf-8', errors='replace')
            for marker in BLOCK_PAGES)]
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
        max_pages = int(settings.get('max_translated_pages', 3))
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
    for source in sources:
        with Image.open(source) as raw_image:
            image = _trim_bottom_blank(raw_image.convert('RGB'))
            # Split tall pages losslessly for image channels; no scaling, markup or text overlays.
            for top in range(0,image.height,12000):
                prefix='chinese' if result['image_kind']=='translated_source_screenshot' else 'original'
                target=folder/f'{prefix}-{len(result["cards"])+1:02d}.png'
                if image.height<=12000:
                    image.save(target)
                else:
                    image.crop((0,top,image.width,min(top+12000,image.height))).save(target)
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
