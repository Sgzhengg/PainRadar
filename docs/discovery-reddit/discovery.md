# 无品类需求发现

> 语料：var\llm_full.db, var\community.db, var\hardware.db, var\reddit.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 119 | 331 | 7 | 6 | pet_water_fountain、budgeting、custom_smart_home |
| 2 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 104 | 246 | 6 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 3 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 100 | 129 | 6 | 6 | pet_water_fountain、custom_smart_home、custom_air_purifier |
| 4 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 94 | 231 | 5 | 6 | pet_water_fountain、budgeting、sleep_tech |
| 5 | 核心功能频繁崩溃闪退 | 核心功能频繁崩溃闪退 | 93 | 96 | 6 | 6 | budgeting、custom_smart_lock、pet_water_fountain |
| 6 | 数据记录与统计不准确 | 数据记录与统计不准确 | 85 | 72 | 5 | 6 | custom_robot_vacuum、budgeting、custom_air_purifier |
| 7 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 78 | 256 | 4 | 6 | pet_water_fountain、custom_air_purifier、custom_smart_home |
| 8 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 73 | 148 | 4 | 6 | pet_water_fountain、sleep_tech、custom_smart_lock |
| 9 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 40 | 20 | 2 | 1 | pet_water_fountain、custom_smart_home |
| 10 | 数据导出与迁移困难 | 数据导出与迁移困难 | 40 | 19 | 2 | 2 | budgeting、custom_smart_home |
| 11 | 识别与诊断准确性低 | 识别与诊断准确性低 | 23 | 79 | 1 | 3 | plant_care |

## 逐个需求

### 1. 设备连接与同步不稳定（119 分，331 条证据，跨 7 个域）

- 来源域：pet_water_fountain(132)、budgeting(78)、custom_smart_home(46)、custom_air_purifier(36)、custom_smart_lock(23)、custom_robot_vacuum(12)
- 需求类型：设备连接与同步不稳定　变体：11 种说法
- 买家：依赖硬件或外部数据的用户
- pet_water_fountain: Home Assistant 用户（132 条）
- budgeting: 付费订阅用户（78 条）
- custom_smart_home: Home Assistant Container（Docker）用户（46 条）
- custom_air_purifier: Everest 空气净化器用户（36 条）
- custom_smart_lock: Microsoft Exchange 邮箱用户（23 条）
- custom_robot_vacuum: 15年内购买至少五台Roomba的老用户（12 条）
- 覆盖 App：1012014442, 1016299342, 1034649547, 1138066420, 1152066360, 1289575311
- 强度：0.66　L2+：46%　代价信号：2%　付费信号：3%

> it decided I wasn’t wearing my Apple Watch

### 2. 关键提醒与警报不可靠（104 分，246 条证据，跨 6 个域）

- 来源域：sleep_tech(80)、pet_water_fountain(71)、plant_care(50)、custom_smart_home(17)、custom_robot_vacuum(15)、custom_air_purifier(13)
- 需求类型：关键提醒与警报不可靠　变体：9 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（80 条）
- pet_water_fountain: 养狗人士（71 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- custom_smart_home: Home Assistant 与 HomeKit Bridge 用户，Blueair Blue Pure 211i Max 用户（17 条）
- custom_robot_vacuum: Roomba 用户，使用 iPhone 操作（15 条）
- custom_air_purifier: Blueair空气净化器用户（13 条）
- 覆盖 App：1016299342, 1138066420, 1252497129, 1410126781, 1462875428, 1477030154
- 强度：0.70　L2+：39%　代价信号：2%　付费信号：4%

> Sounds stop after half hour.

### 3. 更新后功能异常或数据丢失（100 分，129 条证据，跨 6 个域）

- 来源域：pet_water_fountain(96)、custom_smart_home(12)、custom_air_purifier(9)、custom_robot_vacuum(6)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：4 种说法
- 买家：长期使用的老用户
- pet_water_fountain: Home Assistant 用户（96 条）
- custom_smart_home: Home Assistant 用户，使用 pyvesync/VeSync 集成，具备抓包与调试能力（12 条）
- custom_air_purifier: 空气净化器用户（9 条）
- custom_robot_vacuum: iPhone Duo 用户（6 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1012014442, 1016299342, 1138066420, 1289575311, 1462875428, 1477030154
- 强度：0.68　L2+：31%　代价信号：3%　付费信号：1%

> just sent my petlibro litterbox ($600) to the dump a couple weeks ago, had so many issues with the wastebin sensor. only had for maybe 1 year? every update was more AI centered, the box stopped working if the camera saw a cat or person near it. 

ironically each update mentioned updates about the wastebin full issue, but never managed to be fixed. got a cheaper automatic litter box for under $200

### 4. 订阅取消与退款不透明（94 分，231 条证据，跨 5 个域）

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

