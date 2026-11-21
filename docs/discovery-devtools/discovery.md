# 无品类需求发现

> 语料：var\devtools.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 订阅/付费模式不合理 | 订阅/付费模式不合理 | 39 | 8 | 2 | 0 | custom_productivity_tools、custom_developer_tools |
| 2 | 同步/备份状态不透明 | 同步/备份状态不透明 | 39 | 17 | 2 | 0 | custom_productivity_tools、custom_developer_tools |
| 3 | 跨平台行为不一致 | 跨平台行为不一致 | 38 | 15 | 2 | 0 | custom_developer_tools、custom_productivity_tools |
| 4 | 插件/扩展兼容性差 | 插件/扩展兼容性差 | 36 | 16 | 2 | 0 | custom_productivity_tools、custom_developer_tools |
| 5 | 社区发帖被自动删除 | 社区发帖被自动删除 | 34 | 6 | 2 | 0 | custom_developer_tools、custom_productivity_tools |
| 6 | 工具崩溃/卡死无提示 | 工具崩溃/卡死无提示 | 23 | 13 | 1 | 0 | custom_developer_tools |
| 7 | 资源占用高导致卡顿 | 资源占用高导致卡顿 | 20 | 6 | 1 | 0 | custom_developer_tools |
| 8 | 权限提示干扰操作 | 权限提示干扰操作 | 20 | 9 | 1 | 0 | custom_developer_tools |
| 9 | 数据导入导出困难 | 数据导入导出困难 | 19 | 4 | 1 | 0 | custom_productivity_tools |
| 10 | 搜索/导航找不到内容 | 搜索/导航找不到内容 | 18 | 17 | 1 | 0 | custom_productivity_tools |

## 逐个需求

### 1. 订阅/付费模式不合理（39 分，8 条证据，跨 2 个域）

- 来源域：custom_productivity_tools(6)、custom_developer_tools(2)
- 需求类型：订阅/付费模式不合理　变体：2 种说法
- 买家：个人用户/小团队
- custom_productivity_tools: mac apps studio 联合创始人、学生（6 条）
- custom_developer_tools: 开发者（2 条）
- 覆盖 App：—
- 强度：0.57　L2+：50%　代价信号：12%　付费信号：12%

> very few companies actually care to pay for Docker Desktop or the other services they sell

### 2. 同步/备份状态不透明（39 分，17 条证据，跨 2 个域）

- 来源域：custom_productivity_tools(13)、custom_developer_tools(4)
- 需求类型：同步/备份状态不透明　变体：1 种说法
- 买家：多设备用户/自建服务者
- custom_productivity_tools: 使用 Notion 和 Obsidian 做学习笔记的用户（13 条）
- custom_developer_tools: Plex 用户/自建媒体服务器用户（4 条）
- 覆盖 App：—
- 强度：0.54　L2+：65%　代价信号：0%　付费信号：0%

> The two revisions are identical, there is no `cannot sync:` line, no `diverged on disk` line and no approval pending, so the user cannot tell what is out of sync or what to do.

### 3. 跨平台行为不一致（38 分，15 条证据，跨 2 个域）

- 来源域：custom_developer_tools(9)、custom_productivity_tools(6)
- 需求类型：跨平台行为不一致　变体：2 种说法
- 买家：跨平台用户
- custom_developer_tools: 开发者（9 条）
- custom_productivity_tools: Obsidian 与 ChatGPT 用户（6 条）
- 覆盖 App：—
- 强度：0.56　L2+：53%　代价信号：7%　付费信号：0%

> The only serious IDE is Windows-specific, starts at $600 for the typical company (with advanced editions costing more than a small    car   )... and THEN you need to pay $200 more for a JetBrains add-on called ReSharper

### 4. 插件/扩展兼容性差（36 分，16 条证据，跨 2 个域）

- 来源域：custom_productivity_tools(9)、custom_developer_tools(7)
- 需求类型：插件/扩展兼容性差　变体：1 种说法
- 买家：插件开发者/高级用户
- custom_productivity_tools: Echo 的开发者/设计者（9 条）
- custom_developer_tools: Jellyfin 自建服务器用户（Docker/Linux）（7 条）
- 覆盖 App：—
- 强度：0.50　L2+：50%　代价信号：0%　付费信号：0%

> Disabling grouping and selecting individual libraries in the plugin settings resolves and trailers play.

### 5. 社区发帖被自动删除（34 分，6 条证据，跨 2 个域）

- 来源域：custom_developer_tools(4)、custom_productivity_tools(2)
- 需求类型：社区发帖被自动删除　变体：2 种说法
- 买家：社区新用户/开发者
- custom_developer_tools: VS Code 扩展开发者（4 条）
- custom_productivity_tools: macOS 应用开发者（2 条）
- 覆盖 App：—
- 强度：0.43　L2+：50%　代价信号：0%　付费信号：0%

> VS Code character edits held in a destroyed webview, or still in transit, are lost without a dirty marker.

### 6. 工具崩溃/卡死无提示（23 分，13 条证据，跨 1 个域）

- 来源域：custom_developer_tools(13)
- 需求类型：工具崩溃/卡死无提示　变体：2 种说法
- 买家：开发者/终端用户
- custom_developer_tools: Linux x64 上的 VS Code 用户（13 条）
- 覆盖 App：—
- 强度：0.65　L2+：62%　代价信号：0%　付费信号：8%

> it practically crashed (freezing the whole editor) 1/2 of the times so I reverted back to atom

### 7. 资源占用高导致卡顿（20 分，6 条证据，跨 1 个域）

- 来源域：custom_developer_tools(6)
- 需求类型：资源占用高导致卡顿　变体：2 种说法
- 买家：移动端/低配设备用户
- custom_developer_tools: 安卓掌机玩家（6 条）
- 覆盖 App：—
- 强度：0.60　L2+：50%　代价信号：0%　付费信号：0%

> Also lately it has been very error prone. Randomly failing at mounting files, or cleaning up networking rules, or suddenly becoming bog slow so I have to restart the VM.

### 8. 权限提示干扰操作（20 分，9 条证据，跨 1 个域）

- 来源域：custom_developer_tools(9)
- 需求类型：权限提示干扰操作　变体：1 种说法
- 买家：开发者/运维人员
- custom_developer_tools: 开发者（9 条）
- 覆盖 App：—
- 强度：0.53　L2+：56%　代价信号：0%　付费信号：0%

> Permission prompts is a TERRIBLE model, and never should have existed.

### 9. 数据导入导出困难（19 分，4 条证据，跨 1 个域）

- 来源域：custom_productivity_tools(4)
- 需求类型：数据导入导出困难　变体：1 种说法
- 买家：迁移用户/知识工作者
- custom_productivity_tools: Notion 用户，考虑迁移到 Obsidian（4 条）
- 覆盖 App：—
- 强度：0.55　L2+：50%　代价信号：0%　付费信号：0%

> Today this takes four manual steps: build `.rtdd/graph.json`, run graphify's `export obsidian` on it, register the folder as a vault, and open it. On bangwa the whole chain took about 8 seconds. The command should make it one step.

### 10. 搜索/导航找不到内容（18 分，17 条证据，跨 1 个域）

- 来源域：custom_productivity_tools(17)
- 需求类型：搜索/导航找不到内容　变体：1 种说法
- 买家：普通用户/知识工作者
- custom_productivity_tools: Notion 部署管理员（17 条）
- 覆盖 App：—
- 强度：0.52　L2+：29%　代价信号：0%　付费信号：0%

> It seems I can't type anything to get weather in a city with unique characters. I.e check Malmö (Sweden). Malmo, Malm, Malmö - nothing works.
