from __future__ import annotations

from typing import Any

from .schemas import ScoreResult, SessionReport


PERSONA_FIELDS = (
    "personality_openness",
    "personality_conscientiousness",
    "personality_extraversion",
    "personality_agreeableness",
    "personality_neuroticism",
)
FEEDBACK_FIELDS = (
    "openness_change",
    "conscientiousness_change",
    "extraversion_change",
    "agreeableness_change",
    "neuroticism_change",
)


def _evidence_to_dict(item: Any) -> dict[str, str]:
    """Convert Evidence / dict / string evidence into a stable dict format."""
    if hasattr(item, "to_dict"):
        data = item.to_dict()
    elif isinstance(item, dict):
        data = item
    else:
        data = {
            "trait": "general",
            "quote": "",
            "reason": str(item),
        }

    return {
        "trait": str(data.get("trait") or "general"),
        "quote": str(data.get("quote") or ""),
        "reason": str(data.get("reason") or ""),
    }


def _evidence_key(item: Any) -> tuple[str, str, str]:
    """Build a hashable key for evidence deduplication."""
    data = _evidence_to_dict(item)
    return data["trait"], data["quote"], data["reason"]


def build_session_report(results: list[ScoreResult]) -> SessionReport:
    if not results:
        return SessionReport(None, 0, {}, {}, [], 0.0)

    count = len(results)
    persona_sums = {field: 0.0 for field in PERSONA_FIELDS}
    feedback_sums = {field: 0 for field in FEEDBACK_FIELDS}
    evidence: list[Any] = []
    confidence_sum = 0.0

    for result in results:
        persona = result.estimated_persona
        feedback = result.feedback
        persona_sums["personality_openness"] += persona.personality_openness
        persona_sums["personality_conscientiousness"] += persona.personality_conscientiousness
        persona_sums["personality_extraversion"] += persona.personality_extraversion
        persona_sums["personality_agreeableness"] += persona.personality_agreeableness
        persona_sums["personality_neuroticism"] += persona.personality_neuroticism

        for field in FEEDBACK_FIELDS:
            feedback_sums[field] += getattr(feedback, field)

        evidence.extend(result.evidence)
        confidence_sum += result.confidence

    seen = set()
    unique_evidence = []
    for item in evidence:
        key = _evidence_key(item)
        if key not in seen:
            seen.add(key)
            unique_evidence.append(_evidence_to_dict(item))

    return SessionReport(
        session_id=results[0].metadata.session_id,
        event_count=count,
        average_estimated_persona={
            field: round(value / count, 2)
            for field, value in persona_sums.items()
        },
        total_feedback=feedback_sums,
        evidence=unique_evidence,
        average_confidence=confidence_sum / count,
    )
