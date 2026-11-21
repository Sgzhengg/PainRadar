# painradar-crawler

PainRadar 的 MediaCrawler 桥接服务：把不支持 HTTP 的 MediaCrawler 包成
**异步任务 API**，供 Zeabur 同项目内的 PainRadar 调用。

一个容器里同时包含：任务 API、MediaCrawler 源码、Playwright/Chromium。
**不需要再单独部署 MediaCrawler 服务。**

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/crawl` | `{platform, keywords, max_notes, cookies}` → `{task_id}` |
| GET | `/api/tasks/{id}` | `{status, stage, progress, need_login, error}` |
| GET | `/api/tasks/{id}/results` | 帖子 + 评论 JSON 数组 |
| GET | `/health` | 存活检查（免鉴权） |

设置 `MEDIACRAWLER_API_TOKEN` 后，除 `/health` 外都要
`Authorization: Bearer <token>`。任务状态：`queued / running / completed / failed`。

## 1. 准备 MediaCrawler 源码

Dockerfile 在**构建阶段自动 clone** MediaCrawler 到 /app/MediaCrawler，
所以第三方仓库不需要提交进 Git（MediaCrawler/ 已在 .gitignore 与
.dockerignore 中）。

锁定版本（推荐，避免上游改 CLI 导致构建后行为漂移）：

`ash
docker build -t painradar-crawler \
  --build-arg MEDIACRAWLER_REF=<commit-or-tag> .
`

Zeabur 上在服务设置里加构建参数 MEDIACRAWLER_REF=<commit> 即可。

只在本地不用 Docker 跑时，才需要手动 clone：

`ash
cd painradar-crawler
git clone --depth 1 https://github.com/NanmiCoder/MediaCrawler MediaCrawler
`

> MediaCrawler 各版本 CLI 参数不同，若默认命令跑不通，改
> `CRAWLER_CMD_TEMPLATE`（见下）而不是改代码。

## 2. 本地跑

```bash
pip install -r requirements.txt
export MEDIACRAWLER_HOME=./MediaCrawler
export COOKIE_DIR=./data/cookies
export TASK_DB=./data/tasks.db
export RESULT_DIR=./data/results
export MEDIACRAWLER_API_TOKEN=dev-token
export ENABLE_CDP_MODE=False HEADLESS=True
uvicorn app:app --host 0.0.0.0 --port 8080
```

```bash
curl -X POST http://127.0.0.1:8080/api/crawl \
  -H "Authorization: Bearer dev-token" -H "Content-Type: application/json" \
  -d '{"platform":"xhs","keywords":["PDF 转换"],"max_notes":10}'
```

## 3. 部署到 Zeabur

1. 把本目录（含 `MediaCrawler/`）推到独立仓库，或用 monorepo 子目录构建；
2. Zeabur → 同一个 Project → **Add Service** → 部署该仓库；
3. 服务名设为 **`mediacrawler`**（决定内网域名）；
4. 端口 **8080**；**不要**绑定公网域名；
5. 资源 ≥ **1 CPU / 1 GB**（Chromium 吃内存）；
6. 挂卷到 **`/data`**（Cookie、任务库、结果都在这里）；
7. 环境变量：

| 变量 | 必填 | 说明 |
|---|---|---|
| `MEDIACRAWLER_API_TOKEN` | ✅ | 与 PainRadar 保持一致 |
| `ENABLE_CDP_MODE` | ✅ | `False`（容器无桌面） |
| `HEADLESS` | ✅ | `True` |
| `PLATFORM_COOKIES_XHS` | 按平台 | 小红书 Cookie |
| `PLATFORM_COOKIES_DY` | 按平台 | 抖音 |
| `PLATFORM_COOKIES_BILI` | 按平台 | B站 |
| `PLATFORM_COOKIES_ZHIHU` | 按平台 | 知乎 |
| `CRAWLER_CMD_TEMPLATE` | 可选 | 默认 `python main.py --platform {platform} --lt cookie --type search --keywords {keywords}` |
| `CRAWLER_TIMEOUT` | 可选 | 默认 1200 秒 |
| `TASK_CONCURRENCY` | 可选 | 建议 1–2（当前实现按请求起线程，未限流） |

## 4. Cookie 怎么给

两种方式，优先用请求里的临时 Cookie（PainRadar 抓取弹窗可填）：

1. **请求体**：`"cookies": "a=1; b=2"` 或 `[{name,value,domain,path}]`；
2. **环境变量**：`PLATFORM_COOKIES_XHS=...`。

服务会把 Cookie 持久化到 `/data/cookies/<platform>.json`，并复制到
`MediaCrawler/browser_data/<platform>_cookies.json`（MediaCrawler 常见读取路径）。
如果你的 MediaCrawler 版本读取路径不同，改 `runner.py` 的 `_browser_cookie_path`。

Cookie 失效时任务返回 `need_login: true`，PainRadar 会提示更新 Cookie。

## 5. 结果格式

`/results` 返回：

```json
[{
  "note_id": "n1",
  "title": "受够了 Smallpdf 的订阅",
  "desc": "正文摘要",
  "url": "https://...",
  "liked_count": 342,
  "comments": [
    {"comment_id":"c1","content":"取消入口找不到","like_count":286,
     "sub_comments":[{"comment_id":"c1r1","content":"同求买断","like_count":74}]}
  ]
}]
```

`runner.collect` 会：
- 扫描 `CRAWLER_DATA_DIR` 下最近修改的 JSON；
- 合并「笔记文件」和「评论文件」，按 `note_id` 挂到笔记下；
- 识别不同平台的 id 字段（`note_id/aweme_id/bvid/aid/question_id`）；
- 没评论的笔记会被丢弃（对 PainRadar 无价值）。

## 6. PainRadar 侧

```env
MEDIACRAWLER_API_URL=http://mediacrawler.zeabur.internal:8080
MEDIACRAWLER_API_TOKEN=同一个 token
```

然后：

```bash
python run.py doctor
# crawler ping : ok
```

## 7. 已知限制

1. **版本漂移**：MediaCrawler 的 CLI/输出目录经常变；默认命令与
   `browser_data` Cookie 路径按常见版本写，跑不通时改环境变量或两处小函数即可；
2. **登录**：无头容器不能扫码，必须注入 Cookie；Cookie 过期只能手动更新；
3. **风控**：机房 IP 抓小红书/抖音可能被限流，这是平台侧限制；
4. **并发**：当前按请求起线程，没有队列限流；单容器建议串行；
5. **合规**：MediaCrawler 仅用于学习研究，请遵守平台 ToS 与当地法律，不要公开分发抓取数据。
