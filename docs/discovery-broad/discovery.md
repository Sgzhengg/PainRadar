# 无品类需求发现

> 语料：var\broad_llm.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 规则资格不透明难自查 | 规则资格不透明难自查 | 69 | 53 | 4 | 0 | custom_paperwork_compliance、custom_travel_immigration、custom_career_jobs |
| 2 | 沟通无回应跟进困难 | 沟通无回应跟进困难 | 55 | 18 | 3 | 0 | custom_family_education、custom_travel_immigration、custom_paperwork_compliance |
| 3 | 费用不透明与意外扣费 | 费用不透明与意外扣费 | 44 | 31 | 2 | 0 | custom_money_bills、custom_paperwork_compliance |
| 4 | 表格文书复杂难填写 | 表格文书复杂难填写 | 41 | 23 | 2 | 0 | custom_career_jobs、custom_paperwork_compliance |
| 5 | 求职申请无反馈与面试质疑 | 求职申请无反馈与面试质疑 | 26 | 6 | 1 | 0 | custom_career_jobs |
| 6 | 时间管理拖延与 deadline | 时间管理拖延与 deadline | 24 | 5 | 1 | 0 | custom_neuro_accessibility |
| 7 | 流程出错与纠错困难 | 流程出错与纠错困难 | 22 | 12 | 1 | 0 | custom_home_repair |
| 8 | 多方协调家庭决策难 | 多方协调家庭决策难 | 20 | 4 | 1 | 0 | custom_family_education |
| 9 | 记忆沟通遗漏与误解 | 记忆沟通遗漏与误解 | 19 | 4 | 1 | 0 | custom_neuro_accessibility |
| 10 | 预算规划与支出追踪难 | 预算规划与支出追踪难 | 16 | 9 | 1 | 0 | custom_family_education |

## 逐个需求

### 1. 规则资格不透明难自查（69 分，53 条证据，跨 4 个域）

- 来源域：custom_paperwork_compliance(21)、custom_travel_immigration(18)、custom_career_jobs(8)、custom_money_bills(6)
- 需求类型：规则资格不透明难自查　变体：1 种说法
- 买家：申请人/纳税人/员工
- custom_paperwork_compliance: LLC 所有者/小企业主（21 条）
- custom_travel_immigration: 20多岁绿卡持有者，约5.5年前通过家庭获得绿卡，目前与家人失联，在美国有稳定高薪工作和就业记录（18 条）
- custom_career_jobs: 担心为上大学而贷款的学生（8 条）
- custom_money_bills: 前校车司机（6 条）
- 覆盖 App：—
- 强度：0.50　L2+：24%　代价信号：0%　付费信号：0%

> Your submission has been removed because that subreddit is not pre-approved for crossposts.

### 2. 沟通无回应跟进困难（55 分，18 条证据，跨 3 个域）

- 来源域：custom_family_education(11)、custom_travel_immigration(4)、custom_paperwork_compliance(3)
- 需求类型：沟通无回应跟进困难　变体：1 种说法
- 买家：求助者/投诉者
- custom_family_education: 与青少年打交道的人（11 条）
- custom_travel_immigration: H1B申请人（4 条）
- custom_paperwork_compliance: VA（退伍军人事务）医保覆盖者（3 条）
- 覆盖 App：—
- 强度：0.59　L2+：50%　代价信号：0%　付费信号：0%

> raised a e service request, no response, unable to reach out congress person as they are not taking up such cases, what can be done

### 3. 费用不透明与意外扣费（44 分，31 条证据，跨 2 个域）

- 来源域：custom_money_bills(27)、custom_paperwork_compliance(4)
- 需求类型：费用不透明与意外扣费　变体：1 种说法
- 买家：消费者/付费用户
- custom_money_bills: 38岁、从20岁起一直精打细算的人（27 条）
- custom_paperwork_compliance: 年收入超过15万美元的纳税人（4 条）
- 覆盖 App：—
- 强度：0.59　L2+：61%　代价信号：26%　付费信号：3%

