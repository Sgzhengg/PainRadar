# 数据来源与审计

> 回答一个问题：**库里的每一批数据，是什么时候、用什么参数、从哪个源抓的？**
> 这份文档列出当前所有数据库的来源，并说明审计（audit）覆盖情况。

## 1. 数据库清单

| 数据库 | 来源 | 采集工具 | 条数 | 审计 |
|---|---|---|---|---|
| `gold.db` | App Store（宠物/睡眠/记账/植物） | `run.py fetch --source appstore` | 3,734 | ✅ 162 条 |
| `gold200.db` | gold.db 的分层子集 | `tools/make_goldset.py` | 200 | ✅（继承） |
| `llm_full.db` | gold.db 四品类全量副本 | `tools/sample_categories.py` | 3,307 | ✅ |
| `llm.db` | 四品类各 150 条抽样 | `tools/sample_categories.py` | 600 | ✅ |
| `hardware.db` | App Store（扫地机器人/空气净化器/智能门锁） | `tools/fetch_hardware.py` | 725 | ✅ 回填 |
| `topcharts.db` | App Store 总榜 40 个 App | `tools/fetch_topcharts.py` | 3,525 | ✅ 回填 |
| `topcharts_llm.db` | 总榜抽样 1,000 条 | `tools/sample_categories.py` | 1,000 | ✅ 回填 |
| `community.db` | GitHub Issues + Hacker News | `tools/fetch_community.py` | 826 | ✅ 回填 |
| `reddit.db` | Reddit（Arctic Shift 存档） | `tools/fetch_reddit.py` | 1,864 | ✅ 回填 |
| `forward.db` | 植物养护前向测试登记 | `tools/forward_register.py` | 581 | ✅ |
| `painradar.db` | **合成演示数据（非爬取）** | `run.py demo` | 80 | ✅ 标注 synthetic |

真实采集合计约 **10,700 条**、66 个 App。

## 2. 审计表结构

```sql
SELECT ts, actor, action, object_type, object_id, detail FROM audit;
```

- `actor`：`cli` / `tool` / `backfill` / `system`
- `action`：`fetch` / `run` / `delete` / `fetch`
- `object_type`：平台（`appstore` / `github` / `hackernews` / `reddit`）
- `object_id`：品类 key
- `detail`：条数与参数（JSON，CLI 路径是 Python dict 字符串）

示例：

```sql
-- 某个库的数据来源
SELECT ts, actor, object_type, object_id, detail FROM audit WHERE action='fetch';

-- 某个品类的抓取历史
SELECT * FROM audit WHERE object_id='custom_robot_vacuum';
```

## 3. 必须知道的限制

1. **回填的审计不完整**：`backfill` 行只记录“当前条数”，无法恢复原始抓取时间与参数。
2. **演示数据被明确标注**：`painradar.db` 里的 `amazon/xiaohongshu/zhihu/trustpilot` 全部是合成数据，
   不是真实爬取；审计里写着 `synthetic demo data`。
3. **抽样库会继承来源**：`llm.db`、`llm_full.db`、`topcharts_llm.db` 是从主库复制后再抽样的，
   审计记录的是复制时点，不追踪每次抽样。
4. **审计不防篡改**：它是普通表，只能用于追溯，不是密码学证明。

## 4. 复现一次采集

```powershell
# App Store（单品类）
python run.py fetch --source appstore --category pet_water_fountain --search "pet water fountain" --pages 3

# 硬件品类
python tools/fetch_hardware.py --db var/hardware.db --pages 2

# 社区
python tools/fetch_community.py --db var/community.db --per-query 40

# Reddit（存档）
python tools/fetch_reddit.py --db var/reddit.db --pages 2

# 老库补审计
python tools/backfill_audit.py
```

每次采集后，对应库会新增 `actor=tool` 的 `fetch` 审计行。
