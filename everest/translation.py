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
