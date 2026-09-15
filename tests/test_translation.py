from urllib.parse import parse_qs,urlsplit
from PIL import Image
from everest.translation import dismiss_gates
from everest.evidence import make_cards


def test_dismiss_gates_clicks_known_labels_only():
    clicked = []
    state = {'visible': True}
    class Locator:
        def __init__(self, text): self.text = text
        def count(self): return 1 if (self.text == 'Accept all cookies' and state['visible']) else 0
        @property
        def first(self): return self
        def is_visible(self): return state['visible']
        def click(self, timeout=0):
            clicked.append(self.text)
            state['visible'] = False
    class Page:
        def get_by_role(self, role, name=None, exact=False): return Locator(name)
        def get_by_text(self, text, exact=False): return Locator(text)
        def wait_for_timeout(self, ms): pass
    assert dismiss_gates(Page()) == ['Accept all cookies']
    assert clicked == ['Accept all cookies']


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
    # Falls back to the original page; never labelled as Chinese.
    assert record['image_kind']=='original_screenshot'
    assert 'translation unavailable' in record['screenshot_error']
