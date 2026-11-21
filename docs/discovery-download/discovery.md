# 无品类需求发现

> 语料：var\download.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 下载频繁失败或中断 | 下载频繁失败或中断 | 38 | 76 | 1 | 6 | custom_media_download_and_archi |
| 2 | 下载内容无法导出或丢失 | 下载内容无法导出或丢失 | 33 | 37 | 1 | 5 | custom_media_download_and_archi |
| 3 | 付费墙与广告干扰 | 付费墙与广告干扰 | 29 | 13 | 1 | 4 | custom_media_download_and_archi |
| 4 | 下载速度过慢或限速 | 下载速度过慢或限速 | 29 | 9 | 1 | 4 | custom_media_download_and_archi |
| 5 | 站点兼容性差或登录失效 | 站点兼容性差或登录失效 | 28 | 13 | 1 | 5 | custom_media_download_and_archi |
| 6 | 下载后音画缺失或异常 | 下载后音画缺失或异常 | 28 | 35 | 1 | 3 | custom_media_download_and_archi |
| 7 | 应用完全无法使用或诈骗 | 应用完全无法使用或诈骗 | 26 | 9 | 1 | 4 | custom_media_download_and_archi |
| 8 | 隐私泄露与版权限制 | 隐私泄露与版权限制 | 26 | 33 | 1 | 3 | custom_media_download_and_archi |
| 9 | 更新后功能失效或异常 | 更新后功能失效或异常 | 19 | 7 | 1 | 2 | custom_media_download_and_archi |

## 逐个需求

### 1. 下载频繁失败或中断（38 分，76 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(76)
- 需求类型：下载频繁失败或中断　变体：2 种说法
- 买家：媒体下载用户
- custom_media_download_and_archi: Mozilla 视频团队的项目经理（76 条）
- 覆盖 App：1557618225, 1593315967, 1598997500, 1625547458, 6443432155, 6475718094
- 强度：0.63　L2+：24%　代价信号：1%　付费信号：5%

> as of February 9th I have not been able to download any videos of any kind

### 2. 下载内容无法导出或丢失（33 分，37 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(37)
- 需求类型：下载内容无法导出或丢失　变体：1 种说法
- 买家：内容收藏用户
- custom_media_download_and_archi: TrueNAS Scale 用户，使用 6x14TB 硬盘组建存储池（37 条）
- 覆盖 App：1593315967, 1625547458, 6443432155, 6743345585, 970487401
- 强度：0.56　L2+：54%　代价信号：3%　付费信号：8%

> there should be an option to select all downloaded vids and save them to the gallery

### 3. 付费墙与广告干扰（29 分，13 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(13)
- 需求类型：付费墙与广告干扰　变体：1 种说法
- 买家：免费或低频用户
- custom_media_download_and_archi: 对 YouTube 不满的普通用户（13 条）
- 覆盖 App：1598997500, 6443432155, 6475718094, 970487401
- 强度：0.80　L2+：15%　代价信号：0%　付费信号：15%

> it only lets you download 2 videos before hitting a paywall

### 4. 下载速度过慢或限速（29 分，9 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(9)
- 需求类型：下载速度过慢或限速　变体：1 种说法
- 买家：媒体下载用户
- custom_media_download_and_archi: Plex 服务器管理员（9 条）
- 覆盖 App：1593315967, 1625547458, 6443432155, 6475718094
- 强度：0.64　L2+：44%　代价信号：0%　付费信号：11%

> 15 minutes to download a 30-second 240p video

### 5. 站点兼容性差或登录失效（28 分，13 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(13)
- 需求类型：站点兼容性差或登录失效　变体：1 种说法
- 买家：跨站下载用户
- custom_media_download_and_archi: 付费用户（13 条）
- 覆盖 App：1557618225, 1593315967, 1625547458, 6443432155, 6475718094
- 强度：0.61　L2+：31%　代价信号：0%　付费信号：0%

> YouTube doesn’t load anymore at all can’t even download from that site

### 6. 下载后音画缺失或异常（28 分，35 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(35)
- 需求类型：下载后音画缺失或异常　变体：2 种说法
- 买家：影音下载用户
- custom_media_download_and_archi: Google TV 用户（35 条）
- 覆盖 App：1625547458, 6443432155, 6475718094
- 强度：0.57　L2+：46%　代价信号：0%　付费信号：6%

> Every time I save a video, it never has the audio!

### 7. 应用完全无法使用或诈骗（26 分，9 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(9)
- 需求类型：应用完全无法使用或诈骗　变体：1 种说法
- 买家：新安装用户
- custom_media_download_and_archi: 下载与收藏用户（9 条）
- 覆盖 App：1593315967, 1625547458, 6443432155, 970487401
- 强度：0.87　L2+：0%　代价信号：0%　付费信号：0%

> DO NOT DOWNLOAD. This is a scam. Doesn’t work at all.

### 8. 隐私泄露与版权限制（26 分，33 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(33)
- 需求类型：隐私泄露与版权限制　变体：2 种说法
- 买家：隐私敏感用户
- custom_media_download_and_archi: Apple Silicon 逆向工程研究者（33 条）
- 覆盖 App：1557618225, 1625547458, 6743345585
- 强度：0.56　L2+：33%　代价信号：3%　付费信号：0%

> Music doesn’t even play offline, says for copy right reasons it needs WiFi to play.

### 9. 更新后功能失效或异常（19 分，7 条证据，跨 1 个域）

- 来源域：custom_media_download_and_archi(7)
- 需求类型：更新后功能失效或异常　变体：1 种说法
- 买家：长期使用用户
- custom_media_download_and_archi: 下载与收藏用户（7 条）
- 覆盖 App：1557618225, 1625547458
- 强度：0.66　L2+：0%　代价信号：0%　付费信号：0%

> Stopped Working. I’ve been using the app without any major issues for some time, but it stopped working last week.
