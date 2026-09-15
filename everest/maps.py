"""OGC WMS imagery acquisition. An image change is not a hazard classification."""
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from PIL import Image
import io
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
    if source_time: params['time']=source_time
    url=endpoint+separator+urlencode(params)
    data,ctype,_,_=fetch_page(url,settings)
    if 'image/' not in ctype: raise ValueError('WMS did not return imagery')
    image=Image.open(io.BytesIO(data)).convert('RGBA')
    target=folder/'wms.png'; image.save(target)
    return target,{'url':url,'layer':options['layer'],'bbox':options['bbox'],'crs':'EPSG:4326',
                   'time':source_time,'nature':'rendered_imagery','note':'影像产品，不是灾害事件判定'}
