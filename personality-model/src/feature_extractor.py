from __future__ import annotations

import re

from .schemas import ResponseMeta, clamp


POSITIVE_WORDS = {
    "合作",
    "协调",
    "支持",
    "理解",
    "稳定",
    "确认",
    "计划",
    "质量",
    "负责",
    "复盘",
    "帮助",
    "沟通",
    "冷静",
    "方案",
}
NEGATIVE_WORDS = {
    "焦虑",
    "崩溃",
    "害怕",
    "烦",
    "急",
    "攻击",
    "甩锅",
    "拖延",
    "随便",
    "不管",
    "完蛋",
    "压力",
}
SELF_FOCUS_WORDS = ("我的", "我会", "我来", "我想", "我觉得", "我", "自己", "本人")


def _text(response: ResponseMeta) -> str:
    return response.user_free_text_input or ""


def estimate_sentiment(text: str) -> float:
    if not text.strip():
        return 0.0
    positive = sum(text.count(word) for word in POSITIVE_WORDS)
    negative = sum(text.count(word) for word in NEGATIVE_WORDS)
    if positive == 0 and negative == 0:
        return 0.0
    return round(clamp((positive - negative) / max(positive + negative, 1), -1.0, 1.0), 3)


def lexical_diversity(text: str) -> float:
    chars = [char for char in re.sub(r"\s+", "", text) if not re.match(r"\W", char)]
    if not chars:
        return 0.0
    return round(len(set(chars)) / len(chars), 3)


def self_focus_ratio(text: str) -> float:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return 0.0
    count = sum(compact.count(word) for word in SELF_FOCUS_WORDS)
    return round(clamp(count / max(len(compact), 1), 0.0, 1.0), 3)


def enrich_response_meta(response: ResponseMeta) -> ResponseMeta:
    text = _text(response)
    response.response_length = response.response_length if response.response_length is not None else len(text)
    response.response_sentiment = (
        float(response.response_sentiment)
        if response.response_sentiment is not None
        else estimate_sentiment(text)
    )
    response.response_lexical_diversity = (
        float(response.response_lexical_diversity)
        if response.response_lexical_diversity is not None
        else lexical_diversity(text)
    )
    response.response_self_focus_ratio = (
        float(response.response_self_focus_ratio)
        if response.response_self_focus_ratio is not None
        else self_focus_ratio(text)
    )
    return response

