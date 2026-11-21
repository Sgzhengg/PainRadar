# 无品类需求发现

> 语料：var\llm_full.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 87 | 257 | 4 | 6 | budgeting、pet_water_fountain、sleep_tech |
| 2 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 70 | 182 | 3 | 6 | pet_water_fountain、sleep_tech、plant_care |
| 3 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 68 | 115 | 3 | 6 | budgeting、pet_water_fountain、sleep_tech |
| 4 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 62 | 53 | 3 | 6 | pet_water_fountain、sleep_tech、budgeting |
| 5 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 47 | 86 | 2 | 6 | sleep_tech、pet_water_fountain |
| 6 | 数据记录与统计不准确 | 数据记录与统计不准确 | 44 | 131 | 2 | 6 | sleep_tech、budgeting |
| 7 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 27 | 18 | 1 | 4 | pet_water_fountain |
| 8 | 识别与诊断准确性低 | 识别与诊断准确性低 | 25 | 79 | 1 | 3 | plant_care |
| 9 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 24 | 8 | 1 | 1 | pet_water_fountain |

## 逐个需求

### 1. 订阅取消与退款不透明（87 分，257 条证据，跨 4 个域）

- 来源域：budgeting(91)、pet_water_fountain(86)、sleep_tech(72)、plant_care(8)
- 需求类型：订阅取消与退款不透明　变体：1 种说法
- 买家：付费订阅用户
- budgeting: 从 Mint 迁移、使用过 PocketGuard 的预算应用用户（91 条）
- pet_water_fountain: 付费订阅用户（86 条）
- sleep_tech: 使用该应用五六年的 Apple Watch 用户（72 条）
- plant_care: 植物养护应用用户（8 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1621020173
- 强度：0.73　L2+：27%　代价信号：15%　付费信号：4%

> after I woke up it wouldn’t let me view the recordings without paying for a ridiculous subscription

### 2. 关键提醒与警报不可靠（70 分，182 条证据，跨 3 个域）

- 来源域：pet_water_fountain(71)、sleep_tech(61)、plant_care(50)
- 需求类型：关键提醒与警报不可靠　变体：4 种说法
- 买家：依赖提醒功能的用户
- pet_water_fountain: 养狗人士（71 条）
- sleep_tech: 长期用户（61 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1612792132
- 强度：0.69　L2+：34%　代价信号：3%　付费信号：6%

> Deleting and finding another app.

### 3. 设备连接与同步不稳定（68 分，115 条证据，跨 3 个域）

- 来源域：budgeting(78)、pet_water_fountain(20)、sleep_tech(17)
- 需求类型：设备连接与同步不稳定　变体：3 种说法
- 买家：依赖硬件或外部数据的用户
- budgeting: 付费订阅用户（78 条）
- pet_water_fountain: 养狗人士，使用 iPhone 17（20 条）
- sleep_tech: iPhone 17 Pro Max 与 Apple Watch Ultra 3 用户（17 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 1621020173, 320606217, 720151500
- 强度：0.72　L2+：38%　代价信号：4%　付费信号：8%

> it decided I wasn’t wearing my Apple Watch

### 4. 更新后功能异常或数据丢失（62 分，53 条证据，跨 3 个域）

- 来源域：pet_water_fountain(47)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：3 种说法
- 买家：长期使用的老用户
- pet_water_fountain: iOS 用户，刚购买两台宠物饮水机（47 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 720151500, 921588809, 936422955
- 强度：0.77　L2+：17%　代价信号：2%　付费信号：0%

> It doesn’t even track in the middle of the night anymore

### 5. 客服响应慢且售后推诿（47 分，86 条证据，跨 2 个域）

- 来源域：sleep_tech(45)、pet_water_fountain(41)
- 需求类型：客服响应慢且售后推诿　变体：3 种说法
- 买家：需要售后支持的用户
- sleep_tech: 长期用户（45 条）
- pet_water_fountain: 使用PETLIBRO App和多台RFID喂食器、需要为猫控制单独饮食的宠物主人（41 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 320606217, 720151500, 921588809
- 强度：0.74　L2+：21%　代价信号：7%　付费信号：2%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 6. 数据记录与统计不准确（44 分，131 条证据，跨 2 个域）

- 来源域：sleep_tech(70)、budgeting(61)
- 需求类型：数据记录与统计不准确　变体：4 种说法
- 买家：依赖数据做决策的用户
- sleep_tech: 长期用户（70 条）
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（61 条）
- 覆盖 App：1138066420, 1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.65　L2+：26%　代价信号：3%　付费信号：2%

> Sounds stop after half hour.

### 7. 硬件设备耐用性差易故障（27 分，18 条证据，跨 1 个域）

- 来源域：pet_water_fountain(18)
- 需求类型：硬件设备耐用性差易故障　变体：2 种说法
- 买家：硬件产品购买者
- pet_water_fountain: Tractive 老用户、养猫人士（18 条）
- 覆盖 App：1586120661, 921588809, 994053492, 999707163
- 强度：0.73　L2+：50%　代价信号：0%　付费信号：11%

> After replacing the filter (as noted in my electronic notification), the fountain doesn’t work at all.

### 8. 识别与诊断准确性低（25 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died

### 9. 外出时远程监控与喂食失效（24 分，8 条证据，跨 1 个域）

- 来源域：pet_water_fountain(8)
- 需求类型：外出时远程监控与喂食失效　变体：2 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养猫的宠物主人（8 条）
- 覆盖 App：1586120661
- 强度：0.90　L2+：12%　代价信号：25%　付费信号：0%

> It works until you're out of town and it stopped working. What's the point of having batteries but not dispensing food??????
