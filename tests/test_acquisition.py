import json
from everest.collect import extract, collect
from everest.discovery import discover, feed_links
from everest.filters import structured_match, timestamp
from everest import browser

SOURCE={'rule_id':'demo','url':'https://example.test/','name':'示例','watch':{}}


def test_default_keeps_climbing_numeric_and_old_news():
    _,_,matches,_=extract(b'<p>Everest climbing information</p><p>wind 5 m/s, coordinates 27.98 86.92</p><p>2010 Everest flood warning</p>',
                         'text/html',SOURCE,{'keywords':['everest'],'signals':['flood']})
    assert len(matches)==3


def test_config_terms_and_no_default_and_gate():
    from everest.core import read_json
    from pathlib import Path
    config=read_json(Path(__file__).parents[1]/'config/sources.json')
    assert config['defaults']['match_mode']=='all'
    assert {'喜马拉雅山','冰川','himalaya','glacier'}<=set(config['defaults']['keywords'])


def test_advertised_feed_next_detail_and_search():
    body=b'''<link rel="alternate" type="application/rss+xml" href="/feed"><a rel="next" href="/page/2">next</a>
    <h2><a href="/story">story</a></h2><form action="/search"><input type="search" name="q"></form>'''
    links=discover(body,SOURCE['url'],dict(discover_feeds=True,follow_pagination=True,follow_details=True,discover_search=True,search_terms=['glacier']))
    assert {x['kind'] for x in links}=={'feed','next','detail','search'}


def test_rss_preserves_article_date_url():
    items=feed_links(b'<rss><channel><item><title>Ice</title><link>https://example.test/story</link><pubDate>Tue, 15 Sep 2026 00:00:00 GMT</pubDate></item></channel></rss>',SOURCE['url'])
    assert items[0]['url'].endswith('/story') and timestamp(items[0]['published_at'])


def test_optional_coordinate_and_magnitude_without_place_text():
    record={'geometry':{'coordinates':[86.9,27.9]},'properties':{'mag':4.2}}
    rules={'bbox':[85,27,88,29], 'numeric':{'properties.mag':{'min':4}}}
    assert structured_match(record,rules)
    record['properties']['mag']=3
    assert not structured_match(record,rules)


def test_optional_feed_date_filter():
    src={**SOURCE,'watch':{'structured':{'time_path':'published_at','after':'2026-01-01T00:00:00Z'}}}
    body=b'<rss><channel><item><title>Old flood</title><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item></channel></rss>'
    assert extract(body,'application/rss+xml',src,{})[2]==[]


def test_rendered_dom_and_json_feed_back_into_content(monkeypatch,tmp_path):
    import everest.collect as module
    monkeypatch.setattr(module,'fetch_page',lambda *a:(b'<html></html>','text/html',SOURCE['url'],None))
    monkeypatch.setattr(browser,'render',lambda *a:{'dom':b'<p>Dynamic glacier data</p>', 'captured_at':'2026-09-15T00:00:00Z','final_url':SOURCE['url'],
                                                  'network_records':[{'data':{'level':12}}], 'map_images':[]})
    settings={'render_html':True,'max_pages_per_source':1}
    result=collect(SOURCE,{},settings,tmp_path,'run')
    assert result['result']=='found'
    assert 'Dynamic glacier data' in result['matches']
    assert any('12' in x for x in result['matches'])


def test_follow_detail_page_and_report_remaining(monkeypatch,tmp_path):
    import everest.collect as module
    def fetch(url,settings):
        body=b'<h2><a href="/story">story</a></h2><a rel="next" href="/page2">next</a>' if url==SOURCE['url'] else b'<p>actual second page</p>'
        return body,'text/html',url,None
    monkeypatch.setattr(module,'fetch_page',fetch)
    result=collect(SOURCE,{},dict(follow_details=True,follow_pagination=True,max_pages_per_source=2),tmp_path,'run')
    assert len(result['pages'])==2
    assert result['pending_urls'] and result['coverage']=='partial'


def test_public_network_url_redacts_credentials():
    cleaned=browser.public_url('https://example.test/api?token=secret&q=glacier')
    assert 'secret' not in cleaned and 'glacier' in cleaned
