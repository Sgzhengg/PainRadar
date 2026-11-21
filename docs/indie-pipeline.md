# 独立开发者商机流水线（indie）

> 目标：把 MediaCrawler 导出的评论，变成一份**带证据链和 MVP 建议的商机研报**。
> 与现有 `run.py`（品类 → 原子 → 机会卡）并行存在，互不影响。

## 1. 它和旧流程的区别

| | 旧流程 `run.py` | 新流程 `indie` |
|---|---|---|
| 分析单位 | 单条评论 | **对话块**（原帖 + 高赞评论 + 楼中楼） |
| 输入字段 | 文本 | 文本 + **点赞/回复** + 链接 |
| 抽取方式 | 一次宽泛抽取 | **两阶段**：先提信号，再聚类 |
| 输出 | 机会卡片 | **商机研报 Markdown** |
| 噪音处理 | 入库时才去重 | **进模型前按规则丢弃** |

## 2. 使用

```bash
python tools/indie_mine.py \
  --input data/xhs_export.json \
  --keyword "PDF工具" \
  --out reports/report_PDF工具_2026-11-21.md \
  --min-len 6 --top-comments 4 --workers 3
```

参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--input` | 必填 | MediaCrawler JSON / JSONL |
| `--keyword` | 必填 | 报告关键词（也用于文件名） |
| `--min-len` | 6 | 短于该长度的评论直接丢弃 |
| `--top-comments` | 4 | 每个对话保留的高赞评论数 |
| `--batch-size` | 4 | 每次送给模型的对话数 |
| `--workers` | 3 | 并发请求数（配合限流） |
| `--max-threads` | 0 | 只跑前 N 个对话（调试用） |
| `--mapping` | 空 | 自定义字段名 JSON |

## 3. 输入格式与字段映射

支持三种：

1. **帖子数组 + 嵌套评论**（MediaCrawler 常见）：

```json
[{"note_id":"n1","title":"...","desc":"...","url":"...","liked_count":342,
  "comments":[{"comment_id":"c1","content":"...","like_count":286,
               "sub_comments":[{"comment_id":"c2","content":"...","like_count":74}]}]}]
```

2. **JSONL 平铺**：每行一条评论，带 `post_id/title/url` 与评论字段。
3. **单个帖子对象**。

自动识别的字段名：

| 语义 | 候选键 |
|---|---|
| 帖子 ID | note_id / post_id / thread_id / id |
| 标题 | title / note_title / desc / content |
| 正文 | desc / content / text / body |
| 链接 | url / note_url / share_url |
| 帖子赞 | liked_count / like_count / likes / digg_count |
| 评论内容 | content / text / comment / review |
| 评论赞 | like_count / liked_count / likes / digg_count |
| 楼中楼 | sub_comments / replies / children |

字段对不上时，传 `--mapping`：

```json
{"id":"note_id","title":"title","body":"desc","url":"url","likes":"liked_count","text":"content"}
```

## 4. 三段处理

### 清洗（`clean.py`）

丢弃：

- 清洗后长度 < `--min-len`；
- 纯表情 / 纯 @ / 纯链接；
- 纯附和词（"好用""确实""哈哈"）；
- 广告引流（"加V""私我""链接在主页""日入过万"等 20+ 词）。

每条丢弃都计数，写进报告头部，便于判断语料质量。

### Map（`map_stage.py`）

模型扮演"毒舌独立产品经理"，**只**提 4 类信号：

1. `竞品吐槽`、2. `求推荐/平替`、3. `手工繁琐`、4. `付费信号`。

硬约束：

- quote 必须是原文连续片段，**找不到对应评论就丢弃**（不做模糊匹配凑数）；
- 一条评论最多 1 条信号，一段对话最多 4 条；
- 没有合格信号返回空数组。

点赞数与链接从原始评论回填，不依赖模型输出。

### Reduce（`reduce_stage.py`）

把信号按"同一核心需求"聚成 ≤8 类，每类给出：痛点画像、买家、场景、MVP、变现、难度、付费明确度。

**商机指数（1–10）**：

```
freq  = min(1, log10(1+提及数)/log10(51))
heat  = min(1, log10(1+最高赞)/log10(1001))
dev   = 1 - (开发难度-1)/4
div   = 信号类型数/4
score = 10 × (0.30·freq + 0.20·heat + 0.20·付费明确度 + 0.20·dev + 0.10·div)
```

模型漏掉的信号不会丢，会归入"未归类信号"并在报告里标出。

## 5. 工程能力

| 能力 | 实现 |
|---|---|
| 批次级缓存 | 每次 LLM 调用按 `sha256(system+user)` 落盘 `var/indie_cache/`；重跑直接命中 |
| 断点续跑 | 任一批失败只影响该批，下次重跑命中已完成批次的缓存 |
| Token 统计 | 记录 prompt/completion/calls/cache_hits/failures，跑完打印 |
| 并发限流 | `min_interval` 控制最小请求间隔 + `--workers` 并发上限；429 自动退避重试 |
| 证据可信 | quote 必须能在评论原文里找到，否则丢弃 |

## 6. 示例输出（Demo 数据）

`reports/report_PDF工具_demo.md`：

- 3 个商机，按 6.3 / 4.9 / 4.3 排序；
- 每个含痛点画像、证据链（原话 + 赞数 + 链接）、MVP 一句话、变现模式；
- 头部显示清洗统计与 token 消耗。

> 注意：`var/indie_demo.json` 是**手工构造的演示数据**，用于验证流水线，
> 不代表真实市场结论。真实结论请用 MediaCrawler 导出跑。

## 7. 已知限制

1. 评分是排序工具，不是市场验证；
2. 模型对"同一需求"的判断有主观性，跨批次可能漂移；
3. 输入没有点赞字段时（如部分导出），heat 项恒为 0，评分会偏低；
4. 一条对话最多提 4 条信号，长帖会丢信息；
5. 目前只支持 JSON/JSONL，不支持直接读 Excel。

## 8. 领域过滤（`--filter`）

真实数据验证时发现：r/software 的周帖会把备份、壁纸、GIMP 等无关话题带进来。
加 `--filter` 后，**只保留标题或正文包含领域词的对话**（评论不算，避免"顺便提到"混入）：

```bash
python tools/indie_mine.py --input var/reddit_indie.json --keyword PDF \
  --filter "pdf,adobe,acrobat,ocr,compress,annotation" ...
