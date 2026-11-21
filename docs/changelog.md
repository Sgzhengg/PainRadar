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
