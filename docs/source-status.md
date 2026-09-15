# 数据源实测状态

- 规则总数：102
- 当前可用（能生成截图证据）：91
- 受阻：11
- 已翻译中文：73
- 珠峰地图视角：9
- 全球范围（无关键词限制）：87

## 受阻来源

| 规则 | 名称 | 原因 |
| --- | --- | --- |
| earthquake-05 | GEOFON 全球地震列表 | 未能生成截图 |
| weather-02 | 中国气象局 | 该站返回 HTTP 406 拦截 |
| weather-04 | 中国天气网 | 该站返回 HTTP 403 拦截 |
| flood-05 | Google Flood Hub (灾害点放大直达) | 地图视图未捕获到画布 |
| flood-07 | 中国水利部 | 该站返回 HTTP 502（服务端故障） |
| landslide-02 | USGS 滑坡灾害计划 | 该站返回 HTTP 403 拦截 |
| avalanche-07 | Colorado Avalanche Info Center | 浏览器加载报错 |
| satellite-04 | CIRA SLIDER (向日葵9号) | 地图视图未捕获到画布 |
| platform-02 | ReliefWeb (OCHA) | 该站返回 HTTP 403 拦截 |
| special-01 | CMA 气象灾害预警 API | 该站 WAF 拦截自动化访问 |
| special-10 | CMA 气象频道页 | 该站 WAF 拦截自动化访问 |

## 全部来源

