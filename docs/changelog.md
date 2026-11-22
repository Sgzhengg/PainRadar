# 变更与实验记录

> 从 README 归档的历史实验与版本记录。README 只保留安装、导入、界面与核心命令。

## 2026-11 新增能力

### 零 API Key 跑通商机管线

```bash
python tools/indie_demo.py
# -> reports/indie_demo.md（离线回放，token 0）
```

演示数据：`data/samples/indie_pdf_demo.json`（**手工构造的合成样例**，
用于验证清洗 / 上下文 / 信号提取 / 评分链路，不代表真实市场结论）。

### 1. 专项挖掘（deepdive）

面向单个产品/平台/系统的深挖：对话澄清 → 预检（命中率 + 关键词建议）→ 抓取（Reddit + App Store）→ 固定主题归并 → 带图表/证据链的 Markdown 报告，支持缓存与趋势对比。

- 文档：`docs/deepdive-feature.md`
- Web 入口：顶栏「专项挖掘」

### 2. 独立开发者商机流水线（indie）

针对 MediaCrawler 导出数据的高精度、低噪音管线：

```
JSON/JSONL → 规则降噪 → 对话上下文（原帖+高赞+楼中楼）
           → Map（4 类信号，JSON 强约束） → Reduce（聚类 + 1-10 商机分） → 商机研报
```

- 文档：`docs/indie-pipeline.md`
- 诊断：`docs/refactor-diagnosis.md`（旧流程为什么精度低）
- 用法：

```bash
python tools/indie_mine.py --input data/export.json --keyword "PDF工具" \
  --filter "pdf,adobe,acrobat" --workers 3 --out reports/report_PDF.md
```

- 特性：批次级缓存（重跑 0 token）、token 账本、并发限流、证据链要求 quote 必须可在原文定位。

## 早期实验（M1）

### 规则 vs LLM：同一批 99 条真实评论

| 指标 | 规则抽取 | LLM（DeepSeek，双跑） |
|---|---|---|
| 原子数 / 每条 | 67 / 0.68 | 97 / 0.98 |
| L2+ 占比 | 17.9% | 25.8% |
| 识别出绕行方案 | 9.0% | 32.0% |
| 明确代价 | 7.5% | 8.2% |
| 人群字段 | 26.9% | 42.3% |
| 平均置信度 | 0.62 | 0.80 |
| 平均阻碍描述长度 | 72 字符 | 32 字符 |
| 簇数 / 噪声率 | 5 / 1.2% | 6 / 6.2% |
| 调用与 token | — | 197 次，128k in / 32k out |

结论：LLM 把"每条评论能产出的可用证据"提高约 45%，绕行方案识别率约 3.5 倍，阻碍描述更短更适合上卡片；但**双跑只有 61/97 完全一致**，23 条软不一致、14 条硬冲突回退——说明同一句话两次抽取仍不稳定，双跑是"用成本换确定性"。

按 DeepSeek 公开价目量级估算，这批 99 条约 ¥0.5–1（双跑），即 ¥5–10/千条；单跑减半。建议：高价值品类开双跑 + 人工抽检，批量探索用单跑 + 抽样复核。
（2026-11 起默认改为单跑 + CoT，双跑仅作可选复核。）

完整对照见 [docs/llm-vs-rule.md](docs/llm-vs-rule.md)。

### A 集金标：30 条盲标试点

```powershell
# 1) 分层抽样（评分档 × 抽取结果），产出 200 行标注表 + 30 行盲标试点
python tools/make_goldset.py --db var/gold.db --category pet_water_fountain --n 200 --pilot 30

# 2) 标注后评分（对比规则 / LLM）
python tools/score_goldset.py --db var/gold200.db --category pet_water_fountain `
    --labels data/goldset/pilot-labels.csv --out docs/goldset-pilot.md
