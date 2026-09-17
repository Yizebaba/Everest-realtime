# 工业级复杂事件处理（CEP）多维规则控制总表 (Matrix Control Center)

本文档是系统判定的终极控制台。**尚未上传 GitHub**，总调度去重已旁路。
系统包含四大核心引擎：
1. **OpenCEP**：严格时序序列（SEQ）、滑动时间窗口、物理量演进趋势判定。
2. **LightCEP**：多维条件布尔过滤、边界值断言、正向/负向词库匹配。
3. **Siddhi**：流式时间窗口聚合（AVG/MAX/MIN/COUNT/SUM/DELTA 突变率）。
4. **Sigma**：工业与安全级威胁特征签名、多维度上下文交叉验证。

---

## 一、地震监测流（Seismic Event Stream）全要素控制矩阵

### 1.1 震级与能量阶梯（Magnitude Thresholds）
- [ ] 01. 环喜马拉雅核心带微震感知（西藏/尼泊尔/印度北部）：M >= [ 2.0 ]
- [ ] 02. 喜马拉雅中强震危险门槛（定日/日喀则/加德满都）：M >= [ 2.0 ]
- [ ] 03. 破坏性强震破坏门槛（可引发雪崩/滑坡）：M >= [ 2 ]
- [ ] 04. 全球特大破坏性强震预警：M >= [5 ]

### 1.2 震源深度约束（Focal Depth Constraint）
- [ ] 05. 极浅源危险地震（破坏力极大）：深度 <= [ 0.5 ] km
- [ ] 06. 浅源构造地震（典型地壳破裂）：深度 <= [ 1 ] km
- [ ] 07. 深源俯冲地震（通常不触发次生灾害）：深度 >= [ 100.0 ] km 则静默不报

### 1.3 空间地理距离测算（Spatial Radius from Everest）
- [ ] 08. 珠峰特级核心圈（8848m 为中心）：半径 <= [ 50.0 ] km 内发生任意 M>=2.5 地震强制报警
- [ ] 09. 喜马拉雅断裂带近场圈：半径 <= [ 200.0 ] km 内发生 M>=4.0 地震强制报警
- [ ] 10. 远场强震影响圈：半径 <= [ 1000.0 ] km 内发生 M>=6.5 特大强震强制报警

### 1.4 时序前震群与余震演进（OpenCEP Sequential Pattern）
- [ ] 11. 前震密集加速序列（SEQ）：在 [ 30 ] 分钟内，连续发生 [ 3 ] 次地震，且发震间隔越来越短
- [ ] 12. 震级阶梯式攀升序列（Ascending）：在 [ 60 ] 分钟内，连续 [ 3 ] 次地震满足 M1 < M2 < M3
- [ ] 13. 强震余震高频衰减监测：主震发生后 [ 120 ] 分钟内余震频次监控

### 1.5 流式滑动窗口统计（Siddhi Streaming Aggregation）
- [ ] 14. 区域地震频发流聚合：滑动窗口 [ 15 ] 分钟内，累计地震次数 COUNT(*) >= [ 3 ] 次
- [ ] 15. 能量释放突增流：滑动窗口 [ 60 ] 分钟内，震级能量积分累计突增达到黄色预警

### 1.6 多源交叉印证（Cross-Network Join）
- [ ] 16. USGS 与 GEOFON 双源在 [ 5 ] 分钟内同时上报同一震中（误差<50km）才判定真实触发

---

## 二、高海拔极限气象流（High-Altitude Meteorology）全要素控制矩阵

### 2.1 峰顶高空阵风与风暴（Wind & Gust Constraints）
- [ ] 17. 冲顶窗口关闭预警（严重风暴）：最大阵风 >= [ 20.0 ] km/h
- [ ] 18. 高海拔大风警报：最大阵风 >= [ 15.0 ] km/h
- [ ] 19. 持续风力超标：持续 10 米风速 >= [ 10.0 ] km/h
- [ ] 20. 风向突变切变警报：相邻采样风向偏转角度 >= [ 65.0 ] 度

### 2.2 极限低温与体感失温（Temperature & Windchill）
- [ ] 21. 峰顶极限严寒预警：实测气温 <= [ -30.0 ] ℃
- [ ] 22. 高空冷害门槛：实测气温 <= [ -22.0 ] ℃
- [ ] 23. 体感暴跌预警（Wind Chill Factor）：体感温度 <= [ -20.0 ] ℃

### 2.3 气压骤降与气压场斜率（Barometric Pressure Drop）
- [ ] 24. 暴风雪前兆（气压暴跌率 dp/dt）：在 [ 3 ] 分钟内，地表气压下降 >= [ 3.0 ] hPa
- [ ] 25. 极限低压低氧态势：峰顶地表气压 <= [ 340.0 ] hPa（氧含量极低）

### 2.4 降雪、湿度与视程阻碍（Precipitation & Visibility）
- [ ] 26. 暴雪高危门槛：累计降雪量/降水量 >= [ 5.0 ] mm
- [ ] 27. 高空云包雾封（云量与湿度）：空气相对湿度 >= [ 70.0 ] %

