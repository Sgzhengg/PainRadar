# 重构诊断：为什么现在的 PainRadar 精度低、噪音大

> 检查对象：`src/painradar/`（extract / pipeline / discover / deepdive / store）
> 结论先行：现有实现是"评论级、单次、无上下文、无热度"的分析，和你要求的"对话级、两阶段、带证据链"是两种东西。

## 1. 数据层：缺三个关键字段（最致命）

`src/painradar/schema.py` 的 `RawItem` 只有：

```python
platform, item_id, url, text, published_at, category, author, lang, rating, tier, tos_basis
```

`items` 表的列同样没有：`like_count`、`reply_count`、`parent_id`、`post_title`、`post_id`。

后果：

1. **无法做热度加权**——点赞/回复在入库时就被丢掉，后面再怎么评分都补不回来；
2. **无法做上下文绑定**——评论没有父帖/父评论关系，楼中楼被拍平成孤立文本；
3. **无法私信触达**——没有原帖链接/ID，证据链只能给一句引文。

这一条决定了：**不先改数据层，改 prompt 没有意义。**

## 2. 分析层：单评论、单次、宽泛

`src/painradar/extract.py` 的 `SYSTEM_PROMPT` 是：

> "You receive ONE review and return ONE JSON object…"

问题：

1. **一次只看一条评论**——楼中楼里"我也想要""求平替""XX 多少钱"的信息全部丢失；
2. **没有信号类型**——不区分竞品吐槽/求推荐/手工繁琐/付费信号，输出的是泛化的
   scene/job/obstacle，天然容易写成"用户希望更好用"这类废话；
3. **没有强制丢弃**——提示词鼓励"能填就填"，水军和表情评论也会被抽成原子；
4. **没有 JSON Schema 约束**——靠自然语言描述字段，模型自由发挥。

## 3. 清洗层：几乎不存在

pipeline 里只有 PII 脱敏、去重和 span gate，**没有**：

- 最短长度过滤（"好用""不错"这类 2 字评论照样入库）；
- 纯表情 / 纯 @ / 广告引流识别；
- 水军话术（"私我""加V""链接在主页"）过滤。

所以噪音不是模型造成的，是**在进模型之前就没筛**。

## 4. 评分层：算的是"提及数"，不是"共鸣度"

`scoring.py` 的 Pain 公式用 freq/breadth/intensity/cost/persistence，
其中 freq 是原子数，intensity 由模型给分——**点赞和回复不参与**。

结果：一条 0 赞的长评论和一条 2 万赞的吐槽，权重一样。

## 5. 工程层：没有断点、没有 token 账本、没有并发控制

- `deepdive.py` 按批顺序调用，任一批失败整轮重来（只有结果级缓存，没有批次级断点）；
- 没有 token 统计，成本不可见；
- 请求之间只有简单 `rate_per_sec`，没有并发上限与退避。

## 6. 结论：应该重做一条独立流水线

现有 `run.py` 那套（品类 → 原子 → 聚类 → 机会卡）适合"宽而浅"。
你要的是"窄而深"：**对话上下文 → 强信号 → 跨批聚类 → 带证据链的商机研报**。

两者目标不同，硬改会把现有功能改坏。因此新增一条独立管线
`src/painradar/indie/`，不动现有 `run.py` 流程，用新 CLI 驱动：

```
MediaCrawler JSON/JSONL
  → 清洗（规则降噪）
  → 上下文组装（标题+正文+高赞评论+楼中楼）
  → Map（毒舌 PM，4 类信号，JSON Schema）
  → Reduce（聚类 + 1-10 商机分）
  → report_关键词_日期.md
```
