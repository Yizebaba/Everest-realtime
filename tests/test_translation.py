from urllib.parse import parse_qs,urlsplit
from PIL import Image
from everest.translation import website_translation_url
from everest.evidence import make_cards


def test_translation_uses_chinese_and_original_url():
    query=parse_qs(urlsplit(website_translation_url('https://example.test/story?a=2',source='ne')).query)
    assert query=={'u':['https://example.test/story?a=2'],'sl':['ne'],'tl':['zh-CN']}


def test_translate_before_selecting_sent_image_preserves_original(monkeypatch,tmp_path):
    import everest.translation as module
    Image.new('RGB',(40,40),'red').save(tmp_path/'page.png')
    original=(tmp_path/'page.png').read_bytes()
    calls=[]
    def translate(url,path,settings,language):
        calls.append((url,language))
        Image.new('RGB',(40,40),'blue').save(path)
        return {'source_url':url,'target_language':'zh-CN'}
    monkeypatch.setattr(module,'chinese_screenshot',translate)
    record={'source':{'url':'https://example.test','rule_id':'one'},'screenshot':{'captured_at':'2026-09-15T00:00:00Z'}}
    make_cards(record,tmp_path,{'translate_screenshots':True,'screenshots':False})
    assert record['image_kind']=='translated_source_screenshot'
    assert calls==[('https://example.test','auto')]
    assert (tmp_path/'page.png').read_bytes()==original
    with Image.open(record['cards'][0]) as image: assert image.getpixel((0,0))==(0,0,255)


def test_translation_failure_not_mislabelled_chinese(monkeypatch,tmp_path):
    import everest.translation as module
    def fail(*args):raise TimeoutError()
    monkeypatch.setattr(module,'chinese_screenshot',fail)
    Image.new('RGB',(40,40),'red').save(tmp_path/'page.png')
    record={'source':{'url':'https://example.test','rule_id':'one'},'screenshot':{'captured_at':'2026-09-15T00:00:00Z'}}
    make_cards(record,tmp_path,{'translate_screenshots':True,'screenshots':False})
    assert record['cards']==[] and 'failed' in record['screenshot_error']
