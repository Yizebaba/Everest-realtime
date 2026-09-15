import io
from PIL import Image
from everest.maps import fetch_wms


def test_wms_uses_advertised_layer_date_and_bbox(monkeypatch,tmp_path):
    import everest.maps as module
    calls=[]
    def fetch(url,settings):
        calls.append(url)
        if 'GetCapabilities' in url:
            return b'<WMT_MS_Capabilities><Capability><Layer><Layer><Name>ice</Name><Extent name="time" default="2026-09-14"/></Layer></Layer></Capability></WMT_MS_Capabilities>','text/xml',url,None
        stream=io.BytesIO(); image=Image.new('RGBA',(20,20),'blue'); image.putpixel((5,5),(255,255,255,255)); image.save(stream,'PNG')
        return stream.getvalue(),'image/png',url,None
    monkeypatch.setattr(module,'fetch_page',fetch)
    path,meta=fetch_wms({'url':'https://example.test/wms','layer':'ice','bbox':[85,27,88,29]},tmp_path,{})
    assert path.exists() and meta['time']=='2026-09-14'
    assert 'time=2026-09-14' in calls[1] and 'bbox=85%2C27%2C88%2C29' in calls[1]
    assert meta['nature']=='rendered_imagery'


def test_blank_latest_uses_advertised_previous_date(monkeypatch,tmp_path):
    import everest.maps as module
    def fetch(url,settings):
        if 'GetCapabilities' in url:
            return b'<WMT_MS_Capabilities><Layer><Name>ice</Name><Extent name="time" default="2026-09-15">2026-09-10/2026-09-15/P1D</Extent></Layer></WMT_MS_Capabilities>','text/xml',url,None
        image=Image.new('RGBA',(20,20),(0,0,0,0))
        if '2026-09-14' in url:
            image=Image.new('RGBA',(20,20),'blue'); image.putpixel((2,2),(255,255,255,255))
        stream=io.BytesIO(); image.save(stream,'PNG')
        return stream.getvalue(),'image/png',url,None
    monkeypatch.setattr(module,'fetch_page',fetch)
    _,meta=fetch_wms({'url':'https://example.test/wms','layer':'ice','bbox':[85,27,88,29]},tmp_path,{})
    assert meta['time']=='2026-09-14' and meta['advertised_default_time']=='2026-09-15'
    assert meta['attempts'][0]['usable_visual'] is False
