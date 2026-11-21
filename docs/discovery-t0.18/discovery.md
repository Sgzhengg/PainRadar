# 无品类需求发现

> 语料：var\gold.db, var\gold200.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅取消流程不透明 | 订阅付费 | 39 | 45 | 2 | 5 | plant_care、pet_water_fountain |
| 2 | 设备噪音大且已无法使用 | 产品设计 | 32 | 6 | 2 | 3 | sleep_tech、plant_care |
| 3 | 水位误报且无法目视确认 | 数据与准确性 | 25 | 6 | 1 | 1 | pet_water_fountain |
| 4 | 售后无响应且退换成本高 | 客服与售后 | 20 | 12 | 1 | 2 | pet_water_fountain |
| 5 | 银行同步失效需手动记账 | 数据与准确性 | 19 | 44 | 1 | 2 | budgeting |
| 6 | 付费后仍遇付费墙与丢数据 | 订阅付费 | 19 | 25 | 1 | 3 | budgeting |
| 7 | 浇水提醒任务堆积不同步 | 产品设计 | 19 | 32 | 1 | 3 | plant_care |
| 8 | 睡眠记录不准且夜间冻结 | 数据与准确性 | 19 | 27 | 1 | 3 | sleep_tech |
| 9 | 预算功能被订阅墙锁住 | 订阅付费 | 18 | 18 | 1 | 3 | budgeting |
| 10 | 退款申请无人回应 | 客服与售后 | 18 | 20 | 1 | 3 | sleep_tech |

## 逐个需求

### 1. 订阅取消流程不透明（39 分，45 条证据，跨 2 个域）

- 来源域：plant_care(24)、pet_water_fountain(21)
- 需求类型：订阅付费　变体：2 种说法
- 买家：宠物智能设备用户
- 买家（分域）：pet_water_fountain: 宠物智能设备用户；plant_care: 植物 App 试用用户
- 现有凑合：联系客服或放弃取消
- 观察到的代价：金钱损失，情绪愤怒
- 覆盖 App：1252497129, 1410126781, 1586120661, 1612792132, 994053492
- 强度：0.45　L2+：9%　代价信号：11%　付费信号：0%

> It’s easy to make you feel like you have made a mistake when your brand new machine requires hundreds of dollars worth of upgrades to work properly.

### 2. 设备噪音大且已无法使用（32 分，6 条证据，跨 2 个域）

- 来源域：sleep_tech(3)、plant_care(3)
- 需求类型：产品设计　变体：2 种说法
- 买家：睡眠科技产品用户
- 买家（分域）：sleep_tech: 睡眠科技产品用户；plant_care: 植物养护 App 用户
- 观察到的代价：设备报废无法使用
- 覆盖 App：1138066420, 1252497129, 320606217
- 强度：0.43　L2+：0%　代价信号：0%　付费信号：0%

> Was favorite, now useless.

### 3. 水位误报且无法目视确认（25 分，6 条证据，跨 1 个域）

- 来源域：pet_water_fountain(6)
- 需求类型：数据与准确性　变体：1 种说法
- 买家：养猫的宠物主
- 买家（分域）：pet_water_fountain: 养猫的宠物主
- 现有凑合：拆开设备查看水位、改用日历提醒
- 观察到的代价：反复拆装，高价设备体验差
- 覆盖 App：994053492
- 强度：0.70　L2+：83%　代价信号：0%　付费信号：0%

> I cannot even edit this reminder so I deleted it and will use a calendar reminder instead.

### 4. 售后无响应且退换成本高（20 分，12 条证据，跨 1 个域）

- 来源域：pet_water_fountain(12)
- 需求类型：客服与售后　变体：1 种说法
- 买家：宠物喂食器用户
- 买家（分域）：pet_water_fountain: 宠物喂食器用户
- 现有凑合：自行维修故障
- 观察到的代价：48小时等待与72美元退运费
- 覆盖 App：1586120661, 994053492
- 强度：0.45　L2+：33%　代价信号：17%　付费信号：0%

