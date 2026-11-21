# 无品类需求发现

> 语料：var\llm.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 69 | 47 | 3 | 6 | budgeting、plant_care、sleep_tech |
| 2 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 65 | 31 | 3 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 3 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 48 | 35 | 2 | 5 | budgeting、sleep_tech |
| 4 | 数据记录与统计不准确 | 数据记录与统计不准确 | 46 | 46 | 2 | 6 | sleep_tech、budgeting |
| 5 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 31 | 74 | 1 | 5 | pet_water_fountain |
| 6 | 广告与通知骚扰影响体验 | 广告与通知骚扰影响体验 | 30 | 55 | 1 | 3 | sleep_tech |

## 逐个需求

### 1. 订阅取消与退款不透明（69 分，47 条证据，跨 3 个域）

- 来源域：budgeting(24)、plant_care(20)、sleep_tech(3)
- 需求类型：订阅取消与退款不透明　变体：2 种说法
- 买家：付费订阅用户
- budgeting: 从 Mint 迁移过来的预算应用用户（24 条）
- plant_care: 10岁女孩（20 条）
- sleep_tech: 睡眠应用用户（3 条）
- 覆盖 App：1252497129, 1410126781, 1490078804, 1612792132, 1621020173, 320606217
- 强度：0.79　L2+：34%　代价信号：17%　付费信号：4%

> I signed up for free trial cancelled and was still charged

### 2. 关键提醒与警报不可靠（65 分，31 条证据，跨 3 个域）

- 来源域：sleep_tech(11)、pet_water_fountain(10)、plant_care(10)
- 需求类型：关键提醒与警报不可靠　变体：4 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（11 条）
- pet_water_fountain: 住在社区住宅、院子较大的养狗用户（10 条）
- plant_care: iPhone 用户（10 条）
- 覆盖 App：1252497129, 1410126781, 1490078804, 1612792132, 320606217, 720151500
- 强度：0.70　L2+：32%　代价信号：0%　付费信号：6%

> I cannot even edit this reminder so I deleted it and will use a calendar reminder instead.

### 3. 设备连接与同步不稳定（48 分，35 条证据，跨 2 个域）

- 来源域：budgeting(25)、sleep_tech(10)
- 需求类型：设备连接与同步不稳定　变体：2 种说法
- 买家：依赖硬件或外部数据的用户
- budgeting: Redwood Credit Union 银行用户（25 条）
- sleep_tech: iPhone 15 Pro Max 用户（10 条）
- 覆盖 App：1138066420, 1621020173, 320606217, 936422955, 949414211
- 强度：0.76　L2+：54%　代价信号：6%　付费信号：6%

> I tried everything—permissions, settings, reinstalling the app—nothing works.

### 4. 数据记录与统计不准确（46 分，46 条证据，跨 2 个域）

- 来源域：sleep_tech(32)、budgeting(14)
- 需求类型：数据记录与统计不准确　变体：3 种说法
- 买家：依赖数据做决策的用户
- sleep_tech: iPhone 16 Pro Max用户（32 条）
- budgeting: 与他人分摊账单的家庭用户（14 条）
- 覆盖 App：1138066420, 1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.73　L2+：30%　代价信号：4%　付费信号：0%

> 把梦境记录删了. 为什么把记录做梦的删了？以前记录的梦境也没有了？这是乐趣，为什么没了？除了一堆数据，我辛辛苦苦记录的梦境呢？也没给我保留

### 5. 外出时远程监控与喂食失效（31 分，74 条证据，跨 1 个域）

- 来源域：pet_water_fountain(74)
- 需求类型：外出时远程监控与喂食失效　变体：2 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: Furbo 长期用户（74 条）
- 覆盖 App：1586120661, 720151500, 921588809, 994053492, 999707163
- 强度：0.77　L2+：30%　代价信号：1%　付费信号：0%

> Waste of money. Didn’t renew subscription because pet cam is always offline.

### 6. 广告与通知骚扰影响体验（30 分，55 条证据，跨 1 个域）

- 来源域：sleep_tech(55)
- 需求类型：广告与通知骚扰影响体验　变体：1 种说法
- 买家：免费版或所有用户
- sleep_tech: 12岁用户（55 条）
- 覆盖 App：1138066420, 1490078804, 320606217
- 强度：0.79　L2+：38%　代价信号：14%　付费信号：2%

> Must be 16 to enter??!. I mean I get that some apps have age restricting content but what I don’t get is how you must be 16 to enter a sleep tracking app.
