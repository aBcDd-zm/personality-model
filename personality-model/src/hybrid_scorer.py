from __future__ import annotations

from dataclasses import replace

from .llm_scorer import llm_payload_to_persona, score_with_llm
from .rule_scorer import build_feedback, score_with_rules
from .schemas import EstimatedPersona, ScoreInput, ScoreResult


def _mix(rule_value: float, llm_value: float) -> float:
    return 0.4 * rule_value + 0.6 * llm_value


def score(score_input: ScoreInput) -> ScoreResult:
    rule_result = score_with_rules(score_input)
    llm_payload = score_with_llm(score_input)
    if not llm_payload:
        return rule_result

    llm_persona = llm_payload_to_persona(llm_payload)
    hybrid_persona = EstimatedPersona(
        personality_openness=_mix(
            rule_result.estimated_persona.personality_openness, llm_persona.personality_openness
        ),
        personality_conscientiousness=_mix(
            rule_result.estimated_persona.personality_conscientiousness,
            llm_persona.personality_conscientiousness,
        ),
        personality_extraversion=_mix(
            rule_result.estimated_persona.personality_extraversion,
            llm_persona.personality_extraversion,
        ),
        personality_agreeableness=_mix(
            rule_result.estimated_persona.personality_agreeableness,
            llm_persona.personality_agreeableness,
        ),
        personality_neuroticism=_mix(
            rule_result.estimated_persona.personality_neuroticism,
            llm_persona.personality_neuroticism,
        ),
    )
    return replace(
        rule_result,
        estimated_persona=hybrid_persona,
        feedback=build_feedback(score_input, hybrid_persona),
        evidence=rule_result.evidence + [str(item) for item in llm_payload.get("evidence", [])],
        confidence=0.4 * rule_result.confidence + 0.6 * float(llm_payload.get("confidence", 0.5)),
        scoring_method="hybrid",
        model_version=str(llm_payload.get("model_version", "llm")),
    )

