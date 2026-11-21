# Google Trends 集成

> 结论：**能集成，已经接进项目了**；但它给的是"相对热度变化"，不是"搜索量"，
> 只能当作时机信号，不能当作需求规模。

## 1. 有没有官方 API

没有。Google Trends 只有网页内部接口：

| 接口 | 作用 |
|---|---|
| `/trends/api/explore` | 拿 widget token |
| `/trends/api/widgetdata/multiline` | 拿时间序列 |

直接请求会返回 **429**。必须先访问一次首页拿到 `NID` cookie，再带 cookie 请求，
才返回 200。项目里的 `GoogleTrends` 客户端就是按这个流程做的。

## 2. 怎么用

```powershell
# 指定关键词
python run.py trends --terms "pet water fountain,robot vacuum" --geo= --sleep 6

# 从需求快照取前 N 条，按 var/demand_terms.json 映射
python run.py trends --demands 7 --geo= --sleep 6

# 合并进发现页快照
python tools/merge_trends.py --snapshot var/discovery.json \
    --trends var/trends.json --terms var/demand_terms.json
```

结果缓存在 `var/trends_cache.json`，默认 7 天有效，避免频繁请求被限流。

## 3. 实测数据（全球，近 12 个月）

| 关键词 | 均值 | 首尾变化 | 峰值 |
|---|---|---|---|
| pet water fountain | 47.8 | **+87.3%** | 2026-04 |
| robot vacuum | 40.5 | -17.9% | 2026-05 |
| device won't connect to wifi | 12.9 | -34.5% | 2025-12 |
| app keeps disconnecting | 52.5 | -10.5% | 2026-06 |
| cancel subscription | 64.2 | -4.2% | 2026-02 |
| refund subscription | 71.2 | -20.0% | 2025-11 |
| reminder not working | 63.1 | **+20.8%** | 2026-06 |
| app notification not working | 33.6 | -17.8% | 2026-05 |
| app keeps crashing | 68.1 | -9.3% | 2025-12 |
| customer support not responding | 34.2 | **+130.0%** | 2026-05 |
| update broke my app | 3.6 | 无基线 | 2026-11 |

合并到需求后：

| 需求 | 市场趋势 |
|---|---|
| 客服响应慢且售后推诿 | **+130.0%** |
| 关键提醒与警报不可靠 | +1.5% |
| 核心功能频繁崩溃闪退 | -9.3% |
| 订阅取消与退款不透明 | -12.1% |
| 设备连接与同步不稳定 | -22.5% |

发现页每条需求下方现在会显示这一行（带来源关键词）。

## 4. 必须知道的四个限制

1. **相对值，不是量级**：单关键词序列被归一化到自身峰值（0–100），
   所以 `+87%` 只说明"比自己之前热"，不说明"搜的人多"。
2. **稀疏词没有基线**：`update broke my app` 的均值只有 3.6，首段为 0，变化率算不出来。
3. **语言与地域错配**：语料是英文、地理为全球；如果要看中国市场，得换成中文词 + `--geo=CN`，
   但中文词在 Trends 里的量级和英文不可比。
4. **采样噪声**：`customer support not responding` 的 +130% 来自小样本波动，
   不能直接当成"客服需求爆发"。

## 5. 为什么不直接进评分

现有机会分公式里 Timing 占 15%。把 Trends 塞进去很容易过拟合：
一个 +130% 的噪声词就能把某条需求抬高。

建议的做法（尚未启用）：

- 只对**均值 ≥ 30** 的关键词采信趋势；
- 变化率截断到 ±30%；
- 作为 Timing 的**乘数**（0.85–1.15），而不是替换 Timing；
- 在报告里标注"趋势来源：Google Trends，全球，近 12 个月"。

## 6. 工程

- `src/painradar/trends.py`：Cookie bootstrap + explore + multiline 解析
- `run.py trends`：取数、缓存、输出 JSON
- `tools/merge_trends.py`：把趋势合并进发现快照
- `var/demand_terms.json`：需求 → 关键词映射（当前 7 条）
- 测试：`tests/test_trends.py`（序列摘要、平坦序列、空序列）
- 总测试 **107 个全过**

## 7. 下一步

1. 给剩余需求补关键词映射；
2. 用 `--geo=CN` + 中文词做一次对照，看国内外是否同向；
3. 评估把截断后的趋势作为 Timing 乘数，并用 A/B 回测看排名是否更稳。

## 8. 国内 vs 海外对照（5 年窗口，同比）

用 5 年窗口算"最近 52 周 vs 前 52 周"，避开双十一/黑五的季节峰值：

| 主题 | 海外（全球） | 中国（geo=CN） |
|---|---|---|
| 扫地机器人 | **+122.7%** | -30.7% |
| 空气净化器 | **+135.0%** | -3.6% |
| 取消订阅 | +61.4% | **+470.8%** |
| 智能门锁 | +67.3% | -14.6% |

### 怎么读

1. **海外硬件需求在涨**：扫地机器人、空气净化器同比翻倍，门锁也在涨；
2. **国内硬件数据不可信**：Google 在中国大陆不可访问，`geo=CN` 只反映少量翻墙用户，
   样本偏到不能代表中国市场；
3. **取消订阅在中外都在涨**：海外 +61%、中国 +471%（后者基数极低，均值只有 6.3，
   放大效应明显，只能看方向）。

### 结论

- 如果做硬件，**买家更可能在海外**——这和语料来源（App Store 美区、Reddit、GitHub）一致；
- 如果做订阅管理，**中外都有需求**，但中国的真实规模无法用 Google Trends 判断；
- **不要用 geo=CN 的数据做中国市场的决策**，它的偏差比信号大。

## 9. 指标口径

时间序列的"变化"有三种算法，结论会差很多：

| 指标 | 算法 | 问题 |
|---|---|---|
| `change_pct` | 首 25% vs 末 25% | 受首尾峰值影响，中国 11 月会被双十一拉爆 |
| `trend_pct` | 最小二乘斜率 / 均值 | 低均值序列会被放大（扫地机器人算出 -368%） |
| `yoy_pct` | 最近 52 周 vs 前 52 周 | 需要 ≥104 个点（5 年窗口），最稳 |

合并进发现页时优先用 `yoy_pct`，没有则退回 `change_pct`。

## 10. 工程

- `TrendSeries.summary()` 现在输出三种指标：`change_pct` / `trend_pct` / `yoy_pct`
- `run.py trends` 的表格增加 `yoy` 列
- 需求 → 关键词映射补到 11 条（`var/demand_terms.json`）
- 测试新增 2 个（同比、短序列无同比），**共 109 个全过**
