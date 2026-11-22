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
| GET | `/api/platforms` | 各平台 Cookie/Profile 是否就绪 |
| POST | `/api/platforms/{platform}/cookie` | 直接保存该平台 Cookie 到 `/data/cookies/{platform}.txt` |
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

## 1.1 构建常见错误

| 报错 | 处理 |
|---|---|
| libatomic.so.1: cannot open shared object file | 镜像已预装 libatomic1；若你的分支较旧，在 apt 列表里加 libatomic1 后重建 |
| playwright install --with-deps 失败 | 先 pt-get install -y libatomic1 libnss3 libnspr4 libasound2，再执行 python -m playwright install chromium |
| Chromium 启动即退出 | 启动参数加 --no-sandbox --disable-dev-shm-usage，并确认容器内存 ≥ 1 GB |

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
| `PLATFORM_COOKIES_KS` | 按平台 | 快手 |
| `PLATFORM_COOKIES_WB` | 按平台 | 微博 |
| `PLATFORM_COOKIES_TIEBA` | 按平台 | 贴吧 |
| `CRAWLER_CMD_TEMPLATE` | 可选 | 默认 `python main.py --platform {platform} --lt cookie --type search --keywords {keywords}` |
| `CRAWLER_TIMEOUT` | 可选 | 默认 1200 秒 |
| `MAX_CONCURRENT_TASKS` | 可选 | 默认 **1**（串行）；超出直接返回 429，避免 Chromium 并发 OOM |

## 4. Cookie 怎么给

桥接服务把 Cookie 通过 MediaCrawler 的真实 CLI 参数传入：

`ash
python main.py --platform xhs --lt cookie --type search --keywords ... --cookies "web_session=..."
`

来源优先级：

1. 请求体 cookies（PainRadar 抓取弹窗里的临时 Cookie）；
2. 环境变量 PLATFORM_COOKIES_<PLATFORM>；
3. /data/cookies/<platform>.txt 上次持久化的值。

### 小红书只需要 web_session

看 media_platform/xhs/login.py 的 login_by_cookies()：它只应用
web_session 这一个 Cookie，其余会被忽略。所以小红书最小配置就是：

`env
PLATFORM_COOKIES_XHS=web_session=你的值
`

（浏览器里 1 等由页面自己生成；完整字符串也能传，只是会被过滤。）

### 其它平台

ilibili / douyin / zhihu 的 cookie 登录会应用整串 Cookie。
抖音通常还需要 	twid、msToken 等，直接粘贴浏览器导出的完整 Cookie 最稳。

### 怎么拿 Cookie

- 本机 Chrome 登录对应站点 → DevTools → Application → Cookies → 复制
  
ame=value; name2=value2；
- 或本机跑一次 MediaCrawler 扫码登录（--lt qrcode），从
  rowser_data/<platform>_user_data_dir 里取登录态；
- Cookie 等于账号权限，不要提交 Git，不要截图外发。

### 4.1 方法二：上传本地登录后的浏览器 profile

适合不想反复复制 Cookie 的情况。

1. 先改 `config/base_config.py`（这个文件**不读环境变量**，必须改文件）：

   ```python
   ENABLE_CDP_MODE = False
   HEADLESS = False
   LOGIN_TYPE = "qrcode"
   SAVE_LOGIN_STATE = True
   ```

2. 扫码登录一次：

   ```bash
   python main.py --platform xhs --lt qrcode --type search
   ```

   扫码成功后按 `Ctrl+C` 停止，确认生成：

   ```
   browser_data/xhs_user_data_dir/
   ```

3. 压缩这个目录：

   ```bash
   cd browser_data
   zip -r xhs_profile.zip xhs_user_data_dir
   ```

   Windows PowerShell：

   ```powershell
   Compress-Archive -Path browser_data\xhs_user_data_dir -DestinationPath xhs_profile.zip
   ```

4. 通过 PainRadar 代理上传（不需要把爬虫服务暴露到公网）：

   ```bash
   curl -u me:你的PAINRADAR_ADMIN_PASSWORD \
     -F "file=@xhs_profile.zip" \
     https://你的-painradar-域名/api/crawler/profiles/xhs
   ```

   或者直接传给爬虫内网地址（在 PainRadar 容器/同项目内）：

   ```bash
   curl -H "Authorization: Bearer $MEDIACRAWLER_API_TOKEN" \
     -F "file=@xhs_profile.zip" \
     http://painradar-crawler-per.zeabur.internal:8080/api/profiles/xhs
   ```

5. 查看已上传：

   ```bash
   curl -u me:你的密码 https://你的-painradar-域名/api/crawler/profiles
   ```

6. 之后正常抓取即可，不需要再配 `PLATFORM_COOKIES_*`。
   容器启动时 `entrypoint.sh` 会把 `MediaCrawler/browser_data` 链接到
   `/data/browser_data`，重新部署不会丢登录态。

> profile 里是完整登录态，zip 不要外发；过期后重新扫码上传。

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
4. **并发**：默认 `MAX_CONCURRENT_TASKS=1`，第二个任务直接 429；超时会终止整个浏览器进程组（SIGTERM，5 秒后 SIGKILL）；
5. **合规**：MediaCrawler 仅用于学习研究，请遵守平台 ToS 与当地法律，不要公开分发抓取数据。
