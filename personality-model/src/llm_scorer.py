from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .llm_prompt import PROMPT_VERSION, build_zero_shot_prompt
from .schemas import EstimatedPersona, ScoreInput, clamp


TRAIT_FIELDS = (
    "personality_openness",
    "personality_conscientiousness",
    "personality_extraversion",
    "personality_agreeableness",
    "personality_neuroticism",
)
ALLOWED_DECISION_STYLES = {
    "rational",
    "empathetic",
    "assertive",
    "avoidant",
    "balanced",
    "unclear",
}
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 30.0


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for dotenv_path in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=False)
            return
    try:
        load_dotenv(override=False)
    except Exception:
        return


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def llm_enabled_from_env() -> bool:
    _load_dotenv_if_available()
    return _env_bool("LLM_ENABLED", False)


def llm_fallback_reason() -> str | None:
    _load_dotenv_if_available()
    if not _env_bool("LLM_ENABLED", False):
        return "LLM_DISABLED"
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return "MISSING_API_KEY"
    return None


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
    for field in TRAIT_FIELDS:
        if field in payload and field not in persona:
            persona[field] = payload[field]
        if field not in persona:
            raise ValueError(f"LLM result missing estimated_persona.{field}")
        persona[field] = clamp(float(persona[field]), 0, 100)
    payload["estimated_persona"] = persona

    decision_style = str(payload.get("decision_style") or "unclear")
    if decision_style not in ALLOWED_DECISION_STYLES:
        decision_style = "unclear"
    payload["decision_style"] = decision_style

    normalized_evidence = []
    raw_evidence = payload.get("evidence", [])
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            if isinstance(item, dict):
                normalized_evidence.append(
                    {
                        "trait": str(item.get("trait") or "general"),
                        "quote": str(item.get("quote") or ""),
                        "reason": str(item.get("reason") or ""),
                    }
                )
            else:
                normalized_evidence.append(
                    {
                        "trait": "general",
                        "quote": "",
                        "reason": str(item),
                    }
                )

    if not normalized_evidence:
        normalized_evidence.append(
            {
                "trait": "general",
                "quote": "",
                "reason": "LLM 未返回有效证据，本轮证据不足。",
            }
        )

    payload["evidence"] = normalized_evidence
    payload["confidence"] = clamp(float(payload.get("confidence", 0.5)), 0, 0.75)
    payload["prompt_version"] = PROMPT_VERSION
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


def _extract_message_text(response: Any) -> str:
    return str(response.choices[0].message.content or "")


def score_with_llm(score_input: ScoreInput) -> dict[str, Any] | None:
    """Call DeepSeek through the OpenAI-compatible SDK and normalize JSON output.

    Returns None for disabled config, missing keys, API failures, and invalid JSON.
    """

    _load_dotenv_if_available()
    fallback = llm_fallback_reason()
    if fallback is not None:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
    try:
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS

    prompt = get_llm_prompt(score_input)
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You score one player response and return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = parse_llm_json_result(_extract_message_text(response))
    except Exception:
        return None

    payload["model_version"] = model
    return payload
