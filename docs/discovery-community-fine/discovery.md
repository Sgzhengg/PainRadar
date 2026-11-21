# 无品类需求发现

> 语料：var\llm_full.db, var\community.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 87 | 215 | 4 | 6 | budgeting、pet_water_fountain、sleep_tech |
| 2 | 关键提醒与警报不可靠 | 关键提醒与警报不可靠 | 83 | 218 | 4 | 6 | sleep_tech、pet_water_fountain、plant_care |
| 3 | 设备连接与同步不稳定 | 设备连接与同步不稳定 | 77 | 177 | 4 | 5 | budgeting、pet_water_fountain、custom_smart_home |
| 4 | 更新后功能异常或数据丢失 | 更新后功能异常或数据丢失 | 75 | 87 | 4 | 6 | pet_water_fountain、custom_smart_home、sleep_tech |
| 5 | 核心功能频繁崩溃闪退 | 核心功能频繁崩溃闪退 | 69 | 70 | 4 | 4 | budgeting、pet_water_fountain、sleep_tech |
| 6 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 65 | 72 | 3 | 6 | pet_water_fountain、sleep_tech、custom_smart_home |
| 7 | 数据记录与统计不准确 | 数据记录与统计不准确 | 59 | 37 | 3 | 6 | budgeting、sleep_tech、custom_smart_home |
| 8 | 硬件设备耐用性差易故障 | 硬件设备耐用性差易故障 | 44 | 58 | 2 | 4 | pet_water_fountain、custom_smart_home |
| 9 | 外出时远程监控与喂食失效 | 外出时远程监控与喂食失效 | 42 | 37 | 2 | 4 | pet_water_fountain、custom_smart_home |
| 10 | 数据导出与迁移困难 | 数据导出与迁移困难 | 40 | 19 | 2 | 2 | budgeting、custom_smart_home |
| 11 | 识别与诊断准确性低 | 识别与诊断准确性低 | 24 | 79 | 1 | 3 | plant_care |

## 逐个需求

### 1. 订阅取消与退款不透明（87 分，215 条证据，跨 4 个域）

- 来源域：budgeting(91)、pet_water_fountain(86)、sleep_tech(30)、plant_care(8)
- 需求类型：订阅取消与退款不透明　变体：1 种说法
- 买家：付费订阅用户
- budgeting: 从 Mint 迁移、使用过 PocketGuard 的预算应用用户（91 条）
- pet_water_fountain: 付费订阅用户（86 条）
- sleep_tech: 使用该应用五六年的 Apple Watch 用户（30 条）
- plant_care: 植物养护应用用户（8 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1621020173
- 强度：0.79　L2+：32%　代价信号：13%　付费信号：5%

> after I woke up it wouldn’t let me view the recordings without paying for a ridiculous subscription

### 2. 关键提醒与警报不可靠（83 分，218 条证据，跨 4 个域）

- 来源域：sleep_tech(80)、pet_water_fountain(71)、plant_care(50)、custom_smart_home(17)
- 需求类型：关键提醒与警报不可靠　变体：7 种说法
- 买家：依赖提醒功能的用户
- sleep_tech: 多年使用该应用的老用户（80 条）
- pet_water_fountain: 养狗人士（71 条）
- plant_care: 10岁女孩，第一次使用该应用（50 条）
- custom_smart_home: Home Assistant 与 HomeKit Bridge 用户，Blueair Blue Pure 211i Max 用户（17 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1586120661, 1612792132
- 强度：0.69　L2+：38%　代价信号：2%　付费信号：5%

> Sounds stop after half hour.

### 3. 设备连接与同步不稳定（77 分，177 条证据，跨 4 个域）

- 来源域：budgeting(78)、pet_water_fountain(52)、custom_smart_home(43)、sleep_tech(4)
- 需求类型：设备连接与同步不稳定　变体：7 种说法
- 买家：依赖硬件或外部数据的用户
- budgeting: 付费订阅用户（78 条）
- pet_water_fountain: Home Assistant 用户（52 条）
- custom_smart_home: Home Assistant Container（Docker）用户（43 条）
- sleep_tech: iPhone 17 Pro Max 与 Apple Watch Ultra 3 用户（4 条）
- 覆盖 App：1138066420, 1621020173, 320606217, 936422955, 949414211
- 强度：0.67　L2+：56%　代价信号：3%　付费信号：5%

> it decided I wasn’t wearing my Apple Watch

### 4. 更新后功能异常或数据丢失（75 分，87 条证据，跨 4 个域）

