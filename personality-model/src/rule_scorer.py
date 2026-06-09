from __future__ import annotations

from dataclasses import replace

from .feature_extractor import enrich_response_meta
from .schemas import (
    DEFAULT_ACTOR_ID,
    EstimatedPersona,
    Evidence,
    Feedback,
    ScoreInput,
    ScoreResult,
    clamp,
)


PROMPT_VERSION = "rule_baseline_v2"

AVOIDANT_WORDS = {
    "回避",
    "等等",
    "再说",
    "不确定",
    "随便",
    "沉默",
    "不管",
}

RATIONAL_WORDS = {
    "数据",
    "逻辑",
    "风险",
    "方案",
    "优先级",
    "确认",
    "评估",
    "拆分",
}
OPENNESS_STRONG_WORDS = {
    "创新", "新方案", "新方法", "新路径", "尝试", "探索", "突破", "实验",
    "重新设计", "替代方案", "换一种", "从零到一"
}
OPENNESS_WEAK_WORDS = {"优化", "改进", "调整", "完善", "更新"}

CONSCIENTIOUSNESS_STRONG_WORDS = {
    "优先级", "按时", "截止", "复盘", "补救", "承担", "跟进", "核对",
    "风险控制", "质量标准", "时间安排", "分步骤", "交付"
}
CONSCIENTIOUSNESS_WEAK_WORDS = {"质量", "计划", "负责", "确认", "风险", "关键"}

EXTRAVERSION_STRONG_WORDS = {
    "主动", "表达", "发言", "当场", "直接", "公开", "推动", "争取",
    "说出", "提出", "汇报", "主持", "沟通", "协调资源"
}
EXTRAVERSION_WEAK_WORDS = {"会议", "讨论", "沟通", "交流", "说明"}

AGREEABLENESS_STRONG_WORDS = {
    "共情", "安抚", "帮助", "支持", "理解对方", "肯定", "倾听",
    "照顾", "让步", "尊重"
}
AGREEABLENESS_WEAK_WORDS = {"合作", "协调", "团队", "配合", "理解"}

NEUROTICISM_STRONG_WORDS = {
    "焦虑",
    "特别焦虑",
    "崩溃",
    "害怕",
    "很慌",
    "压力太大",
    "撑不住",
    "愧疚",
    "自责",
    "紧张",
    "内疚",
    "不安",
    "罪恶感",
    "下次再也不干",
    "我没有能力",
    "孤僻",
    "没人愿意",
    "没人愿意与我站队",
    "废料",
    "不是人",
    "人身攻击",
}
NEUROTICISM_WEAK_WORDS = {
    "担心",
    "压力",
    "慌",
    "烦",
    "着急",
    "担忧",
    "怕",
    "不公平",
    "难受",
    "调节情绪",
    "情绪",
    "被否定",
    "评价",
    "别人的评价",
    "影响团队",
    "影响了一整个团队",
    "无用功",
    "不服众",
    "适得其反",
    "委屈",
}

OPENNESS_WORDS = OPENNESS_STRONG_WORDS | OPENNESS_WEAK_WORDS
CONSCIENTIOUSNESS_WORDS = CONSCIENTIOUSNESS_STRONG_WORDS | CONSCIENTIOUSNESS_WEAK_WORDS
EXTRAVERSION_WORDS = EXTRAVERSION_STRONG_WORDS | EXTRAVERSION_WEAK_WORDS
AGREEABLENESS_WORDS = AGREEABLENESS_STRONG_WORDS | AGREEABLENESS_WEAK_WORDS
NEUROTICISM_WORDS = NEUROTICISM_STRONG_WORDS | NEUROTICISM_WEAK_WORDS


def _norm_length(length: int | None) -> float:
    return clamp((length or 0) / 200, 0.0, 1.0)


def _norm_time(response_time_ms: int | None) -> float:
    return clamp((response_time_ms or 0) / 60000, 0.0, 1.0)


def _sent01(sentiment: float | None) -> float:
    return clamp(((sentiment or 0.0) + 1) / 2, 0.0, 1.0)


def _hits(text: str, words: set[str]) -> int:
    return sum(1 for word in words if word in text)

def _quote(text: str, fallback: str = "") -> str:
    clean = (text or "").strip()
    if not clean:
        return fallback
    if len(clean) > 80:
        return clean[:80] + "..."
    return clean

def _boost(score: float, hit_count: int, size: float = 6.0) -> float:
    return clamp(score + min(hit_count * size, 14), 0, 100)

