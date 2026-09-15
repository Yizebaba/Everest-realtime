"""Translate the public source website, then capture its rendered page layout."""
import re
from urllib.parse import urlencode, urlsplit
from .core import now


def website_translation_url(url, target='zh-CN', source='auto'):
    parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username:
        raise ValueError('Translation requires a public website URL')
    return 'https://translate.google.com/translate?'+urlencode({'sl':source,'tl':target,'u':url})


def chinese_screenshot(url, path, settings, source_language='auto'):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        opts={'headless':True}
        if settings['browser_channel']!='chromium': opts['channel']=settings['browser_channel']
        if settings.get('proxy'): opts['proxy']={'server':settings['proxy']}
        browser=p.chromium.launch(**opts)
        try:
            page=browser.new_page(viewport={'width':1280,'height':900},locale='zh-CN')
            response=page.goto(website_translation_url(url,source=source_language),wait_until='domcontentloaded',timeout=45000)
            if response and response.status>=400:
                raise ValueError('Website translation HTTP '+str(response.status))
            # Inspect the source frame's translated body, not the Chinese translation toolbar.
            page.wait_for_function("""() => location.hostname.endsWith('.translate.goog') &&
                (document.body.innerText.match(/[\\u3400-\\u9fff]/g)||[]).length >= 20""",timeout=30000)
            page.wait_for_timeout(settings.get('translation_settle_ms',3000))
            # Clean up Google Translate toolbar, banners, and collapse empty dynamic containers (e.g. broken map canvases in iframe)
            page.evaluate("""() => {
                const topBar = document.querySelector('.VIpgJd-ZVi9od-OR9QNe-OZyPf');
                if (topBar) topBar.remove();
                const banner = document.querySelector('iframe.goog-te-banner-frame');
                if (banner) banner.remove();
                document.body.style.top = '0px';
                document.body.style.position = 'static';
                document.body.style.height = 'auto';
                document.documentElement.style.height = 'auto';
                
                // If a map/canvas block inside the translated frame failed to load, collapse it to avoid 500px blank gap
                for (const el of document.querySelectorAll('#mapblock, #maparea, .map-container, #map')) {
                    if (!el.innerText.trim() && !el.querySelector('canvas') && !el.querySelector('img')) {
                        el.style.display = 'none';
                    }
                }
                const wrapper = document.querySelector('.wrapper');
                if (wrapper) {
                    wrapper.style.position = 'static';
                    wrapper.style.overflow = 'visible';
                    wrapper.style.height = 'auto';
                    wrapper.style.minHeight = 'auto';
                }
            }""")
            page.wait_for_timeout(1000)
            body=page.locator('body').inner_text()
            if any(x in body for x in ('您的请求可能存在威胁','请求已被阻断','WEB 应用防火墙')):
                raise ValueError('Translated source is a blocked page')
            if len(re.findall(r'[\u3400-\u9fff]',body))<20:
                raise ValueError('No translated Chinese source content')
            page.screenshot(path=str(path),full_page=True,timeout=20000)
            return {'provider':'Google website translation','source_url':url,'translated_url':page.url,
                    'target_language':'zh-CN','captured_at':now(),'machine_translation':True,
                    'title':page.title()}
        finally:browser.close()
