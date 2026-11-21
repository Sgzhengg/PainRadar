# 价值衰减挖掘：为什么"买了却不用"

> 用户的原话：被外观吸引买了 Apple Watch，用一阵就放一边，"总觉得用处不大"。
> 这类痛点不在差评里，而在**弃用叙述**里。本文说明 PainRadar 怎么补上这一层。

## 1. 为什么现有管线挖不到

现有原子抽取问的是"你在哪里受阻"，适合**有摩擦的显性抱怨**。
但"吃灰"是**沉默的**：用户不会专门去 App Store 写一条"我不用了"，因为那不像 bug，
更像自己的问题。

所以需要换一种语料与抽法：

| 维度 | 痛点挖掘（现有） | 价值衰减挖掘（新增） |
|---|---|---|
| 语料 | 评论、投诉 | 弃用自述、二手转卖、后悔帖 |
| 问题 | 哪里受阻 | 为什么不再用 |
| 单位 | 痛点原子 | 旅程档案 |
| 输出 | 需求排序 | 衰减触发 + 价值缺口 |

## 2. 六段旅程模型

```
购买动机 → 首周价值 → 习惯形成 → 衰减触发 → 替代行为 → 处置动作
   job      expected     habit       decay      substitute    action
```

核心问题是 JTBD：**他当初"雇佣"这个产品完成什么任务？后来为什么"解雇"了它？**

## 3. 信号来源

| 来源 | 典型句式 | 价值 |
|---|---|---|
| 社区自述 | "stopped wearing it after 3 months" | 直接 |
| 后悔帖 | "waste of money", "should have returned it" | 强情绪 |
| 二手转卖 | "barely used, bought 3 months ago" | 行为证据 |
| 求推荐帖 | "is it worth it if I only..." | 购买前犹豫 |
| 长评（按使用时长分段） | "after a year..." | 衰减时间点 |

**二手转卖是最硬的证据**：挂牌理由往往就是衰减原因。

## 4. 抽取字段

| 字段 | 含义 |
|---|---|
| job | 购买时想完成的任务 |
| expected / realized | 期待 vs 实际 |
| decay_trigger | 衰减触发（见下表） |
| substitute | 现在用什么替代 |
| action | sold / shelved / gave_away / still_using |
| relevant | 是否本人真实经历（过滤新闻/提问） |

触发分类：`value_not_realized`、`friction`、`redundancy`、`discomfort`、
`charging`、`notification_fatigue`、`price_regret`、`other`。

## 5. Apple Watch 原型结果

样本：r/AppleWatch + r/AppleWatchFitness 近期评论，信号正则筛出 66 条自述，
模型判定 45 条为有效经历。

| 衰减触发 | 条数 |
|---|---|
| other | 18 |
| **价值未兑现（value_not_realized）** | **14** |
| 冗余（手机已能做） | 5 |
| 摩擦 | 3 |
| 价格后悔 | 2 |
| 不适 | 2 |
| 充电 | 1 |

处置：仍在用 27、不明 10、**吃灰 6**、已卖 2。

**"用处不大"不是一句模糊感受，它对应三个可命名的机制：**

1. **价值未兑现**：买它是为了健身/睡眠/提醒，但没形成习惯，功能没被用起来；
2. **冗余**：手机已经能做，手表是重复设备；
3. **摩擦/不适**：充电、佩戴、通知疲劳，让"戴上"这件事成本太高。

典型原话：

> "I have the Ultra exclusively for travel and long hikes... Otherwise though I barely use it."
> —— 买的是"长途徒步续航"，日常场景不成立，于是只在旅行时戴。

## 6. 这类洞察能变成什么机会

对做产品的人：

| 机会类型 | 例子 | 适合谁 |
|---|---|---|
| 复活层 | 用手机数据反推"你其实需要它"的提醒 | 第三方 App |
| 场景绑定 | 把设备绑定到具体习惯（睡眠/通勤/健身） | 第三方 App |
| 转卖/估值 | "吃灰资产"回收、二手定价 | 平台 |
| 配件 | 充电、佩戴舒适度 | 硬件 |

对 Apple 自己：这是产品路线图（续航、场景化提醒、减少冗余功能）。

## 7. 怎么正式集成进 PainRadar

1. **新语料类型**：`decay`，来源 Reddit/二手平台/长评；
2. **新原子字段**：`job`、`expected`、`realized`、`decay_trigger`、`substitute`、`action`；
3. **新指标**：`value_gap = expected - realized`（由模型判定 1–5 分）；
4. **新视图**：产品页展示"旅程漏斗"：购买 → 首周 → 习惯 → 衰减 → 处置；
5. **新排序**：`decay_score` 高且 `value_gap` 大的场景，是"复活型产品"的机会。

## 8. 局限

- 样本来自 Reddit，偏英语、偏愿意表达的人；
- 45 条里 18 条被归为 `other`，说明触发分类还不够细，需要第二轮归纳；
- 二手平台（eBay/闲鱼）未接入，行为证据缺失；
- LLM 判定是推断，不是实测使用数据。

## 9. 原型工具

```powershell
python tools/decay_mine.py --product "Apple Watch" \
  --subreddits AppleWatch,AppleWatchFitness \
  --pages 10 --max-texts 200 --out docs/apple-watch-decay.md
```

输出：衰减触发分布、处置动作、购买任务、典型叙述。
