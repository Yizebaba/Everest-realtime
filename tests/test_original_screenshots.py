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
    assert (tmp_path/'original-01.png').exists()


def test_tall_original_keeps_one_leading_key_image(tmp_path):
    image=Image.new('RGB',(20,12010),'white'); image.putpixel((1,12005),(100,50,0))
    image.save(tmp_path/'page.png')
    rec=record(); make_cards(rec,tmp_path,{'screenshots':False})
    assert len(rec['cards']) == 1
    with Image.open(rec['cards'][0]) as image:
        assert image.size[0] == 20
        assert image.size[1] > 1000


def test_no_original_never_redraws_data(tmp_path):
    rec=record(); rec['screenshot']=None
    make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['cards']==[]


def test_blocked_page_not_used_as_original(tmp_path):
    Image.new('RGB',(20,20),'white').save(tmp_path/'page.png')
    (tmp_path/'rendered.html').write_text('您的请求可能存在威胁',encoding='utf-8')
    rec=record(); make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['cards']==[]


def test_news_cards_only_use_confirmed_article_screenshots(tmp_path):
    Image.new('RGB',(20,20),'red').save(tmp_path/'page.png')
    article = tmp_path/'page-02'; article.mkdir()
    Image.new('RGB',(20,20),'blue').save(article/'page.png')
    rec = {'source': {'rule_id':'news', 'url':'https://example.test', 'category_id':'news'},
           'alert_screenshots': [str(article/'page.png')], 'cards': []}
    make_cards(rec,tmp_path,{'screenshots':False})
    assert len(rec['cards']) == 1
    with Image.open(rec['cards'][0]) as image:
        assert image.getpixel((0,0)) == (0,0,255)


def test_news_source_image_limit_is_respected(tmp_path):
    first = tmp_path/'page-02'; first.mkdir()
    second = tmp_path/'page-03'; second.mkdir()
    Image.new('RGB',(20,20),'blue').save(first/'page.png')
    Image.new('RGB',(20,20),'green').save(second/'page.png')
    rec = {'source': {'rule_id':'news', 'url':'https://example.test', 'category_id':'news',
                      'max_notification_images': 1},
           'alert_screenshots': [str(first/'page.png'), str(second/'page.png')], 'cards': []}
    make_cards(rec,tmp_path,{'screenshots':False})
    assert len(rec['cards']) == 1


def test_map_views_keep_all_available_layers(tmp_path):
    first = tmp_path/'first.png'; second = tmp_path/'second.png'
    Image.new('RGB',(20,20),'blue').save(first)
    Image.new('RGB',(20,20),'green').save(second)
    rec = {'source': {'rule_id':'map', 'url':'https://example.test'}, 'cards': [], 'map_views': [
        {'layer':'hazards', 'image':str(first), 'error':'', 'view_url':'https://example.test/hazards'},
        {'layer':'rain', 'image':str(second), 'error':'', 'view_url':'https://example.test/rain'},
    ]}
    make_cards(rec,tmp_path,{'screenshots':False})
    assert rec['map_view_layers'] == ['hazards', 'rain']
    assert len(rec['cards']) == 2
