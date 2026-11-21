"""Generate buyer-interview briefs from a discovery snapshot.

    python tools/interview_brief.py --snapshot var/discovery.json --top 3 \
        --out-dir docs/interviews

Every brief is grounded in the snapshot: demand definition, evidence count,
domain split, buyer distribution and the strongest quotes. The script part is a
standard template — the point is that the *evidence* section is not invented.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TEMPLATE = """# 买家访谈提纲：{label}

> 来自需求发现快照（{generated_at}）｜ 证据 {size} 条 ｜ 跨 {domain_count} 个域 ｜ 分数 {score}

## 0. 这次访谈要验证什么

我们不验证"这个想法好不好"，只验证三件事：

1. **痛点是否真实且持续**：对方能不能立刻讲出具体场景和时间；
2. **现有替代是否足够差**：他们现在怎么凑合，为此付出多少时间/钱；
3. **付费是否成立**：谁付钱、付多少、什么时候付。

三条都成立才算通过；只成立一两条记为"方向性支持"。

## 1. 这条需求的现有证据

**定义**：{definition}

**分域买家**：

{buyers}

**最强证据（原文）**：

{quotes}

## 2. 招募谁

优先找**最近 3 个月内**遇到过这个问题的人，而不是"对这个话题感兴趣"的人。

筛选三问（电话/表单先问，答不上来就不约）：

1. 你最近一次遇到「{short}」是什么时候？当时具体发生了什么？
2. 你当时做了什么来处理？花了多久 / 多少钱？
3. 如果明天有一个工具能解决它，你会自己用，还是推荐给别人？

## 3. 访谈脚本（35–45 分钟）

### 破冰（5 分钟）
- 先请对方介绍自己日常的使用场景（不要提我们的方案）。
- 明确：没有标准答案，我们想听真实经历，不推销。

### 还原事件（15 分钟）
- 请回忆**最近一次**发生这件事：那天你在做什么？怎么发现的？
- 当时你的第一反应是什么？接下来做了什么？
- 这件事持续了多久？最后怎么结束的？
- 有没有因此影响到别人（家人、同事、客户）？

### 代价（10 分钟）
- 这件事让你多花了多少时间？折算成钱大概多少？
- 有没有因此产生额外支出（换设备、买替代品、请人帮忙）？
- 情绪上最难受的是哪一刻？

### 现有替代（5 分钟）
- 你现在用什么办法绕过它？
- 这个办法哪里不够好？为什么没有彻底解决？
- 你试过哪些产品/方案？为什么放弃？

### 付费与决策（5 分钟）
- 这件事如果有一个专门的产品，你会考虑吗？为什么？
- 你更愿意一次性买断，还是按月付？大概能接受多少？
- 谁来做决定（你自己 / 家人 / 公司）？

### 反证（3 分钟）
- 有没有什么时候你觉得这其实不是问题？
- 如果一直不解决，会怎样？

## 4. "假需求"信号（出现即记录，不要强行解释）

- 说不出具体时间和场景，只会说"确实挺烦的"；
- 从没为此花过时间或钱；
- 现有替代已经很满意；
- 只愿意免费用，且说不出为什么值钱；
- 把问题归因于"所有产品都这样"，没有比较对象。

## 5. 记录表

| 字段 | 内容 |
|---|---|
| 受访者编号 |  |
| 场景与时间 |  |
| 当时做了什么 |  |
| 时间/金钱代价 |  |
| 现有替代 |  |
| 付费意愿（区间） |  |
| 决策人 |  |
| 假需求信号 |  |
| 访谈者判断（通过/方向性/否决） |  |

## 6. 访谈后怎么用

- 每条需求至少 8–10 人；不足 5 人不下结论；
- 统计"能讲出具体事件"的比例、"为此花过钱"的比例、"愿付区间中位数"；
- 与发现页的证据比例对照：证据多但访谈通过率低，说明线上抱怨≠真实购买意愿。
"""


def _slug(text: str) -> str:
    cleaned = re.sub(r"[\\\\/:*?\"<>|\\s]+", "-", text).strip("-")
    return cleaned[:40] or "demand"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="var/discovery.json")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--out-dir", default="docs/interviews")
    args = ap.parse_args()

    data = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    demands = data.get("demands", [])[: args.top]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, d in enumerate(demands, start=1):
        buyers = "\n".join(
            f"- **{domain}**：{who}（{count} 条）"
            for domain, count in list(d.get("domains", {}).items())[:6]
            for who in [(d.get("buyer_by_domain") or {}).get(domain, d.get("buyer") or "买家待补")]
        ) or "- 暂无分域买家"
        quotes = "\n\n".join(
            f"> {e['quote']}\n> — {e.get('domain','')} · {e.get('app','')} · {e.get('level','')}"
            for e in (d.get("examples") or [])[:3]
        ) or "> 暂无原文"
        text = TEMPLATE.format(
            label=d["label"],
            short=d["label"][:12],
            generated_at=data.get("generated_at", ""),
            size=d.get("size", 0),
            domain_count=len(d.get("domains", {})),
            score=d.get("score", 0),
            definition=d.get("definition") or "（快照未记录定义）",
            buyers=buyers,
            quotes=quotes,
        )
        path = out_dir / f"{i:02d}-{_slug(d['label'])}.md"
        path.write_text(text, encoding="utf-8")
        print(f"written {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
