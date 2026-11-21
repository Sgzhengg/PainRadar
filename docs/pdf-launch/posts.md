# 社区发帖草稿（3 篇英文 + 2 篇中文）

> 品牌与域名：**PayOnce PDF**（一次付费 PDF）· https://payoncepdf.com · hello@payoncepdf.com。
> 第一帖按纪律不带链接；有人问再在评论里给上述官网地址。价格已按 2026-11-16 用户确认统一为 **$39 / ¥199**（首发 14 天早鸟 **$29 / ¥149**）；四个字段见产品仓库的 `config/product.json`。
> 定位口径（2026-11-20）：本文件的数据帖基于 **723 条评论 / 333 痛点原子**的旧语料，37% 的论证保持原样（自洽，不改成 40%）；产品仓库 `docs/positioning-v2.md` 采用 300 样本 / 81 条有效痛点的新语料，两套分母不同，不要混用。功能表述已同步为 15 个工具。

> 原则：先给价值（数据/经验），再提产品；每篇只发一次，不跨版刷屏；
> 发布后 1 小时内回复所有评论。

## 帖 1 · r/PDF（数据帖，主攻）

**Title:** I read 700+ reviews of popular PDF apps. 37% of the complaints are about billing, not features.

**Body:**

I went through recent App Store reviews of the ten most common PDF apps (editors, scanners, converters) plus r/PDF threads — 723 reviews in total, 333 of them containing a concrete complaint.

What people complain about:

| Complaint | Share |
|---|---|
| Free trial charged immediately | 37% |
| Conversion paywalled or failed | 8% |
| Ads / forced sign-up | 8% |
| Sign & form flow broken | 8% |
| File corrupted after edit | 7% |
| OCR poor or slow | 2% |

Features are commodity. The billing model is what people hate.

I’m building a small local PDF tool around that: one-time price, no account, files never uploaded. Before I write more code I’d like to know:

1. Which complaint above hurts you most?
2. Would you pay $39 once (12 months of updates) instead of $9–20/month?
3. What would make you distrust a “local” claim?

Not linking anything yet — genuinely want the answers.

**发布注意**：r/PDF 对推广敏感，第一帖不要带链接；有人问再在评论里给。

## 帖 2 · r/macapps（Maker 故事）

**Title:** I’m building a local PDF tool because I’m tired of $9/month for “merge PDF”

**Body:**

Every PDF tool I tried wanted an account and a subscription. For merging two files. So I’m building a small one:

- merge / split / compress to a target size
- **edit text in place** — fix a typo without a Word round-trip or an Acrobat subscription
- annotate, redact, bookmarks, watermarks, AES-256 protection
- image conversion (PDF ⇄ PNG/JPG) and local OCR; text-layer export to TXT/HTML/DOCX/XLSX (text only, no layout restoration)
- sign & fill forms, batch a whole folder
- no account, no upload, no ads, no rating pop-ups, no telemetry

Price: **$39 once** (launch price **$29 / ¥149** for the first 14 days), 12 months of 1.x updates, 7-day refund. Early access is a $9 refundable deposit.

Two questions for this sub:

1. Would you install a Mac app that processes PDFs locally but is not sandboxed (needs folder access)?
2. What’s the one PDF job you do most often?

Happy to answer anything about the implementation (it’s a native app, not Electron).

## 帖 3 · r/smallbusiness（隐私 + 批量）

**Title:** Do you upload client PDFs to online tools? (I’m building a local alternative)

**Body:**

If you handle contracts, invoices, or client records, uploading them to a free “compress PDF” site is a compliance problem waiting to happen.

I’m building a desktop tool that does the batch work locally:

- compress a folder of PDFs to a target size
- merge/split by page range
- OCR scans into searchable text
- no upload, no account
- $39 once, not a subscription

Before I ship: what would you need to see to trust the “no upload” claim?
(e.g., network monitor demo, open-source client, security review?)

---

## 帖 4 · 小红书（图文）

**标题**：我统计了 700 条 PDF 差评，37% 在骂“试用就扣费”

**正文**：
最近把主流 PDF App 的差评翻了一遍（723 条，333 条有具体抱怨）。
结果有点意外：大家骂得最多的不是功能，是收费。

- 37%：免费试用立刻扣费
- 8%：转换要付费 / 失败
- 8%：广告 + 强制登录
- 8%：签名表单走不通
- 7%：编辑后文件损坏

功能早就同质化了，真正稀缺的是“不骗你钱、不上传文件”。

我在做一个本地 PDF 工具，主用途很窄：**看 PDF 时发现几个字不对，直接在原文件上改掉**——不转 Word、不订 Acrobat、不上传。合并/拆分/压缩/转换/OCR/签名、批注、脱敏、水印、表单与书签都是配套，全部本机处理，¥199 买断，不注册、无广告弹窗。
想先问问大家：**你最烦的是哪一条？** 评论区告诉我，我按票数排功能顺序。

（图：痛点占比表 + 本地处理示意图）

## 帖 5 · 少数派 / V2EX（深度贴）

**标题**：为什么我做了个“反订阅”的 PDF 工具

**正文**：
先说数据：抓了 10 个主流 PDF 应用的 723 条近期评论，333 条含具体抱怨，其中 **37% 与收费方式有关**（试用扣费、转换付费墙、广告、强制登录）；功能类抱怨加起来不到三成。

这解释了一个现象：PDF 功能早已同质化，但用户对订阅制的怨气在累积。

产品逻辑因此很简单：
1. 本地处理，不传文件（律师/会计/HR 的硬需求）；
2. 一次买断 ¥199（首发 14 天早鸟 ¥149），含 12 个月更新；
3. 主用途只选一个「就地修订」（改字、批注、真脱敏、页面、水印）；阅读批注是界面、转换与 OCR 是辅助，都不当卖点。15 个工具入口：合并拆分、压缩、转换、OCR、签名、批量，加上就地改文字、批注、页面、水印、脱敏、表单、书签、文本转 PDF、打印与邮件；
4. 不承诺“全能”，做得到的写清楚，做不到的也写清楚。

想听两类反馈：
- 你愿意为“不上传 + 买断”付多少？
- 哪个功能是你每周都会用到的？

---

## 发帖纪律

1. 每个版只发一次，7 天内不重复；
2. 第一帖不带购买链接，先收集反馈；
3. 被质疑“广告”时，直接承认是 maker，并给数据来源；
4. 评论里出现“免费工具够用”，不要争，问一句“你会把客户合同上传到免费网站吗”；
5. 记录每条评论的反对意见，7 天后归类。
