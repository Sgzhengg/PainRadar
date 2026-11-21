# 给 WorkBuddy 的改名任务提示词

> 用法：把下面整段（从“你是……”到结尾）复制给 WorkBuddy。
> 仓库路径若与实际不同，先让它确认，不要猜。

---

你是 PayOnce PDF 项目的开发代理。请在仓库 `<项目根目录>` 内完成**产品改名与配套调整**，并在结束时给出可核验的报告。

## 背景

- 产品原名：`OncePDF`（域名曾用 `oncepdf.com` / `oncepdf.app`）
- 新名称：**PayOnce PDF**（中文：一次付费 PDF）
- 官网域名：**payoncepdf.com**
- 技术栈：Tauri 2 + Rust + React 19 + TypeScript，目标平台 Windows 10/11 与 macOS 11+（Apple Silicon & Intel）
- 参考资料：`E:\PainRadar\docs\pdf-launch\`（PRD、落地页、预购页、文案、帖子草稿）

## 改名映射

| 旧值 | 新值 |
|---|---|
| `OncePDF` | `PayOnce PDF` |
| `Once PDF` | `PayOnce PDF` |
| `oncepdf`（小写，含域名/包名） | `payoncepdf` |
| `com.oncepdf.*` | `com.payoncepdf.*` |
| `oncepdf.com` / `oncepdf.app` | `payoncepdf.com` |
| 许可证前缀 `ONCE-` | `PAYONCE-` |

## 执行要求

1. **先扫描后修改**：运行 `rg -n -i "oncepdf|once[ _-]?pdf"`，把命中清单先输出，再动手。
2. **用户可见文案全部替换**：窗口标题、托盘菜单、关于页、安装包名、应用名、错误提示、空状态、i18n 资源、邮件模板。
3. **技术标识统一**：`package.json` name、Cargo package name、Tauri `productName` / `identifier`、可执行文件名、协议 handler、更新 feed URL、安装包文件名（`PayOnce-PDF-Setup-x.y.z.exe` / `PayOnce-PDF-x.y.z.dmg`）。
4. **许可证**：前缀改为 `PAYONCE-`；同步更新校验正则、示例密钥、测试用例；若已有旧密钥测试数据，保留一条迁移用例但不要兼容旧前缀（尚未发布）。
5. **链接与邮箱**：统一 `https://payoncepdf.com`，联系邮箱 `hello@payoncepdf.com`，隐私/条款页路径保持一致。
6. **文档同步**：README、PRD、落地页 HTML、预购页、社区帖子草稿中的品牌名与域名。
7. **不要改**：第三方组件名（PDFium、qpdf、Tesseract）、对外 API 路径语义、数据库字段名（除非只是显示名）、许可协议文本。
8. **价格不要自行决定**：当前 PRD 写 `$29 / ¥169`（早鸟 `$19 / ¥109`），落地页写 `$19 / ¥149`。请把价格集中到 `config/product.json`（`price_usd`、`price_cny`、`early_bird_usd`、`early_bird_cny`），保留现状，并在报告中列出冲突，等我确认。

> **状态注记（2026-11-16 22:13，非任务原文）**：用户已确认「参考资料 `$19 / ¥149` 改成 `$29 / ¥169`」，上述冲突已裁决；参考资料 5 个文件的正式价已同步，`config/product.json` 的 `pending_confirmation` 已置为 `false`。此处的 `$19 / ¥149` 是改名任务当时的历史描述，保留不改。
9. **不在代码范围内**：DNS、证书、Gumroad 商品名、Apple/Windows 签名、商标检索——只在报告里列为待办。

## 验收标准

- 源码、配置、文档中 `rg -n -i "oncepdf|once pdf"` 结果为 0（允许出现在 CHANGELOG 或迁移说明中）；
- `pnpm build`（或项目实际包管理器）通过；`cargo check` 通过；
- Rust/TS 单元测试通过；
- Windows 与 macOS 的产物名称、应用名、窗口标题均为 `PayOnce PDF`；
- 安装包路径与截图附在报告中。

## 报告格式

1. **变更摘要**：按「代码 / 配置 / 文档 / 测试」分组，列出文件与改动要点；
2. **grep 前后对比**：改前命中数、改后命中数；
3. **构建与测试结果**：命令 + 结果；
4. **待人工处理清单**：DNS、证书、Gumroad、签名、商标、价格确认；
5. **风险提示**：任何因改名可能失效的旧链接、旧安装包、旧许可证。

## 注意

- 不要重写业务逻辑，只做改名与配套调整；
- 不要删除任何测试；
- 若仓库路径不存在或不是 Tauri 项目，先停下来问，不要自行创建新项目；
- 每完成一批替换就运行一次 grep，避免遗漏与误伤。