### 5. 核心功能频繁崩溃闪退（93 分，96 条证据，跨 6 个域）

- 来源域：budgeting(42)、custom_smart_lock(24)、pet_water_fountain(22)、sleep_tech(4)、custom_smart_home(2)、custom_air_purifier(2)
- 需求类型：核心功能频繁崩溃闪退　变体：6 种说法
- 买家：所有应用用户
- budgeting: 与伴侣合并财务、需要区分家庭与个人支出的用户（42 条）
- custom_smart_lock: iOS 用户（24 条）
- pet_water_fountain: 安卓掌机玩家（22 条）
- sleep_tech: 睡眠应用用户（4 条）
- custom_smart_home: Android 应用开发者/崩溃排查人员（2 条）
- custom_air_purifier: 拥有较完整智能家居系统的用户（2 条）
- 覆盖 App：1034649547, 1138066420, 1152066360, 1477030154, 1621020173, 936422955
- 强度：0.67　L2+：17%　代价信号：2%　付费信号：2%

> the app closes out when you open it

### 6. 数据记录与统计不准确（85 分，72 条证据，跨 5 个域）

- 来源域：custom_robot_vacuum(23)、budgeting(19)、custom_air_purifier(12)、sleep_tech(9)、custom_smart_home(9)
- 需求类型：数据记录与统计不准确　变体：7 种说法
- 买家：依赖数据做决策的用户
- custom_robot_vacuum: iRobot 产品用户（23 条）
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（19 条）
- custom_air_purifier: Blueair app用户（12 条）
- sleep_tech: 把手机放在床头柜上使用睡眠追踪的用户（9 条）
- custom_smart_home: 体育博彩/赔率模型开发者（9 条）
- 覆盖 App：1012014442, 1016299342, 1138066420, 1462875428, 1477030154, 1490078804
- 强度：0.69　L2+：28%　代价信号：1%　付费信号：1%

> It says I’m getting 1-2 hours of sleep a night when I’m getting 7-8.

### 7. 硬件设备耐用性差易故障（78 分，256 条证据，跨 4 个域）

- 来源域：pet_water_fountain(157)、custom_air_purifier(71)、custom_smart_home(15)、custom_robot_vacuum(13)
- 需求类型：硬件设备耐用性差易故障　变体：16 种说法
- 买家：硬件产品购买者
- pet_water_fountain: 养猫用户（157 条）
- custom_air_purifier: 关注空气净化器性能与性价比的用户（71 条）
- custom_smart_home: DIY 迷你主机装机用户（15 条）
- custom_robot_vacuum: Roomba 400combo 系列用户（13 条）
- 覆盖 App：1012014442, 1016299342, 1462875428, 1477030154, 1586120661, 6504274697
- 强度：0.60　L2+：62%　代价信号：4%　付费信号：10%

> There is no way to gauge water level without removing top to look, and to fill.

### 8. 客服响应慢且售后推诿（73 分，148 条证据，跨 4 个域）

- 来源域：pet_water_fountain(121)、sleep_tech(22)、custom_smart_lock(3)、custom_smart_home(2)
- 需求类型：客服响应慢且售后推诿　变体：3 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: 养两只猫的宠物主人（121 条）
- sleep_tech: 付费订阅用户（22 条）
- custom_smart_lock: 智能门锁用户（3 条）
- custom_smart_home: 智能家居用户（2 条）
- 覆盖 App：1034649547, 1138066420, 1490078804, 1586120661, 320606217, 720151500
- 强度：0.71　L2+：18%　代价信号：6%　付费信号：3%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 9. 外出时远程监控与喂食失效（40 分，20 条证据，跨 2 个域）

- 来源域：pet_water_fountain(11)、custom_smart_home(9)
- 需求类型：外出时远程监控与喂食失效　变体：3 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养猫的人，伴侣在中国生活过两年（11 条）
- custom_smart_home: 动手能力强的智能家居用户（9 条）
- 覆盖 App：1586120661
- 强度：0.71　L2+：45%　代价信号：15%　付费信号：5%

> It works until you're out of town and it stopped working. What's the point of having batteries but not dispensing food??????

### 10. 数据导出与迁移困难（40 分，19 条证据，跨 2 个域）

- 来源域：budgeting(17)、custom_smart_home(2)
- 需求类型：数据导出与迁移困难　变体：3 种说法
- 买家：需要备份或换应用的用户
- budgeting: 使用该应用2年的老用户（17 条）
- custom_smart_home: 安全审查者/开发者（2 条）
- 覆盖 App：936422955, 949414211
- 强度：0.70　L2+：47%　代价信号：0%　付费信号：5%

> would be nice to be able to make the categories a different color can’t stand that everything is one color on the graph.

### 11. 识别与诊断准确性低（23 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died
