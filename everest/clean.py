"""Remove ads, cookie gates and site chrome so a screenshot shows source content.

Selectors are deliberately specific. We never remove the element that carries the
location/headline the user needs to verify.
"""
import json

# Advertising, promo and consent overlays.
AD_SELECTORS = (
    'ins.adsbygoogle', '[id^="div-gpt-ad"]', '[class*="adsbygoogle"]',
    '[class*="ad1-box"]', '[class*="ad1-disable"]', '[id*="google_ads"]',
    'iframe[src*="doubleclick"]', 'iframe[src*="googlesyndication"]',
    'iframe[src*="adsystem"]', 'iframe[src*="adservice"]', 'iframe[src*="taboola"]',
    'iframe[src*="outbrain"]', '[class*="advertisement"]', '[class*="ad-banner"]',
    '[class*="sponsored"]', '[class*="app-download"]', '[class*="advert"]',
    '[id*="advert"]', '[class*="promo-banner"]', '[class*="paywall"]',
    '[class*="newsletter-signup"]', '[class*="subscribe-banner"]',
)

# Site chrome: menus, footers and utility bars. `header` is intentionally NOT
# removed because it usually carries the location/headline being verified.
CHROME_SELECTORS = (
    'nav', 'footer', '[role="navigation"]', '[role="contentinfo"]',
    '.main-navigation', '#main_navigation', '.footer', '#footer',
    '[class*="site-footer"]', '[class*="main-footer"]', '[class*="breadcrumb"]',
    '[class*="social-share"]', '[class*="cookie-banner"]', '[class*="cookie-notice"]',
)

HIDE_JS = """(selectors) => {
    let hidden = 0;
    for (const sel of selectors) {
        let nodes = [];
        try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
        for (const el of nodes) {
            try {
                if (!el || !el.style) continue;
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) continue;
                el.style.setProperty('display', 'none', 'important');
                hidden += 1;
            } catch (e) { /* ignore */ }
        }
    }
    return hidden;
}"""


def clean_page(page, settings):
    """Hide ads, consent overlays and site chrome. Returns a small report."""
    report = {}
    if settings.get('hide_ads', True):
        try:
            report['ads_hidden'] = page.evaluate(HIDE_JS, list(AD_SELECTORS))
        except Exception as exc:
            report['ads_error'] = type(exc).__name__
    if settings.get('hide_chrome', True):
        try:
            report['chrome_hidden'] = page.evaluate(HIDE_JS, list(CHROME_SELECTORS))
        except Exception as exc:
            report['chrome_error'] = type(exc).__name__
    # Collapse any remaining fixed/sticky overlays taller than a strip at the top.
    if settings.get('hide_sticky_overlays', True):
        try:
            report['sticky_hidden'] = page.evaluate("""() => {
                let hidden = 0;
                for (const el of document.querySelectorAll('body *')) {
                    try {
                        if (!el || !el.style) continue;
                        const cs = getComputedStyle(el);
                        if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
                        const r = el.getBoundingClientRect();
                        if (r.height >= 150 && r.width >= 300) {
                            el.style.setProperty('display', 'none', 'important');
                            hidden += 1;
                        }
                    } catch (e) { /* ignore */ }
                }
                return hidden;
            }""")
        except Exception as exc:
            report['sticky_error'] = type(exc).__name__
    # Remove small copyright / legal / social strips that read as page chrome.
    if settings.get('hide_legal_strips', True):
        try:
            report['legal_hidden'] = page.evaluate("""() => {
                const pat = /(^\\s*©|copyright|all rights reserved|隐私设置|服务条款|imprint|legal notice)/i;
                let hidden = 0;
                for (const el of document.querySelectorAll('div, section, footer, p, ul')) {
                    try {
                        if (!el || !el.style) continue;
                        const t = (el.innerText || '').trim();
                        if (!t || t.length > 220) continue;
                        if (el.children.length > 10) continue;
                        if (!pat.test(t)) continue;
                        const r = el.getBoundingClientRect();
                        if (r.height === 0) continue;
                        el.style.setProperty('display', 'none', 'important');
                        hidden += 1;
                    } catch (e) { /* ignore */ }
                }
                return hidden;
            }""")
        except Exception as exc:
            report['legal_error'] = type(exc).__name__
    return report
