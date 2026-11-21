# PainRadar 痛点雷达

把公开评论加工成**可追溯、可验证、可打分**的产品机会卡。

本仓库是《PainRadar 开发方案》的 M0/M1 落地：一条能跑通的垂直切片——从评论导入、脱敏去重、痛点原子抽取（带原文锚定）、场景聚类、双因子评分、市场区间估算，到机会卡与 Markdown/DOCX 报告，全部离线可运行，不依赖任何 API Key。

```
评论(JSONL/CSV) → 脱敏去重 → 痛点原子(span 锚定) → 场景聚类 → 评分 → 市场区间 → 机会卡 → 报告
                                  ↑ 证据台账（append-only，可回源、可删除） ↑
```

---

## 1. 快速开始

要求：Python 3.11+（已在 3.12 验证）。CLI 与管线只用标准库；
HTTP 界面需要 `pip install -r requirements.txt`（fastapi + uvicorn），DOCX 导出可选 python-docx。

```powershell
cd E:\PainRadar

# 环境自检
python run.py doctor

# 端到端演示：3 个品类、80 条样例评论、生成 3 份报告
python run.py demo --reset --docx

# 交互式界面（可选）
pip install -r requirements.txt
python run.py serve --db var\gold200.db --db var\gold.db
```

输出：

```
reports/demo/pet_water_fountain-<run>.md / .docx
reports/demo/home_storage-<run>.md / .docx
reports/demo/camping_gear-<run>.md / .docx
```

> 演示报告写到 `reports/demo/`，不会覆盖你用真实数据生成的 `reports/` 报告。

### 用真实数据跑一遍

```powershell
# 1) 从 App Store 搜索并抓取评论（公开 RSS，无需 Key）
python run.py --db var/live.db fetch --source appstore `
    --category pet_water_fountain --search "cat water fountain" --pages 2

# 2) 抓一个外部锚（评分人数 / 平均分），用于计算样本覆盖率
python run.py --db var/live.db anchor --source itunes `
    --category pet_water_fountain --app-id 1586120661

# 3) 抽取 → 聚类 → 评分 → 出报告
python run.py --db var/live.db run --category pet_water_fountain
python run.py --db var/live.db report --category pet_water_fountain --docx
```

Reddit 需要 OAuth（公开 JSON 对未认证请求经常超时/403）：

```powershell
$env:REDDIT_CLIENT_ID="..."; $env:REDDIT_CLIENT_SECRET="..."
$env:REDDIT_USERNAME="..."; $env:REDDIT_PASSWORD="..."
$env:REDDIT_USER_AGENT="PainRadar/0.1 by <your-reddit-username>"
python run.py --db var/live.db fetch --source reddit `
    --category pet_water_fountain --query "fountain noise" --subreddits catadvice --limit 10
```

### 用 LLM 抽取器（可选）

任何 OpenAI 兼容端点都可以（DeepSeek / Qwen / vLLM / Ollama）：

```powershell
$env:PAINRADAR_LLM_BASE_URL="https://api.deepseek.com/v1"
$env:PAINRADAR_LLM_API_KEY="sk-..."
$env:PAINRADAR_LLM_MODEL="deepseek-chat"

python run.py --db var/live.db run --category pet_water_fountain --extractor llm
```

没有 Key 也能验证链路——仓库自带一个确定性假端点：

```powershell
python tools/fake_llm.py --port 8765
python run.py --db var/llm.db run --category pet_water_fountain `
    --extractor llm --llm-base-url http://127.0.0.1:8765 --llm-model fake
```

LLM 抽取不是"信模型"：每条结果都要过原文锚定；默认双跑（第二次温度 +0.3）比对
level/scene/wtp/obstacle 一致性，不一致或锚定失败自动回退规则抽取器，回退比例会写进
`stats.extraction`。

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

## 2. 命令

