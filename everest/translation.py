"""Translate the public source page in place, then capture its rendered layout.

Uses the official Google Translate website widget (element.js) with the
`googtrans` cookie on the ORIGINAL page. This avoids translate.goog proxy
restrictions that return "Can't translate this page" for many sources.
"""
import re
from urllib.parse import urlsplit

from .core import now
from .clean import clean_page

# Modal gates that cover content until dismissed.
DISMISS_TEXTS = (
    'OK, I Understand', 'OK I Understand', 'I Understand', 'Got it', 'Got It',
    'Accept all cookies', 'Accept only essential cookies', 'Accept All', 'Accept',
    'I agree', 'Agree', 'Continue anonymously', 'Continue', 'Dismiss', 'Close',
    '知道了', '我了解', '我同意', '接受', '同意', '关闭', '继续',
)

BLOCK_PAGES = ('您的请求可能存在威胁', '请求已被阻断', 'WEB 应用防火墙', 'Just a moment...')


def dismiss_gates(page, rounds=3):
    """Click only short, exact-label dismiss buttons; record what was clicked."""
    clicked = []
    for _ in range(rounds):
        hit = None
        for text in DISMISS_TEXTS:
            for getter in (lambda t: page.get_by_role('button', name=t, exact=True),
                           lambda t: page.get_by_text(t, exact=True)):
                try:
                    locator = getter(text)
                    if locator.count() and locator.first.is_visible():
                        hit = (text, locator.first)
                        break
                except Exception:
                    continue
            if hit:
                break
        if not hit:
            break
        try:
            hit[1].click(timeout=3000)
            clicked.append(hit[0])
            page.wait_for_timeout(1200)
        except Exception:
            break
    return clicked


def _inject_translate_widget(page, target='zh-CN'):
    page.evaluate("""(target) => {
        window.googleTranslateElementInit = function() {
            new google.translate.TranslateElement({
                pageLanguage: 'auto',
                includedLanguages: target,
                autoDisplay: false
            }, 'everest_gt_slot');
        };
        if (!document.getElementById('everest_gt_slot')) {
            const slot = document.createElement('div');
            slot.id = 'everest_gt_slot';
            slot.style.display = 'none';
            document.body.appendChild(slot);
        }
        if (!document.getElementById('everest_gt_script')) {
            const s = document.createElement('script');
            s.id = 'everest_gt_script';
            s.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
            document.head.appendChild(s);
        }
    }""", target)


def _cleanup_translation_artifacts(page):
    """Remove Google toolbar/banner and undo its body offset so the page is clean."""
    page.evaluate("""() => {
        const drop = ['.VIpgJd-ZVi9od-OR9QNe-OZyPf', 'iframe.goog-te-banner-frame',
                      '.goog-te-banner-frame', '#everest_gt_slot', '.skiptranslate'];
        for (const sel of drop) {
            let nodes = [];
            try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
            for (const el of nodes) {
                try {
                    if (!el || !el.style) continue;
                    el.style.display = 'none';
                    if (el.parentNode && el.tagName !== 'SCRIPT') el.remove();
                } catch (e) { /* ignore */ }
            }
        }
        try {
            document.body.style.top = '0px';
            document.body.style.position = 'static';
            document.body.style.height = 'auto';
            document.body.style.minHeight = 'auto';
            document.documentElement.style.height = 'auto';
        } catch (e) { /* ignore */ }
        for (const sel of ['#mapblock', '#maparea', '.map-container', '#map']) {
            let nodes = [];
            try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
            for (const el of nodes) {
                try {
                    if (!el || !el.style) continue;
                    if (!el.innerText.trim() && !el.querySelector('canvas') && !el.querySelector('img')) {
                        el.style.display = 'none';
                    }
                } catch (e) { /* ignore */ }
            }
        }
        try {
            const wrapper = document.querySelector('.wrapper');
            if (wrapper && wrapper.style) {
                wrapper.style.position = 'static';
                wrapper.style.overflow = 'visible';
                wrapper.style.height = 'auto';
                wrapper.style.minHeight = 'auto';
            }
        } catch (e) { /* ignore */ }
    }""")


def chinese_screenshot(url, path, settings, source_language='auto'):
    from playwright.sync_api import sync_playwright
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username:
        raise ValueError('Translation requires a public website URL')
    host = parts.hostname
    with sync_playwright() as p:
        opts = {'headless': True}
        if settings['browser_channel'] != 'chromium':
            opts['channel'] = settings['browser_channel']
        if settings.get('proxy'):
            opts['proxy'] = {'server': settings['proxy']}
        browser = p.chromium.launch(**opts)
        try:
            context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='zh-CN')
            cookie_value = f"/{source_language}/zh-CN"
            context.add_cookies([
                {'name': 'googtrans', 'value': cookie_value, 'domain': host, 'path': '/'},
                {'name': 'googtrans', 'value': cookie_value, 'domain': '.' + host, 'path': '/'},
            ])
            page = context.new_page()
            response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
            if response and response.status >= 400:
                raise ValueError('Source HTTP ' + str(response.status))
            page.wait_for_timeout(settings.get('browser_wait_ms', 2500))
            dismissed = dismiss_gates(page, rounds=4)
            # Consent banners often mount late and are <a>, not <button>.
            page.wait_for_timeout(1500)
            dismissed += dismiss_gates(page, rounds=4)
            _inject_translate_widget(page)
            # Wait until the in-place translation produces Chinese text.
            try:
                page.wait_for_function(
                    "() => (document.body.innerText.match(/[\\u3400-\\u9fff]/g)||[]).length >= 20",
                    timeout=settings.get('translation_timeout_ms', 30000))
            except Exception:
                pass
            page.wait_for_timeout(settings.get('translation_settle_ms', 3000))
            # Trigger lazy-loaded charts/maps so the screenshot is not full of spinners.
            try:
                for _ in range(settings.get('lazy_scroll_steps', 4)):
                    page.mouse.wheel(0, 900)
                    page.wait_for_timeout(settings.get('lazy_scroll_wait_ms', 700))
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(1200)
            except Exception:
                pass
            dismissed += dismiss_gates(page, rounds=2)
            _cleanup_translation_artifacts(page)
            clean_report = clean_page(page, settings)
            page.wait_for_timeout(800)
            body = page.locator('body').inner_text()
            if any(marker in body for marker in BLOCK_PAGES):
                raise ValueError('Translated source is a blocked page')
            chinese = len(re.findall(r'[\u3400-\u9fff]', body))
            if chinese < 20:
                raise ValueError('No translated Chinese source content')
            page.screenshot(path=str(path), full_page=True, timeout=20000)
            return {'provider': 'Google Translate website widget (in-place)', 'source_url': url,
                    'target_language': 'zh-CN', 'captured_at': now(), 'machine_translation': True,
                    'dismissed': dismissed, 'cleaned': clean_report,
                    'chinese_characters': chinese, 'title': page.title()}
        finally:
            browser.close()