### 2.5 气象复杂复合演进（OpenCEP & Siddhi Multi-Metric Cascade）
- [ ] 28. 极端天气并发序列（Wind+Temp+Press）：风速上升 AND 气温暴跌 AND 气压骤降三项同时发生
- [ ] 29. 连续恶化时序链：在 [ 5 ] 分钟内，风力连续 [ 3 ] 次采样持续走高（V1 < V2 < V3）
- [ ] 30. 极端低温维持时长：连续 [ 3 ] 次采样气温均低于 -10℃

---

## 三、冰川、冰崩与冰湖溃决流（Glacier & GLOF Stream）控制矩阵

### 3.1 冰湖溃决（GLOF）突发预警
- [ ] 31. 冰湖水位急速突变率：河流水位在 [ 1 ] 分钟内较历史均值上涨幅度 >= [ 15.0 ] %
- [ ] 32. 测站超警戒水位线：下游水文站读数达到或超过标定红色警戒线（Danger Level）
- [ ] 33. 连续超警戒确认：在 [ 30 ] 分钟内，连续 [ 2 ] 次读数均未退回安全线以下

### 3.2 冰崩与冰川跃动（Icefall & Glacier Surge）
- [ ] 34. 昆布冰川核心区活动警报：命中关键词 [ khumbu icefall, serac collapse, crevasse movement, 昆布冰崩, 冰裂缝 ]
- [ ] 35. 冰川物质平衡与表面高程剧变：命中专业冰川学术监测异常通报

---

## 四、地质灾害流（Landslide & Debris Flow）控制矩阵

### 4.1 边坡失稳与泥石流（Slope Failure）
- [ ] 36. 降雨诱发滑坡临界指标：0.5小时累计降水 >= [ 1.0 ] mm 叠加山体位移通报
- [ ] 37. 交通动脉与口岸塌方阻断：命中关键词 [ 中尼公路, 友谊桥, 吉隆口岸, 樟木, 塌方, 封路, 通行中断, highway blocked ]
- [ ] 38. 边坡雷达/卫星形变位移报警：InSAR 地表形变速率异常通报

---

## 五、突发搜救与现场情报流（News & Mountain Rescue）控制矩阵

### 5.1 现场人员险情与搜救（Life Safety Alerts）
- [ ] 39. 高山遇难/致命险情第一优先级：命中词 [ dead, dies, died, fatal, killed, body recovered, 遇难, 死亡, 遗体 ]
- [ ] 40. 紧急被困与搜救活动：命中词 [ rescue operation, trapped, missing, evacuated, distress, 被困, 失联, 搜救, 救援 ]
- [ ] 41. 登顶季事故与冻伤通报：命中词 [ frostbite, ams, snow blindness, hapa, hace, 严重冻伤, 脑水肿, 肺水肿 ]

### 5.2 权威机构与登山管理通报（Official Mountain Administration）
- [ ] 42. 封山与登山许可暂停通报：尼泊尔旅游局或西藏登协发布攀登暂停、线路封闭令
- [ ] 43. 昆布修路队（Icefall Doctors）线路通报：修路队搭建梯子受阻、路线改道公报

### 5.3 负向防骚扰排除字典（Negative Noise Exclusions - 命中即静默）
- [ ] 44. 协会人事政治杂讯：排除词 [ election, agm, general meeting, committee, executive, 换届, 选举, 代表大会, 理事会 ]
- [ ] 45. 赞助与商业通稿杂讯：排除词 [ sponsor, partnership, brand, discount, 赞助, 商务合作, 礼品, 抽奖 ]
- [ ] 46. 纪念与历史旧闻：排除词 [ anniversary, golden jubilee, 50 years, in memory, 周年, 金禧, 纪念, 历史回顾 ]
- [ ] 47. 纳税与财务表格：排除词 [ taxpayer, revenue, budget, financial report, 纳税, 财政预算, 财报 ]

---

## 六、科研情报与学术文献流（Scientific & Academic Stream）控制矩阵

### 48. 顶级冰川期刊最新成果确认（The Cryosphere / Nature Geoscience）
- [ ] 48. 权威论文发布判定：必须同时包含 [ 论文标题 + DOI识别码 + 摘要关键词(Himalaya/Everest/Glacier) ]

### 49. 国际遥感数据集更新发布（NASA CMR / NSIDC）
- [ ] 49. 新增数据集入库：捕获到包含版本修订号、数据时间戳的新数据集上线

---

## 七、四大引擎决策表决机制（Arbitration & Voting Architecture）

请在下方选择系统执行微信推送的终极表决模式：
- [a ] **模式 A：单引擎敏锐触发（Fast-Trigger）**：任意 1 个引擎判定成立即触发截图推送（适合全量观察打擂）。
- [ ] **模式 B：双引擎联合投票（Dual-Engine Consensus）**：必须至少 2 个引擎同时达成共识才推送（大幅压制误报）。
- [ ] **模式 C：三引擎严苛共识（Tri-Engine Strict）**：必须 3 个或以上引擎一致裁定为真实险情才推送（只报大事件）。
- [ ] **模式 D：分工专项模式（Domain Specialized）**：气象/地震归 OpenCEP+Siddhi 裁定，新闻/灾情归 LightCEP+Sigma 裁定。

---

## 三、填写后如何生效？
您只需在记事本中勾选 `[X]` 或修改方括号里的数值，按 `Ctrl + S` 保存关闭，告诉我一声即可！