| 规则 | 类别 | 名称 | 状态 | 网址 |
| --- | --- | --- | --- | --- |
| special-01 | 专项监控 | CMA 气象灾害预警 API | 可用·原文截图 | https://weather.cma.cn/api/alarm |
| special-02 | 专项监控 | 尼泊尔 NEMRC 地震列表 | 可用·中文翻译 | https://seismonepal.gov.np/ne/earthquakes |
| special-03 | 专项监控 | GEOFON 地震列表 | 可用·中文翻译 | https://geofon.gfz.de/eqinfo/list.php |
| special-04 | 专项监控 | 中国地震局 震情速递 | 可用·中文翻译 | https://www.cea.gov.cn/cea/dzpd/zqsd/index.html |
| special-05 | 专项监控 | 尼泊尔水文局 洪水预警 | 可用·原文截图 | http://hydrology.gov.np/cm/api-public/alerts |
| special-06 | 专项监控 | 尼泊尔 DHM 全国天气 | 可用·原文截图 | https://dhm.gov.np/mfd/api/country-forecast |
| special-07 | 专项监控 | ThinkHazard 尼泊尔灾种报告 | 可用·原文截图 | https://thinkhazard.org/en/report/175-nepal |
| special-08 | 专项监控 | Dartmouth 洪水百科 | 可用·中文翻译 | https://floodobservatory.colorado.edu/wiki/DischargeFromSpace_Tab |
| special-09 | 专项监控 | GLIMS 冰川地图页 | 可用·中文翻译 | https://www.glims.org/maps/glims |
| special-10 | 专项监控 | CMA 气象频道页 | 可用·原文截图 | https://weather.cma.cn/web/channel-2b0863600e144b13807e606f928b1266.html |
| special-11 | 专项监控 | ISC 国际地震中心 | 可用·中文翻译 | http://www.isc.ac.uk/ |
| special-12 | 专项监控 | NASA CMR 数据集检索(everest) | 可用·中文翻译 | https://cmr.earthdata.nasa.gov/search/collections.json?keyword=everest&page_size=20&sort_key=-revision_date |
| glacier-01 | 冰川与冰湖溃决 | ICIMOD 国际山地综合发展中心 | 可用·中文翻译 | https://www.icimod.org/ |
| glacier-02 | 冰川与冰湖溃决 | ICIMOD RDS 区域数据库 | 可用·中文翻译 | https://rds.icimod.org/metadata/search?q=Everest&page=1&per_page=9&qKeyword= |
| glacier-03 | 冰川与冰湖溃决 | GLIMS 全球冰川数据库 | 可用·中文翻译 | https://www.glims.org/ |
| glacier-04 | 冰川与冰湖溃决 | WGMS 冰川监测(RSS) | 可用·中文翻译 | https://wgms.ch/feed/ |
| glacier-05 | 冰川与冰湖溃决 | NSIDC 美国冰雪数据中心 | 可用·中文翻译 | https://nsidc.org/ |
| glacier-06 | 冰川与冰湖溃决 | NSIDC 世界冰川清单 | 可用·中文翻译 | https://nsidc.org/data/glacier_inventory/ |
| glacier-07 | 冰川与冰湖溃决 | 全球冰冻圈观测 GCW | 可用·中文翻译 | https://globalcryospherewatch.org/ |
| glacier-08 | 冰川与冰湖溃决 | Copernicus 气候服务 | 可用·中文翻译 | https://climate.copernicus.eu/ |
| glacier-09 | 冰川与冰湖溃决 | RGI 兰道夫冰川清单 | 可用·中文翻译 | https://www.glims.org/maps/glims?catalog=RGI |
| glacier-10 | 冰川与冰湖溃决 | The Cryosphere 期刊 | 可用·中文翻译 | https://www.the-cryosphere.net/ |
| satellite-01 | 卫星遥感 | NASA Worldview | 可用·珠峰地图 | https://worldview.earthdata.nasa.gov/ |
| satellite-02 | 卫星遥感 | NASA FIRMS 火情 | 可用·珠峰地图 | https://firms.modaps.eosdis.nasa.gov/ |
| satellite-03 | 卫星遥感 | 向日葵 9 号 (NICT) | 可用·原文截图 | https://himawari8.nict.go.jp/ |
| satellite-04 | 卫星遥感 | CIRA SLIDER (向日葵9号) | 可用·原文截图 | https://slider.cira.colostate.edu/?sat=himawari&sec=full_disk&x=5500&y=5500&z=0&angle=0&im=12&ts=1&st=0&et=0&speed=130&motion=loop&maps%5Bborders%5D=white&p%5B0%5D=geocolor&opacity%5B0%5D=1 |
| satellite-05 | 卫星遥感 | Copernicus Browser | 可用·中文翻译 | https://browser.dataspace.copernicus.eu/ |
| satellite-06 | 卫星遥感 | Planet Insights Browser (原 EO Browser) | 可用·原文截图 | https://insights.planet.com/analyze/browser/ |
| satellite-07 | 卫星遥感 | Google Earth Engine | 可用·中文翻译 | https://earthengine.google.com/ |
| satellite-08 | 卫星遥感 | USGS EarthExplorer | 可用·原文截图 | https://earthexplorer.usgs.gov/ |
| satellite-09 | 卫星遥感 | Sentinel Asia | 可用·中文翻译 | https://sentinel-asia.org/ |
| satellite-10 | 卫星遥感 | Copernicus 计划官网 | 可用·中文翻译 | https://www.copernicus.eu/ |
| earthquake-01 | 地震 | USGS M4.5+ 周报 GeoJSON | 可用·中文翻译 | https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson |
| earthquake-02 | 地震 | USGS ComCat 综合目录 | 可用·中文翻译 | https://earthquake.usgs.gov/data/comcat/ |
| earthquake-03 | 地震 | EMSC 欧洲地中海地震中心 | 可用·中文翻译 | https://www.emsc-csem.org/ |
| earthquake-04 | 地震 | Seismic Portal (EMSC 实时) | 可用·中文翻译 | https://www.seismicportal.eu/ |
| earthquake-05 | 地震 | GEOFON 全球地震列表 | 受阻 | https://geofon.gfz.de/eqinfo/list.php |
| earthquake-06 | 地震 | 尼泊尔 NEMRC 地震中心 | 可用·中文翻译 | http://seismonepal.gov.np/ |
| earthquake-07 | 地震 | 中国地震台网中心 | 可用·中文翻译 | https://www.ceic.ac.cn/ |
| earthquake-08 | 地震 | 中国地震局 | 可用·中文翻译 | https://www.cea.gov.cn/ |
| earthquake-09 | 地震 | ISC 国际地震中心 | 可用·中文翻译 | http://www.isc.ac.uk/ |
| earthquake-10 | 地震 | EarthScope (原 IRIS) | 可用·中文翻译 | https://www.earthscope.org/ |
| news-01 | 新闻与现场信息 | Kathmandu Post | 可用·中文翻译 | https://kathmandupost.com/ |
| news-02 | 新闻与现场信息 | The Himalayan Times | 可用·中文翻译 | https://thehimalayantimes.com/ |
| news-03 | 新闻与现场信息 | myRepublica (尼泊尔) | 可用·中文翻译 | https://myrepublica.nagariknetwork.com/ |
| news-04 | 新闻与现场信息 | Explorer's Web | 可用·中文翻译 | https://explorersweb.com/ |
| news-05 | 新闻与现场信息 | The Watchers 灾害新闻 | 可用·中文翻译 | https://watchers.news/ |
| news-06 | 新闻与现场信息 | Nepali Times | 可用·中文翻译 | https://nepalitimes.com/ |
| news-07 | 新闻与现场信息 | Himalayan Rescue Association | 可用·中文翻译 | https://himalayanrescue.org.np/ |
| news-08 | 新闻与现场信息 | SPCC 萨加玛塔污染控制委员会 | 可用·原文截图 | https://spcc.org.np/ |
| news-09 | 新闻与现场信息 | 尼泊尔登山协会 NMA | 可用·中文翻译 | https://nepalmountaineering.org/ |
| news-10 | 新闻与现场信息 | Windy 网络摄像头 | 可用·珠峰地图 | https://www.windy.com/-Webcams/webcams |
| weather-01 | 气象 | 尼泊尔 DHM 水文气象局 | 可用·中文翻译 | https://www.dhm.gov.np/ |
| weather-02 | 气象 | 中国气象局 | 可用·原文截图 | https://www.cma.gov.cn/ |
| weather-03 | 气象 | 中央气象台 | 可用·中文翻译 | http://www.nmc.cn/ |
| weather-04 | 气象 | 中国天气网 | 可用·原文截图 | https://www.weather.com.cn/ |
| weather-05 | 气象 | 印度气象局 IMD | 可用·中文翻译 | https://mausam.imd.gov.in/ |
| weather-06 | 气象 | Windy | 可用·珠峰地图 | https://www.windy.com/ |
| weather-07 | 气象 | Ventusky | 可用·珠峰地图 | https://www.ventusky.com/ |
| weather-08 | 气象 | Mountain-Forecast 珠峰 | 可用·中文翻译 | https://www.mountain-forecast.com/peaks/Mount-Everest |
| weather-09 | 气象 | meteoblue 珠峰峰顶天气 | 可用·中文翻译 | https://www.meteoblue.com/en/weather/week/27.988N86.925E |
| weather-10 | 气象 | Open-Meteo 珠峰坐标预报 | 可用·中文翻译 | https://open-meteo.com/en/docs?latitude=27.9881&longitude=86.925&elevation=8849 |
| flood-01 | 水文洪水 | 尼泊尔 DHM 水文 | 可用·中文翻译 | http://hydrology.gov.np/ |
| flood-02 | 水文洪水 | GloFAS 全球洪水预警 | 可用·珠峰地图 | https://global-flood.emergency.copernicus.eu/ |
| flood-03 | 水文洪水 | GloFAS 洪水地图查看器 | 可用·中文翻译 | https://global-flood.emergency.copernicus.eu/map-viewer/ |
| flood-04 | 水文洪水 | Copernicus EMS 快速制图 | 可用·原文截图 | https://rapidmapping.emergency.copernicus.eu/ |
| flood-05 | 水文洪水 | Google Flood Hub (灾害点放大直达) | 可用·原文截图 | https://sites.research.google/floods/l/20.448859974710246/106.30645967775808/7.8515200970787316/s/103517bf235842b7a9a201ea0d38cdd9 |
| flood-06 | 水文洪水 | Dartmouth 洪水观测台 | 可用·中文翻译 | https://floodobservatory.colorado.edu/ |
| flood-07 | 水文洪水 | 中国水利部 | 可用·原文截图 | http://www.mwr.gov.cn/ |
| flood-08 | 水文洪水 | FloodList 洪水新闻(RSS) | 可用·中文翻译 | https://floodlist.com/feed |
| flood-09 | 水文洪水 | WMO 水文观测 (HydroHub) | 可用·中文翻译 | https://hydrohub.wmo.int/ |
| flood-10 | 水文洪水 | 日本 JMA 气象厅 | 可用·中文翻译 | https://www.jma.go.jp/ |
| landslide-01 | 滑坡泥石流 | NASA Landslides (COOLR) | 可用·中文翻译 | https://landslides.nasa.gov/ |
| landslide-02 | 滑坡泥石流 | USGS 滑坡灾害计划 | 可用·原文截图 | https://www.usgs.gov/programs/landslide-hazards |
| landslide-03 | 滑坡泥石流 | Landslide Blog (AGU) | 可用·中文翻译 | https://blogs.agu.org/landslideblog/ |
| landslide-04 | 滑坡泥石流 | CNR-IRPI 意大利地质水文保护所 | 可用·原文截图 | https://www.irpi.cnr.it/ |
| landslide-05 | 滑坡泥石流 | 中国自然资源部 | 可用·中文翻译 | https://www.mnr.gov.cn/ |
| landslide-06 | 滑坡泥石流 | 中科院成都山地灾害所 | 可用·中文翻译 | http://www.imde.ac.cn/ |
| landslide-07 | 滑坡泥石流 | 中国地质调查局 | 可用·中文翻译 | https://www.cgs.gov.cn/ |
| landslide-08 | 滑坡泥石流 | 中国地质环境监测院 | 可用·中文翻译 | http://www.cigem.cgs.gov.cn/ |
| landslide-09 | 滑坡泥石流 | GeoNet 新西兰地质灾害 | 可用·中文翻译 | https://www.geonet.org.nz/ |
| landslide-10 | 滑坡泥石流 | GeoHazards International | 可用·中文翻译 | https://geohaz.org/ |
| platform-01 | 综合预警平台 | GDACS 全球灾害预警 | 可用·原文截图 | https://www.gdacs.org/ |
| platform-02 | 综合预警平台 | ReliefWeb (OCHA) | 可用·原文截图 | https://reliefweb.int/ |
| platform-03 | 综合预警平台 | 尼泊尔 BIPAD 灾害门户 | 可用·珠峰地图 | https://bipadportal.gov.np/ |
| platform-04 | 综合预警平台 | 尼泊尔 NDRRMA 减灾管理局 | 可用·中文翻译 | https://ndrrma.gov.np/ |
| platform-05 | 综合预警平台 | Copernicus EMS | 可用·中文翻译 | https://emergency.copernicus.eu/ |
| platform-06 | 综合预警平台 | UNDRR 联合国减灾办 | 可用·中文翻译 | https://www.undrr.org/ |
| platform-07 | 综合预警平台 | WMO 世界气象组织 | 可用·中文翻译 | https://wmo.int/ |
| platform-08 | 综合预警平台 | 中国应急管理部 | 可用·中文翻译 | https://www.mem.gov.cn/ |
| platform-09 | 综合预警平台 | ADRC 亚洲减灾中心 | 可用·中文翻译 | https://www.adrc.asia/ |
| platform-10 | 综合预警平台 | 国家预警信息发布中心 | 可用·中文翻译 | http://www.12379.cn/ |
| avalanche-01 | 雪崩冰崩 | avalanche.org (美国雪崩中心联盟) | 可用·中文翻译 | https://avalanche.org/ |
| avalanche-02 | 雪崩冰崩 | EAWS 欧洲雪崩预警服务 | 可用·中文翻译 | https://www.avalanches.org/ |
| avalanche-03 | 雪崩冰崩 | SLF 瑞士雪与雪崩研究所 | 可用·中文翻译 | https://www.slf.ch/ |
| avalanche-04 | 雪崩冰崩 | Avalanche Canada | 可用·原文截图 | https://www.avalanche.ca/ |
| avalanche-05 | 雪崩冰崩 | AvaFrame 开源雪崩模型 | 可用·中文翻译 | https://www.avaframe.org/ |
| avalanche-06 | 雪崩冰崩 | EVK2CNR 喜马拉雅观测站 | 可用·中文翻译 | https://www.evk2cnr.org/ |
| avalanche-07 | 雪崩冰崩 | Colorado Avalanche Info Center | 可用·原文截图 | https://avalanche.state.co.us/ |
| avalanche-08 | 雪崩冰崩 | 喜马拉雅数据库 | 可用·中文翻译 | https://www.himalayandatabase.com/ |
| avalanche-09 | 雪崩冰崩 | 8000ers.com | 可用·中文翻译 | https://www.8000ers.com/ |
| avalanche-10 | 雪崩冰崩 | Alan Arnette 登山博客 | 可用·中文翻译 | https://www.alanarnette.com/ |
