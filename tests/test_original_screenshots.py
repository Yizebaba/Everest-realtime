from PIL import Image
from everest.evidence import make_cards


def record():
    return {'source':{'rule_id':'one','url':'https://example.test'},'screenshot':{'captured_at':'2026-09-15T00:00:00Z'},
            'matches':['found changed 获取时间 some text'], 'cards':[]}


def test_original_pixels_and_file_bytes_preserved(tmp_path):
    image=Image.new('RGB',(1280,900),'white'); image.putpixel((20,20),(100,50,0))
    source=tmp_path/'page.png'; image.save(source)
    rec=record()
    make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['image_kind']=='original_screenshot'
    assert (tmp_path/'original-01.png').read_bytes()==source.read_bytes()


def test_tall_original_is_split_losslessly(tmp_path):
    image=Image.new('RGB',(20,12010),'white'); image.putpixel((1,12005),(100,50,0))
    image.save(tmp_path/'page.png')
    rec=record(); make_cards(rec,tmp_path,{'screenshots':False})
    assert len(rec['cards'])==2
    with Image.open(rec['cards'][1]) as last:
        assert last.size==(20,10) and last.getpixel((1,5))==(100,50,0)


def test_no_original_never_redraws_data(tmp_path):
    rec=record(); rec['screenshot']=None
    make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['cards']==[]


def test_blocked_page_not_used_as_original(tmp_path):
    Image.new('RGB',(20,20),'white').save(tmp_path/'page.png')
    (tmp_path/'rendered.html').write_text('您的请求可能存在威胁',encoding='utf-8')
    rec=record(); make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['cards']==[]