- 来源域：pet_water_fountain(69)、custom_smart_home(12)、sleep_tech(3)、budgeting(3)
- 需求类型：更新后功能异常或数据丢失　变体：3 种说法
- 买家：长期使用的老用户
- pet_water_fountain: Home Assistant 用户（69 条）
- custom_smart_home: Home Assistant 用户，使用 pyvesync/VeSync 集成，具备抓包与调试能力（12 条）
- sleep_tech: 长期使用该应用的老用户（3 条）
- budgeting: iPhone 用户（3 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 720151500, 921588809, 936422955
- 强度：0.70　L2+：31%　代价信号：1%　付费信号：0%

> It doesn’t even track in the middle of the night anymore

### 5. 核心功能频繁崩溃闪退（69 分，70 条证据，跨 4 个域）

- 来源域：budgeting(42)、pet_water_fountain(22)、sleep_tech(4)、custom_smart_home(2)
- 需求类型：核心功能频繁崩溃闪退　变体：4 种说法
- 买家：所有应用用户
- budgeting: 与伴侣合并财务、需要区分家庭与个人支出的用户（42 条）
- pet_water_fountain: 安卓掌机玩家（22 条）
- sleep_tech: 睡眠应用用户（4 条）
- custom_smart_home: Android 应用开发者/崩溃排查人员（2 条）
- 覆盖 App：1138066420, 1621020173, 936422955, 949414211
- 强度：0.65　L2+：21%　代价信号：1%　付费信号：3%

> the app closes out when you open it

### 6. 客服响应慢且售后推诿（65 分，72 条证据，跨 3 个域）

- 来源域：pet_water_fountain(48)、sleep_tech(22)、custom_smart_home(2)
- 需求类型：客服响应慢且售后推诿　变体：3 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: AI CLI 工具社区开发者（48 条）
- sleep_tech: 付费订阅用户（22 条）
- custom_smart_home: 智能家居用户（2 条）
- 覆盖 App：1138066420, 1490078804, 1586120661, 320606217, 720151500, 921588809
- 强度：0.82　L2+：25%　代价信号：7%　付费信号：3%

> No chance of a refund and I can’t get ahold of a live person to save my life.

### 7. 数据记录与统计不准确（59 分，37 条证据，跨 3 个域）

- 来源域：budgeting(19)、sleep_tech(9)、custom_smart_home(9)
- 需求类型：数据记录与统计不准确　变体：3 种说法
- 买家：依赖数据做决策的用户
- budgeting: 不再是独自生活的学生、当前人生阶段的成年人（19 条）
- sleep_tech: 把手机放在床头柜上使用睡眠追踪的用户（9 条）
- custom_smart_home: 体育博彩/赔率模型开发者（9 条）
- 覆盖 App：1138066420, 1490078804, 1621020173, 320606217, 936422955, 949414211
- 强度：0.65　L2+：22%　代价信号：3%　付费信号：3%

> It says I’m getting 1-2 hours of sleep a night when I’m getting 7-8.

### 8. 硬件设备耐用性差易故障（44 分，58 条证据，跨 2 个域）

- 来源域：pet_water_fountain(43)、custom_smart_home(15)
- 需求类型：硬件设备耐用性差易故障　变体：6 种说法
- 买家：硬件产品购买者
- pet_water_fountain: 养猫用户（43 条）
- custom_smart_home: DIY 迷你主机装机用户（15 条）
- 覆盖 App：1586120661, 921588809, 994053492, 999707163
- 强度：0.64　L2+：59%　代价信号：2%　付费信号：7%

> There is no way to gauge water level without removing top to look, and to fill.

### 9. 外出时远程监控与喂食失效（42 分，37 条证据，跨 2 个域）

- 来源域：pet_water_fountain(31)、custom_smart_home(6)
- 需求类型：外出时远程监控与喂食失效　变体：3 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 养狗人士，使用 iPhone 17（31 条）
- custom_smart_home: 动手能力强的智能家居用户（6 条）
- 覆盖 App：1586120661, 720151500, 994053492, 999707163
- 强度：0.69　L2+：27%　代价信号：8%　付费信号：5%

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

### 11. 识别与诊断准确性低（24 分，79 条证据，跨 1 个域）

- 来源域：plant_care(79)
- 需求类型：识别与诊断准确性低　变体：2 种说法
- 买家：依赖识别功能的用户
- plant_care: 新用户（79 条）
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.72　L2+：32%　代价信号：0%　付费信号：5%

> Followed the advice for helping rid of plant pest. Within a week, the plant rotted and died
