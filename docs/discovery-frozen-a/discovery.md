# 无品类需求发现

> 语料：var\llm_full.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 72 | 180 | 3 | 6 | budgeting、pet_water_fountain、plant_care |
| 2 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 72 | 201 | 3 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 3 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 67 | 85 | 3 | 6 | budgeting、sleep_tech、pet_water_fountain |
| 4 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 63 | 53 | 3 | 6 | pet_water_fountain、sleep_tech、budgeting |
| 5 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 49 | 63 | 2 | 6 | pet_water_fountain、sleep_tech |
| 6 | 数据记录与统计不准确 | 数据记录与统计不准确 | 43 | 25 | 2 | 5 | budgeting、sleep_tech |
| 7 | 核心功能频繁崩溃闪退 | 核心功能频繁崩溃闪退 | 42 | 46 | 2 | 4 | budgeting、sleep_tech |
| 8 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 28 | 27 | 1 | 4 | pet_water_fountain |
| 9 | 识别与诊断准确性低 | 识别与诊断准确性低 | 25 | 79 | 1 | 3 | plant_care |
| 10 | 数据导出与迁移困难 | 数据导出与迁移困难 | 24 | 17 | 1 | 2 | budgeting |
| 11 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 24 | 8 | 1 | 1 | pet_water_fountain |

## 逐个需求

### 1. 订阅取消与退款不透明（72 分，180 条证据，跨 3 个域）

- 来源域：budgeting(91)、pet_water_fountain(86)、plant_care(3)
- 需求类型：订阅取消与退款不透明　变体：1 种说法
- 买家：付费订阅用户
- budgeting: 从 Mint 迁移、使用过 PocketGuard 的预算应用用户（91 条）
- pet_water_fountain: 付费订阅用户（86 条）
- plant_care: 植物养护应用用户（3 条）
- 覆盖 App：1252497129, 1410126781, 1586120661, 1621020173, 720151500, 921588809
- 强度：0.79　L2+：34%　代价信号：12%　付费信号：6%

> This app is only free to download. Once downloading the app there is no way around a paywall.

### 2. 关键提醒与警报不可靠（72 分，201 条证据，跨 3 个域）

- 来源域：sleep_tech(80)、pet_water_fountain(71)、plant_care(50)
- 需求类型：关键提醒与警报不可靠　变体：5 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（80 条）
- pet_water_fountain: 养狗人士（71 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1612792132
- 强度：0.71　L2+：36%　代价信号：2%　付费信号：5%

> Sounds stop after half hour.

### 3. 设备连接与同步不稳定（67 分，85 条证据，跨 3 个域）

- 来源域：budgeting(78)、sleep_tech(4)、pet_water_fountain(3)
- 需求类型：设备连接与同步不稳定　变体：3 种说法
- 买家：依赖硬件或外部数据的用户
- budgeting: 付费订阅用户（78 条）
- sleep_tech: iPhone 17 Pro Max 与 Apple Watch Ultra 3 用户（4 条）
- pet_water_fountain: 宠物智能设备用户（3 条）
- 覆盖 App：1138066420, 1621020173, 320606217, 936422955, 949414211, 994053492
- 强度：0.76　L2+：51%　代价信号：5%　付费信号：11%

> it decided I wasn’t wearing my Apple Watch

### 4. 更新后功能异常或数据丢失（63 分，53 条证据，跨 3 个域）

- 来源域：pet_water_fountain(47)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：3 种说法
- 买家：长期使用的老用户
- pet_water_fountain: iOS 用户，刚购买两台宠物饮水机（47 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 720151500, 921588809, 936422955
- 强度：0.77　L2+：17%　代价信号：2%　付费信号：0%

> It doesn’t even track in the middle of the night anymore

### 5. 客服响应慢且售后推诿（49 分，63 条证据，跨 2 个域）

- 来源域：pet_water_fountain(41)、sleep_tech(22)
- 需求类型：客服响应慢且售后推诿　变体：2 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: 使用PETLIBRO App和多台RFID喂食器、需要为猫控制单独饮食的宠物主人（41 条）
- sleep_tech: 付费订阅用户（22 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 320606217, 720151500, 921588809
- 强度：0.86　L2+：24%　代价信号：8%　付费信号：3%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 6. 数据记录与统计不准确（43 分，25 条证据，跨 2 个域）

- 来源域：budgeting(19)、sleep_tech(6)
- 需求类型：数据记录与统计不准确　变体：2 种说法
- 买家：依赖数据做决策的用户
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（19 条）
- sleep_tech: 把手机放在床头柜上使用睡眠追踪的用户（6 条）
- 覆盖 App：1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.71　L2+：32%　代价信号：4%　付费信号：4%

> It says I’m getting 1-2 hours of sleep a night when I’m getting 7-8.

### 7. 核心功能频繁崩溃闪退（42 分，46 条证据，跨 2 个域）

- 来源域：budgeting(42)、sleep_tech(4)
- 需求类型：核心功能频繁崩溃闪退　变体：2 种说法
- 买家：所有应用用户
- budgeting: 与伴侣合并财务、需要区分家庭与个人支出的用户（42 条）
- sleep_tech: 睡眠应用用户（4 条）
- 覆盖 App：1138066420, 1621020173, 936422955, 949414211
- 强度：0.73　L2+：30%　代价信号：2%　付费信号：4%

> the app closes out when you open it

### 8. 硬件设备耐用性差易故障（28 分，27 条证据，跨 1 个域）

- 来源域：pet_water_fountain(27)
- 需求类型：硬件设备耐用性差易故障　变体：3 种说法
- 买家：硬件产品购买者
- pet_water_fountain: 养猫用户（27 条）
- 覆盖 App：1586120661, 921588809, 994053492, 999707163
- 强度：0.73　L2+：56%　代价信号：0%　付费信号：11%

> There is no way to gauge water level without removing top to look, and to fill.

### 9. 识别与诊断准确性低（25 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died

### 10. 数据导出与迁移困难（24 分，17 条证据，跨 1 个域）

- 来源域：budgeting(17)
- 需求类型：数据导出与迁移困难　变体：2 种说法
- 买家：需要备份或换应用的用户
- budgeting: 使用该应用2年的老用户（17 条）
- 覆盖 App：936422955, 949414211
- 强度：0.72　L2+：53%　代价信号：0%　付费信号：6%

> would be nice to be able to make the categories a different color can’t stand that everything is one color on the graph.

### 11. 外出时远程监控与喂食失效（24 分，8 条证据，跨 1 个域）

- 来源域：pet_water_fountain(8)
- 需求类型：外出时远程监控与喂食失效　变体：2 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养猫的宠物主人（8 条）
- 覆盖 App：1586120661
- 强度：0.90　L2+：12%　代价信号：25%　付费信号：0%

> It works until you're out of town and it stopped working. What's the point of having batteries but not dispensing food??????
