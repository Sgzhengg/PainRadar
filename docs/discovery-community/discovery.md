# 无品类需求发现

> 语料：var\llm_full.db, var\community.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 98 | 221 | 5 | 6 | budgeting、pet_water_fountain、sleep_tech |
| 2 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 78 | 214 | 4 | 6 | custom_smart_home、pet_water_fountain、sleep_tech |
| 3 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 76 | 171 | 4 | 5 | budgeting、pet_water_fountain、custom_smart_home |
| 4 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 70 | 201 | 3 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 5 | 核心功能频繁崩溃闪退 | 核心功能频繁崩溃闪退 | 57 | 68 | 3 | 4 | budgeting、pet_water_fountain、sleep_tech |
| 6 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 48 | 70 | 2 | 6 | pet_water_fountain、sleep_tech |
| 7 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 44 | 46 | 2 | 4 | pet_water_fountain、custom_smart_home |
| 8 | 数据记录与统计不准确 | 数据记录与统计不准确 | 44 | 39 | 2 | 6 | budgeting、sleep_tech |
| 9 | 识别与诊断准确性低 | 识别与诊断准确性低 | 24 | 79 | 1 | 3 | plant_care |
| 10 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 24 | 31 | 1 | 4 | pet_water_fountain |

## 逐个需求

### 1. 订阅取消与退款不透明（98 分，221 条证据，跨 5 个域）

- 来源域：budgeting(91)、pet_water_fountain(86)、sleep_tech(30)、plant_care(8)、custom_smart_home(6)
- 需求类型：订阅取消与退款不透明　变体：2 种说法
- 买家：付费订阅用户
- budgeting: 从 Mint 迁移、使用过 PocketGuard 的预算应用用户（91 条）
- pet_water_fountain: 付费订阅用户（86 条）
- sleep_tech: 使用该应用五六年的 Apple Watch 用户（30 条）
- plant_care: 植物养护应用用户（8 条）
- custom_smart_home: 全屋智能家居用户（6 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1621020173
- 强度：0.78　L2+：32%　代价信号：14%　付费信号：5%

> after I woke up it wouldn’t let me view the recordings without paying for a ridiculous subscription

### 2. 更新后功能异常或数据丢失（78 分，214 条证据，跨 4 个域）

- 来源域：custom_smart_home(139)、pet_water_fountain(69)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：4 种说法
- 买家：长期使用的老用户
- custom_smart_home: 开发者（139 条）
- pet_water_fountain: Home Assistant 用户（69 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 720151500, 921588809, 936422955
- 强度：0.62　L2+：44%　代价信号：1%　付费信号：1%

> It doesn’t even track in the middle of the night anymore

### 3. 设备连接与同步不稳定（76 分，171 条证据，跨 4 个域）

- 来源域：budgeting(78)、pet_water_fountain(52)、custom_smart_home(37)、sleep_tech(4)
- 需求类型：设备连接与同步不稳定　变体：4 种说法
- 买家：依赖硬件或外部数据的用户
- budgeting: 付费订阅用户（78 条）
- pet_water_fountain: Home Assistant 用户（52 条）
- custom_smart_home: Home Assistant 用户（37 条）
- sleep_tech: iPhone 17 Pro Max 与 Apple Watch Ultra 3 用户（4 条）
- 覆盖 App：1138066420, 1621020173, 320606217, 936422955, 949414211
- 强度：0.67　L2+：56%　代价信号：4%　付费信号：5%

> it decided I wasn’t wearing my Apple Watch

### 4. 关键提醒与警报不可靠（70 分，201 条证据，跨 3 个域）

- 来源域：sleep_tech(80)、pet_water_fountain(71)、plant_care(50)
- 需求类型：关键提醒与警报不可靠　变体：5 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（80 条）
- pet_water_fountain: 养狗人士（71 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1612792132
- 强度：0.71　L2+：36%　代价信号：2%　付费信号：5%

> Sounds stop after half hour.

### 5. 核心功能频繁崩溃闪退（57 分，68 条证据，跨 3 个域）

- 来源域：budgeting(42)、pet_water_fountain(22)、sleep_tech(4)
- 需求类型：核心功能频繁崩溃闪退　变体：3 种说法
- 买家：所有应用用户
- budgeting: 与伴侣合并财务、需要区分家庭与个人支出的用户（42 条）
- pet_water_fountain: 安卓掌机玩家（22 条）
- sleep_tech: 睡眠应用用户（4 条）
- 覆盖 App：1138066420, 1621020173, 936422955, 949414211
- 强度：0.65　L2+：21%　代价信号：2%　付费信号：3%

> the app closes out when you open it

### 6. 客服响应慢且售后推诿（48 分，70 条证据，跨 2 个域）

- 来源域：pet_water_fountain(48)、sleep_tech(22)
- 需求类型：客服响应慢且售后推诿　变体：2 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: AI CLI 工具社区开发者（48 条）
- sleep_tech: 付费订阅用户（22 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 320606217, 720151500, 921588809
- 强度：0.83　L2+：26%　代价信号：7%　付费信号：3%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 7. 硬件设备耐用性差易故障（44 分，46 条证据，跨 2 个域）

- 来源域：pet_water_fountain(43)、custom_smart_home(3)
- 需求类型：硬件设备耐用性差易故障　变体：5 种说法
- 买家：硬件产品购买者
- pet_water_fountain: 养猫用户（43 条）
- custom_smart_home: 六口之家（四个孩子）的家长（3 条）
- 覆盖 App：1586120661, 921588809, 994053492, 999707163
- 强度：0.66　L2+：59%　代价信号：2%　付费信号：9%

> There is no way to gauge water level without removing top to look, and to fill.

### 8. 数据记录与统计不准确（44 分，39 条证据，跨 2 个域）

- 来源域：budgeting(30)、sleep_tech(9)
- 需求类型：数据记录与统计不准确　变体：3 种说法
- 买家：依赖数据做决策的用户
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（30 条）
- sleep_tech: 把手机放在床头柜上使用睡眠追踪的用户（9 条）
- 覆盖 App：1138066420, 1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.70　L2+：33%　代价信号：3%　付费信号：3%

> It says I’m getting 1-2 hours of sleep a night when I’m getting 7-8.

### 9. 识别与诊断准确性低（24 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died

### 10. 外出时远程监控与喂食失效（24 分，31 条证据，跨 1 个域）

- 来源域：pet_water_fountain(31)
- 需求类型：外出时远程监控与喂食失效　变体：2 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养狗人士，使用 iPhone 17（31 条）
- 覆盖 App：1586120661, 720151500, 994053492, 999707163
- 强度：0.71　L2+：19%　代价信号：10%　付费信号：6%

> It works until you're out of town and it stopped working. What's the point of having batteries but not dispensing food??????