```

效果（同一份数据）：

| | 无过滤 | 有过滤 |
|---|---|---|
| 对话 | 23 | 18 |
| 丢弃离题对话 | 0 | 7 |
| 商机数 | 7（含备份/壁纸） | 5（全 PDF 相关） |

## 9. 真实数据验证（2026-11-21）

数据：`tools/build_reddit_dataset.py` 抓取 r/pdf + r/software 最近帖子与评论
（带 `score` 与 `link_id`），组装成 25 个对话 / 164 条评论。

运行结果：

```
threads=25 contexts=18 kept_comments=80 kept_replies=33 drop_off_domain=7
signals=8 (竞品吐槽5, 手工繁琐2, 求推荐1, 付费信号1)
tokens: 12,977 (6 calls)
```

报告：`reports/report_PDF工具_real.md`

真实数据下的商机分只有 2.9–4.1，原因很直接：**这批帖子是新帖，最高赞只有 26**。
这恰好说明热度加权在起作用——没有共鸣的证据不会被打高分。

## 10. 低样本标记

提及数 < 2 的商机会在标题后标注 **"样本不足，仅作线索"**，避免单条评论被当成商机。

## 11. 目录结构

```
src/painradar/indie/
  models.py      Thread / Comment / ContextBlock / Signal / Cluster
  clean.py       规则降噪（长度/表情/@/广告/附和词）
  loader.py      字段映射 + 对话组装 + 领域过滤
  llm.py         JSON 调用 + 缓存 + token 统计 + 限流并发
  map_stage.py   4 类信号提取，quote 必须能在原文找到
  reduce_stage.py 聚类 + 1-10 商机分
  report.py      Markdown 研报
  cli.py         命令行入口
tools/indie_mine.py            入口封装
tools/build_reddit_dataset.py  构建带点赞的测试数据
tests/test_indie_pipeline.py   11 个单元测试
```

## 12. 结果回归测试（offline replay）

CI 只能证明代码没坏，证明不了"结论没变差"。为此加了**离线回放模式**：

- `LLM(offline=True)` 只读缓存，**不发任何网络请求**；缓存未命中直接报错；
- CLI 新增 `--offline` 与 `--cache-dir`；
- 把一次真实模型输出固化成 `tests/fixtures/indie_cache/*.json`，
  再配 `tests/fixtures/indie_demo.json` 作为输入。

回归测试 `tests/test_indie_regression.py` 断言：

- 清洗结果（保留 11 条、丢弃 5 条）；
- 信号数（7 条）与三类商机（PDF本地买断工具 / 扫描件表格转Excel / PDF填表压平）；
- 评分 6.3、证据引文与链接存在、排序为分数降序；
- 缓存未命中时确实抛错。

运行：

```bash
python -m unittest tests.test_indie_regression -v
```

耗时 0.16 秒、token 0。

**用途**：以后改 prompt、清洗规则或评分公式，只要离线测试变了，
就说明"分析结论"变了，需要人工确认是新版本更好还是回归。

## 13. 零成本试跑

```bash
python tools/indie_demo.py
```

- 输入：`data/samples/indie_pdf_demo.json`（合成样例，URL 均为 example.com）
- 模型响应：`tests/fixtures/indie_cache/`（离线回放）
- 输出：`reports/indie_demo.md`
- 消耗：**0 token、0 次网络请求**

这条路径同时也是回归测试的执行方式（见第 12 节）。
