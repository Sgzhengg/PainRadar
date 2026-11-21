# 结局回测 — budgeting

- T0：2025-11-01 ｜ 窗口：2025-11-01 → 2026-11-01（12 个月）
- 训练集：258 条评论（T0 之前）→ 140 个原子 → 9 个簇（2 组）
- 抽取器：`rule` ｜ 关键词来源：`llm` ｜ 语义裁决：`llm`
- 预测数：6 ｜ 命中：2（33%）
- 随机基线：4 组，命中 1（25%）

| 簇 | 关键词 | GitHub 命中/候选 | App Store 命中/候选 | 命中 |
|---|---|---|---|---|
| 936422955:银行同步 | bank transaction sync / automatic transaction import / budget bank notifications | — 0 | — 1 | — |
| 936422955:记账与分类 | auto categorize transactions / bank sync budgeting / expense category rules | — 0 | ✓ 3 | ✓ |
| 936422955:预算与超支 | budget tracker crash fix / missing synced transactions / simple budgeting no overspend | — 0 | — 3 | — |
| 949414211:银行同步 | bank sync fix / plaid connection error / bank reconnect transactions | — 0 | — 2 | — |
| 949414211:记账与分类 | budgeting app alternative / expense tracker categories / personal finance analytics | — 0 | ✓ 1 | ✓ |
| 949414211:订阅与付费 | budget app free tier / subscription tracker no premium / money tracker one-time purchase | — 0 | — 5 | — |

## 证据

- **936422955:记账与分类** — `在 2025-11-01 起 12 个月内，出现至少一个以「auto categorize transactions / bank sync budgeting / expense category rules」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - Skarbo: Budget Expense Tracker · https://apps.apple.com/us/app/skarbo-budget-expense-tracker/id6795880230?uo=4 （yes: AI auto-categorizes receipts and imports bank statements）
  - Quanto: Budget Expense Tracker · https://apps.apple.com/us/app/quanto-budget-expense-tracker/id6749017099?uo=4 （yes: AI assigns categories from receipts and bank statements）
- **949414211:记账与分类** — `在 2025-11-01 起 12 个月内，出现至少一个以「budgeting app alternative / expense tracker categories / personal finance analytics」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。`
  - Quanto: Budget Expense Tracker · https://apps.apple.com/us/app/quanto-budget-expense-tracker/id6749017099?uo=4 （yes: Expense tracker with categories, matches pain directly）

## 解读与限制

- 这些预测在 2025-11-01 时点只能看到 258 条评论，样本很小；命中率只能当方向性参考。
- 结局来源只有 GitHub 与 App Store，覆盖不到硬件众筹、线下服务与 B 端采购，真实命中率会被低估。
- 随机基线使用同一语料词表，规模相同；若两者接近，说明关键词没有区分度，而不是「系统有效」。
- 关键词来自评论原文，可能包含噪声词；证据链接需要人工复核后才算数。