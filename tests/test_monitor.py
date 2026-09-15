import copy
import hashlib
import json
from pathlib import Path
import sys
import os

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from everest.collect import extract
from everest.core import Store, catalog, read_json, run_lock
from everest.delivery import deliver, destination
from everest.evidence import make_cards, write_report
import monitor

DEFAULTS = {'match_mode': 'all_groups', 'keywords': ['everest'], 'signals': ['flood'], 'ignore': []}
SOURCE = {'rule_id':'one', 'name':'珠峰数据源', 'url':'https://example.test', 'category':'新闻', 'nature':'news', 'interval_minutes':30}
CONFIG = {'serverchan': {'sendkey':'fake-unit-test-key'}}
SETTINGS = {'screenshots':False, 'font':os.environ.get('EVEREST_FONT','C:/Windows/Fonts/msyh.ttc'), 'notification_interval_seconds':3}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    def deny(*a, **kw): raise AssertionError('Tests cannot access network')
    monkeypatch.setattr(requests.sessions.Session, 'request', deny)


@pytest.fixture
def store(tmp_path):
    db = Store(tmp_path/'test.db')
    yield db
    db.close()


def result(run='run-one', text='Everest flood', outcome='found'):
    return {'run_id':run,'source':copy.deepcopy(SOURCE),'result':outcome,
            'retrieved_at':'2026-09-15T00:00:00+00:00','source_time':None,
            'matches':[text] if text else [],'content':[text], 'error':'','cards':[]}


def test_catalog_preserves_original_rules():
    root=Path(__file__).resolve().parents[1]
    old=read_json(root/'data-sources/hazard_sites.json')
    current=catalog(root/'config/sources.json')['sources']
    originals=[s for cat in old['categories'] for s in cat['sites']]
    assert len(current)==len(originals)==102
    assert len({s['url'] for s in current})==101
    by_id={s['rule_id']:s for s in current}
    for s in originals:
        assert all(by_id[s['rule_id']][k]==v for k,v in s.items())


def test_no_cross_article_keyword_leak():
    body=b'<article><p>Everest climbing</p></article><article><p>Flood on Mars</p></article>'
    assert extract(body,'text/html',SOURCE,DEFAULTS)[2]==[]


def test_nested_selector_and_decimal():
    src={**SOURCE,'watch':{'selector':'article .body'}}
    body=b'<article><p class="body">Everest flood level 15.5 metres</p></article>'
    assert extract(body,'text/html',src,DEFAULTS)[2]==['Everest flood level 15.5 metres']


def test_missing_selector_not_empty_success():
    with pytest.raises(ValueError):
        extract(b'<p>Everest flood</p>','text/html',{**SOURCE,'watch':{'selector':'#missing'}},DEFAULTS)


def test_exclude_keyword():
    assert extract(b'<p>Everest flood advertisement</p>','text/html',{**SOURCE,'watch':{'exclude_keywords':['advertisement']}},DEFAULTS)[2]==[]


def test_explicit_empty_filter_keeps_data():
    assert extract(b'{"value":1}','application/json',{**SOURCE,'watch':{'filter_keywords':[]}},DEFAULTS)[2]==['{"value": 1}']


def test_json_per_record_not_cross_record():
    body=b'{"features":[{"name":"Everest"},{"name":"flood elsewhere"}]}'
    assert extract(body,'application/json',SOURCE,DEFAULTS)[2]==[]


def test_rss_per_entry():
    body=b'<rss><channel><item><title>Everest flood</title></item><item><title>Mars news</title></item></channel></rss>'
    assert extract(body,'application/rss+xml',SOURCE,DEFAULTS)[2]==['Everest flood']


def test_malformed_json_rejected():
    with pytest.raises(ValueError): extract(b'{invalid','application/json',SOURCE,DEFAULTS)


def test_same_url_different_rule_ids(store,tmp_path):
    a=result(); b=result(); b['source']['rule_id']='two'
    store.record(a,tmp_path/'a.json','all',destination(CONFIG))
    store.record(b,tmp_path/'b.json','all',destination(CONFIG))
    assert len(store.notices('run-one'))==2


def test_new_baseline_no_changed_notice(store,tmp_path):
    r=result()
    assert not store.record(r,tmp_path/'a.json','changed',destination(CONFIG))
    assert r['change']=='baseline'


