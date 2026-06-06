from __future__ import annotations

from dataclasses import replace
from typing import Any

from .llm_scorer import llm_fallback_reason, llm_payload_to_persona, score_with_llm
from .rule_scorer import build_feedback, score_with_rules
from .schemas import EstimatedPersona, ScoreInput, ScoreResult, clamp


TRAIT_FIELDS = (
    "personality_openness",
    "personality_conscientiousness",
    "personality_extraversion",
    "personality_agreeableness",
    "personality_neuroticism",
)


def _mix(rule_value: float, llm_value: float) -> float:
    return 0.4 * rule_value + 0.6 * llm_value


def _persona_dict(persona: EstimatedPersona) -> dict[str, Any]:
    return persona.to_dict()


def _result_summary(result: ScoreResult) -> dict[str, Any]:
    return {
        "estimated_persona": result.estimated_persona.to_dict(),
        "feedback": result.feedback.to_dict(),
        "decision_style": result.decision_style,
        "evidence": [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in result.evidence
        ],
        "confidence": round(result.confidence, 2),
        "scoring_method": result.scoring_method,
        "prompt_version": result.prompt_version,
        "model_version": result.model_version,
    }


def _llm_summary(score_input: ScoreInput, llm_payload: dict[str, Any]) -> dict[str, Any]:
    llm_persona = llm_payload_to_persona(llm_payload)
    return {
        "estimated_persona": _persona_dict(llm_persona),
        "feedback": build_feedback(score_input, llm_persona).to_dict(),
        "decision_style": llm_payload.get("decision_style", "unclear"),
        "evidence": llm_payload.get("evidence", []),
        "confidence": round(float(llm_payload.get("confidence", 0)), 2),
        "scoring_method": "llm_zero_shot",
        "prompt_version": llm_payload.get("prompt_version"),
        "model_version": llm_payload.get("model_version"),
    }


def _mean_trait_delta(rule_persona: EstimatedPersona, llm_persona: EstimatedPersona) -> float:
    total = 0.0
    for field in TRAIT_FIELDS:
        total += abs(float(getattr(rule_persona, field)) - float(getattr(llm_persona, field)))
    return total / len(TRAIT_FIELDS)


def _hybrid_confidence(rule_result: ScoreResult, llm_payload: dict[str, Any]) -> float:
    llm_persona = llm_payload_to_persona(llm_payload)
    delta = _mean_trait_delta(rule_result.estimated_persona, llm_persona)
    base = 0.4 * rule_result.confidence + 0.6 * float(llm_payload.get("confidence", 0.5))
    if delta <= 12:
        base += 0.08
    elif delta >= 35:
        base -= 0.2
    else:
        base -= (delta - 12) / 23 * 0.12
    return clamp(base, 0.15, 0.9)


def _build_hybrid_result(
    score_input: ScoreInput, rule_result: ScoreResult, llm_payload: dict[str, Any]
) -> ScoreResult:
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
        decision_style=str(llm_payload.get("decision_style") or rule_result.decision_style),
        evidence=rule_result.evidence + list(llm_payload.get("evidence", [])),
        confidence=_hybrid_confidence(rule_result, llm_payload),
        scoring_method="hybrid",
        prompt_version=llm_payload.get("prompt_version"),
        model_version=str(llm_payload.get("model_version", "llm")),
    )


def _attach_v03_fields(
    result: ScoreResult,
    rule_result: ScoreResult,
    llm_result: dict[str, Any] | None,
    hybrid_result: dict[str, Any] | None,
    scoring_trace: dict[str, Any],
) -> ScoreResult:
    return replace(
        result,
        rule_result=_result_summary(rule_result),
        llm_result=llm_result,
        hybrid_result=hybrid_result,
        final_result=_result_summary(result),
        scoring_trace=scoring_trace,
    )


def score(score_input: ScoreInput, method: str = "hybrid", use_llm: bool = False) -> ScoreResult:
    rule_result = score_with_rules(score_input)
    method = method.lower()
    if method not in {"rule", "llm", "hybrid"}:
        raise ValueError("method must be one of rule, llm, hybrid")

    if method == "rule":
        return _attach_v03_fields(
            rule_result,
            rule_result,
            llm_result=None,
            hybrid_result=None,
            scoring_trace={
                "llm_enabled": False,
                "llm_used": False,
                "fallback_reason": "METHOD_RULE",
            },
        )

    fallback = llm_fallback_reason()
    llm_enabled = use_llm and fallback is None
    llm_payload = score_with_llm(score_input) if llm_enabled else None
    if llm_payload is None:
        return _attach_v03_fields(
            rule_result,
            rule_result,
            llm_result=None,
            hybrid_result=None,
            scoring_trace={
                "llm_enabled": llm_enabled,
                "llm_used": False,
                "fallback_reason": fallback or ("LLM_NOT_REQUESTED" if not use_llm else "LLM_ERROR"),
            },
        )

    llm_result = _llm_summary(score_input, llm_payload)
    if method == "llm":
        llm_as_result = replace(
            rule_result,
            estimated_persona=llm_payload_to_persona(llm_payload),
            feedback=build_feedback(score_input, llm_payload_to_persona(llm_payload)),
            decision_style=str(llm_payload.get("decision_style") or "unclear"),
            evidence=list(llm_payload.get("evidence", [])),
            confidence=float(llm_payload.get("confidence", 0)),
            scoring_method="llm_zero_shot",
            prompt_version=llm_payload.get("prompt_version"),
            model_version=str(llm_payload.get("model_version", "llm")),
        )
        return _attach_v03_fields(
            llm_as_result,
            rule_result,
            llm_result=llm_result,
            hybrid_result=None,
            scoring_trace={
                "llm_enabled": True,
                "llm_used": True,
                "fallback_reason": None,
            },
        )

    hybrid = _build_hybrid_result(score_input, rule_result, llm_payload)
    return _attach_v03_fields(
        hybrid,
        rule_result,
        llm_result=llm_result,
        hybrid_result=_result_summary(hybrid),
        scoring_trace={
            "llm_enabled": True,
            "llm_used": True,
            "fallback_reason": None,
        },
    )
