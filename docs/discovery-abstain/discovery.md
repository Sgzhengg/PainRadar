# 无品类需求发现

> 语料：var\llm_full.db, var\community.db, var\hardware.db, var\reddit.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 118 | 319 | 7 | 6 | pet_water_fountain、budgeting、custom_air_purifier |
| 2 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 95 | 55 | 6 | 6 | pet_water_fountain、custom_smart_home、custom_air_purifier |
| 3 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 93 | 231 | 5 | 6 | pet_water_fountain、budgeting、sleep_tech |
| 4 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 90 | 272 | 5 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 5 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 88 | 211 | 5 | 6 | pet_water_fountain、custom_robot_vacuum、sleep_tech |
| 6 | 核心功能频繁崩溃闪退 | 核心功能频繁崩溃闪退 | 68 | 92 | 4 | 6 | budgeting、custom_smart_lock、pet_water_fountain |
| 7 | 数据记录与统计不准确 | 数据记录与统计不准确 | 59 | 41 | 3 | 6 | budgeting、custom_air_purifier、sleep_tech |
| 8 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 43 | 193 | 2 | 6 | pet_water_fountain、custom_robot_vacuum |
| 9 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 39 | 14 | 2 | 1 | pet_water_fountain、custom_smart_home |
| 10 | 识别与诊断准确性低 | 识别与诊断准确性低 | 23 | 79 | 1 | 3 | plant_care |

## 逐个需求

### 1. 设备连接与同步不稳定（118 分，319 条证据，跨 7 个域）

- 来源域：pet_water_fountain(132)、budgeting(78)、custom_air_purifier(36)、custom_robot_vacuum(24)、custom_smart_lock(23)、custom_smart_home(22)
- 需求类型：设备连接与同步不稳定　变体：10 种说法
- 买家：依赖硬件或外部数据的用户
- pet_water_fountain: Home Assistant 用户（132 条）
- budgeting: 付费订阅用户（78 条）
- custom_air_purifier: Everest 空气净化器用户（36 条）
- custom_robot_vacuum: 15年内购买至少五台Roomba的老用户（24 条）
- custom_smart_lock: Microsoft Exchange 邮箱用户（23 条）
- custom_smart_home: Home Assistant 与 Matter 集成用户（22 条）
- 覆盖 App：1012014442, 1016299342, 1034649547, 1138066420, 1152066360, 1289575311
- 强度：0.66　L2+：46%　代价信号：2%　付费信号：3%

> it decided I wasn’t wearing my Apple Watch

### 2. 更新后功能异常或数据丢失（95 分，55 条证据，跨 6 个域）

- 来源域：pet_water_fountain(22)、custom_smart_home(12)、custom_air_purifier(9)、custom_robot_vacuum(6)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：4 种说法
- 买家：长期使用的老用户
- pet_water_fountain: Home Assistant 用户（22 条）
- custom_smart_home: Home Assistant 用户，使用 pyvesync/VeSync 集成，具备抓包与调试能力（12 条）
- custom_air_purifier: 空气净化器用户（9 条）
- custom_robot_vacuum: iPhone Duo 用户（6 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1012014442, 1016299342, 1138066420, 1289575311, 1462875428, 1477030154
- 强度：0.64　L2+：34%　代价信号：2%　付费信号：0%

> It doesn’t even track in the middle of the night anymore

### 3. 订阅取消与退款不透明（93 分，231 条证据，跨 5 个域）

- 来源域：pet_water_fountain(98)、budgeting(91)、sleep_tech(30)、plant_care(8)、custom_smart_lock(4)
- 需求类型：订阅取消与退款不透明　变体：2 种说法
- 买家：付费订阅用户
- pet_water_fountain: 付费订阅用户（98 条）
- budgeting: 从 Mint 迁移、使用过 PocketGuard 的预算应用用户（91 条）
- sleep_tech: 使用该应用五六年的 Apple Watch 用户（30 条）
- plant_care: 植物养护应用用户（8 条）
- custom_smart_lock: 使用Tuya app多年的智能灯泡用户（4 条）
- 覆盖 App：1034649547, 1138066420, 1152066360, 1252497129, 1410126781, 1490078804
- 强度：0.78　L2+：33%　代价信号：13%　付费信号：5%

> after I woke up it wouldn’t let me view the recordings without paying for a ridiculous subscription

### 4. 关键提醒与警报不可靠（90 分，272 条证据，跨 5 个域）

