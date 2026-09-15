# Everest-realtime

## 原文截图输出

发送图片直接使用原网页截图，不重绘 JSON/提取文字，不叠加程序标题、found/changed、
获取时间或页脚。长图仅按原像素无损分段。网页截图及已访问详情页截图都保留原站排版。
截图失败或遇到拦截页时，不用数据卡冒充原文。通知正文只保留来源链接和图片。
`config/runtime.json` 的 `original_screenshot_urls` 仅用于指定原文截图页面，不改变采集 URL 或筛选。
CMA API 的截图页面指向官方预警页面；原站拒绝访问时会明确保存截图失败。
以下旧“数据卡”表述以本节的原文截图方式为准。

珠峰、喜马拉雅山与冰川信息采集。102 条原始来源规则集中配置；浏览器渲染、详情页、
翻页、RSS、网络 JSON、地图影像共同形成逐来源记录和图片通知。

## 当前筛选行为

默认 `match_mode: all`：保留取得的内容，不要求“地名词 + 事件词”同时出现。
攀登信息、只有坐标/数值的数据、历史文章不会因为这道关键词门槛被排除。
词表包含珠峰、喜马拉雅山、冰川及 Everest/Himalaya/glacier 等英文词，可在显式筛选时使用。

可选模式 `any` 匹配任一关键词/信号词，`all_groups` 才要求两组同时匹配。
日期、范围和数值过滤都是逐来源显式配置，不自动替用户设置。

## Docker 运行

```powershell
# 首次使用：复制空配置并填写自己的 SendKey；已有 notify.local.json 时不要覆盖
Copy-Item config/notify.example.json config/notify.local.json

docker compose build

# 全量真实采集，生成逐来源截图卡片，不发送
docker compose run --rm --entrypoint python monitor -B monitor.py run --all --notify none

# 指定来源，真实采集并发送带图片的消息
docker compose run --rm --entrypoint python monitor -B monitor.py run --all --source earthquake-01 --notify all --send

# 全部来源逐条发送（受实际渠道配额限制）
docker compose run --rm --entrypoint python monitor -B monitor.py run --all --notify all --send

# 后台持续运行，每 5 分钟检查到期来源，并逐条发送变化
docker compose up -d

docker compose logs --tail 50 monitor
docker compose down
```

Server 酱配置通过 Compose secret 挂载到 `/run/secrets/notify_config`，不进入镜像或 Git。
本机原有配置已保留，不需要重复复制。浏览器采用镜像中的 Chromium，中文使用 Noto CJK 字体。
项目使用独立非 root 用户、init 和 Playwright 官方 seccomp 配置。

需要主机代理时可在本地 `.env` 中配置 `EVEREST_DOCKER_PROXY`，例如可从容器访问的
`http://host.docker.internal:端口`。`.env` 不提交。

## 数据在哪里

容器 `/app/data` 持久化到本机 `data-docker/`。每轮位于：

```text
data-docker/runs/<运行ID>/
  index.html                       逐来源图片和内容
  status.json                      运行状态、退出码
  <rule_id>/result.json             页面、文章、网络数据、影像、错误、待访问 URL
  <rule_id>/response.bin            原始响应
  <rule_id>/rendered.html           浏览器渲染后的 HTML
  <rule_id>/page.png                实际网页截图
  <rule_id>/page-02/...              下一页、详情页、RSS 或搜索结果
  <rule_id>/network-*.bin           浏览器取得的结构化数据
  <rule_id>/map-*.png / wms.png     地图或卫星影像
  <rule_id>/card-*.png              分页数据卡
```

`source_time` 未知时保留未知，`retrieved_at` 为获取时间。`article_records` 保存能够从来源
提取的文章链接和发布时间，原文日期未提供则为空。

`found` 代表取得内容/数据，不代表发现灾害。`not_found` 代表本次解析后为空。
`unknown` 代表未成功取得可用来源数据。`coverage: partial` 表示存在获取错误或尚未遍历完的链接。

## 各类来源怎样获取

| 类型 | 方法 |
| --- | --- |
| HTML | HTTP 原始响应 + Chromium 渲染 DOM，两者都留存；筛选读取渲染后的正文 |
| 新闻详情/分页 | 自动发现文章链接、`rel=next`/下一页、公开订阅链接和 GET 搜索表单 |
| JSON/GeoJSON | 解析独立记录；支持 JSON 路径、坐标范围、数值和时间条件 |
| RSS/Atom | 逐文章保存链接/发布时间，访问文章详情 |
| 动态接口 | 保存浏览器实际请求得到的 JSON 响应，内容进入同一提取链路 |
| 地图门户 | 保存浏览器实际加载的 JSON 和地图图片，保留请求 URL 与影像 |
| NASA Worldview | 另接 GIBS WMS：读取 GetCapabilities 中的图层默认时间，再 GetMap 获取指定范围影像 |
| NICT | 页面动态采集之外，直接读取其 latest.json 帧元数据 |

没有伪造不存在的站点 API；需要账号、许可或服务端拒绝的接口仍会记录失败。
这是信息采集，不是物理灾害分类器。地图图片不自动解释成洪水、冰崩或地表位移。

## 配置

- `config/sources.json`：102 条原始来源字段、启用开关、轮询频率和可选筛选。
- `config/acquisition.json`：逐来源显式数据接口及 WMS 参数。
- `config/runtime.json`：浏览器、详情/翻页/搜索开关、采集预算、图片和发送间隔。
- `config/notify.local.json`：本地私密渠道配置。

关键词模式示例：

```json
{"watch": {"match_mode": "any", "filter_keywords": ["喜马拉雅山", "冰川", "glacier"], "signal_keywords": []}}
```

只有明确需要过滤时，才给某个 API 配置结构化条件。例如：

```json
{"watch": {"structured": {
  "bbox": [85, 27, 88, 29],
  "coordinates_path": "geometry.coordinates",
  "numeric": {"properties.mag": {"min": 4}},
  "time_path": "properties.time",
  "after": "2026-01-01T00:00:00Z"
}}}
```

采集预算可调：默认每来源每轮 6 页、最多 30 个网络 JSON 响应及 4 个地图图片。
它们用于避免无限翻页；超出部分明确保存在 `pending_urls`，不声称抓完整站。
原始响应单次 5 MB，卡片展示上限 20,000 字符，完整已提取内容保存在 JSON/HTML。

## 通知

每个来源单独一条图片消息，可包含多个分页卡片。卡片或图床失败则阻止该条发送，不降级成纯文字。
Server 酱至少间隔 3 秒，接口拒绝后停止本轮发送。`accepted` 表示服务端接收，不表示手机已读。
超时后的 `unconfirmed` 不自动重发；崩溃留下的 `sending` 同样保留待核实，避免重复。
只派送指定运行批次，通知绑定创建时的 SendKey 摘要。

## 验证

```powershell
C:\Python314\python.exe -B -m pytest -q tests
docker compose run --rm --entrypoint python monitor -B -m pytest -q tests
```

## 原始资料与依据

原始 102 条规则、101 个 URL 及额外接口资料保存在 `data-sources/`。
原项目完整备份在本机 `E:\Everest-realtime-preserved-20260915T040245Z`，备份和原通知记录不上传 Git。

- Playwright Docker：https://playwright.dev/python/docs/docker
- NASA GIBS：https://nasa-gibs.github.io/gibs-api-docs/access-basics/
- USGS FDSN：https://earthquake.usgs.gov/fdsnws/event/1/
- Server 酱：https://sct.ftqq.com/docs/integrations/python/
- Compose secrets：https://docs.docker.com/compose/how-tos/use-secrets/
