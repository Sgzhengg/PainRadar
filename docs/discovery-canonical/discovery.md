# 无品类需求发现

> 语料：var\gold.db, var\gold200.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 数据同步与准确性差 | 数据同步与准确性差 | 64 | 105 | 3 | 6 | budgeting、sleep_tech、plant_care |
| 2 | 设备/App频繁故障或崩溃 | 设备/App频繁故障或崩溃 | 52 | 16 | 3 | 5 | pet_water_fountain、sleep_tech、plant_care |
| 3 | 提醒机制不灵活或缺失 | 提醒机制不灵活或缺失 | 41 | 58 | 2 | 5 | plant_care、pet_water_fountain |
| 4 | 关键功能需额外付费 | 关键功能需额外付费 | 40 | 46 | 2 | 5 | budgeting、pet_water_fountain |
| 5 | 订阅自动续费不透明 | 订阅自动续费不透明 | 38 | 39 | 2 | 4 | plant_care、sleep_tech |
| 6 | 界面复杂难用 | 界面复杂难用 | 37 | 29 | 2 | 5 | budgeting、pet_water_fountain |
| 7 | 客服响应慢且不解决问题 | 客服响应慢且不解决问题 | 37 | 15 | 2 | 3 | pet_water_fountain、sleep_tech |
| 8 | 广告过多干扰使用 | 广告过多干扰使用 | 35 | 12 | 2 | 4 | custom_coffee_maker、sleep_tech |
| 9 | 外出时远程监控不可靠 | 外出时远程监控不可靠 | 23 | 5 | 1 | 2 | pet_water_fountain |
| 10 | 退款流程困难 | 退款流程困难 | 18 | 20 | 1 | 3 | sleep_tech |
| 11 | 硬件设计缺陷影响使用 | 硬件设计缺陷影响使用 | 17 | 17 | 1 | 2 | pet_water_fountain |

## 逐个需求

### 1. 数据同步与准确性差（64 分，105 条证据，跨 3 个域）

- 来源域：budgeting(44)、sleep_tech(37)、plant_care(24)
- 需求类型：数据同步与准确性差　变体：5 种说法
- 买家：依赖数据记录的用户
- budgeting: 记账理财应用用户（44 条）
- sleep_tech: 长期用户（37 条）
- plant_care: 植物养护应用用户（24 条）
- 覆盖 App：1138066420, 1252497129, 1410126781, 1490078804, 1612792132, 320606217
- 强度：0.47　L2+：11%　代价信号：7%　付费信号：0%

> The sleep app that comes on the watch always had me asleep when I was laying wide awake staring at my ceiling.

### 2. 设备/App频繁故障或崩溃（52 分，16 条证据，跨 3 个域）

- 来源域：pet_water_fountain(7)、sleep_tech(6)、plant_care(3)
- 需求类型：设备/App频繁故障或崩溃　变体：4 种说法
- 买家：智能设备/App用户
- pet_water_fountain: 上班族（7 条）
- sleep_tech: 长期用户（6 条）
- plant_care: 植物养护应用用户（3 条）
- 覆盖 App：1138066420, 1252497129, 1586120661, 320606217, 994053492
- 强度：0.42　L2+：6%　代价信号：0%　付费信号：0%

> It’s definitely a cool design but the sensor only worked 1 time for my cat going to the bathroom and now I have to manually get it to scoop which is still easy just not what they say with the automatic scooping. Also to get kitty litter into it is almost impossible without making a mess.

### 3. 提醒机制不灵活或缺失（41 分，58 条证据，跨 2 个域）

- 来源域：plant_care(32)、pet_water_fountain(26)
- 需求类型：提醒机制不灵活或缺失　变体：3 种说法
- 买家：需要提醒管理的用户
- plant_care: 植物养护应用用户（32 条）
- pet_water_fountain: 上班族（26 条）
- 覆盖 App：1252497129, 1410126781, 1586120661, 1612792132, 994053492
- 强度：0.49　L2+：19%　代价信号：3%　付费信号：2%

> the one feature the app needs is a push notification when the water gets low

### 4. 关键功能需额外付费（40 分，46 条证据，跨 2 个域）

- 来源域：budgeting(25)、pet_water_fountain(21)
- 需求类型：关键功能需额外付费　变体：1 种说法
- 买家：已购买产品的用户
- budgeting: 记账理财应用用户（25 条）
- pet_water_fountain: 上班族（21 条）
- 覆盖 App：1586120661, 1621020173, 936422955, 949414211, 994053492
- 强度：0.46　L2+：11%　代价信号：11%　付费信号：0%

