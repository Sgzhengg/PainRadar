# 在 Zeabur 上一体化私有部署（PainRadar + MediaCrawler）

> 目标：一个 Zeabur Project 里跑两个服务，内网互通；SQLite 放持久化卷；
> 整套只给自己用，公网入口有密码锁。**不再需要 Cloudflare Workers / D1。**

## 0. 架构

```
你的浏览器
   │  https://painradar.zeabur.app（Basic Auth / 30 天 Cookie）
   ▼
Zeabur Project
 ├── painradar      Python/FastAPI + 静态前端（8080）
 │     └── /app/var  ← 持久化卷（SQLite + 上传/临时数据）
 └── mediacrawler   MediaCrawler HTTP 服务（内网 8080）
        ▲
        └── painradar 通过 http://mediacrawler.zeabur.internal:8080 调用
```

同项目内网直连：不走公网、不加域名、延迟更低，采集服务无需暴露到公网。

## 1. 部署 PainRadar

1. Zeabur → **Create Project** → **Deploy from GitHub** → 选择本仓库；
2. 服务类型选 **Dockerfile**（仓库根目录已提供 `Dockerfile`）；
3. 端口填 **8080**（Dockerfile 已 EXPOSE）；
4. **Storage → Add Volume**：
   - Mount Path：`/app/var`
   - 大小：1 GB 起步（SQLite + 报告足够）
5. 环境变量（Settings → Environment）：

| 变量 | 必填 | 说明 |
|---|---|---|
| `PAINRADAR_DATA_DIR` | ✅ | 固定 `/app/var`，与卷挂载路径一致 |
| `PAINRADAR_ADMIN_PASSWORD` | ✅ | 你的访问密码；**不设置则公网裸奔** |
| `PAINRADAR_STORE` | 建议 | `local`（默认，SQLite） |
| `MEDIACRAWLER_API_URL` | ✅ | `http://mediacrawler.zeabur.internal:8080` |
| `MEDIACRAWLER_API_TOKEN` | ✅ | 与采集服务一致的 Bearer Token |
| `PAINRADAR_LLM_BASE_URL` | 可选 | 如 `https://api.deepseek.com/v1` |
| `PAINRADAR_LLM_API_KEY` | 可选 | 大模型 Key（不填则用规则抽取器） |
| `PAINRADAR_LLM_MODEL` | 可选 | 如 `deepseek-chat` |

6. 部署完成后打开 `https://<你的域名>/`，浏览器会弹 Basic Auth：
   用户名随意，**密码填 `PAINRADAR_ADMIN_PASSWORD`**。登录成功后 30 天内免密。

## 2. 部署 MediaCrawler（同项目）

1. 同一个 Project → **Add Service** → 部署你封装好的 MediaCrawler 镜像/仓库；
2. 服务名建议就叫 **`mediacrawler`**（内网域名由此生成）；
3. 端口 **8080**（或你镜像实际端口，同步改 `MEDIACRAWLER_API_URL`）；
4. 环境变量：

```env
ENABLE_CDP_MODE=False       # 容器内无桌面，必须关闭
HEADLESS=True
MEDIACRAWLER_API_TOKEN=换成随机长字符串   # 与 PainRadar 保持一致
PLATFORM_COOKIES_XHS=...    # 小红书 Cookie
PLATFORM_COOKIES_DY=...     # 抖音
PLATFORM_COOKIES_BILI=...   # B站
PLATFORM_COOKIES_ZHIHU=...  # 知乎
TASK_CONCURRENCY=2
```

5. **不要**给 mediacrawler 绑定公网域名；PainRadar 走内网即可。

采集服务需要实现 4 个接口（契约见下节）。如果它返回 401/403 或
`need_login: true`，PainRadar 的任务状态会提示“登录态已过期”。

## 3. 内网地址怎么写

| 场景 | 地址 |
|---|---|
| 同项目服务间 | `http://mediacrawler.zeabur.internal:8080` |
| 同项目不同环境 | `http://mediacrawler.<env>.zeabur.internal:8080` |
| 本地开发 | `http://127.0.0.1:8080` |

`zeabur.internal` 只在内网可达，外网解析不到，适合放采集服务和内部 API。

## 4. 持久化卷与数据安全

- 挂载点必须是 **`/app/var`**，并设置 `PAINRADAR_DATA_DIR=/app/var`；
- 所有 SQLite 数据库、`var/*.db`、临时抓取结果都在这里；
- 重新部署代码不会删除卷；只有你手动删除 Volume 才会丢数据；
- 备份：在 Zeabur 控制台下载卷，或执行
  `sqlite3 /app/var/painradar.db ".backup '/app/var/backup-$(date +%F).db'"`。

> 不要同时挂载多个服务到同一个 SQLite 文件；SQLite 只适合单实例写入。

## 5. 访问锁行为

| 请求 | 未登录 | 已登录 |
|---|---|---|
| `/api/health` | ✅ 公开 | ✅ |
| `/static/*` | ✅ 公开（无数据） | ✅ |
| 页面 `/` | 401 Basic 挑战 | ✅ |
| `/api/*`（含抓取、运行） | 401 JSON | ✅ |
| `/api/logout` | 401 | 清 Cookie |

- Cookie 名 `pr_auth`，HttpOnly，30 天；
- 改密码后旧 Cookie 立即失效（token 由密码派生）；
- 本地开发不设置 `PAINRADAR_ADMIN_PASSWORD` 即可免密。

## 6. 验证

```bash
# 容器内/本地
python run.py doctor
# store mode   : local (SQLite)
# data dir     : /app/var (writable=True)
# admin lock   : enabled
# crawler ping : ok
```

线上自检：

```bash
curl -u me:你的密码 https://<域名>/api/health
curl -u me:你的密码 https://<域名>/api/runs
```

## 7. 采集服务接口契约

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/crawl` | `{platform, keywords, max_notes, cookies}` → `{task_id}` |
| GET | `/api/tasks/{id}` | `{status, progress, need_login, error}` |
| GET | `/api/tasks/{id}/results` | 帖子+评论 JSON 数组 |
| GET | `/health` | 存活检查（免鉴权） |

鉴权：`Authorization: Bearer $MEDIACRAWLER_API_TOKEN`。

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| 打开页面一直弹密码框 | 确认 `PAINRADAR_ADMIN_PASSWORD` 已设置且与服务一致 |
| 登录后又要求登录 | 检查是否 HTTPS；`secure` Cookie 在 HTTP 下不会保存 |
| 重启后数据没了 | Volume 没挂到 `/app/var`，或 `PAINRADAR_DATA_DIR` 不一致 |
| 抓取任务失败 | 先用 `curl` 测内网地址；再看 mediacrawler 日志与 Cookie |
| 内网域名解析失败 | 服务名是否就是 `mediacrawler`，端口是否 8080 |

## 9. 已归档的 Cloudflare 方案

`docs/archive/` 里保留了旧的 Workers/D1 配置，仅作历史参考，当前架构不需要。
`PAINRADAR_STORE=d1` 与 `CloudflareD1Store` 代码仍在，但不再推荐。