```

标注规则见 [docs/annotation-guide.md](docs/annotation-guide.md)；给第二标注者的一页操作说明见
[docs/second-annotator.md](docs/second-annotator.md)（可直接转发，40 条约 1 小时）。
已盲标 55 条（试点 30 + 第二批 25）的结果：

| 指标 | 规则 | LLM |
|---|---|---|
| 有效痛点 P / R / F1 | 89.3% / 67.6% / 76.9% | **91.7% / 89.2% / 90.4%** |
| L 级完全一致 / ±1 | 72.0% / 96.0% | 75.8% / 93.9% |
| 场景一致 | **68.0%** | 60.6% |
| 绕行方案 F1 | 20.0% | **58.8%** |

结论：LLM 的 F1 优势在大样本上仍然成立；但**场景一致率是最弱项**，问题在分类体系边界（App 与连接 / 固件与更新 / 其他场景），不在模型。剩余 145 条已切成 4 个批次放在 `data/goldset/batches/`，供第二标注者使用。

> 场景词表 v2 做过一次实验（新增广告/功能/硬件桶、去掉泛词 "app"），重映射后一致率反而从 68%/60.6% 降到 40%/57.6%。原因是金标自身未按新词表全量重标，且关键词重映射与模型读全文不可比。已回退，实验记录见 [goldset-pilot.md](docs/goldset-pilot.md)。

### B 集：结局回测（脚手架可用，结论暂不可用）

```powershell
python tools/backtest.py --source var/gold.db --db var/backtest.db `
    --category pet_water_fountain --t0 2025-11-01 --months 12 --top 10 --queries llm
```

做法：只用 T0 之前的评论聚类，给每个簇生成预测（簇 + 搜索词 + 12 个月窗口），
再去 GitHub / App Store 查窗口内是否出现对应付费产品，并与随机词组基线对比。

**B 集的结论是"证据可信、统计不足"**。三次迭代后：
v1 用词面匹配（1/4 vs 基线 9/10，命中是巧合）；v2 加语义裁决（2/4 vs 4/8）；
v3 扩到 3 个品类并按品类定义 domain_terms（**12 个预测、2 个命中、基线 5/12**）。

v3 把"订阅通吃"切掉了：宠物与记账不再命中取消订阅类工具。**记账品类首次出现正向信号**——
6 个预测命中 2 个（Skarbo / Quanto，AI 自动归类流水的预算 App），基线 1/4。
但 12 个预测仍不足以下结论。详见 [backtest-v2.md](docs/backtest-v2.md)。

### 前向测试（植物养护，进行中）

回测只能做事后检验；前向测试是唯一没有选择偏差的数据。已经登记：

```powershell
python tools/forward_register.py --source var/gold.db --db var/forward.db `
    --category plant_care --months 12