def test_failure_preserves_baseline_and_removal_notifies(store,tmp_path):
    store.record(result(),tmp_path/'a.json','changed',destination(CONFIG))
    store.record(result('run-two','', 'unknown'),tmp_path/'b.json','changed',destination(CONFIG))
    r=result('run-three','','not_found')
    assert store.record(r,tmp_path/'c.json','changed',destination(CONFIG))
    assert r['removed']==['Everest flood']


def test_os_lock_exclusive(tmp_path):
    with run_lock(tmp_path):
        with pytest.raises(OSError):
            with run_lock(tmp_path): pass
    with run_lock(tmp_path): pass


def queued(store,tmp_path):
    r=result()
    from PIL import Image
    path=tmp_path/'page.png'
    Image.new('RGB',(50,50),'blue').save(path)
    r['screenshot']={'captured_at':r['retrieved_at']}
    make_cards(r,tmp_path,SETTINGS)
    r['card_hashes']={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in r['cards']}
    store.record(r,tmp_path/'r.json','all',destination(CONFIG))
    return r


def test_cards_required_no_text_fallback(store,tmp_path):
    store.record(result(),tmp_path/'r.json','all',destination(CONFIG))
    sent=[]
    stats=deliver(store,'run-one',CONFIG,SETTINGS,sender=lambda *a:sent.append(a))
    assert stats['blocked']==1 and not sent


def test_changed_destination_blocks_before_upload(store,tmp_path):
    queued(store,tmp_path)
    calls=[]
    stats=deliver(store,'run-one',{'serverchan':{'sendkey':'different'}},SETTINGS,uploader=lambda *a:calls.append(a))
    assert stats['blocked']==1 and not calls


def test_exactly_one_notice_per_source_contains_image_and_no_repeat(store,tmp_path):
    queued(store,tmp_path)
    sent=[]
    def sender(c,t,b): sent.append((t,b)); return {'code':0}
    stats=deliver(store,'run-one',CONFIG,SETTINGS,uploader=lambda *a:'https://example.test/card.png',sender=sender,sleeper=lambda _:None)
    assert stats['accepted']==1 and len(sent)==1 and '![原文截图' in sent[0][1]
    assert 'found' not in sent[0][1] and '获取时间' not in sent[0][1]
    assert sent[0][1].endswith('vx:No1-Shine ｜ 珠峰多灾监控系统［测试版］')
    deliver(store,'run-one',CONFIG,SETTINGS,sender=sender)
    assert len(sent)==1


def test_uncertain_send_not_retried(store,tmp_path):
    queued(store,tmp_path)
    def sender(*a): raise TimeoutError()
    stats=deliver(store,'run-one',CONFIG,SETTINGS,uploader=lambda *a:'https://example.test/card.png',sender=sender,sleeper=lambda _:None)
    assert stats['unconfirmed']==1 and store.notices('run-one')==[]


def test_modified_card_blocked(store,tmp_path):
    r=queued(store,tmp_path)
    Path(r['cards'][0]).write_bytes(b'bad')
    assert deliver(store,'run-one',CONFIG,SETTINGS)['blocked']==1


def test_report_escapes_source_content(tmp_path):
    r=result(text='<script>alert(1)</script>')
    write_report(tmp_path,[r])
    html=(tmp_path/'index.html').read_text(encoding='utf-8')
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html


def test_cli_full_run_isolated(monkeypatch,tmp_path):
    def collector(s,d,c,f,run_id):
        f.mkdir(parents=True,exist_ok=True)
        r=result(run_id); r['source']=s
        from PIL import Image
        Image.new('RGB',(50,50),'blue').save(f/'page.png')
        r['screenshot']={'captured_at':r['retrieved_at']}
        return r
    monkeypatch.setattr(monitor,'collect',collector)
    import everest.evidence
    import everest.translation
    def translate(url,path,settings,language):
        from PIL import Image
        Image.new('RGB',(50,50),'blue').save(path)
        return {'source_url':url,'target_language':'zh-CN'}
    monkeypatch.setattr(everest.translation,'chinese_screenshot',translate)
    monkeypatch.setattr(everest.evidence,'screenshot',lambda *a:None)
    assert monitor.main(['--data-dir',str(tmp_path),'run','--all','--source','news-05','--notify','all'])==0
    latest=read_json(tmp_path/'latest.json')
    assert latest['completed']==1 and Path(latest['report']).exists()
