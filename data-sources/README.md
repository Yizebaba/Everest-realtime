# 数据源保全清单

全部数据来源于删除前的原项目，不是重新搜索后替换的列表。

- `hazard_sites.json`：原始 102 条规则、101 个 URL、10 类，保留原字段。
- `sources.json`：标准化可读清单，补充分类、启用开关和轮询间隔。
- `regions.json`：中国、台湾地区、珠峰区域地震查询范围和原多边形。
- `source-constants.json`：从原 Python 模块提取的字面量配置，包括 NICT 最新帧/瓦片地址、Open-Meteo 模型 URL、GIBS 模板及图层、区域地震接口、地图/搜索 PLAN 等。
- `endpoint-inventory.json`：代码中 URL 的文件和行号索引。包括数据端点、地图、搜索和通知基础设施；不能把每个 URL 都算成独立观测来源。

完整原项目备份：`E:\Everest-realtime-preserved-20260915T040245Z\project`。
其兄弟文件 `manifest.json` 保存 1,881 个文件的 SHA-256，用于核验完整性。

新程序执行清单位于 `../config/sources.json`，此目录作为原始资料保全。
代码内的额外接口均已保留。当前额外接入 NICT latest.json 和 NASA GIBS WMS，
参数见 `../config/acquisition.json`；其他地图支持浏览器网络数据采集。
NICT 裁峰、GIBS 像素变化解释、专用区域地震消费者等旧处理算法没有照搬，
不能把仅保留的接口声明为已接入，也不把影像变化解释为灾害。