def _weighted_hits(text: str, strong_words: set[str], weak_words: set[str], *, strong_size: float, weak_size: float, cap: float) -> float:
    strong_hits = _hits(text, strong_words)
    weak_hits = _hits(text, weak_words)
    return min(strong_hits * strong_size + weak_hits * weak_size, cap)


def _time_signal(response_time_ms: int | None) -> float:
    if response_time_ms is None:
        return 0.5
    return 1 - _norm_time(response_time_ms)


def _self_signal(self_focus_ratio: float | None) -> float:
    return clamp((self_focus_ratio or 0.0) * 8, 0.0, 1.0)

def estimate_persona_from_response(score_input: ScoreInput) -> EstimatedPersona:
    response = enrich_response_meta(score_input.response_meta)
    text = response.user_free_text_input or ""
    norm_l = _norm_length(response.response_length)
    norm_t = _norm_time(response.response_time_ms)
    time_signal = _time_signal(response.response_time_ms)
    sent = _sent01(response.response_sentiment)
    diversity = response.response_lexical_diversity or 0.0
    self_signal = _self_signal(response.response_self_focus_ratio)

    if response.user_selected_option and not text.strip():
        option_profiles = {
            1: (42, 72, 38, 56, 34),
            2: (55, 64, 46, 72, 32),
            3: (78, 48, 66, 45, 48),
            4: (84, 36, 74, 30, 68),
        }
        scores = option_profiles.get(response.user_selected_option, option_profiles[2])
        return EstimatedPersona(*scores)

    openness = 47 + 20 * (diversity - 0.45) + 8 * norm_l
    conscientiousness = 42 + 10 * (diversity - 0.45) + 8 * time_signal
    extraversion = 38 + 16 * norm_l + 14 * self_signal
    agreeableness = 45 + 12 * (sent - 0.5) + 6 * (1 - self_signal)
    neuroticism = 42 + 22 * (0.5 - sent) + 8 * norm_t

    openness += _weighted_hits(
        text,
        OPENNESS_STRONG_WORDS,
        OPENNESS_WEAK_WORDS,
        strong_size=7,
        weak_size=2,
        cap=18,
    )
    conscientiousness += _weighted_hits(
        text,
        CONSCIENTIOUSNESS_STRONG_WORDS,
        CONSCIENTIOUSNESS_WEAK_WORDS,
        strong_size=5,
        weak_size=1.5,
        cap=15,
    )
    extraversion += _weighted_hits(
        text,
        EXTRAVERSION_STRONG_WORDS,
        EXTRAVERSION_WEAK_WORDS,
        strong_size=9,
        weak_size=4,
        cap=30,
    )
    agreeableness += _weighted_hits(
        text,
        AGREEABLENESS_STRONG_WORDS,
        AGREEABLENESS_WEAK_WORDS,
        strong_size=6.0,
        weak_size=1.5,
        cap=16,
    )
    neuroticism += _weighted_hits(
        text,
        NEUROTICISM_STRONG_WORDS,
        NEUROTICISM_WEAK_WORDS,
        strong_size=9,
        weak_size=3.5,
        cap=34,
    )

    calm_words = {
        "冷静",
        "稳定",
        "分步骤",
        "理性",
        "没必要太在意",
        "不太在意",
        "解决问题",
        "先解决问题",
        "确认事实",
        "解释原因",
        "承认问题",
        "及时沟通",
        "请负责人协调",
        "说明情况",
        "请示",
        "取舍",
        "暂时无法",
    }
    neuroticism_hit_count = _hits(text, NEUROTICISM_WORDS)
    if any(word in text for word in calm_words):
        if neuroticism_hit_count == 0:
            neuroticism = clamp(neuroticism - 4, 0, 100)
        else:
            neuroticism = clamp(neuroticism - 1, 0, 100)

    if _hits(text, AVOIDANT_WORDS) > 0:
        extraversion = clamp(extraversion - 8, 0, 100)
        conscientiousness = clamp(conscientiousness - 5, 0, 100)

    return EstimatedPersona(
        personality_openness=clamp(openness, 0, 100),
        personality_conscientiousness=clamp(conscientiousness, 0, 100),
        personality_extraversion=clamp(extraversion, 0, 100),
        personality_agreeableness=clamp(agreeableness, 0, 100),
        personality_neuroticism=clamp(neuroticism, 0, 100),
    )

