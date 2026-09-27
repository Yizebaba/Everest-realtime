"""Discover advertised feeds, detail links, next pages, and GET search forms."""
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, urlencode
from bs4 import BeautifulSoup


NEWS_HAZARD_TERMS = (
    'earthquake', 'seismic', 'aftershock', 'flood', 'flash flood', 'glof',
    'landslide', 'mudslide', 'debris flow', 'avalanche', 'icefall',
    'glacial lake', 'glacier burst', 'rescue', 'evacuat', 'closure',
    'warning', 'alert', 'heavy rain', 'snowfall', 'blizzard',
    '地震', '洪水', '山洪', '滑坡', '泥石流', '雪崩', '冰崩', '冰湖', '救援',
    '疏散', '封路', '预警', '警报', '暴雨', '降雪',
)
NMC_ALERT_TITLES = ('农业气象灾害风险预警', '山洪灾害气象预警', '地质灾害气象风险预警')
def news_candidate(text):
    lowered = (text or '').lower()
    return any(term.lower() in lowered for term in NEWS_HAZARD_TERMS)


def news_direct_event(text):
    return news_candidate(text)


def discover(body, base, settings, news_only=False, nmc_alerts_only=False):
    soup = BeautifulSoup(body, 'html.parser')
    links = []
    def add(href, kind):
        url = urljoin(base, href or '')
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or parts.hostname != urlsplit(base).hostname:
            return
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
        if url != base and not any(x['url'] == url for x in links):
            links.append({'url': url, 'kind': kind})
    if nmc_alerts_only:
        for tag in soup.select('a[title][href]'):
            if tag.get('title', '').strip() in NMC_ALERT_TITLES:
                add(tag['href'], 'nmc_alert')
        return links
    if news_only:
        for tag in soup.select('article a[href], h1 a[href], h2 a[href], h3 a[href], h4 a[href], a[rel="bookmark"], a[href*="/news/"], a[href*="/story/"], a[href*="/article/"]'):
            if news_direct_event(tag.get_text(' ', strip=True)):
                add(tag.get('href'), 'matched_article')
        return links
    if settings.get('discover_feeds'):
        for tag in soup.select('link[rel="alternate"][href]'):
            if any(t in tag.get('type', '') for t in ('rss', 'atom')):
                add(tag['href'], 'feed')
    if settings.get('follow_pagination'):
        for tag in soup.select('a[href], link[rel="next"][href]'):
            text = tag.get_text(' ', strip=True)
            if 'next' in tag.get('rel', []) or text.lower() in ('next', 'next page', 'older posts', '下一页', '下页'):
                add(tag['href'], 'next')
    if settings.get('follow_details'):
        keywords = [k.lower() for k in settings.get('search_terms', [])] + ['everest', 'himalaya', 'glacier', 'flood', 'avalanche', 'basecamp', 'disaster', 'landslide', 'icefall']
        # Priority 1: Specifically matched articles with target keywords in anchor text
        for tag in soup.select('article a[href], h1 a[href], h2 a[href], h3 a[href], h4 a[href], a[rel="bookmark"], a[href*="/news/"], a[href*="/story/"], a[href*="/article/"]'):
            text = tag.get_text(' ', strip=True).lower()
            if any(k in text for k in keywords):
                add(tag.get('href'), 'matched_article')
        # Priority 2: General article links if no specific match
        for tag in soup.select('article a[href], h2 a[href], h3 a[href], a[rel="bookmark"]'):
            add(tag.get('href'), 'detail')
    if settings.get('discover_search'):
        for form in soup.find_all('form'):
            if form.get('method', 'get').lower() != 'get':
                continue
            field = form.select_one('input[type="search"][name], input[name="q"], input[name="s"], input[name="search"]')
            if not field:
                continue
            action = urljoin(base, form.get('action') or base)
            for term in settings.get('search_terms', []):
                params = {x['name']: x.get('value', '') for x in form.select('input[type="hidden"][name]')}
                params[field['name']] = term
                add(action + ('&' if '?' in action else '?') + urlencode(params), 'search')
    return links


def feed_links(body, base):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(body)
    out = []
    for entry in root.iter():
        if entry.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        data = {'title': '', 'url': '', 'published_at': None}
        for node in entry:
            tag = node.tag.split('}')[-1]
            if tag == 'title': data['title'] = ''.join(node.itertext()).strip()
            if tag == 'link' and node.get('rel', 'alternate') == 'alternate':
                data['url'] = urljoin(base, node.get('href') or node.text or '')
            if tag in ('pubDate', 'published', 'updated', 'date'):
                data['published_at'] = node.text
        if data['url'].startswith(('http://', 'https://')):
            out.append(data)
    return out


def article_metadata(body, url):
    soup=BeautifulSoup(body,'html.parser')
    published=soup.select_one('meta[property="article:published_time"], meta[name="date"], time[datetime]')
    return {'url':url, 'title':soup.title.get_text(' ',strip=True) if soup.title else '',
            'published_at':(published.get('content') or published.get('datetime')) if published else None}
