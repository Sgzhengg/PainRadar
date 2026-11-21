# 无品类需求发现

> 语料：var\smb.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 客服响应慢且售后推诿 | 客服响应慢且售后推诿 | 48 | 177 | 1 | 6 | custom_small_business_operation |
| 2 | 订阅取消与退款不透明 | 订阅取消与退款不透明 | 42 | 54 | 1 | 6 | custom_small_business_operation |
| 3 | 数据记录与统计不准确 | 数据记录与统计不准确 | 35 | 32 | 1 | 5 | custom_small_business_operation |

## 逐个需求

### 1. 客服响应慢且售后推诿（48 分，177 条证据，跨 1 个域）

- 来源域：custom_small_business_operation(177)
- 需求类型：客服响应慢且售后推诿　变体：5 种说法
- 买家：需要售后支持的用户
- custom_small_business_operation: 小企业主（177 条）
- 覆盖 App：1014146758, 1052884030, 335393788, 371294472, 584606479, 881629660
- 强度：0.76　L2+：45%　代价信号：10%　付费信号：4%

> Square permanently closed my account without providing a specific explanation and is withholding $1,600 of my hard-earned money until December 9, possibly longer.

### 2. 订阅取消与退款不透明（42 分，54 条证据，跨 1 个域）

- 来源域：custom_small_business_operation(54)
- 需求类型：订阅取消与退款不透明　变体：1 种说法
- 买家：付费订阅用户
- custom_small_business_operation: 小企业主（54 条）
- 覆盖 App：1014146758, 1052884030, 335393788, 371294472, 584606479, 881629660
- 强度：0.77　L2+：39%　代价信号：20%　付费信号：7%

> Shopify keeps hitting my accounts for 40 dollars I had to cancel all of my accounts to stop the charges

### 3. 数据记录与统计不准确（35 分，32 条证据，跨 1 个域）

- 来源域：custom_small_business_operation(32)
- 需求类型：数据记录与统计不准确　变体：2 种说法
- 买家：依赖数据做决策的用户
- custom_small_business_operation: Shopify 商家，管理大量商品的小企业运营者（32 条）
- 覆盖 App：1052884030, 335393788, 371294472, 584606479, 881629660
- 强度：0.58　L2+：62%　代价信号：6%　付费信号：3%

> The dashboard shows the monthly P&L summary, but when you click it, it shows a completely different number for the same report for “this month.”