def build_feedback(score_input: ScoreInput, persona: EstimatedPersona) -> Feedback:
    return Feedback(
        game_id=score_input.dialogue_event.game_id,
        round_id=score_input.dialogue_event.round_id,
        actor_id=DEFAULT_ACTOR_ID,
        openness_change=_change(persona.personality_openness),
        conscientiousness_change=_change(persona.personality_conscientiousness),
        extraversion_change=_change(persona.personality_extraversion),
        agreeableness_change=_change(persona.personality_agreeableness),
        neuroticism_change=_change(persona.personality_neuroticism),
    )


def _change(score: float) -> int:
    if score >= 75:
        return 2
    if score >= 60:
        return 1
    if score <= 25:
        return -2
    if score <= 40:
        return -1
    return 0


def decision_style(score_input: ScoreInput, persona: EstimatedPersona) -> str:
    text = score_input.response_meta.user_free_text_input or ""
    if _hits(text, AVOIDANT_WORDS) > 0:
        return "avoidant"
    if _hits(text, RATIONAL_WORDS) >= 2:
        return "rational"
    if persona.personality_agreeableness >= 68:
        return "empathetic"
    if persona.personality_extraversion >= 62 or persona.personality_openness >= 75:
        return "assertive"
    return "balanced"


def evidence_for(score_input: ScoreInput, persona: EstimatedPersona) -> list[Evidence]:
    text = score_input.response_meta.user_free_text_input or ""
    selected_option = score_input.response_meta.user_selected_option
    quote = _quote(text)

    evidence: list[Evidence] = []

    if _hits(text, CONSCIENTIOUSNESS_WORDS):
        evidence.append(
            Evidence(
                trait="personality_conscientiousness",
                quote=quote,
                reason="用户提到质量、计划、交付、确认或风险控制，体现尽责倾向。",
            )
        )

    if _hits(text, AGREEABLENESS_WORDS):
        evidence.append(
            Evidence(
                trait="personality_agreeableness",
                quote=quote,
                reason="用户关注合作、协调、帮助或团队支持，体现宜人性线索。",
            )
        )

    if _hits(text, OPENNESS_WORDS):
        evidence.append(
            Evidence(
                trait="personality_openness",
                quote=quote,
                reason="用户提出新方案、尝试、探索或突破，体现开放性线索。",
            )
        )

    if _hits(text, EXTRAVERSION_WORDS):
        evidence.append(
            Evidence(
                trait="personality_extraversion",
                quote=quote,
                reason="用户主动沟通、表达判断或推动讨论，体现外倾性线索。",
            )
        )

    if _hits(text, NEUROTICISM_WORDS):
        evidence.append(
            Evidence(
                trait="personality_neuroticism",
                quote=quote,
                reason="用户表达焦虑、压力、攻击性或强烈负面情绪，体现较高神经质线索。",
            )
        )

    if selected_option is not None:
        evidence.append(
            Evidence(
                trait="decision_style",
                quote=f"用户选择了预设选项 {selected_option}",
                reason="用户通过预设选项表达处理策略，用于映射本轮决策风格和行为倾向。",
            )
        )

    if not evidence:
        evidence.append(
            Evidence(
                trait="general",
                quote=quote,
                reason="本轮明确证据较少，仅根据回复长度、耗时和基础文本特征做临时估计。",
            )
        )

    return evidence


def confidence_for(score_input: ScoreInput, evidence: list[Evidence]) -> float:
    response = score_input.response_meta
    text_len = response.response_length or len(response.user_free_text_input or "")
    base = 0.35

    if text_len >= 80:
        base += 0.3
    elif text_len >= 30:
        base += 0.22
    elif text_len >= 10:
        base += 0.12

    valid_evidence_count = len([item for item in evidence if item.trait != "general"])
    base += min(valid_evidence_count / 4, 1) * 0.25

    if response.user_selected_option is not None:
        base += 0.08

    return clamp(base, 0.25, 0.9)


def score_with_rules(score_input: ScoreInput) -> ScoreResult:
    enriched_response = enrich_response_meta(score_input.response_meta)
    enriched_input = replace(score_input, response_meta=enriched_response)
    persona = estimate_persona_from_response(enriched_input)
    feedback = build_feedback(enriched_input, persona)
    style = decision_style(enriched_input, persona)
    evidence = evidence_for(enriched_input, persona)
    return ScoreResult(
        metadata=enriched_input.metadata,
        dialogue_event=enriched_input.dialogue_event,
        estimated_persona=persona,
        feedback=feedback,
        decision_style=style,
        evidence=evidence,
        confidence=confidence_for(enriched_input, evidence),
        scoring_method="rule_baseline",
        prompt_version=PROMPT_VERSION,
        model_version=None,
    )