> IT IS BY FAR CHEAPER THAN YNAB! YNAB is up to $109/year. Pikapods plus SimpleFin importing is $30.

### 4. 表格文书复杂难填写（41 分，23 条证据，跨 2 个域）

- 来源域：custom_career_jobs(13)、custom_paperwork_compliance(10)
- 需求类型：表格文书复杂难填写　变体：1 种说法
- 买家：求职者/纳税人/申请人
- custom_career_jobs: 求职者（13 条）
- custom_paperwork_compliance: 税务会计从业者（10 条）
- 覆盖 App：—
- 强度：0.50　L2+：74%　代价信号：4%　付费信号：0%

> Instead of "Head Server" you can call yourself "Team Lead" and pull back on the restaurant-specific words.

### 5. 求职申请无反馈与面试质疑（26 分，6 条证据，跨 1 个域）

- 来源域：custom_career_jobs(6)
- 需求类型：求职申请无反馈与面试质疑　变体：1 种说法
- 买家：求职者
- custom_career_jobs: 在职员工，三年内无法离职（6 条）
- 覆盖 App：—
- 强度：0.70　L2+：100%　代价信号：0%　付费信号：0%

> I get endless rejections when I apply on LinkedIn, Sprout, or Indeed, and it's as if they don't even take a glance at my resume.

### 6. 时间管理拖延与 deadline（24 分，5 条证据，跨 1 个域）

- 来源域：custom_neuro_accessibility(5)
- 需求类型：时间管理拖延与 deadline　变体：1 种说法
- 买家：ADHD/拖延者
- custom_neuro_accessibility: 27岁才被诊断的神经多样性人士（5 条）
- 覆盖 App：—
- 强度：0.68　L2+：80%　代价信号：0%　付费信号：0%

> Procrastination was the norm at all times, followed by "emergency mode" where I would work sometimes for days straight with no or minimal sleep

### 7. 流程出错与纠错困难（22 分，12 条证据，跨 1 个域）

- 来源域：custom_home_repair(12)
- 需求类型：流程出错与纠错困难　变体：1 种说法
- 买家：操作失误者
- custom_home_repair: 1992年楼房的住户（12 条）
- 覆盖 App：—
- 强度：0.53　L2+：67%　代价信号：0%　付费信号：8%

> All of them make more noise than I think they should.

### 8. 多方协调家庭决策难（20 分，4 条证据，跨 1 个域）

- 来源域：custom_family_education(4)
- 需求类型：多方协调家庭决策难　变体：1 种说法
- 买家：家庭决策者
- custom_family_education: 关心家庭关系的伴侣或家人（4 条）
- 覆盖 App：—
- 强度：0.60　L2+：50%　代价信号：0%　付费信号：0%

> This is a financial decision. Sit down with your husband & figure out what your family needs for the next year. Next 5 years. Make a plan, set some goals.

### 9. 记忆沟通遗漏与误解（19 分，4 条证据，跨 1 个域）

- 来源域：custom_neuro_accessibility(4)
- 需求类型：记忆沟通遗漏与误解　变体：1 种说法
- 买家：有记忆困扰者
- custom_neuro_accessibility: 38岁、自述短期记忆变差的人（4 条）
- 覆盖 App：—
- 强度：0.70　L2+：25%　代价信号：0%　付费信号：0%

> But it fucks me up, not remembering when friends told me personal things.

### 10. 预算规划与支出追踪难（16 分，9 条证据，跨 1 个域）

- 来源域：custom_family_education(9)
- 需求类型：预算规划与支出追踪难　变体：1 种说法
- 买家：预算紧张者
- custom_family_education: 双职工、有四个孩子的家长（9 条）
- 覆盖 App：—
- 强度：0.51　L2+：22%　代价信号：0%　付费信号：0%

> I also couldn’t tell you exactly where every dollar is going right now
