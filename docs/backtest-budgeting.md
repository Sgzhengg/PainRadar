# 结局回测 — budgeting

- T0：2025-11-01 ｜ 窗口：2025-11-01 → 2026-11-01（12 个月）
- 训练集：258 条评论（T0 之前）→ 140 个原子 → 9 个簇（2 组）
- 抽取器：`rule` ｜ 关键词来源：`llm` ｜ 语义裁决：`llm`
- 预测数：2 ｜ 命中：2（100%）
- 随机基线：4 组，命中 2（50%）

| 簇 | 关键词 | GitHub 命中/候选 | App Store 命中/候选 | 命中 |
|---|---|---|---|---|
| 936422955:订阅与付费 | premium subscription buggy / subscription refund request / cancel subscription easily | — 0 | ✓ 15 | ✓ |
| 949414211:订阅与付费 | budget app free version / no subscription budgeting / one-time purchase budget | — 0 | ✓ 7 | ✓ |

## 证据

- **936422955:订阅与付费** — `在 2025-11-01 起 12 个月内，出现至少一个以「premium subscription buggy / subscription refund request / cancel subscription easily」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - Cancel Subscriptions: Submo · https://apps.apple.com/us/app/cancel-subscriptions-submo/id6796041389?uo=4 （yes: Subscription manager with cancel guidance）
  - Cancely: Subscription Manager · https://apps.apple.com/us/app/cancely-subscription-manager/id6778323362?uo=4 （yes: Track and cancel subscriptions, cancel guides）
  - Subtracker AI · https://apps.apple.com/us/app/subtracker-ai/id6783674801?uo=4 （yes: Manage subscriptions, understand how to cancel）
- **949414211:订阅与付费** — `在 2025-11-01 起 12 个月内，出现至少一个以「budget app free version / no subscription budgeting / one-time purchase budget」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - Budget & Subscriptions Kirum · https://apps.apple.com/us/app/budget-subscriptions-kirum/id6756943009?uo=4 （yes: Explicitly 'pay once', no subscription budget app）

## 解读与限制

- 这些预测在 2025-11-01 时点只能看到 258 条评论，样本很小；命中率只能当方向性参考。
- 结局来源只有 GitHub 与 App Store，覆盖不到硬件众筹、线下服务与 B 端采购，真实命中率会被低估。
- 随机基线使用同一语料词表，规模相同；若两者接近，说明关键词没有区分度，而不是「系统有效」。
- 关键词来自评论原文，可能包含噪声词；证据链接需要人工复核后才算数。