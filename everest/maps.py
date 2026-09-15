"""OGC WMS imagery acquisition. An image change is not a hazard classification."""
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from PIL import Image
import io
import datetime as dt
from .collect import fetch_page


def fetch_wms(options, folder, settings):
    endpoint=options['url']
    separator='&' if '?' in endpoint else '?'
    caps_url=endpoint+separator+urlencode({'service':'WMS','version':'1.1.1','request':'GetCapabilities'})
    body,_,_,_=fetch_page(caps_url,settings)
    (folder/'wms-capabilities.xml').write_bytes(body)
    tree=ET.fromstring(body)
    layer=next((e for e in tree.iter('Layer') if e.findtext('Name')==options['layer']),None)
    if layer is None: raise ValueError('WMS layer not advertised')
    extent=layer.find("Extent[@name='time']")
    source_time=extent.get('default') if extent is not None else None
    params={'service':'WMS','request':'GetMap','version':'1.1.1','layers':options['layer'],
            'styles':'','format':'image/png','SRS':'EPSG:4326','width':1024,'height':768,
            'bbox':','.join(str(x) for x in options['bbox'])}
    params['transparent']='true'
    dates=[source_time]
    # Only backtrack within an explicitly advertised daily interval.
    if source_time and extent is not None:
        for interval in (extent.text or '').split(','):
            parts=interval.split('/')
            if len(parts)==3 and parts[2]=='P1D':
                try:
                    start=dt.date.fromisoformat(parts[0][:10]); end=dt.date.fromisoformat(parts[1][:10])
                    latest=dt.date.fromisoformat(source_time[:10])
                    dates += [(latest-dt.timedelta(days=i)).isoformat() for i in range(1,4)
                              if start<=latest-dt.timedelta(days=i)<=end]
                except ValueError: pass
    attempts=[]
    for date in dict.fromkeys(dates):
        if date: params['time']=date
        url=endpoint+separator+urlencode(params)
        data,ctype,_,_=fetch_page(url,settings)
        if 'image/' not in ctype: raise ValueError('WMS did not return imagery')
        image=Image.open(io.BytesIO(data)).convert('RGBA')
        raw_target=folder/f'wms-{date or "default"}.png'; image.save(raw_target)
        extrema=image.convert('RGB').getextrema()
        usable=image.getchannel('A').getbbox() is not None and any(lo!=hi for lo,hi in extrema)
        attempts.append({'time':date,'usable_visual':usable,'path':str(raw_target)})
        if not usable: continue
        target=folder/'wms.png'; image.save(target)
        return target,{'url':url,'layer':options['layer'],'bbox':options['bbox'],'crs':'EPSG:4326',
                       'time':date,'advertised_default_time':source_time,'attempts':attempts,
                       'nature':'rendered_imagery','note':'影像产品，不是灾害事件判定；产品日期按实际使用值记录'}
    raise ValueError('WMS images are transparent or uniform; no usable visual evidence')
