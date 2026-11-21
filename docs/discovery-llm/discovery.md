# 无品类需求发现

> 语料：var\llm.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消后仍被扣费 | 订阅取消后仍被扣费 | 69 | 47 | 3 | 6 | budgeting、plant_care、sleep_tech |
| 2 | 提醒功能不准确或无法编辑 | 提醒功能不准确或无法编辑 | 65 | 31 | 3 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 3 | 设备频繁断连或离线 | 设备频繁断连或离线 | 51 | 84 | 2 | 6 | pet_water_fountain、sleep_tech |
| 4 | 数据记录丢失或错乱 | 数据记录丢失或错乱 | 46 | 43 | 2 | 6 | sleep_tech、budgeting |
| 5 | App内广告干扰正常使用 | App内广告干扰正常使用 | 30 | 55 | 1 | 3 | sleep_tech |
| 6 | 客服响应慢且不解决问题 | 客服响应慢且不解决问题 | 28 | 6 | 1 | 3 | pet_water_fountain |
| 7 | 银行同步失败或中断 | 银行同步失败或中断 | 28 | 25 | 1 | 3 | budgeting |
| 8 | 报表分析功能缺失或崩溃 | 报表分析功能缺失或崩溃 | 26 | 6 | 1 | 2 | budgeting |
| 9 | 核心功能识别或追踪不准 | 核心功能识别或追踪不准 | 22 | 12 | 1 | 3 | plant_care |
| 10 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 20 | 7 | 1 | 2 | pet_water_fountain |

## 逐个需求

### 1. 订阅取消后仍被扣费（69 分，47 条证据，跨 3 个域）

- 来源域：budgeting(24)、plant_care(20)、sleep_tech(3)
- 需求类型：订阅取消后仍被扣费　变体：2 种说法
- 买家：订阅制App用户
- budgeting: 从 Mint 迁移过来的预算应用用户（24 条）
- plant_care: 10岁女孩（20 条）
- sleep_tech: 睡眠应用用户（3 条）
- 覆盖 App：1252497129, 1410126781, 1490078804, 1612792132, 1621020173, 320606217
- 强度：0.79　L2+：34%　代价信号：17%　付费信号：4%

> I signed up for free trial cancelled and was still charged

### 2. 提醒功能不准确或无法编辑（65 分，31 条证据，跨 3 个域）

- 来源域：sleep_tech(11)、pet_water_fountain(10)、plant_care(10)
- 需求类型：提醒功能不准确或无法编辑　变体：4 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（11 条）
- pet_water_fountain: 住在社区住宅、院子较大的养狗用户（10 条）
- plant_care: iPhone 用户（10 条）
- 覆盖 App：1252497129, 1410126781, 1490078804, 1612792132, 320606217, 720151500
- 强度：0.70　L2+：32%　代价信号：0%　付费信号：6%

> I cannot even edit this reminder so I deleted it and will use a calendar reminder instead.

### 3. 设备频繁断连或离线（51 分，84 条证据，跨 2 个域）

- 来源域：pet_water_fountain(74)、sleep_tech(10)
- 需求类型：设备频繁断连或离线　变体：3 种说法
- 买家：智能设备用户
- pet_water_fountain: Furbo 长期用户（74 条）
- sleep_tech: iPhone 15 Pro Max 用户（10 条）
- 覆盖 App：1138066420, 1586120661, 320606217, 720151500, 921588809, 994053492
- 强度：0.77　L2+：33%　代价信号：1%　付费信号：0%

> Waste of money. Didn’t renew subscription because pet cam is always offline.

### 4. 数据记录丢失或错乱（46 分，43 条证据，跨 2 个域）

- 来源域：sleep_tech(32)、budgeting(11)
- 需求类型：数据记录丢失或错乱　变体：2 种说法
- 买家：记录数据的用户
- sleep_tech: iPhone 16 Pro Max用户（32 条）
- budgeting: 与他人分摊账单的家庭用户（11 条）
- 覆盖 App：1138066420, 1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.72　L2+：28%　代价信号：5%　付费信号：0%

> 把梦境记录删了. 为什么把记录做梦的删了？以前记录的梦境也没有了？这是乐趣，为什么没了？除了一堆数据，我辛辛苦苦记录的梦境呢？也没给我保留

### 5. App内广告干扰正常使用（30 分，55 条证据，跨 1 个域）

- 来源域：sleep_tech(55)
- 需求类型：App内广告干扰正常使用　变体：1 种说法
- 买家：免费版或试用期用户
- sleep_tech: 12岁用户（55 条）
- 覆盖 App：1138066420, 1490078804, 320606217
- 强度：0.79　L2+：38%　代价信号：14%　付费信号：2%

> Must be 16 to enter??!. I mean I get that some apps have age restricting content but what I don’t get is how you must be 16 to enter a sleep tracking app.

### 6. 客服响应慢且不解决问题（28 分，6 条证据，跨 1 个域）

- 来源域：pet_water_fountain(6)
- 需求类型：客服响应慢且不解决问题　变体：1 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: 使用双追踪器约四年的宠物主人（6 条）
- 覆盖 App：720151500, 921588809, 994053492
- 强度：0.87　L2+：33%　代价信号：0%　付费信号：33%

> I am actively looking for better and more reliable products with decent customer service if anyone has a recommendation.

### 7. 银行同步失败或中断（28 分，25 条证据，跨 1 个域）

- 来源域：budgeting(25)
- 需求类型：银行同步失败或中断　变体：1 种说法
- 买家：使用自动同步的用户
- budgeting: Redwood Credit Union 银行用户（25 条）
- 覆盖 App：1621020173, 936422955, 949414211
- 强度：0.76　L2+：52%　代价信号：8%　付费信号：8%

> Now they’re not responding at all, since I’ve paid and couldn’t get the issue resolved before my trial period ended.

### 8. 报表分析功能缺失或崩溃（26 分，6 条证据，跨 1 个域）

- 来源域：budgeting(6)
- 需求类型：报表分析功能缺失或崩溃　变体：2 种说法
- 买家：需要分析数据的用户
- budgeting: 使用PocketGuard超过一年的忠实用户（6 条）
- 覆盖 App：936422955, 949414211
- 强度：0.77　L2+：67%　代价信号：0%　付费信号：0%

> Going back to the Dave Ramsey app.

### 9. 核心功能识别或追踪不准（22 分，12 条证据，跨 1 个域）

- 来源域：plant_care(12)
- 需求类型：核心功能识别或追踪不准　变体：1 种说法
- 买家：依赖核心功能的用户
- plant_care: 夏威夷用户（12 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.70　L2+：25%　代价信号：0%　付费信号：0%

> I am canceling and asking for a full refund! Not worth the money or time I spent trying to get this app to recognize my plant!

### 10. 更新后功能异常或数据丢失（20 分，7 条证据，跨 1 个域）

- 来源域：pet_water_fountain(7)
- 需求类型：更新后功能异常或数据丢失　变体：1 种说法
- 买家：依赖自动更新的用户
- pet_water_fountain: 使用自动喂食器 App 的宠物主人（7 条）
- 覆盖 App：1586120661, 994053492
- 强度：0.74　L2+：14%　代价信号：0%　付费信号：0%

> Updated app and it deleted my account. Worked fine until they forced update and now I can’t feed my pets.
