# 在 Zeabur 部署 MediaCrawler 采集服务

> 目标：把浏览器采集放进一个独立容器，PainRadar 只通过 HTTP 调度它。
> Zeabur 负责常驻运行、Cookie 与无头浏览器；Cloudflare / 本地只发任务、取结果。

## 1. 为什么需要这一层

MediaCrawler 依赖 Playwright/Chromium，不能跑在 Cloudflare Worker 里，也不适合塞进
FastAPI 进程（内存、超时、登录态都会互相影响）。拆成独立服务后：

- 抓取是**异步任务**：触发立即返回 `task_id`，不会触发网关超时；
- Cookie 只存在采集服务，不进入前端；
- PainRadar 侧只依赖 4 个接口。

## 2. 服务契约（PainRadar 只认这 4 个接口）

所有接口都要求：

```
Authorization: Bearer $MEDIACRAWLER_API_TOKEN
```

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/crawl` | 启动任务，返回 `{task_id, status}` |
| GET | `/api/tasks/{task_id}` | 查询 `{status, progress, message, need_login, result_url}` |
| GET | `/api/tasks/{task_id}/results` | 完成后返回帖子/评论 JSON 数组 |
| GET | `/health` | 存活检查（无需鉴权） |

`status` 取值：`queued` / `running` / `completed` / `failed`。
Cookie 失效时返回 `need_login: true`（或 401/403），PainRadar 会在任务状态里提示
“登录态已过期”。

请求示例：

```bash
curl -X POST https://your-crawler.zeabur.app/api/crawl \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"platform":"xhs","keywords":["PDF 转换"],"max_notes":50}'
# {"task_id":"t_123","status":"queued"}
```

## 3. Zeabur 服务实现要点

1. **关闭 CDP 图形模式**：环境变量 `ENABLE_CDP_MODE=False`
   （容器里没有桌面，开启只会卡住）。
2. **无头浏览器**：`HEADLESS=True`；Dockerfile 安装 Chromium 依赖
   （`playwright install --with-deps chromium`）。
3. **异步执行**：`POST /api/crawl` 只写任务表并返回，后台线程/进程池跑 MediaCrawler；
   `GET /api/tasks/{id}` 读状态。不要在处理函数里同步等待抓取结束。
4. **结果落盘转 JSON**：MediaCrawler 默认写 `data/*.json`，任务完成后读文件、
   统一成 PainRadar 能识别的结构（见第 4 节），由 `/results` 返回。
5. **Cookie 注入**：服务端保存平台 Cookie；请求里可用 `cookies` 字段临时覆盖。
   Cookie 失效时任务标记 `need_login`，不要静默重试。
6. **并发与配额**：单容器建议 2–3 个并发任务；`max_notes` 上限 1000。

推荐环境变量：

```env
ENABLE_CDP_MODE=False
HEADLESS=True
MEDIACRAWLER_API_TOKEN=change-me
PLATFORM_COOKIES_XHS=...
PLATFORM_COOKIES_DY=...
TASK_CONCURRENCY=2
```

## 4. 结果格式

`/results` 返回数组，每条是“帖子 + 评论”：

```json
[{
  "note_id": "n1",
  "title": "受够了 Smallpdf 的订阅",
  "desc": "正文摘要",
  "url": "https://www.xiaohongshu.com/...",
  "liked_count": 342,
  "comments": [
    {"comment_id": "c1", "content": "取消入口找不到", "like_count": 286,
     "sub_comments": [{"comment_id": "c1r1", "content": "同求买断", "like_count": 74}]}
  ]
}]
```

字段名不一致时，PainRadar 侧可用 `--field-map` 覆盖（JSON: `{"id":"note_id",...}`）。
清洗、上下文组装、降噪由 `connectors/mediacrawler.py` 统一完成。

## 5. PainRadar 侧配置

```env
MEDIACRAWLER_API_URL=https://your-crawler.zeabur.app
MEDIACRAWLER_API_TOKEN=change-me
REMOTE_CRAWL_TIMEOUT=900
REMOTE_CRAWL_INTERVAL=3
```

验证：

```bash
python run.py doctor
# crawler url  : https://your-crawler.zeabur.app
# crawler token: configured
# crawler ping : ok
```

WebUI 顶栏「＋ 抓取新商机」→「云端全网抓取」即可触发；
任务阶段会依次显示：Zeabur 抓取中 → 清洗入库中 → AI 提纯聚类中。

## 6. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `need_login` | Cookie 过期 / 风控 | 更新平台 Cookie，重新触发 |
| 任务一直 `queued` | 并发已满 | 降低触发频率或调大 `TASK_CONCURRENCY` |
| `results` 为空 | 关键词太窄 | 放宽关键词、增加 `max_notes` |
| 401 | token 不一致 | 同时更新 Zeabur 与 PainRadar 的 `MEDIACRAWLER_API_TOKEN` |
