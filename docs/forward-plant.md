# 前向测试登记 — 植物养护应用

- 登记日 T0：2026-11-14 ｜ 回看日：2027-11-09（12 个月）
- 训练语料：581 条评论 → 170 原子 → 7 簇
- 登记预测：3 条（域名门槛：plant / leaf / soil / pest / watering / sunlight / fertilizer / pot …）
- 判定规则：预注册，跑之前不得修改；见 `docs/forward-protocol.md`

| # | 簇 | 关键词 | 证据条数 |
|---|---|---|---|
| 1 | 浇水与提醒 | plant watering reminder / watering schedule tracker / plant care reminders | 32 |
| 2 | 识别准确性 | plant identification accuracy / accurate plant identifier / fix wrong plant ID | 21 |
| 3 | 病虫害诊断 | plant disease identifier / pest diagnosis camera / plant health scanner | 12 |

## 命题原文

- `pred_7fd7055b5baf` — 在 2026-11-14 起 12 个月内，出现至少一个以「plant watering reminder / watering schedule tracker / plant care reminders」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。
- `pred_f4e8d3ab6420` — 在 2026-11-14 起 12 个月内，出现至少一个以「plant identification accuracy / accurate plant identifier / fix wrong plant ID」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。
- `pred_cb24d7da2298` — 在 2026-11-14 起 12 个月内，出现至少一个以「plant disease identifier / pest diagnosis camera / plant health scanner」为卖点的付费产品（GitHub 项目 ≥5 stars 或 App Store 新上架应用）。

## 预注册基线（6 组，同流程）

- `base_01` — reminders steep / charged canceled / almost won
- `base_02` — subscription sick / freezes audio / feature freezes
- `base_03` — ending subscription / copy pasted / subscription don
- `base_04` — care plants / see changing / subscription paid
- `base_05` — wrong able / planta support / busy forgetful
- `base_06` — problem providing / manage collection / always right