| 命令 | 作用 |
|---|---|
| `python run.py doctor` | 检查运行环境、样例、凭据与依赖 |
| `python run.py demo [--reset] [--docx]` | 跑通三个品类的完整链路并出报告 |
| `python run.py fetch --source appstore --category X --search "..."` | 从 App Store 搜索并抓取评论（公开 RSS） |
| `python run.py fetch --source reddit ...` | 从 Reddit 抓取（OAuth 或公开 JSON；本机不可达） |
| `python run.py fetch --source github --category X --query "petkit"` | GitHub Issues 公开搜索（集成/固件问题） |
| `python run.py fetch --source hn --category X --query "water fountain"` | Hacker News 评论（Algolia） |
| `python run.py anchor --source itunes --category X --app-id N` | 写入评分人数/平均分锚 |
| `python run.py anchor --source file --category X --file anchors.csv` | 从 CSV 导入价格/BSR/广告数等锚 |
| `python run.py ingest --category X --file data.jsonl` | 导入 BYOD 文件 |
| `python run.py run --category X` | 抽取 → 聚类 → 评分 → 机会卡 |
| `python run.py discover --db var\gold.db --db var\gold200.db` | **无品类发现**：丢掉品类标签，跨域合并簇并排序需求 |
| `python run.py discover --canonical ...` | 先做需求归一化（LLM）再合并，跨域率从 1/11 提到 5/6 |
| `python run.py report --category X --docx` | 为最近一次 run 出报告 |
| `python run.py stats` | 台账统计与最近 runs |
| `python run.py delete --uid cm_xxx` | 级联删除一条评论及其派生原子（PIPL/GDPR） |

`run` 支持 `--extractor rule|llm`、`--threshold`、`--min-size`。
`discover` 的结果与限制见 [docs/discovery-notes.md](docs/discovery-notes.md)；
加 `--canonical` 后的效果见 [docs/discovery-canonical-notes.md](docs/discovery-canonical-notes.md)；
全量 LLM 抽取后的最终结果见 [docs/discovery-full-notes.md](docs/discovery-full-notes.md)；
需求表 v2 已冻结，清单与用法见 [docs/demand-taxonomy-v2.md](docs/demand-taxonomy-v2.md)；
跨类目验证（App Store 总榜 40 个 App）见 [docs/topcharts-notes.md](docs/topcharts-notes.md)。
非 App 渠道（GitHub Issues + Hacker News）见 [docs/community-notes.md](docs/community-notes.md)。
买家访谈执行指南见 [docs/interview-guide.md](docs/interview-guide.md)（含前 3 条需求的提纲，可生成）。
硬件品类补充（扫地机器人/空气净化器/智能门锁）见 [docs/hardware-notes.md](docs/hardware-notes.md)。
Reddit 经 Arctic Shift 存档打通（直连 403）见 [docs/reddit-notes.md](docs/reddit-notes.md)。
数据来源与审计（哪个库从哪来、抓了多少、何时抓的）见 [docs/data-provenance.md](docs/data-provenance.md)。
Google Trends 集成（无官方 API，Cookie + 内部接口）见 [docs/trends-notes.md](docs/trends-notes.md)。
锚 CSV 列：`metric,value[,source,as_of,url,grade,note]`（例如 `rating_count`、`price`、`bsr`、`ad_count`）。

---

## 3. 看看效果

把任意一次运行渲染成单文件 HTML（无服务器、无 JS 依赖，双击即开）：

```powershell
python tools/build_html.py --db var/gold200.db --category pet_water_fountain --out reports/ui-demo.html
```

截图：`reports/ui-demo-v2.png`（修复后：宠物智能设备 · LLM，证据带来源 App）、
`reports/ui-demo.png`（修复前，可对比）、`reports/ui-budgeting.png`（记账 · 规则抽取）。
页面包含：分母与噪声率、一页结论、机会卡（痛感/机会分、因子条、原文证据、人群、替代方案、
梯子分布、SOM 区间）、风险提示、外部锚。

数据质量修复（2026-11-14）：
- 移除了混入的宠物保险 App（Pet Cloud，44 条），`CategorySpec.excluded_apps` + `tools/purge_apps.py`；
- 品类更名为「宠物智能设备」（语料含饮水机/喂食器/猫砂盆/摄像头，原名不准）；
- 证据显示来源 App（Petlibro / PETKIT / Furbo…）；
- 没有人群证据时不再编造「该品类用户」，改为「用户」/「待补」。