python tools/forward_check.py --db var/forward.db --category plant_care
```

- 3 条品类内预测 + 6 组预注册随机基线，T0=2026-11-14，回看日 2027-11-09；
- 判定规则写在 [forward-protocol.md](docs/forward-protocol.md)，登记后不得修改；
- `forward_check` 在到期前会**拒绝运行**（当前提示还剩 360 天），避免提前偷看结局。

登记清单见 [forward-plant.md](docs/forward-plant.md)。

这个过滤器已经落地（`validity.py`）：在试点上 P/R/F1 = 90.9%/90.9%/90.9%，优于单独 LLM；
在 200 条上直接挡掉 34% 的非痛点文本，token 成本同比例下降。默认开启，`--no-validity-filter` 可关闭。

数据库默认在 `var/painradar.db`，可用 `--db` 或环境变量 `PAINRADAR_DB` 覆盖。

安装为命令（可选）：

```powershell
pip install -e .
painradar demo --reset
```

---

## 2026-11-21 · WebUI v16

- 顶栏收敛为 3 个主操作（导入/运行/跨品类总榜），品类移到独立中文二级栏；
- 新增可折叠三步引导条；
- 机会卡改为双列网格：一人开发徽章、最高赞原话、L2+ 占比、详情/导出按钮；
- 快捷筛选（纯软件 / 1 周可做 / L3–L4）与三种排序；
- 抽屉顶部固定「导出种子用户外联表 (CSV)」；
- 新增 `POST /api/ingest`，支持在界面里导入 MediaCrawler JSON/JSONL/CSV。

## 2026-11-21 · B 端 / 传统行业模式

- `--mode b2b`：识别老板/管理者/员工与人工成本、接单、报价等信号；
- 评分新增 `buyer` 因子（B 端权重 15%），原子记录 `buyer_role` / `b2b_score`；
- 外联 CSV 切换为商务口吻（免费流程诊断 + Demo），新增 `buyer_role` 列；
- WebUI 运行/抓取弹窗增加模式选择，B 端机会卡显示 `B端`。

## 2026-11-21 · B 端模式深化

- 新增 `decision_maker_signal` / `manual_bottleneck`；人工耗时或赔钱线索强制 L3；
- B 端 `min_size=2`，决策者 20% + 人工替代 15% 加权；
- solo 可行性输出行业工作流形态与 `¥3,000–15,000/家/年` 客单价；
- 外联话术改为「行业共鸣 + 具体痛点 + 免费体验链接/演示视频，不推销」；
- WebUI 模式改为单选框，机会卡显示 `🏢 B端高客单`。

## 2026-11-21 · Zeabur 一体化私有部署

- 新增 `PAINRADAR_ADMIN_PASSWORD`：Basic Auth + 30 天 Cookie 保护整站（`/api/health` 公开）；
- `PAINRADAR_DATA_DIR` 可配置，配合 Zeabur 卷挂载 `/app/var` 持久化 SQLite；
- 根目录新增 `Dockerfile`（python:3.11-slim，8080，健康检查）与 `.dockerignore`；
- 归档 `cloudflare/`、`wrangler.toml`、`docs/deploy-cloudflare.md` 到 `docs/archive/`；
- 重写 `docs/deploy-zeabur.md`：同项目双服务、内网地址、卷挂载、环境变量与排错；
- `doctor` 检查数据目录可写、管理员密码、内网采集连通性。

## 2026-11-21 · 探索方向（对话式）

- 新增 `explore.py` 与 `/api/explore/*`：证据采样 → 方向卡 → 反应 → 收敛；
- 种子关键词相关性过滤，无相关证据时明确提示先抓数据；
- WebUI 新增「🧭 探索方向」全屏面板，方向卡可点击反馈；
- 会话持久化到 `var/explore_sessions/`。

## 2026-11-21 · 探索模式压力测试

- 方向选定后依次追问：反常识验证（痛点是否不成立）→ 付费意愿（谁掏钱/多少钱/预算来源）→ 替代方案；
- 追问以可点击的「probe 卡」呈现，回答写入会话；
- 收敛简报新增「付费假设（需要当面验证）」。

## 2026-11-21 · 探索→验证闭环

- 探索面板新增「用这个方向抓真实数据」：选平台、填关键词、设条数；
- `POST /api/explore/sessions/{id}/validate` 自动注册自定义品类并提交远程抓取任务；
- 前端轮询任务阶段，完成后自动打开新运行；
- 中文关键词的自定义品类键改为哈希后缀，避免冲突。

## 2026-11-21 · 验证结果回灌探索

- 新增 `POST /api/explore/sessions/{id}/validation-result`：按新运行的原子数、L2+ 占比、簇分布判定支持/削弱/样本不足；
- 结论与下一步问题写回探索会话，面板顶部显示「✅/⚠️/❔」卡片；
- 可一键查看新运行，或继续探索；
- 验证后发现旧追问卡仍在，已隐藏。

## 2026-11-21 · 跨会话探索记忆

- `var/explore_memory.json` 记录方向验证结论与付费回答；
- 新会话按种子关键词召回记忆，削弱方向自动避开并标注“上次验证”；
- 付费问题回答后写入记忆，下次探索可引用；
- 收敛简报增加「历史验证记忆」。

## 2026-11-21 · 探索记忆管理

- 新增 `GET/DELETE /api/explore/memory` 与 `POST /api/explore/memory/delete`；
- 探索面板「记忆」弹窗可查看方向验证结论与付费回答，支持单条删除/清空；
- 截图 `reports/explore-memory.png`。

## 2026-11-21 · 机会卡草案

- 新增 `POST /api/explore/sessions/{id}/draft`：把方向 + 验证结论 + 付费回答转成机会卡草案；
- 草案含人群/痛点、2 周 MVP 范围、定价假设、风险、7 天验证计划、原话证据；
- 探索面板「生成机会卡草案」展示并支持下载 Markdown；
- 截图 `reports/explore-draft.png`。

## 2026-11-21 · 灵感工作台

- 首页改为三步灵感闭环：抓热点评论 → 碰撞产品灵感 → 锁定 MVP；
- 机会卡重做为灵感卡：热点总赞/最高赞、一人开发徽章、高赞原话、深度测算折叠；
- 新增筛选：高赞热点、适合 AI/自动化、纯软件、1 周内、明确付费；
- 默认按「热度 × 一人开发可行性」排序，硬件/重运营降权；
- 探索方向卡改为「灵感切入点 / 为什么是热点 / 最小 MVP」表述。

## 2026-11-22 · 收拢入口与总榜表单

- 顶栏移除「抓取新商机」「运行分析」，只保留「碰撞产品灵感」「跨品类总榜」；
- 抓云端/导入本地文件移入探索首屏，导入后自动运行规则分析；
- 跨品类总榜新增「品类 → 最近运行」表单，避免空白页；
- 修复抓取弹窗 z-index 低于探索面板导致“点击无反应”。

## 2026-11-22 · 移除工作流引导条

- 删除首页「🚀 商机挖掘工作流」整块及对应 JS/CSS；
- 抓取、导入、重跑全部收进「碰撞产品灵感」；
- 首屏直接展示品类与灵感卡，减少引导噪音。

## 2026-11-22 · 总榜空快照处理

- 总榜页在快照 0 需求时展示配置表单，而不是“没有需求”；
- 空快照自动从现有语料重建一次，并显示生成进度；
- 明确文案：总榜是聚类已有语料，不实时抓取；
- `/api/discovery/corpora` 返回 db 路径、快照需求数。

## 2026-11-22 · 全网热点扫描

- 探索页新增「🌐 全网热点扫描」：默认宽泛关键词依次扫 xhs/dy/bili/zhihu，汇总后只跑一次聚类；
- 新任务类型 `scan_trend`，单平台失败不阻塞其他平台；
- 扫描完成自动打开新运行，直接看痛点卡与热点排序；
- 没配置爬虫时返回明确提示，可改用指定关键词或本地导入。

## 2026-11-22 · 热点话题横条

- 灵感页新增「🔥 热点话题」横条，按总赞排序，可点击到对应痛点卡；
- 与痛点卡列表分离，先看全网在聊什么，再看能做什么。

## 2026-11-22 · 平台就绪检查与七平台接入

- 爬虫桥接层支持 xhs/dy/ks/bili/wb/tieba/zhihu 七个平台；
- 新增 `/api/platforms`（爬虫）与 `/api/crawler/platforms`（PainRadar）检查 Cookie/Profile 是否就绪；
- 全网扫描先过滤未就绪平台，避免无谓等待；
- 探索页展示各平台 ✅/❌ 状态。

## 2026-11-22 · 页面内配置平台 Cookie

- 探索页平台状态徽章可点击，弹出 Cookie 配置框；
- 新增 `POST /api/platforms/{platform}/cookie`（爬虫）与 PainRadar 代理；
- Cookie 保存在爬虫 `/data/cookies/{platform}.txt`，保存后立即刷新就绪状态。

## 2026-11-22 · 爬虫镜像补 Node.js

- MediaCrawler 小红书签名依赖 execjs → Node.js；
- 爬虫镜像 apt 增加 nodejs，修复 `Could not find an available JavaScript runtime`。

## 2026-11-22 · 爬虫构建层优化

- Node.js 安装从第一层移到 Playwright 之后，避免小改动导致依赖层全量重建；
- MediaCrawler 改为 `git init + fetch --depth 1`，不再因 SHA/tag 触发全量 clone；
- 构建耗时主要来自 MediaCrawler 依赖（OpenCV/Playwright/pandas/matplotlib）和 Chromium + 系统依赖下载。

## 2026-11-22 · 修复 XHS a1 Cookie

- MediaCrawler 的 XHS Cookie 登录只写入 web_session，xhshow 签名要求 a1；
- 构建时 patch `media_platform/xhs/login.py`，写入完整 Cookie；
- 扫码登录后需同时保留 `a1` 与 `web_session`。
