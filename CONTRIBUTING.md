# 贡献指南

本仓库是**专有代码**（见 `LICENSE`），默认不接受外部贡献。
如需提交改动，请先联系仓库所有者获得书面同意。

## 开发环境

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows
pip install -r requirements.txt
export PYTHONPATH=src           # PowerShell: $env:PYTHONPATH="E:\PainRadar\src"
export PAINRADAR_LLM_BASE_URL=https://api.deepseek.com/v1
export PAINRADAR_LLM_MODEL=deepseek-chat
export PAINRADAR_LLM_API_KEY=<your-key>   # 不要提交到仓库
```

## 运行测试

```bash
python -m unittest discover -s tests -v
```

只跑新增的商机流水线：

```bash
python -m unittest tests.test_indie_pipeline -v
```

## 提交前检查清单

- [ ] 没有提交 `var/*.db`、`var/indie_cache/`、`var/deepdive_corpus/`
- [ ] 没有提交任何 API Key、`.env`、个人数据
- [ ] `docs/` 里新增的结论写清了样本量与局限
- [ ] 新增/修改的 prompt 附带了对应的测试或样例
- [ ] 报告类文件放在 `reports/`，不要放临时调试输出

## 代码约定

- Python 3.11+，只用标准库 + `fastapi/uvicorn/httpx/python-docx`；
- 模块保持单一职责，新增管线放在 `src/painradar/<name>/`；
- 任何"为了凑结果而放宽过滤"的兜底逻辑都必须显式记录原因，并默认关闭；
- 涉及模型输出时，优先用严格 schema + 后置校验，不要相信自由文本。

## 提交信息

```
feat: 一句话说明
fix: 修了什么
docs: 文档
test: 测试
```

一条提交只做一件事；涉及数据结论的提交请在正文写明样本量与日期。