### 交互式界面（FastAPI + 前端）

```powershell
pip install -r requirements.txt
python run.py serve --db var\gold200.db --db var\gold.db --port 8770
# 打开 http://127.0.0.1:8770/
```

- 顶部切换品类（宠物智能设备 / 睡眠 / 记账 / 植物养护），「历史运行」下拉可切到旧 run；
- **「发现」标签页**：展示无品类发现的需求（分数、定义、跨域数、来源域徽章），
  点开看分域买家与原文证据；数据来自 `var/discovery.json` 快照；
- **「手动运行」按钮**：选品类与抽取器（规则/LLM），后台线程执行，弹窗显示进度，
  完成后自动切到新 run——不需要回到命令行；
- **「新增品类」按钮**：输入中文品类名 + 英文搜索词，系统自动找 3 个 App Store 应用、
  抓取评论、生成通用场景词表，新品类随即出现在「手动运行」下拉里；
- 左侧筛选：机会等级、最低痛感、场景多选、证据关键词搜索；
- 点卡片打开右侧下钻：证据分页加载（每页 50）、来源 App、置信度、梯子、原文链接、
  因子条、SOM 区间、证伪条件；
- 深链：`/#run=<run_id>&cluster=<cluster_id>` 可直接打开某张卡。

API（OpenAPI 文档在 `/docs`）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/runs` | 所有运行（含 `latest_for_category`） |
| GET | `/api/runs/{run_id}` | 运行详情 + 机会卡（首屏 12 条证据） |
| GET | `/api/runs/{run_id}/members` | 证据分页（`cluster_id`、`offset`、`limit`） |
| GET | `/api/anchors` | 品类外部锚 |
| GET | `/api/discovery` | 最新一次需求发现快照（无则 404） |
| POST | `/api/run` | 触发一次运行 `{category, extractor}`（202 + job） |
| GET | `/api/run/{job_id}` | 作业状态（`queued/running/done/failed`） |
| GET | `/api/run/active` | 当前运行的作业（无则 null） |
| POST | `/api/categories/custom` | 新建品类并抓取 `{name, term, pages}`（202 + job） |

截图：`reports/api-default.png`、`reports/api-drawer.png`。

离线单文件仍保留（无服务、可邮件发送）：

```powershell
python tools/build_app.py --db var/gold200.db --db var/gold.db --out reports/app.html
```

**边界**：目前是只读查看器 + API，没有账号、权限、任务队列和写操作。
多租户与审核流仍在路线图后半段。

## 4. 已实现 / 未实现
对照开发方案的 M0–M1：

| 方案条目 | 状态 | 位置 |
|---|---|---|
| BYOD 文件导入（JSONL/JSON/CSV） | ✅ 已实现 | `connectors/file_connector.py` |
| Connector 协议（平台可插拔） | ✅ 骨架 | `connectors/base.py` |
| PII 脱敏 + 作者加盐哈希 | ✅ 已实现 | `textproc.mask_pii` / `author_key` |
| 去重（精确 + MinHash 近似） | ✅ 已实现 | `textproc.minhash` / `store.find_duplicate` |
| 原文锚定三道闸 | ✅ 已实现（exact/normalized/fuzzy） | `extract._locate` |
| 规则抽取器（离线基线） | ✅ 已实现 | `extract.RuleExtractor` |
| LLM 抽取器（span 校验 + 双跑一致性 + 规则回退） | ✅ 已实现 | `extract.LLMExtractor` |
| L0–L4 痛点梯子 | ✅ 已实现 | `extract._build` |
| 场景分类 + 场景优先聚类 | ✅ 已实现 | `config.CATEGORIES` / `cluster.py` |
| 痛感分 / 机会分（可解释） | ✅ 已实现 | `scoring.score_clusters` |
| 市场区间（蒙特卡洛 P10/P50/P90） | ✅ 已实现 | `scoring.estimate_market` |
| 机会卡 + 证伪条件 + 7 天验证包 | ✅ 已实现 | `pipeline.run_category` |
| Markdown / DOCX 报告 | ✅ 已实现 | `report.py` |
| Append-only 台账 + 软删除 | ✅ 已实现 | `store.py` |
| App Store 评论连接器（公开 RSS） | ✅ 已实现 | `connectors/appstore.py` |
| Reddit 连接器（OAuth + 公开 JSON 兜底） | ✅ 已实现 | `connectors/reddit.py` |
| 外部锚：iTunes 评分人数/均分 | ✅ 已实现 | `anchors.ItunesAnchor` |
| 外部锚：CSV 导入（Keepa/Ad Library） | ✅ 已实现 | `anchors.import_csv` |
| A 集金标：分层抽样 + 盲标表 + 评分 | ✅ 已实现（55 条） | `tools/make_goldset.py` / `tools/score_goldset.py` |
| B 集：时间切分 + 预测 + 结局采集 + 基线 | ✅ 脚手架（结论暂不可用） | `tools/backtest.py` |
| B 集：前向测试登记与守卫 | ✅ 已登记（2027-11 回看） | `tools/forward_register.py` / `tools/forward_check.py` |
| 有效性预过滤（好评/品类外） | ✅ 已实现 | `validity.py` |
| 官方 API 连接器（Amazon PA-API 等） | ⏳ M1 下一批 | — |
| Web UI / FastAPI | ⏳ M2 | — |
| 回测集与校准 | ⏳ M2 | — |
| 多租户 RLS / 计费 | ⏳ M2 | — |

---

## 5. 目录结构
```
PainRadar/
├─ run.py                     # 免安装入口
├─ pyproject.toml
├─ src/painradar/
│  ├─ schema.py               # RawItem / PainAtom / Cluster / Score / MarketEstimate
│  ├─ config.py               # 路径、品类、场景词典、市场假设
│  ├─ textproc.py             # 归一化、PII、语言识别、MinHash、TF-IDF
│  ├─ store.py                # SQLite append-only 证据台账
│  ├─ extract.py              # span gate + 规则抽取 + LLM 抽取
│  ├─ cluster.py              # 场景优先 + 簇内层次聚类
│  ├─ scoring.py              # 痛感/机会评分 + 市场蒙特卡洛
│  ├─ pipeline.py             # 编排：导入→抽取→聚类→评分→机会卡
│  ├─ report.py               # Markdown / DOCX
│  ├─ cli.py                  # argparse 命令
│  └─ connectors/             # Connector 协议 + 文件连接器
├─ data/samples/              # 三个品类的合成样例（演示用）
├─ tests/                     # 19 个 unittest（离线）
├─ tools/                     # 开发辅助：inspect_run / tune_cluster
├─ reports/                   # 生成的报告
└─ var/                       # SQLite 台账
```

---

## 6. 关键设计

### 5.1 证据先行

每条痛点原子都保存 `quote + span_start + span_end + match_score`。入库前必须通过三道闸：

1. **原文锚定**：quote 必须是原文的精确子串（先 exact，再 NFKC/空白归一，再 ±窗口模糊匹配 ≥0.90）。
2. **槽位可定位**：抽不到的槽位置 `unknown`，不猜。
3. **入库后校验**：报告与测试均可回查 `text[span_start:span_end] == quote`。

锚定失败的原子直接丢弃，不修补——这是"可审计"的地基。

### 5.2 痛点梯子

只有同时具备「阻碍 + 代价 +（替代方案或显式无解）」才进入商业模型：

| 级别 | 定义 | 处理 |
|---|---|---|
| L0 | 纯情绪 | 丢弃 |
| L1 | 只有抱怨/现象 | 保留，但不单独构成机会 |
| L2 | 有阻碍 + 有绕行方案 | 进簇、进评分 |
| L3 | 已询价/比价/试过失败 | 定价锚 |
| L4 | 已付费/明确求购 | 销售线索 |

### 5.3 评分

```
Pain = 100 × (0.30·频次 + 0.25·人群广度 + 0.20·情绪强度 + 0.15·代价清晰度 + 0.10·持续性)
Opp  = 100 × (Pain^0.30 × 供给缺口^0.20 × 付费信号^0.20 × 可服务性^0.15 × 时机^0.15) / 竞争^0.10
```

- 几何平均用于惩罚"一票否决"型缺陷。
- **付费信号缺失时向中性先验 0.5 收缩**，并显示「覆盖率 0」，避免把"没观测到"误读成"没有需求"。
- 对外只给三档（强/中/弱），内部保留连续分。

### 5.4 市场区间

自下而上：`人群 × 渗透率 × 可触达率 × 年转化率 × 客单价`。五项均为 (low, mid, high) 三角分布，蒙特卡洛 2 万次取 P10/P50/P90；每个假设带来源等级（A/B/C/D），并输出敏感性排序与**证伪条件**。

> 相乘各假设的下界会得到跨两个数量级的假区间；蒙特卡洛给出的是可以被人反驳的区间。

### 5.5 合规

- 只处理用户提供/授权数据；不接登录态、不做签名逆推。
- 入库前脱敏：邮箱、电话、微信、@、地址、长数字 → 类型化占位符；作者只存加盐哈希。
- 原文只存片段 + 哈希 + 快照元数据；支持 72 小时级联删除（评论 + 派生原子）。
- 报告每条证据都可回源到平台、时间、链接。

---

## 7. 测试

```powershell
$env:PYTHONPATH="E:\PainRadar\src"
python -m unittest discover -s tests -v
```

覆盖：文本归一化、PII、语言识别、MinHash、span 三道闸、L2/L4 判定、聚类与噪声、评分边界、市场区间有序性、端到端流水线、幂等导入、级联删除。

---

## 8. 已知限制（M1 诚实清单）

1. **规则抽取器是基线**，不是最终方案：它能稳定抓到"阻碍/替代/代价/付费信号"，但对反讽、长句、隐含痛点会漏。LLM 抽取器已可用，但需要端点与成本预算；建议先用规则跑通品类，再对高价值品类开 LLM。
2. **场景分类靠词典**，覆盖有限；未命中的进「其他场景」并按相似度拆分，拆不动就计入噪声。真实评论的主题分布会倒逼词典迭代（App Store 的智能硬件评论里，"App 与连接/固件更新/订阅付费"往往比硬件本身更多）。
3. **Reddit 公开 JSON 经常超时/403**，生产使用必须配置 OAuth；`fetch` 会给出明确提示而不是抛栈。
4. **Amazon 评论正文拿不到官方接口**：PA-API 不提供评论文本，抓取又违反 ToS。Amazon 侧只做"锚"（价格/BSR/评分人数），评论文本走 BYOD（卖家后台导出）或持牌数据商。
5. **市场假设多为 C/D 级**，仅用于演示区间方法，不能对外定价；接入 Keepa / Ad Library / Trends 后才有资格升级等级。
6. **聚类是场景优先**，不是 embedding 聚类；跨场景的同一痛点会被切开。
7. **没有 Web UI / API / 多租户**，目前是 CLI + 报告。

---

## 9. 下一步（按方案）

- **M1-a**：Reddit / Amazon / App Store 官方 API 连接器 + 配额与熔断。
- **M1-b**：LLM 抽取器上线（JSON Schema + span 校验 + 双跑一致性），规则抽取降级为兜底。
- **M1-c**：外部锚（Keepa/Ad Library/Trends）接入，替换 C/D 级市场假设。
- **M1-d**：A 集金标（600 条）与逐字段 α、span 匹配率看板。
- **M2**：FastAPI + Next.js 机会卡界面、订阅计费、回测集。

---

## 10. 许可与来源

本项目为自研代码。参考项目 MediaCrawler 采用《非商业学习使用许可证 1.1》，本仓库**不包含其任何代码、注释或数据结构**，仅借鉴其"平台适配器 + 统一模型"的架构思想（见开发方案 §2）。

---

## 新增能力（2026-11）

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