- 来源域：sleep_tech(80)、pet_water_fountain(71)、plant_care(50)、custom_robot_vacuum(50)、custom_smart_home(21)
- 需求类型：关键提醒与警报不可靠　变体：8 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（80 条）
- pet_water_fountain: 养狗人士（71 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- custom_robot_vacuum: Roomba 400combo 系列用户（50 条）
- custom_smart_home: Home Assistant Container（Docker）用户（21 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1462875428, 1490078804, 1586120661
- 强度：0.68　L2+：41%　代价信号：2%　付费信号：4%

> Sounds stop after half hour.

### 5. 客服响应慢且售后推诿（88 分，211 条证据，跨 5 个域）

- 来源域：pet_water_fountain(114)、custom_robot_vacuum(70)、sleep_tech(22)、custom_smart_lock(3)、custom_smart_home(2)
- 需求类型：客服响应慢且售后推诿　变体：4 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: 养两只猫的宠物主人（114 条）
- custom_robot_vacuum: 首次购买扫地机器人的用户（70 条）
- sleep_tech: 付费订阅用户（22 条）
- custom_smart_lock: 智能门锁用户（3 条）
- custom_smart_home: 智能家居用户（2 条）
- 覆盖 App：1012014442, 1034649547, 1138066420, 1462875428, 1490078804, 1586120661
- 强度：0.71　L2+：24%　代价信号：5%　付费信号：3%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 6. 核心功能频繁崩溃闪退（68 分，92 条证据，跨 4 个域）

- 来源域：budgeting(42)、custom_smart_lock(24)、pet_water_fountain(22)、sleep_tech(4)
- 需求类型：核心功能频繁崩溃闪退　变体：4 种说法
- 买家：所有应用用户
- budgeting: 与伴侣合并财务、需要区分家庭与个人支出的用户（42 条）
- custom_smart_lock: iOS 用户（24 条）
- pet_water_fountain: 安卓掌机玩家（22 条）
- sleep_tech: 睡眠应用用户（4 条）
- 覆盖 App：1034649547, 1138066420, 1152066360, 1621020173, 936422955, 949414211
- 强度：0.67　L2+：16%　代价信号：2%　付费信号：2%

> the app closes out when you open it

### 7. 数据记录与统计不准确（59 分，41 条证据，跨 3 个域）

- 来源域：budgeting(19)、custom_air_purifier(13)、sleep_tech(9)
- 需求类型：数据记录与统计不准确　变体：4 种说法
- 买家：依赖数据做决策的用户
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（19 条）
- custom_air_purifier: Blueair app用户（13 条）
- sleep_tech: 把手机放在床头柜上使用睡眠追踪的用户（9 条）
- 覆盖 App：1016299342, 1138066420, 1477030154, 1490078804, 1621020173, 320606217
- 强度：0.69　L2+：29%　代价信号：2%　付费信号：2%

> It says I’m getting 1-2 hours of sleep a night when I’m getting 7-8.

### 8. 硬件设备耐用性差易故障（43 分，193 条证据，跨 2 个域）

- 来源域：pet_water_fountain(154)、custom_robot_vacuum(39)
- 需求类型：硬件设备耐用性差易故障　变体：7 种说法
- 买家：硬件产品购买者
- pet_water_fountain: 养猫用户（154 条）
- custom_robot_vacuum: i4 与 Roomba 用户（39 条）
- 覆盖 App：1012014442, 1586120661, 720151500, 921588809, 994053492, 999707163
- 强度：0.63　L2+：45%　代价信号：3%　付费信号：4%

> just sent my petlibro litterbox ($600) to the dump a couple weeks ago, had so many issues with the wastebin sensor. only had for maybe 1 year? every update was more AI centered, the box stopped working if the camera saw a cat or person near it. 

ironically each update mentioned updates about the wastebin full issue, but never managed to be fixed. got a cheaper automatic litter box for under $200

### 9. 外出时远程监控与喂食失效（39 分，14 条证据，跨 2 个域）

- 来源域：pet_water_fountain(8)、custom_smart_home(6)
- 需求类型：外出时远程监控与喂食失效　变体：3 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养猫的宠物主人（8 条）
- custom_smart_home: 关注本地控制和HomeKit/Home Assistant的智能家居用户（6 条）
- 覆盖 App：1586120661
- 强度：0.77　L2+：36%　代价信号：14%　付费信号：0%

> It works until you're out of town and it stopped working. What's the point of having batteries but not dispensing food??????

### 10. 识别与诊断准确性低（23 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died
