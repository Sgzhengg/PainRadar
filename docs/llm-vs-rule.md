# Rule vs LLM — pet_water_fountain

- A (rule): `20261110T161437Z-7a3513`
- B (llm):  `20261110T163648Z-9977da`

| metric | A (rule) | B (llm) |
|---|---|---|
| items | 99 | 99 |
| atoms | 67 | 97 |
| atoms/item | 0.68 | 0.98 |
| L2+ share | 17.9% | 25.8% |
| avg confidence | 0.62 | 0.80 |
| has workaround | 9.0% | 32.0% |
| has cost | 7.5% | 8.2% |
| has persona | 26.9% | 42.3% |
| has wtp | 1.5% | 4.1% |
| avg quote chars | 88 | 113 |
| avg obstacle chars | 72 | 32 |
| clusters | 5 | 6 |
| noise rate | 1.2% | 6.2% |

**LLM extraction stats**

- calls: 197
- tokens in/out: 127923 / 31861
- fallback: 15 {'disagree': 14, 'no_span': 1}
- disagree: 14
- errors: {}

**model versions (B)**: `{"extract-llm-v0.2|agree": 61, "extract-llm-v0.2|soft": 23, "extract-llm-v0.2|fallback-disagree": 12, "extract-llm-v0.2|fallback-no_span": 1}`

## Samples — A (rule)

- [L1] 外出托管 · 'not recommended for travel - it’s just not reliable' · wa='' · conf=0.61
- [L2] App 与连接 · 'Waste of money on the device and absolutely useless app' · wa='I just bought the cordless water fountai' · conf=0.67
- [L4] App 与连接 · 'Purchased Granary Feeder 2 and app is straight up does not work outside home network' · wa='' · conf=0.67
- [L1] App 与连接 · "It works until you're out of town and it stopped working" · wa='' · conf=0.61
- [L1] 固件与更新 · 'It will not open or reset' · wa='' · conf=0.53

## Samples — B (llm)

- [L1] 客服与售后 · '联系不上客服，且对方不履行保修' · wa='' · conf=0.90
- [L1] 其他场景 · "Doesn't stay cold" · wa='' · conf=0.47
- [L1] App 与连接 · 'The feeder stopped working without any warning' · wa='' · conf=0.49
- [L1] App 与连接 · '服务器宕机导致无法通过 App 喂食' · wa='' · conf=0.72
- [L1] App 与连接 · 'App 更新后喂食器被删除，重新连接反复失败' · wa='' · conf=0.90

## 结论

1. **覆盖**：LLM 把可用原子从 0.68/条 提到 0.98/条，绕行方案识别率 9% → 32%，人群字段 27% → 42%。
2. **可读性**：阻碍描述从 72 字符降到 32 字符，且统一为中文，卡片更像"人写的"。
3. **稳定性**：双跑只有 61/97 完全一致（63%），23 条软不一致（同结构不同措辞），14 条硬冲突回退。
   双跑是"用 2 倍成本换确定性"，不是免费的保险。
4. **代价字段**：初次运行 cost_type 覆盖 86.7%，抽查发现大量"推断成本"（把情绪/风险当代价）。
   加"必须有明确金额或时长才允许标注"的硬门后降到 8.2%，与规则抽取（7.5%）对齐。
5. **L4 定义**：初次把"买过产品"判成 L4，导致 46% 的原子堆在 L4，阶梯失效。
   改为"为**解决这个痛点**付过钱"后，L4 降到 1%，分布恢复。
6. **成本**：197 次调用、128k 输入 / 32k 输出 token。按 DeepSeek 公开价目量级估算，
   99 条约 ¥0.5–1（双跑），即 ¥5–10/千条；以实际账单为准。

**建议**：高价值品类默认双跑 + 人工抽检；批量探索用单跑 + 10% 抽样复核。
在 A 集金标建立之前，LLM 结果只能用于"生成假设"，不能用于对外定价。
