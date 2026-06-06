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


PROMPT_VERSION = "rule_baseline_v1"

OPENNESS_WORDS = {"创新", "新方案", "尝试", "探索", "突破", "实验", "新路径", "改进"}
CONSCIENTIOUSNESS_WORDS = {"质量", "计划", "交付", "负责", "确认", "复盘", "风险", "按时", "关键"}
EXTRAVERSION_WORDS = {"沟通", "表达", "推动", "主动", "争取", "会议", "讨论", "协调资源"}
AGREEABLENESS_WORDS = {"合作", "支持", "理解", "安抚", "协调", "帮助", "共情", "团队"}
NEUROTICISM_WORDS = {"焦虑", "着急", "慌", "很慌", "压力太大", "崩溃", "害怕", "烦","攻击", "甩锅", "完蛋", "撑不住"}
AVOIDANT_WORDS = {"回避", "等等", "再说", "不确定", "随便", "沉默", "不管"}
RATIONAL_WORDS = {"数据", "逻辑", "风险", "方案", "优先级", "确认", "评估", "拆分"}


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


def estimate_persona_from_response(score_input: ScoreInput) -> EstimatedPersona:
    response = enrich_response_meta(score_input.response_meta)
    text = response.user_free_text_input or ""
    norm_l = _norm_length(response.response_length)
    norm_t = _norm_time(response.response_time_ms)
    sent = _sent01(response.response_sentiment)
    diversity = response.response_lexical_diversity or 0.0
    self_focus = response.response_self_focus_ratio or 0.0

    if response.user_selected_option and not text.strip():
        option_profiles = {
            1: (42, 72, 38, 56, 34),
            2: (55, 64, 46, 72, 32),
            3: (78, 48, 66, 45, 48),
            4: (84, 36, 74, 30, 68),
        }
        scores = option_profiles.get(response.user_selected_option, option_profiles[2])
        return EstimatedPersona(*scores)

    openness = 100 * (0.60 * diversity + 0.40 * norm_l)
    conscientiousness = 100 * (0.50 * (1 - norm_t) + 0.50 * diversity)
    extraversion = 100 * (0.60 * self_focus + 0.40 * norm_l)
    agreeableness = 100 * (0.60 * sent + 0.40 * (1 - self_focus))
    neuroticism = 100 * (0.60 * (1 - sent) + 0.40 * norm_t)

    openness = _boost(openness, _hits(text, OPENNESS_WORDS))
    conscientiousness = _boost(conscientiousness, _hits(text, CONSCIENTIOUSNESS_WORDS))
    extraversion = _boost(extraversion, _hits(text, EXTRAVERSION_WORDS))
    agreeableness = _boost(agreeableness, _hits(text, AGREEABLENESS_WORDS))
    neuroticism = _boost(neuroticism, _hits(text, NEUROTICISM_WORDS), size=10)
    if any(word in text for word in {"冷静", "稳定", "分步骤"}):
        neuroticism = clamp(neuroticism - 12, 0, 100)

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
