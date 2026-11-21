# 无品类需求发现

> 语料：var\pdf.db ｜ 方法：跨品类簇合并 + 需求打分（品类是输出，不是输入）

| # | 需求 | 类型 | 分数 | 证据 | 域数 | 覆盖 App | 来源域 |
|---|---|---|---|---|---|---|---|
| 1 | 免费试用被立即扣费 | 免费试用被立即扣费 | 48 | 123 | 1 | 6 | custom_pdf_tools |
| 2 | 格式转换收费且失败 | 格式转换收费且失败 | 34 | 28 | 1 | 6 | custom_pdf_tools |
| 3 | 签名表单流程走不通 | 签名表单流程走不通 | 33 | 25 | 1 | 4 | custom_pdf_tools |
| 4 | 编辑后文件损坏或丢失 | 编辑后文件损坏或丢失 | 29 | 22 | 1 | 5 | custom_pdf_tools |
| 5 | 广告多且强制登录授权 | 广告多且强制登录授权 | 28 | 27 | 1 | 3 | custom_pdf_tools |
| 6 | 批注高亮操作难且易丢 | 批注高亮操作难且易丢 | 28 | 6 | 1 | 3 | custom_pdf_tools |
| 7 | OCR识别差且速度慢 | OCR识别差且速度慢 | 27 | 7 | 1 | 3 | custom_pdf_tools |
| 8 | 文件管理混乱难定位 | 文件管理混乱难定位 | 24 | 6 | 1 | 3 | custom_pdf_tools |
| 9 | 打印与邮件导出失败 | 打印与邮件导出失败 | 22 | 4 | 1 | 3 | custom_pdf_tools |

## 逐个需求

### 1. 免费试用被立即扣费（48 分，123 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(123)
- 需求类型：免费试用被立即扣费　变体：1 种说法
- 买家：试用期订阅用户
- custom_pdf_tools: CEO（123 条）
- 覆盖 App：1199564834, 1515133401, 1627156674, 381786507, 388627783, 469337564
- 强度：0.76　L2+：21%　代价信号：15%　付费信号：4%

> Your company just charged me $15.17 for selecting your 7 day free trial

### 2. 格式转换收费且失败（34 分，28 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(28)
- 需求类型：格式转换收费且失败　变体：1 种说法
- 买家：格式转换需求者
- custom_pdf_tools: 2018 年买断 PDF Converter 的老用户，使用近八年（28 条）
- 覆盖 App：1199564834, 1515133401, 381786507, 388627783, 469337564, 6502760201
- 强度：0.67　L2+：36%　代价信号：7%　付费信号：0%

> I’m paying $70 for the year to have a PDF converter to try to make my life a little bit more easier and unfortunately it’s not doing so every time I try to create a PDF it tells me that it’s too big try a drop now what’s the sense of me paying all this money and it doesn’t serve my purpose so unfortunately, after this year is up I will not be renewing my sub

### 3. 签名表单流程走不通（33 分，25 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(25)
- 需求类型：签名表单流程走不通　变体：1 种说法
- 买家：表单签署用户
- custom_pdf_tools: 企业用户（25 条）
- 覆盖 App：1627156674, 381786507, 469337564, 6745093574
- 强度：0.73　L2+：60%　代价信号：4%　付费信号：16%

> Even after paying $99 for the year, you are only allowed to send off 5 documents per month to be signed.

### 4. 编辑后文件损坏或丢失（29 分，22 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(22)
- 需求类型：编辑后文件损坏或丢失　变体：1 种说法
- 买家：文档编辑用户
- custom_pdf_tools: Pro 版用户，从 Files > OneDrive 打开文件（22 条）
- 覆盖 App：1199564834, 1627156674, 469337564, 6745093574, 743974925
- 强度：0.65　L2+：36%　代价信号：0%　付费信号：0%

> Can’t edit text on graphic. It can’t edit text on graphic from my phone screen shot.

### 5. 广告多且强制登录授权（28 分，27 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(27)
- 需求类型：广告多且强制登录授权　变体：1 种说法
- 买家：免费版新用户
- custom_pdf_tools: 使用 iPad Pro 扫描书籍的用户（27 条）
- 覆盖 App：1199564834, 388627783, 6502760201
- 强度：0.79　L2+：26%　代价信号：7%　付费信号：7%

> Way too many ads just for a simple scanner app

### 6. 批注高亮操作难且易丢（28 分，6 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(6)
- 需求类型：批注高亮操作难且易丢　变体：1 种说法
- 买家：批注笔记用户
- custom_pdf_tools: 土木图纸标注用户（6 条）
- 覆盖 App：1627156674, 469337564, 743974925
- 强度：0.73　L2+：67%　代价信号：0%　付费信号：0%

> Just lost an hour’s worth of highlights and notes.

### 7. OCR识别差且速度慢（27 分，7 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(7)
- 需求类型：OCR识别差且速度慢　变体：1 种说法
- 买家：文献与档案用户
- custom_pdf_tools: 扫描旧书的用户（7 条）
- 覆盖 App：1199564834, 1627156674, 743974925
- 强度：0.63　L2+：57%　代价信号：0%　付费信号：14%

> It also has a poor OCR (by today’s standards) esp with older typeset books so I always end up using Claude to extract the text

### 8. 文件管理混乱难定位（24 分，6 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(6)
- 需求类型：文件管理混乱难定位　变体：1 种说法
- 买家：多文件整理用户
- custom_pdf_tools: AEC 行业用户（6 条）
- 覆盖 App：1627156674, 469337564, 743974925
- 强度：0.77　L2+：17%　代价信号：0%　付费信号：0%

> All my tabs are blank, the files are there, but have to open each one to see which one it is, as all the tabs show no title.

### 9. 打印与邮件导出失败（22 分，4 条证据，跨 1 个域）

- 来源域：custom_pdf_tools(4)
- 需求类型：打印与邮件导出失败　变体：1 种说法
- 买家：办公打印用户
- custom_pdf_tools: iPhone 17 Pro 用户，使用 CamScanner 扫描文档（4 条）
- 覆盖 App：388627783, 469337564, 743974925
- 强度：0.75　L2+：0%　代价信号：0%　付费信号：0%

> Bombs out when trying to print to HP. PDF files will not cooperate with my HP printer. I don’t know if the settings. Totally incompatible.
