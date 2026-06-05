from __future__ import annotations

import json
import re
from typing import Any

from .llm_prompt import PROMPT_VERSION, build_zero_shot_prompt
from .schemas import EstimatedPersona, ScoreInput, clamp


def get_llm_prompt(score_input: ScoreInput) -> str:
    return build_zero_shot_prompt(score_input)


def parse_llm_json_result(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("LLM result does not contain a JSON object")
        text = match.group(0)
    payload = json.loads(text)
    persona = payload.get("estimated_persona") or {}
    for field in (
        "personality_openness",
        "personality_conscientiousness",
        "personality_extraversion",
        "personality_agreeableness",
        "personality_neuroticism",
    ):
        if field not in persona:
            raise ValueError(f"LLM result missing estimated_persona.{field}")
        persona[field] = clamp(float(persona[field]), 0, 100)
    payload["estimated_persona"] = persona
    payload["evidence"] = [str(item) for item in payload.get("evidence", [])]
    payload["decision_style"] = payload.get("decision_style") or "rational"
    payload["confidence"] = clamp(float(payload.get("confidence", 0.5)), 0, 1)
    return payload


def llm_payload_to_persona(payload: dict[str, Any]) -> EstimatedPersona:
    persona = payload["estimated_persona"]
    return EstimatedPersona(
        personality_openness=persona["personality_openness"],
        personality_conscientiousness=persona["personality_conscientiousness"],
        personality_extraversion=persona["personality_extraversion"],
        personality_agreeableness=persona["personality_agreeableness"],
        personality_neuroticism=persona["personality_neuroticism"],
    )


def score_with_llm(score_input: ScoreInput) -> None:
    """Placeholder for future API integration.

    First version deliberately does not call real APIs or read API keys.
    """

    _ = get_llm_prompt(score_input)
    return None

