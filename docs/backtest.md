# 结局回测 — pet_water_fountain

- T0：2025-11-01 ｜ 窗口：2025-11-01 → 2026-11-01（12 个月）
- 训练集：307 条评论（T0 之前）→ 173 个原子 → 9 个簇（3 组）
- 抽取器：`rule` ｜ 关键词来源：`llm` ｜ 语义裁决：`llm`
- 预测数：5 ｜ 命中：2（40%）
- 随机基线：6 组，命中 4（67%），错误 2 组

| 簇 | 关键词 | GitHub 命中/候选 | App Store 命中/候选 | 命中 |
|---|---|---|---|---|
| 720151500:App 与连接 | pet camera app lag / dog barking alert / camera app glitch fix | — 0 | — 7 | — |
| 720151500:固件与更新 | firmware update rollback / camera setup travel / auto update disable | — 0 | — 3 | — |
| 720151500:订阅与付费 | cancel subscription refund / unauthorized charge dispute / subscription cancellation tracker | — 0 | ✓ 15 | ✓ |
| 994053492:App 与连接 | device already bound error / remove fake devices / app false sensor alerts | — 0 | — 2 | — |
| 994053492:清洗换水 | self-cleaning litter box / automatic litter waste disposal / no-spill water refill | — 0 | ✓ 5 | ✓ |

## 证据

- **720151500:订阅与付费** — `在 2025-11-01 起 12 个月内，出现至少一个以「cancel subscription refund / unauthorized charge dispute / subscription cancellation tracker」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - SubSeek: Subscription Manager · https://apps.apple.com/us/app/subseek-subscription-manager/id6769329967?uo=4 （yes: Manages cancellations and refund guidance for subscriptions）
  - Cancel Subscriptions: Submo · https://apps.apple.com/us/app/cancel-subscriptions-submo/id6796041389?uo=4 （yes: Shows how to cancel subscriptions, core cancellation tracker）
  - Subtracker AI · https://apps.apple.com/us/app/subtracker-ai/id6783674801?uo=4 （yes: Tracks subscriptions and explains how to cancel）
- **994053492:清洗换水** — `在 2025-11-01 起 12 个月内，出现至少一个以「self-cleaning litter box / automatic litter waste disposal / no-spill water refill」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - Popur S7 · https://apps.apple.com/us/app/popur-s7/id6756484154?uo=4 （yes: Smart cat device with cleaning control, likely litter box）

## 解读与限制

- 这些预测在 2025-11-01 时点只能看到 307 条评论，样本很小；命中率只能当方向性参考。
- 结局来源只有 GitHub 与 App Store，覆盖不到硬件众筹、线下服务与 B 端采购，真实命中率会被低估。
- 随机基线使用同一语料词表，规模相同；若两者接近，说明关键词没有区分度，而不是「系统有效」。
- 关键词来自评论原文，可能包含噪声词；证据链接需要人工复核后才算数。
## 第三次回测（按 App 拆分，6 个应用）

| 指标 | 数值 |
|---|---|
| 训练集 | 307 条（T0 前，3 个 App 各 ≥60 条） |
| 簇 | 9 |
| 合格预测 | 5（域名门槛过滤后） |
| 命中 | 2（40%） |
| 随机基线 | 4/6（67%），2 组因 GitHub 限流出错 |

**证据质量明显变好**：

- 订阅与付费：`SubSeek / Submo / Subtracker AI`——2025-12 至 2026-08 上架，
  都是"取消订阅/退款"工具，与"订阅取消难"的痛点直接对应。
- 清洗换水：`Popur S7`——自动猫砂盆 App，与"自清洁/自动清空"对应。

**但 lift 仍然是负的**（40% vs 67%）。原因不是预测差，而是基线仍然太容易：
随机 bigram 组合（如 "clean water"）配上语义裁决，依然能匹配到大量通用 App。

## 结论：B 集停在"证据可信、统计不可用"

三次回测给出的稳定结论只有一条：**单条证据现在可以信，整体命中率还不能用**。

要继续，缺的不是代码，而是三样东西：

1. **预测数量**：5 条无法做统计；至少 30 条，需要 5+ 品类、数千条评论。
2. **合格的基线**：随机 bigram 太容易命中。应改成"随机品类主题"（如随机抽 3 个
   App Store 分类），或"同语料随机簇"，让基线难度与预测可比。
3. **预注册**：先写死判定规则、阈值、样本量，再跑；否则每轮都会得到不同结论。

在这三件事完成前，B 集不应该对外发布任何"命中率"数字。
