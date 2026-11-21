# 部署到 Cloudflare（前端 + 边缘层）

> 先说明一个硬约束：**Cloudflare Workers 不能运行 Python/FastAPI**。
> 因此本项目采用“Cloudflare 托管静态前端 + 边缘代理/健康检查，Python API 与
> 爬虫分别部署在 Zeabur”的分层方式；`CloudflareD1Store` 让 Python API 可以
> 直接读写 D1（无本地磁盘依赖）。

## 1. 架构

```
浏览器
  │
  ▼
Cloudflare Worker  ── /api/health（边缘直接返回）
  │  静态资源 [assets]
  │  其余 /api/* 反向代理
  ▼
Python API（Zeabur 容器，FastAPI）
  ├── D1（Cloudflare REST API）  ← PAINRADAR_STORE=d1
  └── MediaCrawler 微服务（Zeabur）
```

可选：Worker 绑定 D1 后，`/api/runs` 可只读直出（`EDGE_READS=d1`），减少回源。

## 2. 文件

| 文件 | 作用 |
|---|---|
| `wrangler.toml` | Worker 名称、静态资源目录、`API_ORIGIN`、可选 D1 绑定 |
| `cloudflare/worker.js` | 静态资源 + `/api/health` + `/api/*` 代理 + 可选 D1 只读 |
| `src/painradar/store.py` | `SQLiteStore` / `CloudflareD1Store` / `Store()` 工厂 |

## 3. 必填环境变量

### Cloudflare Worker

| 变量 | 说明 |
|---|---|
| `API_ORIGIN` | Python API 地址，如 `https://painradar-api.zeabur.app` |
| `EDGE_READS` | 可选，`d1` 时 `/api/runs` 直接读 D1 |
| `DB`（binding） | 可选，D1 数据库绑定 |

### Python API（Zeabur）

| 变量 | 说明 |
|---|---|
| `PAINRADAR_STORE` | `local`（默认）或 `d1` |
| `CLOUDFLARE_ACCOUNT_ID` | D1 所在账号 |
| `CLOUDFLARE_D1_DATABASE_ID` | D1 数据库 ID |
| `CLOUDFLARE_API_TOKEN` | 具备 D1 读写权限的 API Token |
| `MEDIACRAWLER_API_URL` | 采集服务地址 |
| `MEDIACRAWLER_API_TOKEN` | 采集服务 Bearer Token |
| `PAINRADAR_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | LLM 抽取器（可选） |

## 4. 部署步骤

```bash
# 1) 建 D1
npx wrangler d1 create painradar
# 把输出的 database_id 填进 wrangler.toml（或只给 Python API 用）

# 2) 建表：本地先生成 schema，再在 D1 执行
python -c "from painradar.store import SCHEMA; print(SCHEMA)" > var/schema.sql
npx wrangler d1 execute painradar --remote --file=var/schema.sql

# 3) 部署静态前端 + 边缘代理
npx wrangler deploy

# 4) 在 Zeabur 部署 Python API
#    启动命令（D1 模式下 db 参数仅作占位）：
python run.py serve --db d1:main --host 0.0.0.0 --port 8000
#    环境变量：PAINRADAR_STORE=d1 + D1 三项 + 爬虫两项
```

> `create_app` 需要 `db_paths`；D1 模式下会自动替换为 `["d1:main"]`，
> 其它数据库参数可随意传一个占位值，例如
> `python run.py serve --db d1:main --port 8770`。

## 5. 验证

```bash
# 边缘
curl https://<worker>.workers.dev/api/health
# {"ok":true,"edge":true,...}

# D1 连通性（在 Python API 所在机器）
PAINRADAR_STORE=d1 python run.py doctor
# store mode   : cloud (D1)
# d1 config    : configured
# d1 reachable : yes (items=…)
```

## 6. 已知边界（必须知道）

1. **Worker 不执行 Python**：所有写操作、抽取、聚类仍由 Zeabur 上的 API 完成；
   Cloudflare 只做静态托管、健康检查、代理与可选只读。
2. **D1 无事务**：`CloudflareD1Store` 通过 REST 逐条执行 SQL，`tx()` 语义退化为
   “每条自动提交”；批量导入失败时可能留下部分数据（本地 SQLite 不受影响）。
3. **D1 开销**：每条 SQL 一次 HTTP 往返。大批量导入/运行建议仍在本地或
   Zeabur + 持久磁盘完成，D1 适合托管已生成的结果供边缘读取。
4. **D1 迁移**：`_ensure_columns` 会尝试 `PRAGMA`/`ALTER`；若 D1 拒绝 PRAGMA，
   初始化会跳过迁移，请先用 `schema.sql` 建全量表。
5. **登录态**：Cookie 只在采集服务侧，Cloudflare 不接触。

## 7. 只部署前端（最省事）

如果暂时不想维护 Worker 代理：

```bash
npx wrangler pages deploy src/painradar/api/static --project-name painradar
```

但静态页面的 `/api/*` 会 404；需要在页面里把 API 地址指向 Zeabur，或加一层
`_redirects`/代理。当前前端用同源 `/api`，所以推荐第 4 节的 Worker 方案。
