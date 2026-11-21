"""Rule-based cleaning: drop noise before any model sees it.

Three classes of junk dominate comment exports:
1. too short to carry a need ("好用", "👍");
2. no natural language at all (emoji-only, @-only, URLs);
3. ads / lead-gen ("私我", "加V", "链接在主页").
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2b00-\u2bff\ufe0f\u200d]+"
)
AT_RE = re.compile(r"@[\w\u4e00-\u9fa5\-\.]{1,30}")
URL_RE = re.compile(r"(https?://\S+|www\.\S+)")

AD_PATTERNS = (
    "私我", "私信我", "加v", "加微", "加我", "v我", "滴滴我", "主页有",
    "链接在主页", "看我主页", "点我头像", "免费领取", "限时优惠", "扫码",
    "代理", "招学员", "带徒弟", "日入", "月入过万", "副业", "兼职",
    "承接", "代做", "代写", "优惠券", "返利", "推广", "广告",
)

# pure filler that says nothing about a need
FILLER = {
    "好用", "不错", "哈哈", "哈哈哈", "笑死", "确实", "同意", "支持",
    "路过", "打卡", "沙发", "顶", "赞", "收藏了", "mark", "马克",
}


def is_noise(text: str, min_len: int = 6) -> tuple[bool, str]:
    """Return (is_noise, reason)."""
    raw = (text or "").strip()
    if not raw:
        return True, "empty"

    stripped = EMOJI_RE.sub("", raw)
    stripped = AT_RE.sub("", stripped)
    stripped = URL_RE.sub("", stripped).strip(" \t\r\n，。！？~～、,.!?")
    if len(stripped) < min_len:
        return True, "too_short"
    if not re.search(r"[\u4e00-\u9fa5a-zA-Z]", stripped):
        return True, "no_text"
    if stripped.strip() in FILLER:
        return True, "filler"
    low = raw.lower()
    for pat in AD_PATTERNS:
        if pat in low:
            return True, "ad"
    # a wall of punctuation / repeated chars
    if len(set(stripped)) <= 3 and len(stripped) < 12:
        return True, "repetition"
    return False, ""


def clean_comments(texts: Iterable[str], min_len: int = 6) -> tuple[list[str], Counter]:
    kept: list[str] = []
    stats: Counter = Counter()
    for text in texts:
        noise, reason = is_noise(text, min_len=min_len)
        if noise:
            stats[reason] += 1
            continue
        kept.append(text.strip())
        stats["kept"] += 1
    return kept, stats