> It’s easy to make you feel like you have made a mistake when your brand new machine requires hundreds of dollars worth of upgrades to work properly.

### 5. 订阅自动续费不透明（38 分，39 条证据，跨 2 个域）

- 来源域：plant_care(36)、sleep_tech(3)
- 需求类型：订阅自动续费不透明　变体：2 种说法
- 买家：订阅制App用户
- plant_care: 新手（36 条）
- sleep_tech: 睡眠应用用户（3 条）
- 覆盖 App：1252497129, 1410126781, 1490078804, 1612792132
- 强度：0.44　L2+：5%　代价信号：18%　付费信号：0%

> 99 for a year that you think you are signing up for but you get seven day free trial when you click it they charge you the $59.

### 6. 界面复杂难用（37 分，29 条证据，跨 2 个域）

- 来源域：budgeting(26)、pet_water_fountain(3)
- 需求类型：界面复杂难用　变体：3 种说法
- 买家：所有用户
- budgeting: 记账理财应用用户（26 条）
- pet_water_fountain: 宠物智能设备用户（3 条）
- 覆盖 App：1586120661, 1621020173, 936422955, 949414211, 994053492
- 强度：0.43　L2+：3%　代价信号：10%　付费信号：0%

> I deleted the app within 10 minutes when I realized I couldn’t even add my expenses / savings and create a budget without subscribing for $25.

### 7. 客服响应慢且不解决问题（37 分，15 条证据，跨 2 个域）

- 来源域：pet_water_fountain(12)、sleep_tech(3)
- 需求类型：客服响应慢且不解决问题　变体：2 种说法
- 买家：需要售后支持的用户
- pet_water_fountain: 上班族（12 条）
- sleep_tech: 长期用户（3 条）
- 覆盖 App：1138066420, 1586120661, 994053492
- 强度：0.44　L2+：27%　代价信号：13%　付费信号：0%

> When I call customer support, I'm told there are no agents available, that I need to leave a message and and I will hear back within 48 hours.

### 8. 广告过多干扰使用（35 分，12 条证据，跨 2 个域）

- 来源域：custom_coffee_maker(8)、sleep_tech(4)
- 需求类型：广告过多干扰使用　变体：3 种说法
- 买家：免费版用户
- custom_coffee_maker: 咖啡机用户（8 条）
- sleep_tech: 长期用户（4 条）
- 覆盖 App：1591921962, 1603584945, 1610991235, 320606217
- 强度：0.50　L2+：0%　代价信号：0%　付费信号：0%

> I’ve used the app for years and have always liked it.

### 9. 外出时远程监控不可靠（23 分，5 条证据，跨 1 个域）

- 来源域：pet_water_fountain(5)
- 需求类型：外出时远程监控不可靠　变体：1 种说法
- 买家：经常外出的宠物主人
- pet_water_fountain: 经常出差旅行的养宠人（5 条）
- 覆盖 App：1586120661, 994053492
- 强度：0.64　L2+：20%　代价信号：20%　付费信号：20%

> I have had to make them go and buy an old litter box at Walmart in place of the $600 litter box.

### 10. 退款流程困难（18 分，20 条证据，跨 1 个域）

- 来源域：sleep_tech(20)
- 需求类型：退款流程困难　变体：1 种说法
- 买家：申请退款的用户
- sleep_tech: 长期用户（20 条）
- 覆盖 App：1138066420, 1490078804, 320606217
- 强度：0.42　L2+：15%　代价信号：5%　付费信号：0%

> I used to love it. Has deteriorated over time. Doesn’t record sometimes. Tried getting support, sent data, asked to resend data, slow response. Today it will not refresh only crash.

### 11. 硬件设计缺陷影响使用（17 分，17 条证据，跨 1 个域）

- 来源域：pet_water_fountain(17)
- 需求类型：硬件设计缺陷影响使用　变体：1 种说法
- 买家：硬件产品用户
- pet_water_fountain: 上班族（17 条）
- 覆盖 App：1586120661, 994053492
- 强度：0.43　L2+：24%　代价信号：0%　付费信号：0%

> Petkit’s opening is smaller than my past and the cats did not like the tofu litter. I do have multiple cats and each one has their own issues. In order to make it work I had to go back to the clay type litter they were use too.