> When I call customer support, I'm told there are no agents available, that I need to leave a message and and I will hear back within 48 hours.

### 5. 银行同步失效需手动记账（19 分，44 条证据，跨 1 个域）

- 来源域：budgeting(44)
- 需求类型：数据与准确性　变体：1 种说法
- 买家：个人记账 App 用户
- 买家（分域）：budgeting: 个人记账 App 用户
- 现有凑合：每月手动重复录入交易
- 观察到的代价：订阅费白花，情绪挫败
- 覆盖 App：936422955, 949414211
- 强度：0.45　L2+：16%　代价信号：9%　付费信号：0%

> It works fine when I don’t try to repeat it, but now I’ll have to manually repeat it every month (annoying)!

### 6. 付费后仍遇付费墙与丢数据（19 分，25 条证据，跨 1 个域）

- 来源域：budgeting(25)
- 需求类型：订阅付费　变体：1 种说法
- 买家：记账 App 付费用户
- 买家（分域）：budgeting: 记账 App 付费用户
- 现有凑合：换用其他记账 App
- 观察到的代价：订阅费浪费，数据反复丢失
- 覆盖 App：1621020173, 936422955, 949414211
- 强度：0.46　L2+：12%　代价信号：12%　付费信号：0%

> it does help a lot with budgeting but $13 a month isn’t worth it let alone $75 for a whole year when the whole point is for me to save money.

### 7. 浇水提醒任务堆积不同步（19 分，32 条证据，跨 1 个域）

- 来源域：plant_care(32)
- 需求类型：产品设计　变体：1 种说法
- 买家：多植物养护用户
- 买家（分域）：plant_care: 多植物养护用户
- 现有凑合：手动忽略或自行记录
- 观察到的代价：每日任务列表冗长、养护焦虑
- 覆盖 App：1252497129, 1410126781, 1612792132
- 强度：0.46　L2+：6%　代价信号：6%　付费信号：3%

> if there was a cheaper option so i could just keep track of when to water my many plants but $40 a year for basic reminders is too steep.

### 8. 睡眠记录不准且夜间冻结（19 分，27 条证据，跨 1 个域）

- 来源域：sleep_tech(27)
- 需求类型：数据与准确性　变体：1 种说法
- 买家：睡眠监测 App 用户
- 买家（分域）：sleep_tech: 睡眠监测 App 用户
- 现有凑合：手动调整睡眠时间
- 观察到的代价：整夜数据作废，情绪挫败
- 覆盖 App：1138066420, 1490078804, 320606217
- 强度：0.49　L2+：7%　代价信号：7%　付费信号：0%

> The sleep app that comes on the watch always had me asleep when I was laying wide awake staring at my ceiling.

### 9. 预算功能被订阅墙锁住（18 分，18 条证据，跨 1 个域）

- 来源域：budgeting(18)
- 需求类型：订阅付费　变体：1 种说法
- 买家：预算管理 App 用户
- 买家（分域）：budgeting: 预算管理 App 用户
- 现有凑合：只用最基础功能凑合
- 观察到的代价：无法建预算，数据丢失
- 覆盖 App：1621020173, 936422955, 949414211
- 强度：0.42　L2+：6%　代价信号：17%　付费信号：0%

> I deleted the app within 10 minutes when I realized I couldn’t even add my expenses / savings and create a budget without subscribing for $25.

### 10. 退款申请无人回应（18 分，20 条证据，跨 1 个域）

- 来源域：sleep_tech(20)
- 需求类型：客服与售后　变体：1 种说法
- 买家：睡眠 App 付费用户
- 买家（分域）：sleep_tech: 睡眠 App 付费用户
- 现有凑合：反复发邮件催问
- 观察到的代价：被扣 69 美元且无回复
- 覆盖 App：1138066420, 1490078804, 320606217
- 强度：0.42　L2+：15%　代价信号：5%　付费信号：0%

> I used to love it. Has deteriorated over time. Doesn’t record sometimes. Tried getting support, sent data, asked to resend data, slow response. Today it will not refresh only crash.
