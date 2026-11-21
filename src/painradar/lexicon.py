"""Shared lexicons (English + Chinese).

Kept in one module so the extractor, the validity filter and the tests agree on
what counts as a pain, a praise, a negation or an off-topic term.
"""

from __future__ import annotations

PAIN_TERMS: tuple[str, ...] = (
    "can't", "cannot", "can not", "doesn't", "does not", "don't", "did not",
    "won't", "will not", "keeps", "kept", "always", "never", "no way", "struggle",
    "annoying", "annoy", "hate", "frustrat", "useless", "unusable", "waste",
    "ridiculous", "terrible", "awful", "stupid", "pointless", "overpriced",
    "leak", "leaking", "leaked", "broke", "broken", "snapped", "snap", "jam",
    "jamming", "too loud", "so loud", "too noisy", "noise", "noisy", "vibrat",
    "grind", "whine", "gurgl", "splash", "mold", "mould", "slimy", "deflat",
    "flimsy", "fiddly", "cheap", "wobbl", "drift", "burn", "died", "seized",
    "too short", "too small", "too tall", "too heavy", "not fit", "hard to",
    "difficult", "mess", "clutter", "cramped", "disappoint", "regret", "problem",
    "issue", "fails", "failing", "stopped working", "crashed", "freeze", "frozen",
    "unable", "not working", "doesn't work", "does not work", "won't connect",
    "没法", "不能", "总是", "每次", "根本", "结果", "只能", "只好", "受不了", "崩溃",
    "太吵", "噪音", "漏水", "漏气", "坏了", "踩坑", "翻车", "麻烦", "鸡肋", "难用",
    "后悔", "放不下", "塞不进", "装不下", "够不着", "拿不出来", "打孔", "生锈",
    "发霉", "难清理", "费劲", "折腾", "白买", "退货", "不合适", "太挤", "太乱",
    "太重", "太矮", "太浅", "潮", "掉下来", "滑", "歪", "堆", "翻找", "占地",
    "卡死", "闪退", "连不上", "无法连接", "加载不出", "广告", "订阅", "取消",
)

PRAISE_TERMS: tuple[str, ...] = (
    "love", "loved", "great", "best", "awesome", "amazing", "perfect", "excellent",
    "fantastic", "wonderful", "recommend", "worth every penny", "works great",
    "works perfectly", "no issues", "flawless", "happy with", "game changer",
    "5 stars", "five stars", "good job", "well made", "solid",
    "很好", "好用", "满意", "推荐", "完美", "喜欢", "值得", "不错", "棒", "给力",
)

NEGATORS: tuple[str, ...] = (
    "not", "no", "never", "hardly", "doesn't", "don't", "didn't", "isn't",
    "wasn't", "won't", "can't", "cannot", "no longer", "far from",
    "不", "没", "没有", "别", "并非", "不再",
)

HELP_TERMS: tuple[str, ...] = (
    "how do i", "anyone else", "any recommendations", "looking for", "help",
    "why does", "is there a way", "求推荐", "有没有", "怎么", "求助", "请问",
)

#: Terms that indicate the review is about a different product line.
OFF_TOPIC: dict[str, tuple[str, ...]] = {
    "pet_water_fountain": ("insurance", "policy", "premium", "claim", "vet bill"),
    "home_storage": ("mortgage", "landlord dispute", "insurance"),
    "camping_gear": ("flight", "hotel", "rental car"),
}
