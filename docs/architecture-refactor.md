# 架构统一与体验升级（2026-11-21）

> 目标：把 MediaCrawler 数据纳入主干证据台账，降低 LLM 成本，补上独立开发者可行性，
> 并让机会卡能直接导出外联名单。

## 1. 管线统一

| 之前 | 现在 |
|---|---|
| `tools/indie_mine.py` 独立跑 JSON，结果不进 SQLite | `connectors/mediacrawler.py` 走标准 Connector，写入 `items` 台账 |
| WebUI 看不到国内平台数据 | 与 App Store/Reddit 同一条 `run` 流程 |
| 上下文只存在脚本内存 | `items.parent_context` 持久化 |

新增字段（自动迁移，旧库无需重建）：

- `items`: `parent_context`, `likes`, `replies`, `post_id`
- `atoms`: `canonical_pain`
- `opportunities`: `solo_fit_json`

## 2. 连接器

`src/painradar/connectors/mediacrawler.py`

- 支持 JSON / JSONL / CSV；
- 自动识别小红书（note_id）、B站（bvid/aid）、知乎（question_id）、抖音（aweme_id）字段；
- 每条评论产出 `RawItem`，`text` 只含该条评论（span 闸门仍锚定它），
  原帖标题/正文/高赞评论/楼层放在 `parent_context`；
- 复用 `indie.clean` 的降噪规则（过短 / 表情 / @ / 广告）；
- `likes`、`replies` 入库，用于热度排序与外联导出。

CLI：

```bash
python run.py ingest --source mediacrawler --category pet_water_fountain \
  --file data/xhs_export.json [--field-map mapping.json]
```

## 3. LLM 单跑 + CoT

- `LLMExtractor.consistency` 默认 `False`；`--double-run` 才启用第二遍一致性校验；
- 提示词新增 `reasoning`（先推理目标与阻碍）与 `canonical_pain`（4–12 字需求短语）；
- `parent_context` 作为 `thread_context` 传入，但 `quote` 仍必须能在本评论原文定位。

预期：调用量减半；用 CoT + 三道 span 闸门替代双跑一致性。

## 4. 聚类改为语义优先

`cluster.py` 先按 `canonical_pain` 分组，缺失时回退到 `scene`：

- 同一痛点跨场景不再被切碎；
- 新品类不必先维护静态场景词典。

## 5. 独立开发者可行性

`scoring.assess_solo_fit(atoms)` 返回：

```json
{"level": "低|中|高", "mvp_days": "3–10 天", "form": "浏览器插件",
 "monetization": "买断", "score": 0.9, "note": "..."}
```

规则：

- 命中硬件/供应链/安装 → 高难度，排序时降权（排在软件机会之后）；
- 命中人工运营/客服/交付 → 中；
- 纯软件 → 低，并按文本推荐插件/小程序/脚本形态。

## 6. WebUI

- 机会卡显示 `⚡ 3–10 天可做 · 浏览器插件 · 买断`；
- 下钻抽屉显示“一人开发”一行；
- 证据引用显示点赞数；
- 新增按钮：**导出种子用户外联表 (CSV)**。

接口：

```
GET /api/runs/{run_id}/clusters/{cluster_id}/outreach.csv
```

导出列：`url, quote, likes, level, scene, icebreaker`；只含 L2–L4，按点赞降序，
`icebreaker` 由该条证据的 scene + quote 生成。

## 7. 测试

新增：

- `tests/test_mediacrawler.py`：字段识别、上下文、降噪、入台账；
- `tests/test_solo_outreach.py`：solo_fit、单跑默认值、CoT 字段、CSV 过滤与排序。

全量：144 个测试通过。

## 8. 已知限制

1. CSV 导出只覆盖同一簇内的 L2–L4，簇较小时名单会很少；
2. `assess_solo_fit` 是关键词规则，不理解“两周能否做完”；
3. 单跑后若模型漏抽，只有规则兜底，没有第二次意见；
4. `tools/indie_mine.py` 仍保留用于离线实验，但不再是数据入口。
